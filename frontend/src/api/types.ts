// Mirrors backend/app/schemas/analysis.py. Units: MW for generation and errors, 0-100 for percentages.

export type IntervalStatus =
  | "matched"
  | "missing_actual"
  | "missing_forecast"
  | "missing_both"
  | "no_forecast_scheduled";

export interface Metrics {
  n: number;
  mae: number;
  rmse: number;
  bias: number;
  mape: number | null;
  nMape: number;
  p50AbsoluteError: number;
  p90AbsoluteError: number;
  maxOverforecast: number;
  maxUnderforecast: number;
  meanActual: number;
  meanForecast: number;
  nOverforecast: number;
  nUnderforecast: number;
}

export interface GroupCounts {
  expectedForecastIntervals: number;
  matched: number;
  missingActual: number;
  missingForecast: number;
}

export interface DataQuality {
  expectedIntervals: number;
  actualRecordsReceived: number;
  validActualIntervals: number;
  missingActualIntervals: number;
  invalidActualRecords: number;
  duplicateActualRecords: number;
  excludedFuelTypeRecords: number;
  forecastRecordsReceived: number;
  validForecastRecords: number;
  invalidForecastRecords: number;
  duplicateForecastRecords: number;
  forecastPublications: number;
  expectedForecastIntervals: number;
  eligibleForecastsSelected: number;
  missingEligibleForecasts: number;
  matchedPairs: number;
  coveragePct: number | null;
  distinctSelectedPublishTimes: number;
}

export interface Summary {
  window: { startDate: string; endDate: string; startTime: string; endTime: string };
  selection: GroupCounts & { startDate: string; endDate: string };
  cutoff: { description: string; localTime: string; daysBefore: number; timezone: string; inclusive: boolean };
  metrics: Metrics | null;
  emptyReason: string | null;
  quality: DataQuality;
  conventions: { units: string; error: string; mape: string; forecastResolutionMinutes: number };
  dataSource: { provider: string; endpoints: string[]; mode: "live" | "cache" | "snapshot"; fetchedAt: string };
}

export interface TimeseriesPoint {
  startTime: string;
  actual: number | null;
  forecast: number | null;
  error: number | null;
  publishTime: string | null;
  decisionCutoff: string | null;
  status: IntervalStatus;
}

export interface Timeseries {
  startDate: string;
  endDate: string;
  points: TimeseriesPoint[];
}

export interface DailyRow extends GroupCounts {
  date: string;
  metrics: Metrics | null;
}

export interface HourlyRow extends GroupCounts {
  hour: number;
  metrics: Metrics | null;
}

export interface IntervalRecord {
  startTime: string;
  deliveryDate: string;
  actualGeneration: number | null;
  forecastGeneration: number | null;
  publishTime: string | null;
  decisionCutoff: string | null;
  horizonHours: number | null;
  forecastError: number | null;
  absoluteError: number | null;
  squaredError: number | null;
  absolutePercentageError: number | null;
  eligibleForecastCount: number;
  rejectedAfterCutoffCount: number;
  status: IntervalStatus;
}

export interface RecordPage {
  items: IntervalRecord[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface IntervalDetail {
  record: IntervalRecord;
  candidates: { publishTime: string; generation: number; eligible: boolean; selected: boolean }[];
  explanation: string;
}

export type SortField = "startTime" | "absoluteError" | "forecastError" | "actualGeneration" | "forecastGeneration";
export type StatusFilter = "any" | "matched" | "missing";

export interface DateRange {
  startDate: string;
  endDate: string;
}

export interface RecordQuery extends DateRange {
  sort: SortField;
  order: "asc" | "desc";
  status: StatusFilter;
  page: number;
  pageSize: number;
}
