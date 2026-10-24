"""Environment-based configuration.

Every analytical assumption that is not fixed by the brief (decision cutoff, MAPE threshold,
analysis window) is read from here so it can be changed without touching the logic.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date, time
from functools import lru_cache
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CutoffRule:
    """Purchase-decision cutoff for a delivery day D: `local_time` on D - `days_before`."""

    local_time: time
    days_before: int
    timezone: str
    inclusive: bool = True

    def describe(self) -> str:
        comparator = "at or before" if self.inclusive else "strictly before"
        day = "the day before" if self.days_before == 1 else f"{self.days_before} days before"
        return (
            f"Latest WINDFOR forecast published {comparator} {self.local_time:%H:%M} "
            f"{self.timezone} on {day} the delivery day"
        )


@dataclass(frozen=True)
class Settings:
    elexon_base_url: str
    delivery_start: date
    delivery_end: date  # inclusive
    timezone: str
    cutoff: CutoffRule
    mape_min_actual_mw: float
    forecast_resolution_minutes: int
    forecast_lookback_hours: int
    http_timeout_s: float
    http_max_retries: int
    http_concurrency: int
    cors_origins: tuple[str, ...]
    data_source: str  # auto | live | snapshot
    cache_dir: Path
    snapshot_path: Path


def _parse_time(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    env = os.environ.get
    tz = env("ANALYSIS_TIMEZONE", "Europe/London")
    data_source = env("DATA_SOURCE", "auto").lower()
    if data_source not in {"auto", "live", "snapshot"}:
        raise ValueError("DATA_SOURCE must be one of auto, live, snapshot")
    return Settings(
        elexon_base_url=env("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1").rstrip("/"),
        delivery_start=date.fromisoformat(env("DELIVERY_START", "2026-01-01")),
        delivery_end=date.fromisoformat(env("DELIVERY_END", "2026-01-31")),
        timezone=tz,
        cutoff=CutoffRule(
            local_time=_parse_time(env("DECISION_CUTOFF_LOCAL", "11:00")),
            days_before=int(env("DECISION_CUTOFF_DAYS_BEFORE", "1")),
            timezone=tz,
            inclusive=_parse_bool(env("DECISION_CUTOFF_INCLUSIVE", "true")),
        ),
        mape_min_actual_mw=float(env("MAPE_MIN_ACTUAL_MW", "1")),
        forecast_resolution_minutes=int(env("FORECAST_RESOLUTION_MINUTES", "60")),
        forecast_lookback_hours=int(env("FORECAST_LOOKBACK_HOURS", "96")),
        http_timeout_s=float(env("HTTP_TIMEOUT_SECONDS", "30")),
        http_max_retries=int(env("HTTP_MAX_RETRIES", "3")),
        http_concurrency=int(env("HTTP_CONCURRENCY", "6")),
        cors_origins=tuple(
            o.strip()
            for o in env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        ),
        data_source=data_source,
        cache_dir=Path(env("CACHE_DIR", str(Path(tempfile.gettempdir()) / "wind-forecast-cache"))),
        snapshot_path=Path(env("SNAPSHOT_PATH", str(BACKEND_ROOT / "data" / "elexon-jan-2026.json.gz"))),
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()
