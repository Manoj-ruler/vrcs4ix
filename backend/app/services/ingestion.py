"""Normalisation and validation of raw FUELHH / WINDFOR rows into typed records.

Invalid rows are counted, never repaired: a missing generation value is not turned into zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from app.utils.datetime_utils import UTC, parse_utc


@dataclass(frozen=True)
class ActualRecord:
    start_time: datetime
    generation: float
    publish_time: datetime | None
    settlement_date: str | None
    settlement_period: int | None


@dataclass(frozen=True)
class ForecastRecord:
    start_time: datetime
    publish_time: datetime
    generation: float


@dataclass
class IngestStats:
    received: int = 0
    valid: int = 0
    invalid: int = 0
    duplicates: int = 0
    conflicting_duplicates: int = 0
    excluded_fuel_type: int = 0
    out_of_window: int = 0


def _generation(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("generation must be a finite number")
    return float(value)


def _publish_key(record: ActualRecord) -> datetime:
    return record.publish_time or datetime.min.replace(tzinfo=UTC)


def _dataset_ok(row: dict[str, Any], expected: str) -> bool:
    return row.get("dataset") in (None, expected)


def normalize_actuals(
    rows: Iterable[dict[str, Any]], window_start: datetime, window_end: datetime
) -> tuple[list[ActualRecord], IngestStats]:
    """FUELHH rows -> one WIND record per half-hour startTime within [window_start, window_end).

    If the same startTime appears more than once, the row with the latest publishTime wins
    (a later publication is a revision); ties keep the last row in source order.
    """
    stats = IngestStats()
    by_start: dict[datetime, ActualRecord] = {}
    for row in rows:
        stats.received += 1
        if row.get("fuelType") != "WIND":
            stats.excluded_fuel_type += 1
            continue
        try:
            if not _dataset_ok(row, "FUELHH"):
                raise ValueError("wrong dataset")
            start = parse_utc(row.get("startTime"))
            generation = _generation(row.get("generation"))
            publish = parse_utc(row["publishTime"]) if row.get("publishTime") else None
        except (ValueError, KeyError):
            stats.invalid += 1
            continue
        if not window_start <= start < window_end:
            stats.out_of_window += 1
            continue
        record = ActualRecord(
            start_time=start, generation=generation, publish_time=publish,
            settlement_date=row.get("settlementDate"), settlement_period=row.get("settlementPeriod"),
        )
        existing = by_start.get(start)
        if existing is not None:
            stats.duplicates += 1
            if existing.generation != record.generation:
                stats.conflicting_duplicates += 1
            if _publish_key(existing) > _publish_key(record):
                continue
        by_start[start] = record
    records = sorted(by_start.values(), key=lambda r: r.start_time)
    stats.valid = len(records)
    return records, stats


def normalize_forecasts(rows: Iterable[dict[str, Any]]) -> tuple[list[ForecastRecord], IngestStats]:
    """WINDFOR rows -> unique (startTime, publishTime) records; all publication versions are kept.

    A repeated (startTime, publishTime) pair keeps the last row in source order and is counted.
    """
    stats = IngestStats()
    by_key: dict[tuple[datetime, datetime], ForecastRecord] = {}
    for row in rows:
        stats.received += 1
        try:
            if not _dataset_ok(row, "WINDFOR"):
                raise ValueError("wrong dataset")
            record = ForecastRecord(
                start_time=parse_utc(row.get("startTime")),
                publish_time=parse_utc(row.get("publishTime")),
                generation=_generation(row.get("generation")),
            )
        except ValueError:
            stats.invalid += 1
            continue
        key = (record.start_time, record.publish_time)
        existing = by_key.get(key)
        if existing is not None:
            stats.duplicates += 1
            if existing.generation != record.generation:
                stats.conflicting_duplicates += 1
        by_key[key] = record
    records = sorted(by_key.values(), key=lambda r: (r.start_time, r.publish_time))
    stats.valid = len(records)
    return records, stats
