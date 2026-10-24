"""API tests against a mocked Elexon transport (fixture rows, clearly not production data)."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.clients.elexon import ElexonClient
from app.main import create_app
from app.services.analysis import AnalysisService
from tests.factories import actual_row, forecast_row, settings

FUELHH = [actual_row("2026-01-01T00:00:00Z", 100), actual_row("2026-01-01T00:30:00Z", 105),
          actual_row("2026-01-01T01:00:00Z", 200), actual_row("2026-01-02T00:00:00Z", 300),
          actual_row("2026-01-01T00:00:00Z", 999, fuel="CCGT")]
WINDFOR = [forecast_row("2026-01-01T00:00:00Z", "2025-12-31T09:30:00Z", 120),
           forecast_row("2026-01-01T00:00:00Z", "2025-12-31T15:30:00Z", 101),  # after cutoff
           forecast_row("2026-01-01T01:00:00Z", "2025-12-31T09:30:00Z", 180),
           forecast_row("2026-01-02T00:00:00Z", "2026-01-01T09:30:00Z", 330)]


def transport(fail: bool = False, fuelhh=FUELHH, windfor=WINDFOR) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(503)
        if "FUELHH" in request.url.path:
            lo, hi = request.url.params["settlementDateFrom"], request.url.params["settlementDateTo"]
            return httpx.Response(200, json=[r for r in fuelhh if lo <= r["settlementDate"] <= hi])
        lo, hi = request.url.params["publishDateTimeFrom"], request.url.params["publishDateTimeTo"]
        return httpx.Response(200, json=[r for r in windfor if lo <= r["publishTime"] <= hi])
    return httpx.MockTransport(handler)


def make_client(tmp_path, **kw) -> TestClient:
    s = settings(tmp_path)
    svc = AnalysisService(s, lambda: ElexonClient(s.elexon_base_url, 5, 1, 2, backoff_base_s=0, transport=transport(**kw)))
    return TestClient(create_app(s, svc))


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)


def test_health_does_not_load_data(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "version": "1.0.0", "dataLoaded": False}


def test_docs_are_served_under_api(client):
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").json()["info"]["title"] == "Wind Forecast Accuracy API"


def test_summary(client):
    body = client.get("/api/analysis/summary").json()
    m, q = body["metrics"], body["quality"]
    assert m["n"] == 3 and m["mae"] == pytest.approx((20 + 20 + 30) / 3) and m["bias"] == pytest.approx(10)
    assert q["expectedIntervals"] == 96 and q["expectedForecastIntervals"] == 48
    assert q["matchedPairs"] == 3 and q["excludedFuelTypeRecords"] == 1 and q["missingActualIntervals"] == 92
    assert body["cutoff"]["localTime"] == "11:00" and body["dataSource"]["mode"] == "live"
    assert client.get("/api/health").json()["dataLoaded"] is True


def test_summary_for_date_range(client):
    body = client.get("/api/analysis/summary", params={"startDate": "2026-01-02", "endDate": "2026-01-02"}).json()
    assert body["metrics"]["n"] == 1 and body["metrics"]["mae"] == 30
    assert body["selection"] == {"startDate": "2026-01-02", "endDate": "2026-01-02", "expectedForecastIntervals": 24,
                                 "matched": 1, "missingActual": 23, "missingForecast": 23}
    assert body["quality"]["matchedPairs"] == 3  # whole-window quality is unchanged


def test_timeseries_and_leakage(client):
    pts = client.get("/api/analysis/timeseries", params={"startDate": "2026-01-01", "endDate": "2026-01-01"}).json()["points"]
    assert len(pts) == 48
    assert pts[0] == {"startTime": "2026-01-01T00:00:00Z", "actual": 100.0, "forecast": 120.0, "error": 20.0,
                      "publishTime": "2025-12-31T09:30:00Z", "decisionCutoff": "2025-12-31T11:00:00Z", "status": "matched"}
    assert pts[1]["status"] == "no_forecast_scheduled" and pts[1]["forecast"] is None


def test_daily_and_hourly(client):
    daily = client.get("/api/analysis/daily").json()
    assert [d["date"] for d in daily] == ["2026-01-01", "2026-01-02"]
    assert daily[1]["metrics"]["mae"] == 30 and daily[1]["matched"] == 1
    assert len(client.get("/api/analysis/hourly").json()) == 24


@pytest.mark.parametrize("params", [
    {"startDate": "2026-01-02", "endDate": "2026-01-01"},
    {"startDate": "2025-12-01"},
    {"endDate": "2026-02-10"},
    {"startDate": "not-a-date"},
])
def test_invalid_dates_are_422(client, params):
    assert client.get("/api/analysis/timeseries", params=params).status_code == 422


def test_records_pagination_sort_filter(client):
    page = client.get("/api/analysis/records", params={"pageSize": 10, "page": 2}).json()
    assert page["total"] == 48 and page["totalPages"] == 5 and len(page["items"]) == 10
    top = client.get("/api/analysis/records", params={"sort": "absoluteError", "order": "desc", "status": "matched"}).json()
    assert [i["absoluteError"] for i in top["items"]] == [30.0, 20.0, 20.0]
    assert top["items"][1]["startTime"] < top["items"][2]["startTime"]  # stable tie-break
    missing = client.get("/api/analysis/records", params={"status": "missing"}).json()
    assert missing["total"] == 45
    every = client.get("/api/analysis/records", params={"scope": "all", "pageSize": 500}).json()
    assert every["total"] == 96
    assert client.get("/api/analysis/records", params={"page": 99}).status_code == 422
    assert client.get("/api/analysis/records", params={"pageSize": 0}).status_code == 422
    assert client.get("/api/analysis/records", params={"sort": "bogus"}).status_code == 422


def test_csv_export(client):
    res = client.get("/api/analysis/records.csv", params={"status": "matched"})
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    lines = res.text.strip().splitlines()
    assert lines[0].startswith("startTime,deliveryDate,actualGeneration") and len(lines) == 4


def test_interval_detail_explains_selection(client):
    body = client.get("/api/analysis/interval", params={"startTime": "2026-01-01T00:00:00Z"}).json()
    assert [(c["publishTime"], c["eligible"], c["selected"]) for c in body["candidates"]] == [
        ("2025-12-31T15:30:00Z", False, False), ("2025-12-31T09:30:00Z", True, True)]
    assert "excluded" in body["explanation"]
    assert client.get("/api/analysis/interval", params={"startTime": "2026-03-01T00:00:00Z"}).status_code == 404
    assert client.get("/api/analysis/interval", params={"startTime": "yesterday"}).status_code == 422


def test_empty_data_returns_null_metrics(tmp_path):
    body = make_client(tmp_path, fuelhh=[], windfor=[]).get("/api/analysis/summary").json()
    assert body["metrics"] is None and body["emptyReason"] and body["quality"]["coveragePct"] == 0


def test_upstream_failure_is_502_without_internals(tmp_path):
    res = make_client(tmp_path, fail=True).get("/api/analysis/summary")
    assert res.status_code == 502 and res.json()["code"] == "upstream_unavailable"
    assert "Traceback" not in res.text


def test_cache_is_reused(tmp_path):
    make_client(tmp_path).get("/api/analysis/summary")
    body = make_client(tmp_path, fail=True).get("/api/analysis/summary").json()
    assert body["dataSource"]["mode"] == "cache" and body["metrics"]["n"] == 3


def test_snapshot_fallback_when_live_fails(tmp_path):
    from dataclasses import replace

    from app.services.analysis import RawData, write_raw_file
    from app.utils.datetime_utils import parse_utc

    s = replace(settings(tmp_path), data_source="auto")
    write_raw_file(s.snapshot_path, RawData(FUELHH, WINDFOR, parse_utc("2026-02-02T00:00:00Z"), "live"), s)
    svc = AnalysisService(s, lambda: ElexonClient(s.elexon_base_url, 5, 0, 1, backoff_base_s=0, transport=transport(fail=True)))
    body = TestClient(create_app(s, svc)).get("/api/analysis/summary").json()
    assert body["dataSource"]["mode"] == "snapshot" and body["metrics"]["n"] == 3
