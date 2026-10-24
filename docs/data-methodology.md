# Data methodology

## 1. Sources and why these endpoints

| | FUELHH | WINDFOR |
| --- | --- | --- |
| Endpoint | `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream` | `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream` |
| Filters used | `settlementDateFrom`, `settlementDateTo`, `fuelType=WIND` | `publishDateTimeFrom`, `publishDateTimeTo` |
| Resolution | 30 min (`startTime` on :00 and :30) | 60 min (`startTime` on :00 only) |
| Unit | MW (`generation`, integer) | MW (`generation`, integer) |
| Auth | none | none |

The **stream** endpoints return a bare JSON array with no paging. A month of FUELHH WIND is 1,488 rows,
and the whole WINDFOR publication window is 19,856 rows, so neither needs a continuation token. We
still request in bounded windows: 7 settlement days per FUELHH call and 1 publication day per WINDFOR
call, 40 requests in all (5 FUELHH + 35 WINDFOR), run with limited concurrency.

**Why filter WINDFOR by publish time.** A start-time filter, or a "latest" endpoint, would hide or
overwrite earlier versions. Filtering by `publishTime` returns every version published in the window.
This is what reconstructing the decision needs. Checked live on 2026-10-24: each publication
carries 73 hourly start times (about 3 days ahead). There are 8 publications a day at 02:30, 04:30,
07:30, 09:30, 11:30, 15:30, 18:30 and 22:30 UTC, with an occasional extra (one at 12:25). Both publish
bounds are inclusive, so window ends are set to 23:59:59 to avoid overlap. Duplicates are removed
anyway.

**Window fetched.** Publications from `first cutoff − 96 h` (27 Dec 2025 11:00 UTC) to the last
cutoff (30 Jan 2026 11:00 UTC). Nothing published after the final cutoff is downloaded, because no
decision could have used it.

## 2. Normalisation and validation (`services/ingestion.py`)

- Timestamps are parsed as timezone-aware UTC. A timestamp with no zone is rejected, not guessed.
- FUELHH rows with `fuelType != WIND` are excluded and counted. Rows whose `dataset` field names another
  dataset are invalid.
- `generation` must be a finite number. `null`, strings and NaN are counted as invalid and **never
  turned into 0**.
- FUELHH rows outside [1 Jan 00:00, 1 Feb 00:00) UK time are counted as out-of-window.
- FUELHH duplicate `startTime`: the row with the later `publishTime` wins (a revision). On a tie, the
  last row in source order wins. Conflicting values are counted.
- WINDFOR duplicate (`startTime`, `publishTime`): the last row in source order is kept and counted.
  Every distinct publication version is preserved for the selection step.

January 2026 result: 1,488 valid actuals, 19,856 valid forecast rows from 272 publications,
0 invalid rows, 0 duplicates.

## 3. Decision-time forecast selection (`services/forecast_selection.py`)

For a delivery interval starting at T:

1. Delivery day D = the date of T in Europe/London. This is the GB settlement day, and it handles BST.
2. Cutoff C = 11:00 Europe/London on D − 1, converted to UTC (11:00 UTC in January).
3. Eligible = forecasts for T with `publishTime ≤ C`. The comparison is inclusive by default
   (`DECISION_CUTOFF_INCLUSIVE`).
4. Selected = the eligible forecast with the greatest `publishTime`. If two share it, the later one
   in input order wins.
5. If nothing is eligible, the interval's forecast is **missing**. Nothing is substituted.

**Why 11:00 UK on D−1.** The brief says only that purchase decisions are made "one day before" the
delivery day. The main GB day-ahead auctions (EPEX SPOT and Nord Pool) close at 12:00 CET, which is
11:00 UK time, for delivery the next day. A team buying day-ahead must decide by then, so the newest
forecast it could use is the newest one published by 11:00. This is our **pilot assumption**, not a rule
the client stated. All three parts (time, days before, inclusive or exclusive) are configurable. With
the January publishing pattern, the selected version is always the **09:30 UTC publication on D−1**,
with 14.5–37.5 h of lead time. The 11:30 UTC publication arrives just after the cutoff and is rejected.

Leakage controls:
- Selection always applies the cutoff. It never takes "max publishTime per startTime".
- The cache holds raw rows only. The cutoff is re-applied on every build.
- Tests cover a forecast newer than the cutoff, one exactly at the cutoff (inclusive and exclusive),
  duplicate timestamps, missing forecasts, determinism, timezone offsets, BST, and 1 January using a
  forecast published in December.

## 4. Alignment (`services/alignment.py`)

Every expected half-hour (1,488) produces one record. The join is on the exact normalised `startTime`,
never on publish time or a nearby timestamp.

| Status | Meaning |
| --- | --- |
| `matched` | valid actual and selected forecast |
| `missing_actual` | forecast selected, actual missing or invalid |
| `missing_forecast` | actual present, no forecast published by the cutoff |
| `missing_both` | neither |
| `no_forecast_scheduled` | half-hour starting at :30; WINDFOR has no value for it by design |

Per matched record: `forecastError = F − A`, `absoluteError`, `squaredError`, and
`absolutePercentageError = |F − A| / |A| × 100` when `|A| ≥ MAPE_MIN_ACTUAL_MW` (1 MW). Each record also
keeps `publishTime`, `decisionCutoff`, the lead time (`startTime − publishTime`), and the counts of
eligible and rejected versions.

**Why not use :30 half-hours.** Giving the hourly forecast to the :30 half-hour as well would assume the
forecast is flat within the hour. Averaging two half-hours would change what "actual" means. Matching on
the exact start time adds no assumption. The cost is that half the actuals are not scored. They are
still shown on the chart and counted in coverage.

## 5. Metrics (`services/metrics.py`)

Over N matched records:

- MAE = mean(|F − A|), in MW
- RMSE = sqrt(mean((F − A)²)), in MW
- Bias = mean(F − A), in MW. Positive means the forecast is too high (overforecast).
- MAPE = mean(|F − A| / |A|) × 100 over records with |A| ≥ 1 MW. Its own sample size `nMape` is reported.
  January's minimum actual is far above 1 MW, so nMape = N = 744.
- P50 and P90 of |F − A| (linear interpolation, the same as numpy's default), the largest over- and
  under-forecast, the counts of over and under hours, and mean actual and mean forecast.

Daily and hour-of-day figures are recomputed from the interval records in each group. Monthly RMSE is
not an average of daily RMSEs; a test asserts this. If a group has no matched record, its metrics are
`null` with a reason, never 0.

## 6. Coverage and quality figures

Reported for the whole window: expected intervals (1,488), actual rows received, valid actuals,
missing actuals, invalid and duplicate rows, excluded fuel-type rows, forecast rows received and valid,
publications, expected forecast hours (744), eligible forecasts selected, missing eligible forecasts,
matched pairs, and coverage % (matched ÷ expected forecast hours). The summary also returns counts for
the selected date range.

## 7. Caching and the snapshot

- Raw rows are cached in process memory and as a gzip file in `CACHE_DIR` (default: the OS temp dir).
  The file name is a hash of the request window. A different window or base URL means a different
  file, so nothing has to be invalidated by hand. Delete the file to force a fresh download.
- `backend/data/elexon-jan-2026.json.gz` (129 KB) holds the unmodified API rows, made by
  `scripts/build_snapshot.py`. With `DATA_SOURCE=auto`, it is used only if the live download fails. The
  API reports `dataSource.mode` (`live`, `cache` or `snapshot`), and the page shows it.
