# API reference

Base path `/api`. All responses are JSON in camelCase, except the CSV export. Times are ISO-8601 UTC
(`Z`); dates are UK delivery dates. Generation and error values are in MW. Date filters use
`startDate` and `endDate` (`YYYY-MM-DD`, inclusive, inside 2026-01-01…2026-01-31; the default is the
whole window).

## `GET /api/health`
Liveness. Never triggers a download.
```json
{ "status": "ok", "version": "1.0.0", "dataLoaded": true }
```

## `GET /api/analysis/summary?startDate&endDate`
Metrics for the selected dates, whole-window data quality, the cutoff rule, conventions and the data
source.
```json
{
  "window": { "startDate": "2026-01-01", "endDate": "2026-01-31", "startTime": "2026-01-01T00:00:00Z", "endTime": "2026-02-01T00:00:00Z" },
  "selection": { "startDate": "2026-01-01", "endDate": "2026-01-31", "expectedForecastIntervals": 744, "matched": 744, "missingActual": 0, "missingForecast": 0 },
  "cutoff": { "description": "Latest WINDFOR forecast published at or before 11:00 Europe/London on the day before the delivery day", "localTime": "11:00", "daysBefore": 1, "timezone": "Europe/London", "inclusive": true },
  "metrics": { "n": 744, "mae": 2107.18, "rmse": 2611.24, "bias": 1839.92, "mape": 21.88, "nMape": 744,
               "p50AbsoluteError": 1707.0, "p90AbsoluteError": 4377.0, "maxOverforecast": 6857.0, "maxUnderforecast": -3967.0,
               "meanActual": 11581.11, "meanForecast": 13421.03, "nOverforecast": 628, "nUnderforecast": 116 },
  "emptyReason": null,
  "quality": { "expectedIntervals": 1488, "validActualIntervals": 1488, "forecastRecordsReceived": 19856, "forecastPublications": 272,
               "expectedForecastIntervals": 744, "eligibleForecastsSelected": 744, "matchedPairs": 744, "coveragePct": 100.0, "...": "..." },
  "conventions": { "units": "...", "error": "forecastError = forecast - actual; positive = overforecast, negative = underforecast", "mape": "...", "forecastResolutionMinutes": 60 },
  "dataSource": { "provider": "Elexon BMRS Insights API", "endpoints": ["..."], "mode": "live", "fetchedAt": "2026-10-24T04:43:51Z" }
}
```
(The numbers above are abridged from a real response.) If nothing is matched, `metrics` is `null` and
`emptyReason` explains why.

## `GET /api/analysis/timeseries?startDate&endDate`
Every half-hour in range, ordered by `startTime`:
`{ startTime, actual, forecast, error, publishTime, decisionCutoff, status }`. `forecast` is `null` on
:30 half-hours (`status: "no_forecast_scheduled"`).

## `GET /api/analysis/daily?startDate&endDate`
`[{ date, metrics | null, expectedForecastIntervals, matched, missingActual, missingForecast }]`,
recomputed from that day's interval records.

## `GET /api/analysis/hourly`
The same shape keyed by `hour` (0–23, UK time), over the whole window.

## `GET /api/analysis/records`
| Param | Values | Default |
| --- | --- | --- |
| `startDate`, `endDate` | dates in window | whole window |
| `scope` | `forecast` (hourly slots) · `all` (include :30) | `forecast` |
| `status` | `any` · `matched` · `missing` | `any` |
| `sort` | `startTime` · `absoluteError` · `forecastError` · `actualGeneration` · `forecastGeneration` | `startTime` |
| `order` | `asc` · `desc` | `asc` |
| `page`, `pageSize` | ≥1 · 1–500 | 1 · 50 |

Returns `{ items: Record[], page, pageSize, total, totalPages }`. Sorting is stable; nulls go last and
ties keep delivery order. A `page` past the end returns 422.

A `Record` has: `startTime, deliveryDate, actualGeneration, forecastGeneration, publishTime,
decisionCutoff, horizonHours, forecastError, absoluteError, squaredError, absolutePercentageError,
eligibleForecastCount, rejectedAfterCutoffCount, status`.

## `GET /api/analysis/records.csv`
The same filters as `/records`, without paging. Columns are the `Record` fields.

## `GET /api/analysis/interval?startTime=2026-01-10T12:00:00Z`
`{ record, candidates: [{ publishTime, generation, eligible, selected }], explanation }`. Candidates
cover every version in the downloaded window, newest first. 404 if no interval starts at that time;
422 if the timestamp has no timezone.

## Errors
`{ "detail": "...", "code"?: "upstream_unavailable" | "data_unavailable" | "internal_error" }` with
422 / 404 / 502 / 503 / 500 as described in [architecture.md](architecture.md#error-handling).

FastAPI also serves interactive docs at `/api/docs` and the OpenAPI schema at `/api/openapi.json`
(live: <https://vrcs4ix.vercel.app/api/docs>).
