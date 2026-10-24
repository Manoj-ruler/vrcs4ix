"""Decision-time forecast selection (the leakage-sensitive step).

For each delivery interval: compute the purchase-decision cutoff, discard every forecast published
after it, and pick the most recently published of the rest. Nothing here touches the network.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from app.core.config import CutoffRule
from app.services.ingestion import ForecastRecord
from app.utils.datetime_utils import UTC


@dataclass(frozen=True)
class ForecastSelection:
    start_time: datetime
    decision_cutoff: datetime
    selected: ForecastRecord | None
    eligible_count: int
    rejected_after_cutoff: int


def decision_cutoff(start_time: datetime, rule: CutoffRule) -> datetime:
    """Cutoff for the delivery day that contains `start_time` (delivery day = local calendar date)."""
    tz = ZoneInfo(rule.timezone)
    delivery_day = start_time.astimezone(tz).date()
    decision_day = delivery_day - timedelta(days=rule.days_before)
    return datetime.combine(decision_day, rule.local_time, tzinfo=tz).astimezone(UTC)


def is_eligible(publish_time: datetime, cutoff: datetime, inclusive: bool) -> bool:
    return publish_time <= cutoff if inclusive else publish_time < cutoff


def group_by_start(forecasts: Iterable[ForecastRecord]) -> dict[datetime, list[ForecastRecord]]:
    groups: dict[datetime, list[ForecastRecord]] = defaultdict(list)
    for forecast in forecasts:
        groups[forecast.start_time].append(forecast)
    return groups


def select_forecast(candidates: list[ForecastRecord], cutoff: datetime, inclusive: bool) -> tuple[ForecastRecord | None, int, int]:
    """Latest eligible candidate; on equal publishTime the later candidate in the list wins."""
    selected: ForecastRecord | None = None
    eligible = rejected = 0
    for candidate in candidates:
        if not is_eligible(candidate.publish_time, cutoff, inclusive):
            rejected += 1
            continue
        eligible += 1
        if selected is None or candidate.publish_time >= selected.publish_time:
            selected = candidate
    return selected, eligible, rejected


def select_forecasts(
    forecasts: Iterable[ForecastRecord], start_times: Iterable[datetime], rule: CutoffRule
) -> dict[datetime, ForecastSelection]:
    groups = group_by_start(forecasts)
    selections = {}
    for start in start_times:
        cutoff = decision_cutoff(start, rule)
        selected, eligible, rejected = select_forecast(groups.get(start, []), cutoff, rule.inclusive)
        selections[start] = ForecastSelection(start, cutoff, selected, eligible, rejected)
    return selections
