"""Filtering, sorting and paging of aligned records for the API (no metric logic here)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.services.alignment import AlignedRecord, IntervalStatus

SortField = Literal["startTime", "absoluteError", "forecastError", "actualGeneration", "forecastGeneration"]
Scope = Literal["forecast", "all"]
StatusFilter = Literal["any", "matched", "missing"]

_SORT_ATTR = {
    "startTime": "start_time",
    "absoluteError": "absolute_error",
    "forecastError": "forecast_error",
    "actualGeneration": "actual_generation",
    "forecastGeneration": "forecast_generation",
}


class InvalidQueryError(ValueError):
    pass


@dataclass(frozen=True)
class Page:
    items: list[AlignedRecord]
    page: int
    page_size: int
    total: int
    total_pages: int


def validate_range(start: date | None, end: date | None, window_start: date, window_end: date) -> tuple[date, date]:
    start = start or window_start
    end = end or window_end
    if start > end:
        raise InvalidQueryError("startDate must be on or before endDate")
    if start < window_start or end > window_end:
        raise InvalidQueryError(f"dates must be within {window_start.isoformat()} and {window_end.isoformat()}")
    return start, end


def filter_records(
    records: list[AlignedRecord], start: date, end: date, scope: Scope = "all", status: StatusFilter = "any"
) -> list[AlignedRecord]:
    out = []
    for r in records:
        if not start <= r.delivery_date <= end:
            continue
        if scope == "forecast" and r.status is IntervalStatus.NOT_FORECAST:
            continue
        if status == "matched" and r.status is not IntervalStatus.MATCHED:
            continue
        if status == "missing" and r.status in (IntervalStatus.MATCHED, IntervalStatus.NOT_FORECAST):
            continue
        out.append(r)
    return out


def sort_records(records: list[AlignedRecord], field: SortField, descending: bool) -> list[AlignedRecord]:
    """Stable sort; records without a value always go last; ties keep delivery-time order."""
    attr = _SORT_ATTR[field]
    present = [r for r in records if getattr(r, attr) is not None]
    missing = [r for r in records if getattr(r, attr) is None]
    present.sort(key=lambda r: r.start_time)
    present.sort(key=lambda r: getattr(r, attr), reverse=descending)
    return present + missing


def paginate(records: list[AlignedRecord], page: int, page_size: int) -> Page:
    total = len(records)
    total_pages = max(1, math.ceil(total / page_size))
    if page > total_pages:
        raise InvalidQueryError(f"page {page} is beyond the last page ({total_pages})")
    begin = (page - 1) * page_size
    return Page(records[begin:begin + page_size], page, page_size, total, total_pages)
