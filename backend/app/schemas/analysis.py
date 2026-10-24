"""Response schemas (camelCase on the wire). Units: generation and errors in MW, percentages 0-100."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Status = Literal["matched", "missing_actual", "missing_forecast", "missing_both", "no_forecast_scheduled"]


class Schema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Health(Schema):
    status: Literal["ok"]
    version: str
    data_loaded: bool


class Metrics(Schema):
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


class DataQuality(Schema):
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


class CutoffInfo(Schema):
    description: str
    local_time: str
    days_before: int
    timezone: str
    inclusive: bool


class DataSource(Schema):
    provider: str
    endpoints: list[str]
    mode: Literal["live", "cache", "snapshot"]
    fetched_at: str


class Window(Schema):
    start_date: date
    end_date: date
    start_time: str
    end_time: str


class Conventions(Schema):
    units: str
    error: str
    mape: str
    forecast_resolution_minutes: int


class Selection(Schema):
    start_date: date
    end_date: date
    expected_forecast_intervals: int
    matched: int
    missing_actual: int
    missing_forecast: int


class Summary(Schema):
    window: Window
    selection: Selection
    cutoff: CutoffInfo
    metrics: Metrics | None
    empty_reason: str | None
    quality: DataQuality
    conventions: Conventions
    data_source: DataSource


class TimeseriesPoint(Schema):
    start_time: str
    actual: float | None
    forecast: float | None
    error: float | None
    publish_time: str | None
    decision_cutoff: str | None
    status: Status


class Timeseries(Schema):
    start_date: date
    end_date: date
    points: list[TimeseriesPoint]


class GroupRow(Schema):
    metrics: Metrics | None
    expected_forecast_intervals: int
    matched: int
    missing_actual: int
    missing_forecast: int


class DailyRow(GroupRow):
    date: date


class HourlyRow(GroupRow):
    hour: int


class Record(Schema):
    start_time: str
    delivery_date: date
    actual_generation: float | None
    forecast_generation: float | None
    publish_time: str | None
    decision_cutoff: str | None
    horizon_hours: float | None
    forecast_error: float | None
    absolute_error: float | None
    squared_error: float | None
    absolute_percentage_error: float | None
    eligible_forecast_count: int
    rejected_after_cutoff_count: int
    status: Status


class RecordPage(Schema):
    items: list[Record]
    page: int
    page_size: int
    total: int
    total_pages: int


class Candidate(Schema):
    publish_time: str
    generation: float
    eligible: bool
    selected: bool


class IntervalDetail(Schema):
    record: Record
    candidates: list[Candidate]
    explanation: str
