import asyncio
from datetime import date

import httpx
import pytest

from app.clients.elexon import ElexonClient, ElexonError
from app.utils.datetime_utils import parse_utc


def run(coro):
    return asyncio.run(coro)


def client_with(handler, retries=2) -> ElexonClient:
    return ElexonClient("https://example.test", 5, retries, 2, backoff_base_s=0, transport=httpx.MockTransport(handler))


def test_windfor_windows_cover_range_without_overlap():
    seen = []

    def handler(request):
        seen.append((request.url.params["publishDateTimeFrom"], request.url.params["publishDateTimeTo"]))
        return httpx.Response(200, json=[])

    run(client_with(handler).fetch_windfor(parse_utc("2025-12-30T00:00:00Z"), parse_utc("2026-01-01T11:00:00Z")))
    assert seen == [("2025-12-30T00:00:00Z", "2025-12-30T23:59:59Z"), ("2025-12-31T00:00:00Z", "2025-12-31T23:59:59Z"),
                    ("2026-01-01T00:00:00Z", "2026-01-01T11:00:00Z")]


def test_fuelhh_windows_and_order():
    def handler(request):
        p = request.url.params
        assert p["fuelType"] == "WIND"
        return httpx.Response(200, json=[{"from": p["settlementDateFrom"], "to": p["settlementDateTo"]}])

    rows = run(client_with(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 31)))
    assert [(r["from"], r["to"]) for r in rows] == [
        ("2026-01-01", "2026-01-07"), ("2026-01-08", "2026-01-14"), ("2026-01-15", "2026-01-21"),
        ("2026-01-22", "2026-01-28"), ("2026-01-29", "2026-01-31")]


def test_retries_transient_errors_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectTimeout("slow")
        if calls["n"] == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": [{"ok": 1}]})

    assert run(client_with(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 1))) == [{"ok": 1}]
    assert calls["n"] == 3


def test_gives_up_after_bounded_retries():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500)

    with pytest.raises(ElexonError, match="after 3 attempts"):
        run(client_with(handler).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 1)))
    assert calls["n"] == 3


@pytest.mark.parametrize("response", [httpx.Response(400), httpx.Response(200, text="<html>"), httpx.Response(200, json={"x": 1})])
def test_client_errors_and_malformed_bodies_raise(response):
    with pytest.raises(ElexonError):
        run(client_with(lambda request: response).fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 1)))
