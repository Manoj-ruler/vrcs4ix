"""Timezone-aware datetime helpers. Internally every instant is a UTC-aware datetime."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


def parse_utc(value: object) -> datetime:
    """Parse an Elexon ISO-8601 timestamp into an aware UTC datetime.

    Naive timestamps are rejected instead of being guessed: Elexon always sends a `Z` suffix.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"timestamp must be a non-empty string, got {value!r}")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {value!r}")
    return parsed.astimezone(UTC)


def to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_midnight_utc(day: date, tz_name: str) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=ZoneInfo(tz_name)).astimezone(UTC)


def local_date(value: datetime, tz_name: str) -> date:
    return value.astimezone(ZoneInfo(tz_name)).date()


def delivery_window_utc(start: date, end_inclusive: date, tz_name: str) -> tuple[datetime, datetime]:
    """[start of first local delivery day, start of the day after the last one) in UTC."""
    return local_midnight_utc(start, tz_name), local_midnight_utc(end_inclusive + timedelta(days=1), tz_name)


def half_hour_intervals(start: date, end_inclusive: date, tz_name: str) -> list[datetime]:
    """Every settlement-period start in the local delivery days (46/50 periods on clock-change days)."""
    begin, finish = delivery_window_utc(start, end_inclusive, tz_name)
    step = timedelta(minutes=30)
    intervals = []
    current = begin
    while current < finish:
        intervals.append(current)
        current += step
    return intervals
