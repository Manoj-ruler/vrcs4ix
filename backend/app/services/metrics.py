"""Accuracy metrics. Every aggregate is recomputed from interval-level errors, never from other aggregates."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Callable, Hashable, Iterable, Sequence, TypeVar
from zoneinfo import ZoneInfo

from app.services.alignment import AlignedRecord, IntervalStatus

K = TypeVar("K", bound=Hashable)


@dataclass(frozen=True)
class AccuracyMetrics:
    n: int
    mae: float
    rmse: float
    bias: float
    mape: float | None
    n_mape: int
    p50_absolute_error: float
    p90_absolute_error: float
    max_overforecast: float
    max_underforecast: float
    mean_actual: float
    mean_forecast: float
    n_overforecast: int
    n_underforecast: int


@dataclass(frozen=True)
class GroupCounts:
    expected_forecast_intervals: int
    matched: int
    missing_actual: int
    missing_forecast: int


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (same definition as numpy's default)."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile of empty sequence")
    position = (len(ordered) - 1) * q / 100.0
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def compute_metrics(records: Iterable[AlignedRecord]) -> AccuracyMetrics | None:
    """Metrics over matched pairs only; None when there is nothing valid to measure."""
    matched = [r for r in records if r.status is IntervalStatus.MATCHED]
    if not matched:
        return None
    n = len(matched)
    errors = [r.forecast_error for r in matched]
    abs_errors = [r.absolute_error for r in matched]
    apes = [r.absolute_percentage_error for r in matched if r.absolute_percentage_error is not None]
    return AccuracyMetrics(
        n=n,
        mae=sum(abs_errors) / n,
        rmse=math.sqrt(sum(r.squared_error for r in matched) / n),
        bias=sum(errors) / n,
        mape=sum(apes) / len(apes) if apes else None,
        n_mape=len(apes),
        p50_absolute_error=percentile(abs_errors, 50),
        p90_absolute_error=percentile(abs_errors, 90),
        max_overforecast=max(0.0, max(errors)),
        max_underforecast=min(0.0, min(errors)),
        mean_actual=sum(r.actual_generation for r in matched) / n,
        mean_forecast=sum(r.forecast_generation for r in matched) / n,
        n_overforecast=sum(e > 0 for e in errors),
        n_underforecast=sum(e < 0 for e in errors),
    )


def counts(records: Iterable[AlignedRecord]) -> GroupCounts:
    expected = matched = missing_actual = missing_forecast = 0
    for r in records:
        if r.status is IntervalStatus.NOT_FORECAST:
            continue
        expected += 1
        matched += r.status is IntervalStatus.MATCHED
        missing_actual += r.status in (IntervalStatus.MISSING_ACTUAL, IntervalStatus.MISSING_BOTH)
        missing_forecast += r.status in (IntervalStatus.MISSING_FORECAST, IntervalStatus.MISSING_BOTH)
    return GroupCounts(expected, matched, missing_actual, missing_forecast)


def grouped_metrics(
    records: Iterable[AlignedRecord], key: Callable[[AlignedRecord], K]
) -> list[tuple[K, AccuracyMetrics | None, GroupCounts]]:
    groups: dict[K, list[AlignedRecord]] = defaultdict(list)
    for r in records:
        groups[key(r)].append(r)
    return [(k, compute_metrics(groups[k]), counts(groups[k])) for k in sorted(groups)]


def daily_metrics(records: Iterable[AlignedRecord]) -> list[tuple[date, AccuracyMetrics | None, GroupCounts]]:
    return grouped_metrics(records, lambda r: r.delivery_date)


def hourly_metrics(records: Iterable[AlignedRecord], tz_name: str) -> list[tuple[int, AccuracyMetrics | None, GroupCounts]]:
    tz = ZoneInfo(tz_name)
    forecast_slots = [r for r in records if r.status is not IntervalStatus.NOT_FORECAST]
    return grouped_metrics(forecast_slots, lambda r: r.start_time.astimezone(tz).hour)
