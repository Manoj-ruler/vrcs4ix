"""Orchestrates loading -> normalisation -> decision-time selection -> alignment -> metrics.

Raw upstream responses (which contain every forecast version) are what gets cached; the cutoff rule
is re-applied on every build, so a cache can never smuggle a post-cutoff forecast into the analysis.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from app.clients.elexon import FUELHH_PATH, WINDFOR_PATH, ElexonClient, ElexonError
from app.core.config import Settings
from app.services.alignment import AlignedRecord, IntervalStatus, align, is_forecast_slot
from app.services.forecast_selection import decision_cutoff, group_by_start, select_forecasts
from app.services.ingestion import ForecastRecord, IngestStats, normalize_actuals, normalize_forecasts
from app.services.metrics import AccuracyMetrics, GroupCounts, daily_metrics, hourly_metrics, compute_metrics
from app.utils.datetime_utils import UTC, delivery_window_utc, half_hour_intervals, parse_utc, to_iso

logger = logging.getLogger(__name__)
SNAPSHOT_VERSION = 1


class DataUnavailableError(RuntimeError):
    """No usable data source (live API failed and no matching snapshot)."""


@dataclass(frozen=True)
class RawData:
    fuelhh: list[dict[str, Any]]
    windfor: list[dict[str, Any]]
    fetched_at: datetime
    mode: str  # live | cache | snapshot


@dataclass(frozen=True)
class DataQuality:
    expected_intervals: int
    actual_records_received: int
    valid_actual_intervals: int
    missing_actual_intervals: int
    invalid_actual_records: int
    duplicate_actual_records: int
    excluded_fuel_type_records: int
    forecast_records_received: int
    valid_forecast_records: int
    invalid_forecast_records: int
    duplicate_forecast_records: int
    forecast_publications: int
    expected_forecast_intervals: int
    eligible_forecasts_selected: int
    missing_eligible_forecasts: int
    matched_pairs: int
    coverage_pct: float | None
    distinct_selected_publish_times: int


@dataclass
class Dataset:
    window_start: datetime
    window_end: datetime
    records: list[AlignedRecord]
    by_start: dict[datetime, AlignedRecord]
    candidates: dict[datetime, list[ForecastRecord]]
    quality: DataQuality
    overall: AccuracyMetrics | None
    daily: list[tuple[date, AccuracyMetrics | None, GroupCounts]]
    hourly: list[tuple[int, AccuracyMetrics | None, GroupCounts]]
    fetched_at: datetime
    mode: str
    built_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def forecast_publish_range(settings: Settings) -> tuple[datetime, datetime]:
    """Publication window to download: lookback before the first cutoff up to the last cutoff.

    Forecasts published after the final decision cutoff are never needed, so they are never fetched.
    """
    intervals = half_hour_intervals(settings.delivery_start, settings.delivery_end, settings.timezone)
    first_cutoff = decision_cutoff(intervals[0], settings.cutoff)
    last_cutoff = decision_cutoff(intervals[-1], settings.cutoff)
    return first_cutoff - timedelta(hours=settings.forecast_lookback_hours), last_cutoff


def request_signature(settings: Settings) -> dict[str, str]:
    publish_from, publish_to = forecast_publish_range(settings)
    return {
        "baseUrl": settings.elexon_base_url,
        "settlementDateFrom": settings.delivery_start.isoformat(),
        "settlementDateTo": settings.delivery_end.isoformat(),
        "publishDateTimeFrom": to_iso(publish_from) or "",
        "publishDateTimeTo": to_iso(publish_to) or "",
    }


def read_raw_file(path: Path, settings: Settings, mode: str) -> RawData:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    if payload.get("version") != SNAPSHOT_VERSION:
        raise DataUnavailableError(f"{path.name} has an unsupported format version")
    stored, wanted = payload.get("request", {}), request_signature(settings)
    if any(stored.get(k) != v for k, v in wanted.items() if k != "baseUrl"):
        raise DataUnavailableError(f"{path.name} was built for a different analysis window")
    return RawData(payload["fuelhh"], payload["windfor"], parse_utc(payload["fetchedAt"]), mode)


def write_raw_file(path: Path, raw: RawData, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump({
            "version": SNAPSHOT_VERSION,
            "fetchedAt": to_iso(raw.fetched_at),
            "request": request_signature(settings),
            "fuelhh": raw.fuelhh,
            "windfor": raw.windfor,
        }, fh, separators=(",", ":"))
    tmp.replace(path)


async def fetch_live(settings: Settings, client: ElexonClient) -> RawData:
    publish_from, publish_to = forecast_publish_range(settings)
    fuelhh, windfor = await asyncio.gather(
        client.fetch_fuelhh(settings.delivery_start, settings.delivery_end),
        client.fetch_windfor(publish_from, publish_to),
    )
    logger.info("elexon_fetch_complete fuelhh_rows=%d windfor_rows=%d", len(fuelhh), len(windfor))
    return RawData(fuelhh, windfor, datetime.now(UTC), "live")


def build_dataset(raw: RawData, settings: Settings) -> Dataset:
    """Pure transformation from raw upstream rows to the analysed dataset."""
    window_start, window_end = delivery_window_utc(settings.delivery_start, settings.delivery_end, settings.timezone)
    intervals = half_hour_intervals(settings.delivery_start, settings.delivery_end, settings.timezone)
    actuals, a_stats = normalize_actuals(raw.fuelhh, window_start, window_end)
    forecasts, f_stats = normalize_forecasts(raw.windfor)

    slots = [t for t in intervals if is_forecast_slot(t, settings.forecast_resolution_minutes)]
    selections = select_forecasts(forecasts, slots, settings.cutoff)
    records = align(
        intervals, actuals, selections,
        tz_name=settings.timezone,
        resolution_minutes=settings.forecast_resolution_minutes,
        mape_min_actual_mw=settings.mape_min_actual_mw,
    )
    return Dataset(
        window_start=window_start,
        window_end=window_end,
        records=records,
        by_start={r.start_time: r for r in records},
        candidates={k: sorted(v, key=lambda f: f.publish_time) for k, v in group_by_start(forecasts).items()},
        quality=_quality(records, intervals, slots, selections, a_stats, f_stats, forecasts),
        overall=compute_metrics(records),
        daily=daily_metrics(records),
        hourly=hourly_metrics(records, settings.timezone),
        fetched_at=raw.fetched_at,
        mode=raw.mode,
    )


def _quality(records, intervals, slots, selections, a_stats: IngestStats, f_stats: IngestStats, forecasts) -> DataQuality:
    matched = sum(r.status is IntervalStatus.MATCHED for r in records)
    selected = [s.selected for s in selections.values() if s.selected is not None]
    valid_actuals = sum(r.actual_generation is not None for r in records)
    return DataQuality(
        expected_intervals=len(intervals),
        actual_records_received=a_stats.received,
        valid_actual_intervals=valid_actuals,
        missing_actual_intervals=len(intervals) - valid_actuals,
        invalid_actual_records=a_stats.invalid,
        duplicate_actual_records=a_stats.duplicates,
        excluded_fuel_type_records=a_stats.excluded_fuel_type,
        forecast_records_received=f_stats.received,
        valid_forecast_records=f_stats.valid,
        invalid_forecast_records=f_stats.invalid,
        duplicate_forecast_records=f_stats.duplicates,
        forecast_publications=len({f.publish_time for f in forecasts}),
        expected_forecast_intervals=len(slots),
        eligible_forecasts_selected=len(selected),
        missing_eligible_forecasts=len(slots) - len(selected),
        matched_pairs=matched,
        coverage_pct=(matched / len(slots) * 100.0) if slots else None,
        distinct_selected_publish_times=len({f.publish_time for f in selected}),
    )


class AnalysisService:
    """Holds the analysed dataset for the process lifetime (historical data does not change)."""

    def __init__(self, settings: Settings, client_factory: Callable[[], ElexonClient] | None = None) -> None:
        self.settings = settings
        self._client_factory = client_factory or (lambda: ElexonClient(
            settings.elexon_base_url, settings.http_timeout_s, settings.http_max_retries, settings.http_concurrency,
        ))
        self._dataset: Dataset | None = None
        self._lock = asyncio.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._dataset is not None

    @property
    def cache_path(self) -> Path:
        digest = hashlib.sha256(json.dumps(request_signature(self.settings), sort_keys=True).encode()).hexdigest()[:16]
        return self.settings.cache_dir / f"elexon-raw-{digest}.json.gz"

    async def dataset(self) -> Dataset:
        if self._dataset is not None:
            return self._dataset
        async with self._lock:
            if self._dataset is None:
                raw = await self._load_raw()
                self._dataset = build_dataset(raw, self.settings)
                q = self._dataset.quality
                logger.info("dataset_built mode=%s matched=%d expected_forecast_intervals=%d",
                            raw.mode, q.matched_pairs, q.expected_forecast_intervals)
        return self._dataset

    async def _load_raw(self) -> RawData:
        s = self.settings
        if s.data_source == "snapshot":
            return self._snapshot()
        if self.cache_path.exists():
            try:
                return read_raw_file(self.cache_path, s, "cache")
            except (OSError, ValueError, KeyError, DataUnavailableError) as exc:
                logger.warning("cache_unreadable path=%s error=%s", self.cache_path.name, exc)
        try:
            raw = await fetch_live(s, self._client_factory())
        except ElexonError as exc:
            if s.data_source == "auto" and s.snapshot_path.exists():
                logger.warning("live_fetch_failed_using_snapshot error=%s", exc)
                return self._snapshot()
            raise
        try:
            write_raw_file(self.cache_path, raw, s)
        except OSError as exc:  # read-only filesystem: keep serving from memory
            logger.warning("cache_write_failed error=%s", exc)
        return raw

    def _snapshot(self) -> RawData:
        path = self.settings.snapshot_path
        if not path.exists():
            raise DataUnavailableError("DATA_SOURCE=snapshot but no snapshot file is present")
        return read_raw_file(path, self.settings, "snapshot")


ENDPOINTS = [FUELHH_PATH, WINDFOR_PATH]
