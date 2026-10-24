import math
from datetime import date

import pytest

from app.services.alignment import IntervalStatus, align
from app.services.forecast_selection import select_forecasts
from app.services.ingestion import ActualRecord, ForecastRecord
from app.services.metrics import compute_metrics, daily_metrics, hourly_metrics, percentile
from app.utils.datetime_utils import half_hour_intervals, parse_utc
from tests.factories import RULE

P = "2025-12-31T09:30:00Z"  # eligible for 1 Jan
P2 = "2026-01-01T09:30:00Z"  # eligible for 2 Jan


def build(actuals: dict[str, float], forecasts: list[tuple[str, str, float]], mape_min=1.0, days=(1, 1)):
    intervals = half_hour_intervals(date(2026, 1, days[0]), date(2026, 1, days[1]), "Europe/London")
    acts = [ActualRecord(parse_utc(k), v, None, None, None) for k, v in actuals.items()]
    fcs = [ForecastRecord(parse_utc(s), parse_utc(p), g) for s, p, g in forecasts]
    slots = [t for t in intervals if t.minute == 0]
    sel = select_forecasts(fcs, slots, RULE)
    return align(intervals, acts, sel, tz_name="Europe/London", resolution_minutes=60, mape_min_actual_mw=mape_min)


def by_start(records):
    return {r.start_time: r for r in records}


def test_join_on_exact_start_time_and_statuses():
    recs = by_start(build(
        {"2026-01-01T00:00:00Z": 100, "2026-01-01T00:30:00Z": 110, "2026-01-01T02:00:00Z": 50},
        [("2026-01-01T00:00:00Z", P, 120), ("2026-01-01T01:00:00Z", P, 80)],
    ))
    assert len(recs) == 48
    assert recs[parse_utc("2026-01-01T00:00:00Z")].status is IntervalStatus.MATCHED
    assert recs[parse_utc("2026-01-01T00:30:00Z")].status is IntervalStatus.NOT_FORECAST
    assert recs[parse_utc("2026-01-01T00:30:00Z")].forecast_generation is None  # never borrowed from 00:00
    assert recs[parse_utc("2026-01-01T01:00:00Z")].status is IntervalStatus.MISSING_ACTUAL
    assert recs[parse_utc("2026-01-01T02:00:00Z")].status is IntervalStatus.MISSING_FORECAST
    assert recs[parse_utc("2026-01-01T03:00:00Z")].status is IntervalStatus.MISSING_BOTH


def test_error_sign_convention_and_fields():
    r = by_start(build({"2026-01-01T00:00:00Z": 100}, [("2026-01-01T00:00:00Z", P, 120)]))[parse_utc("2026-01-01T00:00:00Z")]
    assert r.forecast_error == 20  # overforecast is positive
    assert r.absolute_error == 20 and r.squared_error == 400 and r.absolute_percentage_error == 20
    assert r.publish_time == parse_utc(P) and r.decision_cutoff == parse_utc("2025-12-31T11:00:00Z")
    assert r.horizon_hours == 14.5


def test_metrics_hand_calculated():
    # errors: +20, -10, +30, -40 -> MAE 25, bias 0, RMSE sqrt((400+100+900+1600)/4)=sqrt(750)
    recs = build(
        {"2026-01-01T00:00:00Z": 100, "2026-01-01T01:00:00Z": 200, "2026-01-01T02:00:00Z": 300, "2026-01-01T03:00:00Z": 400},
        [("2026-01-01T00:00:00Z", P, 120), ("2026-01-01T01:00:00Z", P, 190),
         ("2026-01-01T02:00:00Z", P, 330), ("2026-01-01T03:00:00Z", P, 360)],
    )
    m = compute_metrics(recs)
    assert m.n == 4 and m.mae == 25 and m.bias == 0
    assert m.rmse == pytest.approx(math.sqrt(750))
    assert m.mape == pytest.approx((20 + 5 + 10 + 10) / 4)
    assert (m.max_overforecast, m.max_underforecast) == (30, -40)
    assert (m.n_overforecast, m.n_underforecast) == (2, 2)
    assert m.p50_absolute_error == 25 and m.p90_absolute_error == pytest.approx(37)


def test_bias_sign_for_underforecast():
    recs = build({"2026-01-01T00:00:00Z": 100}, [("2026-01-01T00:00:00Z", P, 70)])
    assert compute_metrics(recs).bias == -30


def test_mape_skips_zero_actuals_and_reports_its_own_n():
    recs = build({"2026-01-01T00:00:00Z": 0, "2026-01-01T01:00:00Z": 100},
                 [("2026-01-01T00:00:00Z", P, 50), ("2026-01-01T01:00:00Z", P, 110)])
    m = compute_metrics(recs)
    assert m.n == 2 and m.n_mape == 1 and m.mape == pytest.approx(10) and m.mae == 30


def test_mape_none_when_all_actuals_below_threshold():
    m = compute_metrics(build({"2026-01-01T00:00:00Z": 0.5}, [("2026-01-01T00:00:00Z", P, 2)]))
    assert m.mape is None and m.n_mape == 0 and m.n == 1


def test_empty_input_gives_no_metrics():
    assert compute_metrics(build({}, [])) is None
    assert compute_metrics([]) is None


def test_partial_coverage_uses_only_matched_pairs():
    recs = build({"2026-01-01T00:00:00Z": 100}, [("2026-01-01T00:00:00Z", P, 110), ("2026-01-01T01:00:00Z", P, 999)])
    m = compute_metrics(recs)
    assert m.n == 1 and m.mae == 10


def test_monthly_rmse_is_not_mean_of_daily_rmse():
    recs = build(
        {"2026-01-01T00:00:00Z": 100, "2026-01-02T00:00:00Z": 100, "2026-01-02T01:00:00Z": 100},
        [("2026-01-01T00:00:00Z", P, 110), ("2026-01-02T00:00:00Z", P2, 140), ("2026-01-02T01:00:00Z", P2, 60)],
        days=(1, 2),
    )
    daily = daily_metrics(recs)
    assert [d for d, _, _ in daily] == [date(2026, 1, 1), date(2026, 1, 2)]
    assert daily[0][1].rmse == 10 and daily[1][1].rmse == 40
    overall = compute_metrics(recs)
    assert overall.rmse == pytest.approx(math.sqrt((100 + 1600 + 1600) / 3))
    assert overall.rmse != pytest.approx((10 + 40) / 2)
    assert daily[1][2].matched == 2 and daily[1][2].expected_forecast_intervals == 24


def test_hourly_and_deterministic_order():
    recs = build({"2026-01-01T05:00:00Z": 100}, [("2026-01-01T05:00:00Z", P, 90)])
    hourly = hourly_metrics(recs, "Europe/London")
    assert [h for h, _, _ in hourly] == list(range(24))
    assert hourly[5][1].mae == 10 and hourly[4][1] is None
    assert [r.start_time for r in recs] == sorted(r.start_time for r in recs)
    assert build({"2026-01-01T05:00:00Z": 100}, [("2026-01-01T05:00:00Z", P, 90)]) == recs


def test_percentile_linear():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    with pytest.raises(ValueError):
        percentile([], 50)
