"""Mapping from service dataclasses to response schemas (presentation only)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from app.clients.elexon import FUELHH_PATH, WINDFOR_PATH
from app.core.config import Settings
from app.schemas import analysis as s
from app.services.alignment import AlignedRecord, IntervalStatus
from app.services.analysis import Dataset
from app.services.forecast_selection import is_eligible
from app.services.ingestion import ForecastRecord
from app.services.metrics import AccuracyMetrics, GroupCounts, compute_metrics, counts
from app.utils.datetime_utils import to_iso

RECORD_FIELDS = tuple(s.Record.model_json_schema(by_alias=True)["properties"].keys())


def metrics(m: AccuracyMetrics | None) -> s.Metrics | None:
    return s.Metrics(**asdict(m)) if m else None


def summary(ds: Dataset, settings: Settings, selected: list[AlignedRecord], rng: tuple[date, date]) -> s.Summary:
    rule = settings.cutoff
    selected_metrics = compute_metrics(selected)
    return s.Summary(
        window=s.Window(
            start_date=settings.delivery_start, end_date=settings.delivery_end,
            start_time=to_iso(ds.window_start), end_time=to_iso(ds.window_end),
        ),
        selection=s.Selection(start_date=rng[0], end_date=rng[1], **_counts(counts(selected))),
        metrics=metrics(selected_metrics),
        empty_reason=None if selected_metrics else "No delivery interval in the selected dates has both a valid actual and an eligible forecast.",
        cutoff=s.CutoffInfo(
            description=rule.describe(), local_time=rule.local_time.strftime("%H:%M"),
            days_before=rule.days_before, timezone=rule.timezone, inclusive=rule.inclusive,
        ),
        quality=s.DataQuality(**asdict(ds.quality)),
        conventions=s.Conventions(
            units="MW (half-hourly average generation for actuals; hourly forecast values)",
            error="forecastError = forecast - actual; positive = overforecast, negative = underforecast",
            mape=(f"mean(|forecast - actual| / actual) x 100 over matched intervals with actual >= "
                  f"{settings.mape_min_actual_mw:g} MW (sample size reported as nMape)"),
            forecast_resolution_minutes=settings.forecast_resolution_minutes,
        ),
        data_source=s.DataSource(
            provider="Elexon BMRS Insights API",
            endpoints=[settings.elexon_base_url + p for p in (FUELHH_PATH, WINDFOR_PATH)],
            mode=ds.mode, fetched_at=to_iso(ds.fetched_at),
        ),
    )


def point(r: AlignedRecord) -> s.TimeseriesPoint:
    return s.TimeseriesPoint(
        start_time=to_iso(r.start_time), actual=r.actual_generation, forecast=r.forecast_generation,
        error=r.forecast_error, publish_time=to_iso(r.publish_time), decision_cutoff=to_iso(r.decision_cutoff),
        status=r.status.value,
    )


def record(r: AlignedRecord) -> s.Record:
    return s.Record(
        start_time=to_iso(r.start_time), delivery_date=r.delivery_date,
        actual_generation=r.actual_generation, forecast_generation=r.forecast_generation,
        publish_time=to_iso(r.publish_time), decision_cutoff=to_iso(r.decision_cutoff),
        horizon_hours=r.horizon_hours, forecast_error=r.forecast_error, absolute_error=r.absolute_error,
        squared_error=r.squared_error, absolute_percentage_error=r.absolute_percentage_error,
        eligible_forecast_count=r.eligible_forecast_count, rejected_after_cutoff_count=r.rejected_after_cutoff_count,
        status=r.status.value,
    )


def _counts(c: GroupCounts) -> dict:
    return {
        "expected_forecast_intervals": c.expected_forecast_intervals, "matched": c.matched,
        "missing_actual": c.missing_actual, "missing_forecast": c.missing_forecast,
    }


def _group(m: AccuracyMetrics | None, c: GroupCounts) -> dict:
    return {"metrics": metrics(m), **_counts(c)}


def daily_row(d: date, m: AccuracyMetrics | None, c: GroupCounts) -> s.DailyRow:
    return s.DailyRow(date=d, **_group(m, c))


def hourly_row(h: int, m: AccuracyMetrics | None, c: GroupCounts) -> s.HourlyRow:
    return s.HourlyRow(hour=h, **_group(m, c))


def interval_detail(r: AlignedRecord, candidates: list[ForecastRecord], inclusive: bool = True) -> s.IntervalDetail:
    selected_publish = r.publish_time
    items = [
        s.Candidate(
            publish_time=to_iso(c.publish_time), generation=c.generation,
            eligible=r.decision_cutoff is not None and is_eligible(c.publish_time, r.decision_cutoff, inclusive),
            selected=selected_publish is not None and c.publish_time == selected_publish,
        )
        for c in sorted(candidates, key=lambda c: c.publish_time, reverse=True)
    ]
    if r.status is IntervalStatus.NOT_FORECAST:
        explanation = "WINDFOR publishes hourly forecasts; no forecast exists for a half-hour starting at :30."
    elif r.publish_time is None:
        explanation = (f"No forecast for this interval was published before the decision cutoff "
                       f"{to_iso(r.decision_cutoff)}; it is reported as missing, not estimated.")
    else:
        explanation = (f"Selected the forecast published {to_iso(r.publish_time)}, the latest of "
                       f"{r.eligible_forecast_count} published at or before the cutoff {to_iso(r.decision_cutoff)}. "
                       f"{r.rejected_after_cutoff_count} later forecast(s) were excluded because they were "
                       f"published after the purchase decision.")
    return s.IntervalDetail(record=record(r), candidates=items, explanation=explanation)
