"""Elexon BMRS Insights API client (FUELHH and WINDFOR stream endpoints).

Only raw transport lives here: bounded date windows, timeouts, retries with exponential backoff.
No filtering or interpretation of the records happens in this module.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.utils.datetime_utils import to_iso

logger = logging.getLogger(__name__)

FUELHH_PATH = "/datasets/FUELHH/stream"
WINDFOR_PATH = "/datasets/WINDFOR/stream"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ElexonError(RuntimeError):
    """The upstream API could not provide a usable response."""


class ElexonClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        concurrency: int = 6,
        backoff_base_s: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout_s
        self._max_retries = max_retries
        self._backoff_base = backoff_base_s
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._transport = transport

    async def fetch_fuelhh(self, start: date, end_inclusive: date, window_days: int = 7) -> list[dict[str, Any]]:
        """FUELHH WIND rows for settlement dates [start, end_inclusive], in bounded windows."""
        windows = []
        current = start
        while current <= end_inclusive:
            window_end = min(current + timedelta(days=window_days - 1), end_inclusive)
            windows.append({
                "settlementDateFrom": current.isoformat(),
                "settlementDateTo": window_end.isoformat(),
                "fuelType": "WIND",
            })
            current = window_end + timedelta(days=1)
        return await self._fetch_windows(FUELHH_PATH, windows)

    async def fetch_windfor(self, publish_from: datetime, publish_to: datetime) -> list[dict[str, Any]]:
        """Every WINDFOR publication with publishTime in [publish_from, publish_to], one day per request.

        Filtering by publish time (not start time) is what returns the full version history.
        Both API bounds are inclusive, so windows end one second before the next one starts.
        """
        windows = []
        current = publish_from
        while current <= publish_to:
            window_end = min(current + timedelta(days=1) - timedelta(seconds=1), publish_to)
            windows.append({"publishDateTimeFrom": to_iso(current), "publishDateTimeTo": to_iso(window_end)})
            current = window_end + timedelta(seconds=1)
        return await self._fetch_windows(WINDFOR_PATH, windows)

    async def _fetch_windows(self, path: str, windows: list[dict[str, str]]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport,
            headers={"Accept": "application/json"},
        ) as client:
            results = await asyncio.gather(*(self._get(client, path, params) for params in windows))
        # Windows are processed in request order, so the combined list is deterministic.
        return [row for rows in results for row in rows]

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        last_error = "unknown error"
        for attempt in range(self._max_retries + 1):
            if attempt:
                await asyncio.sleep(self._backoff_base * 2 ** (attempt - 1))
            try:
                async with self._semaphore:
                    response = await client.get(path, params=params)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}"
                logger.warning("elexon_request_failed path=%s attempt=%d error=%s", path, attempt + 1, last_error)
                continue
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}"
                logger.warning("elexon_request_retry path=%s attempt=%d status=%d", path, attempt + 1, response.status_code)
                continue
            if response.status_code != 200:
                raise ElexonError(f"Elexon returned HTTP {response.status_code} for {path}")
            return self._parse(response, path)
        raise ElexonError(f"Elexon request to {path} failed after {self._max_retries + 1} attempts ({last_error})")

    @staticmethod
    def _parse(response: httpx.Response, path: str) -> list[dict[str, Any]]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ElexonError(f"Elexon returned a non-JSON body for {path}") from exc
        # The stream endpoints return a bare array; the paged endpoints wrap it in {"data": [...]}.
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            payload = payload["data"]
        if not isinstance(payload, list):
            raise ElexonError(f"Unexpected Elexon response shape for {path}")
        return [row for row in payload if isinstance(row, dict)]
