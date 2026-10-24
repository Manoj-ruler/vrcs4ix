from __future__ import annotations

import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api import serializers as ser
from app.schemas.analysis import DailyRow, HourlyRow, IntervalDetail, RecordPage, Summary, Timeseries
from app.services.analysis import AnalysisService, Dataset
from app.services.query import (
    InvalidQueryError, Scope, SortField, StatusFilter, filter_records, paginate, sort_records, validate_range,
)
from app.utils.datetime_utils import parse_utc

router = APIRouter(prefix="/api/analysis")


def service(request: Request) -> AnalysisService:
    return request.app.state.analysis


async def dataset(svc: AnalysisService = Depends(service)) -> Dataset:
    return await svc.dataset()


def date_range(
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    svc: AnalysisService = Depends(service),
) -> tuple[date, date]:
    try:
        return validate_range(start_date, end_date, svc.settings.delivery_start, svc.settings.delivery_end)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/summary", response_model=Summary)
async def summary(
    rng: tuple[date, date] = Depends(date_range), ds: Dataset = Depends(dataset), svc: AnalysisService = Depends(service),
) -> Summary:
    """Metrics for the selected delivery dates (default: whole window); data quality is always whole-window."""
    return ser.summary(ds, svc.settings, filter_records(ds.records, *rng), rng)


@router.get("/timeseries", response_model=Timeseries)
async def timeseries(rng: tuple[date, date] = Depends(date_range), ds: Dataset = Depends(dataset)) -> Timeseries:
    records = filter_records(ds.records, *rng)
    return Timeseries(start_date=rng[0], end_date=rng[1], points=[ser.point(r) for r in records])


@router.get("/daily", response_model=list[DailyRow])
async def daily(rng: tuple[date, date] = Depends(date_range), ds: Dataset = Depends(dataset)) -> list[DailyRow]:
    return [ser.daily_row(d, m, c) for d, m, c in ds.daily if rng[0] <= d <= rng[1]]


@router.get("/hourly", response_model=list[HourlyRow])
async def hourly(ds: Dataset = Depends(dataset)) -> list[HourlyRow]:
    return [ser.hourly_row(h, m, c) for h, m, c in ds.hourly]


def _selected_records(ds: Dataset, rng: tuple[date, date], scope: Scope, status: StatusFilter, sort: SortField, order: str):
    return sort_records(filter_records(ds.records, *rng, scope=scope, status=status), sort, order == "desc")


@router.get("/records", response_model=RecordPage)
async def records(
    rng: tuple[date, date] = Depends(date_range),
    scope: Scope = "forecast",
    status: StatusFilter = "any",
    sort: SortField = "startTime",
    order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500, alias="pageSize"),
    ds: Dataset = Depends(dataset),
) -> RecordPage:
    try:
        result = paginate(_selected_records(ds, rng, scope, status, sort, order), page, page_size)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RecordPage(
        items=[ser.record(r) for r in result.items], page=result.page, page_size=result.page_size,
        total=result.total, total_pages=result.total_pages,
    )


@router.get("/records.csv")
async def records_csv(
    rng: tuple[date, date] = Depends(date_range),
    scope: Scope = "forecast",
    status: StatusFilter = "any",
    sort: SortField = "startTime",
    order: str = Query("asc", pattern="^(asc|desc)$"),
    ds: Dataset = Depends(dataset),
) -> StreamingResponse:
    rows = [ser.record(r).model_dump(by_alias=True, mode="json") for r in _selected_records(ds, rng, scope, status, sort, order)]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(ser.RECORD_FIELDS))
    writer.writeheader()
    writer.writerows(rows)
    filename = f"wind-forecast-records-{rng[0].isoformat()}-{rng[1].isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/interval", response_model=IntervalDetail)
async def interval(
    start_time: str = Query(..., alias="startTime"),
    ds: Dataset = Depends(dataset),
    svc: AnalysisService = Depends(service),
) -> IntervalDetail:
    try:
        start: datetime = parse_utc(start_time)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="startTime must be an ISO-8601 timestamp with timezone") from exc
    record = ds.by_start.get(start)
    if record is None:
        raise HTTPException(status_code=404, detail="no delivery interval starts at that time in the analysis window")
    return ser.interval_detail(record, ds.candidates.get(start, []), svc.settings.cutoff.inclusive)
