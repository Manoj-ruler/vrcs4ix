import pytest

from app.services.ingestion import normalize_actuals, normalize_forecasts
from app.utils.datetime_utils import parse_utc
from tests.factories import actual_row, forecast_row

START, END = parse_utc("2026-01-01T00:00:00Z"), parse_utc("2026-02-01T00:00:00Z")


def test_only_wind_rows_are_kept():
    rows = [actual_row("2026-01-01T00:00:00Z", 10), actual_row("2026-01-01T00:00:00Z", 99, fuel="CCGT")]
    records, stats = normalize_actuals(rows, START, END)
    assert [r.generation for r in records] == [10.0]
    assert stats.excluded_fuel_type == 1 and stats.received == 2


def test_missing_or_bad_generation_is_invalid_not_zero():
    rows = [actual_row("2026-01-01T00:00:00Z", None), actual_row("2026-01-01T00:30:00Z", "12"),
            actual_row("2026-01-01T01:00:00Z", float("nan")), actual_row("2026-01-01T01:30:00Z", 5)]
    records, stats = normalize_actuals(rows, START, END)
    assert [r.generation for r in records] == [5.0]
    assert stats.invalid == 3


def test_out_of_window_rows_are_counted():
    rows = [actual_row("2025-12-31T23:30:00Z", 1), actual_row("2026-02-01T00:00:00Z", 1), actual_row("2026-01-31T23:30:00Z", 1)]
    records, stats = normalize_actuals(rows, START, END)
    assert len(records) == 1 and stats.out_of_window == 2


def test_duplicate_actual_keeps_latest_publication():
    rows = [actual_row("2026-01-01T00:00:00Z", 10, publish="2026-01-01T00:30:00Z"),
            actual_row("2026-01-01T00:00:00Z", 12, publish="2026-01-01T01:00:00Z"),
            actual_row("2026-01-01T00:00:00Z", 11, publish="2026-01-01T00:45:00Z")]
    records, stats = normalize_actuals(rows, START, END)
    assert records[0].generation == 12 and stats.duplicates == 2 and stats.conflicting_duplicates == 2


def test_wrong_dataset_rejected():
    row = actual_row("2026-01-01T00:00:00Z", 10) | {"dataset": "WINDFOR"}
    assert normalize_actuals([row], START, END)[1].invalid == 1


def test_forecast_versions_are_all_preserved_and_sorted():
    rows = [forecast_row("2026-01-02T00:00:00Z", "2026-01-01T09:30:00Z", 2),
            forecast_row("2026-01-01T00:00:00Z", "2025-12-31T09:30:00Z", 1),
            forecast_row("2026-01-02T00:00:00Z", "2025-12-31T09:30:00Z", 3)]
    records, stats = normalize_forecasts(rows)
    assert [(r.start_time.day, r.publish_time.day, r.generation) for r in records] == [(1, 31, 1), (2, 31, 3), (2, 1, 2)]
    assert stats.valid == 3


def test_forecast_duplicates_and_naive_timestamps():
    rows = [forecast_row("2026-01-01T00:00:00Z", "2025-12-31T09:30:00Z", 1),
            forecast_row("2026-01-01T00:00:00Z", "2025-12-31T09:30:00Z", 2),
            forecast_row("2026-01-01T00:00:00", "2025-12-31T09:30:00Z", 3)]
    records, stats = normalize_forecasts(rows)
    assert [r.generation for r in records] == [2.0]
    assert (stats.duplicates, stats.conflicting_duplicates, stats.invalid) == (1, 1, 1)


@pytest.mark.parametrize("value", ["2026-01-01T00:00:00Z", "2026-01-01T00:00:00+00:00", "2026-01-01T01:00:00+01:00"])
def test_parse_utc_normalises_offsets(value):
    assert parse_utc(value) == parse_utc("2026-01-01T00:00:00Z")
    assert parse_utc(value).utcoffset().total_seconds() == 0
