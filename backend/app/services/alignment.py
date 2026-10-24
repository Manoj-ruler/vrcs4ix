"""Join selected forecasts to actuals on the exact delivery interval (startTime).

Every expected half-hour interval produces one record, so missing data stays visible instead of
being dropped by an inner join. Error convention: forecast - actual (positive = overforecast).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Iterable

from app.services.forecast_selection import ForecastSelection
from app.services.ingestion import ActualRecord
from app.utils.datetime_utils import local_date


class IntervalStatus(str, Enum):
    MATCHED = "matched"
    MISSING_ACTUAL = "missing_actual"
    MISSING_FORECAST = "missing_forecast"
    MISSING_BOTH = "missing_both"
    # WINDFOR is hourly: half-hours starting at :30 have no forecast by design.
    NOT_FORECAST = "no_forecast_scheduled"


@dataclass(frozen=True)
class AlignedRecord:
    start_time: datetime
    delivery_date: date
    actual_generation: float | None
    forecast_generation: float | None
    publish_time: datetime | None
    decision_cutoff: datetime | None
    horizon_hours: float | None
    eligible_forecast_count: int
    rejected_after_cutoff_count: int
    status: IntervalStatus
    forecast_error: float | None
    absolute_error: float | None
    squared_error: float | None
    absolute_percentage_error: float | None


def is_forecast_slot(start_time: datetime, resolution_minutes: int) -> bool:
    minutes = start_time.hour * 60 + start_time.minute
    return start_time.second == 0 and minutes % resolution_minutes == 0


def align(
    intervals: Iterable[datetime],
    actuals: Iterable[ActualRecord],
    selections: dict[datetime, ForecastSelection],
    *,
    tz_name: str,
    resolution_minutes: int,
    mape_min_actual_mw: float,
) -> list[AlignedRecord]:
    actual_by_start = {a.start_time: a for a in actuals}
    records = []
    for start in sorted(intervals):
        actual = actual_by_start.get(start)
        actual_mw = actual.generation if actual else None
        selection = selections.get(start) if is_forecast_slot(start, resolution_minutes) else None
        forecast = selection.selected if selection else None
        forecast_mw = forecast.generation if forecast else None

        if selection is None:
            status = IntervalStatus.NOT_FORECAST
        elif actual_mw is not None and forecast_mw is not None:
            status = IntervalStatus.MATCHED
        elif actual_mw is None and forecast_mw is None:
            status = IntervalStatus.MISSING_BOTH
        elif actual_mw is None:
            status = IntervalStatus.MISSING_ACTUAL
        else:
            status = IntervalStatus.MISSING_FORECAST

        error = abs_error = sq_error = ape = None
        if status is IntervalStatus.MATCHED:
            error = forecast_mw - actual_mw
            abs_error = abs(error)
            sq_error = error * error
            if abs(actual_mw) >= mape_min_actual_mw and actual_mw != 0:
                ape = abs_error / abs(actual_mw) * 100.0

        records.append(AlignedRecord(
            start_time=start,
            delivery_date=local_date(start, tz_name),
            actual_generation=actual_mw,
            forecast_generation=forecast_mw,
            publish_time=forecast.publish_time if forecast else None,
            decision_cutoff=selection.decision_cutoff if selection else None,
            horizon_hours=(start - forecast.publish_time).total_seconds() / 3600 if forecast else None,
            eligible_forecast_count=selection.eligible_count if selection else 0,
            rejected_after_cutoff_count=selection.rejected_after_cutoff if selection else 0,
            status=status,
            forecast_error=error,
            absolute_error=abs_error,
            squared_error=sq_error,
            absolute_percentage_error=ape,
        ))
    return records
