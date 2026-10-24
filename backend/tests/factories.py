"""TEST FIXTURES ONLY: small hand-made rows shaped like Elexon responses. Never used by the app."""

from __future__ import annotations

from datetime import date, time

from app.core.config import CutoffRule, Settings, load_settings
from dataclasses import replace

RULE = CutoffRule(local_time=time(11, 0), days_before=1, timezone="Europe/London", inclusive=True)


def actual_row(start: str, generation, fuel="WIND", publish: str | None = None) -> dict:
    return {"dataset": "FUELHH", "startTime": start, "publishTime": publish or start, "fuelType": fuel,
            "generation": generation, "settlementDate": start[:10], "settlementPeriod": 1}


def forecast_row(start: str, publish: str, generation) -> dict:
    return {"dataset": "WINDFOR", "startTime": start, "publishTime": publish, "generation": generation}


def settings(tmp_path, **overrides) -> Settings:
    base = replace(
        load_settings(),
        delivery_start=date(2026, 1, 1), delivery_end=date(2026, 1, 2),
        cutoff=RULE, data_source="live", cache_dir=tmp_path / "cache", snapshot_path=tmp_path / "none.json.gz",
        mape_min_actual_mw=1.0,
    )
    return replace(base, **overrides)
