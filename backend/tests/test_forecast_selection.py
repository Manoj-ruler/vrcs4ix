from datetime import datetime, time, timezone

from app.core.config import CutoffRule
from app.services.forecast_selection import decision_cutoff, select_forecasts
from app.services.ingestion import ForecastRecord
from app.utils.datetime_utils import parse_utc
from tests.factories import RULE


def f(start: str, publish: str, gen: float) -> ForecastRecord:
    return ForecastRecord(parse_utc(start), parse_utc(publish), gen)


T = parse_utc("2026-01-10T12:00:00Z")  # cutoff = 2026-01-09 11:00 UTC (GMT in January)


def test_cutoff_is_11_london_on_previous_day_in_winter():
    assert decision_cutoff(T, RULE) == datetime(2026, 1, 9, 11, 0, tzinfo=timezone.utc)


def test_cutoff_respects_bst():
    summer = parse_utc("2026-07-10T12:00:00Z")
    assert decision_cutoff(summer, RULE) == datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc)


def test_delivery_day_is_local_date_not_utc_date():
    # 23:30 UTC on 30 June is 00:30 BST on 1 July -> delivery day 1 July -> cutoff 30 June 10:00 UTC.
    late = parse_utc("2026-06-30T23:30:00Z")
    assert decision_cutoff(late, RULE) == datetime(2026, 6, 30, 10, 0, tzinfo=timezone.utc)


def test_selects_newest_eligible_and_rejects_post_cutoff():
    rows = [
        f("2026-01-10T12:00:00Z", "2026-01-09T04:30:00Z", 100),
        f("2026-01-10T12:00:00Z", "2026-01-09T09:30:00Z", 200),  # newest eligible
        f("2026-01-10T12:00:00Z", "2026-01-09T11:30:00Z", 999),  # after cutoff: must be ignored
        f("2026-01-10T12:00:00Z", "2026-01-10T09:30:00Z", 888),  # much closer to delivery: ignored
    ]
    sel = select_forecasts(rows, [T], RULE)[T]
    assert sel.selected.generation == 200
    assert sel.selected.publish_time == parse_utc("2026-01-09T09:30:00Z")
    assert (sel.eligible_count, sel.rejected_after_cutoff) == (2, 2)


def test_not_just_max_publish_time():
    rows = [f("2026-01-10T12:00:00Z", "2026-01-09T09:30:00Z", 1), f("2026-01-10T12:00:00Z", "2026-01-10T02:30:00Z", 2)]
    assert select_forecasts(rows, [T], RULE)[T].selected.generation == 1


def test_forecast_exactly_at_cutoff_inclusive_and_exclusive():
    rows = [f("2026-01-10T12:00:00Z", "2026-01-09T09:30:00Z", 1), f("2026-01-10T12:00:00Z", "2026-01-09T11:00:00Z", 2)]
    assert select_forecasts(rows, [T], RULE)[T].selected.generation == 2
    exclusive = CutoffRule(time(11, 0), 1, "Europe/London", inclusive=False)
    assert select_forecasts(rows, [T], exclusive)[T].selected.generation == 1


def test_duplicate_publish_time_resolved_deterministically():
    rows = [f("2026-01-10T12:00:00Z", "2026-01-09T09:30:00Z", 1), f("2026-01-10T12:00:00Z", "2026-01-09T09:30:00Z", 2)]
    results = {select_forecasts(rows, [T], RULE)[T].selected.generation for _ in range(5)}
    assert results == {2}  # the later row in input order wins, every time


def test_missing_eligible_forecast_stays_missing():
    rows = [f("2026-01-10T12:00:00Z", "2026-01-09T15:30:00Z", 5)]
    sel = select_forecasts(rows, [T], RULE)[T]
    assert sel.selected is None and sel.eligible_count == 0 and sel.rejected_after_cutoff == 1
    assert select_forecasts([], [T], RULE)[T].selected is None


def test_stable_across_runs_and_input_order():
    rows = [f("2026-01-10T12:00:00Z", p, g) for p, g in
            [("2026-01-08T22:30:00Z", 3), ("2026-01-09T07:30:00Z", 4), ("2026-01-09T09:30:00Z", 5)]]
    first = select_forecasts(rows, [T], RULE)
    assert select_forecasts(list(reversed(rows)), [T], RULE) == first
    assert select_forecasts(rows, [T], RULE) == first


def test_timezone_offsets_do_not_change_eligibility():
    # 11:30+01:00 is 10:30 UTC: eligible. The same wall-clock string in UTC would not be.
    rows = [f("2026-01-10T12:00:00Z", "2026-01-09T11:30:00+01:00", 7)]
    assert select_forecasts(rows, [T], RULE)[T].selected.generation == 7


def test_january_first_uses_december_forecast():
    jan1 = parse_utc("2026-01-01T00:00:00Z")
    rows = [f("2026-01-01T00:00:00Z", "2025-12-31T09:30:00Z", 10), f("2026-01-01T00:00:00Z", "2025-12-31T22:30:00Z", 11)]
    sel = select_forecasts(rows, [jan1], RULE)[jan1]
    assert sel.decision_cutoff == parse_utc("2025-12-31T11:00:00Z")
    assert sel.selected.generation == 10
