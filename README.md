# Wind Forecast Desk

A web app for a UK energy utility's day-ahead purchasing team. For every hour of January 2026 it shows
the **national wind generation forecast that was actually available when the purchase decision was
made**, compares it with **actual national wind generation**, and quantifies the error.

**Live app:** <https://vrcs4ix.vercel.app> · API health: <https://vrcs4ix.vercel.app/api/health> ·
interactive API docs: <https://vrcs4ix.vercel.app/api/docs>.

---

## 1. The business problem

The team buys power in the GB day-ahead market. Whatever wind does not produce must be bought from
other sources, so they lean on wind forecasts the day before delivery. They need to:

1. see the latest wind forecast that existed at their decision time (not a later, better one), and
2. know how wrong such forecasts typically are, so they can size the risk they carry.

The app covers national wind only, from two Elexon datasets. It is **not** a full demand/supply
balance: demand, solar, interconnectors and other plants are outside the data, so it does not
calculate how much power the team must buy. It quantifies one input to that decision.

### What January 2026 shows (real Elexon data, default settings)

| Measure (744 matched hours) | Value |
| --- | --- |
| Mean absolute error (MAE) | 2,107 MW |
| RMSE | 2,611 MW |
| Bias (forecast − actual) | +1,840 MW (forecast too high in 628 of 744 hours) |
| 90th percentile absolute error | 4,377 MW |
| MAPE | 21.9 % |
| Coverage | 744 / 744 forecast hours matched (100 %) |

The worst days were 28 Jan (MAE 5,329 MW), 11 Jan and 12 Jan. Only four days (5, 10, 14, 19 Jan) had
a negative bias. The forecast overestimated wind far more often than it underestimated it: relying
on it unadjusted would have meant buying too little other power. One possible cause is curtailment
or constraints that reduce metered output. This is a hypothesis; these datasets cannot confirm it.

## 2. Features

- Headline accuracy for any date range: MAE, RMSE, signed bias, P90 absolute error, MAPE (with its own
  sample size) and coverage.
- Forecast-vs-actual time series. The tooltip shows the forecast, actual, signed error, publication time
  and decision cutoff.
- Daily error (switchable bias / MAE / RMSE; click a day to filter to it) and error by hour of day.
- Interval table: sortable, filterable (all / matched / missing), paginated, with CSV export.
- **"Why this forecast"** panel for any hour: every forecast version on a time strip, the cutoff,
  which versions were eligible, which were rejected because they came later, and the one selected.
- Data coverage and data-quality counts; the methodology stated on the page.
- Honest states: loading skeletons, error with retry, empty data, partial-coverage notice and invalid
  date-range messages. No figure is shown before the API returns it.

## 3. Data sources

| Dataset | Endpoint | Used fields |
| --- | --- | --- |
| FUELHH: actual generation by fuel type, half-hourly | [`/datasets/FUELHH/stream`](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream) | `fuelType = WIND`, `startTime`, `generation` (MW) |
| WINDFOR: wind generation forecast | [`/datasets/WINDFOR/stream`](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream) | `startTime`, `publishTime`, `generation` (MW) |

Base URL `https://data.elexon.co.uk/bmrs/api/v1`. The API is public and needs no key.

**Delivery time vs publication time.** `startTime` is the delivery interval being described.
`publishTime` (WINDFOR) is when that forecast was issued. A single hour has about 24 forecast versions,
published from about three days before delivery up to the hour itself. Only versions published by the
decision cutoff could have informed the purchase.

## 4. Methodology (summary — full detail in [docs/data-methodology.md](docs/data-methodology.md))

- **Window:** delivery 1–31 January 2026, local UK days: 1,488 half-hours. WINDFOR is hourly, so 744
  hours can be forecast.
- **Decision cutoff (pilot assumption):** 11:00 Europe/London on the day before delivery, inclusive. This
  matches the GB day-ahead auction gate closure (12:00 CET). The brief only says "one day before", so
  this is a documented, configurable assumption, not a client-confirmed rule.
- **Selection:** for each hour, discard every forecast published after its cutoff and take the newest of
  the rest. In January this is always the 09:30 UTC publication of the previous day; 1 January uses the
  forecast published on 31 December.
- **Matching:** exact join on `startTime`. A forecast for 13:00 is compared with the half-hour starting
  13:00. Half-hours starting at :30 have no forecast and are not scored. Nothing is interpolated.
- **Error:** `forecastError = forecast − actual`. Positive means overforecast; negative means underforecast.
- **Metrics:** MAE, RMSE, bias, MAPE. Every aggregate (overall, daily, hourly) is computed from the
  interval-level errors; daily RMSEs are never averaged.
- **Missing data:** never filled with zero. Missing actuals and missing eligible forecasts stay as
  records with a status, and are counted in the coverage figures.

## 5. Architecture

```
React + TypeScript (Vite, Recharts)      FastAPI (Python)                         Elexon BMRS
  typed client  ──/api/analysis/*──▶  routes → serializers                         FUELHH/stream
                                      AnalysisService (cache) ──▶ ElexonClient ──▶ WINDFOR/stream
                                        ingestion → forecast_selection → alignment → metrics
```

Raw API rows are cached (in memory, plus a gzip file in `/tmp`). The cutoff rule is applied on every
build, so a cache cannot leak post-cutoff forecasts. A 129 KB snapshot of the unmodified January rows
ships in `backend/data/`. It is used only if the live API is unreachable, and the UI labels it.
See [docs/architecture.md](docs/architecture.md) and [docs/api.md](docs/api.md).

## 6. Repository layout

```
api/index.py                 Vercel serverless entry (imports backend/app)
backend/
  app/
    main.py                  FastAPI app, CORS, error handlers
    core/config.py           environment settings, CutoffRule
    clients/elexon.py        HTTP client: windows, timeouts, bounded retries
    services/ingestion.py    validate + normalise FUELHH / WINDFOR rows
    services/forecast_selection.py   decision cutoff + latest eligible forecast (pure)
    services/alignment.py    join on startTime, per-interval errors and status
    services/metrics.py      MAE / RMSE / bias / MAPE / percentiles, daily + hourly
    services/analysis.py     orchestration, caching, snapshot fallback, data quality
    services/query.py        API filtering, sorting, paging
    api/routes/, api/serializers.py, schemas/analysis.py
    utils/datetime_utils.py  timezone-aware helpers
  data/elexon-jan-2026.json.gz   snapshot of raw API rows (fallback only)
  scripts/build_snapshot.py  regenerate the snapshot
  tests/                     pytest suite (fixtures are hand-made, labelled)
  Dockerfile, requirements.txt, requirements-dev.txt
frontend/
  src/api/                   typed API client and types
  src/components/            KPI strip, charts, table, interval panel, coverage
  src/lib/                   formatting, data-fetch hook, tests
  Dockerfile, nginx.conf
docs/                        architecture, methodology, API, traceability, demo, submission
docker-compose.yml, vercel.json, requirements.txt (Vercel function deps), .env.example
```

## 7. Running locally

Requirements: Python 3.10+, Node 20+ (22 recommended), or Docker.

```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000
```

```bash
# frontend (second terminal); /api is proxied to :8000
cd frontend
npm ci
npm run dev                   # http://localhost:5173
```

The first request downloads about 21k rows from Elexon (about 5–10 s), then results are cached.

### Docker

```bash
docker compose up --build     # app on http://localhost:8080, API on http://localhost:8000
```

### Environment variables

All are optional; see [.env.example](.env.example). Key ones: `DECISION_CUTOFF_LOCAL` (default
`11:00`), `DECISION_CUTOFF_DAYS_BEFORE` (`1`), `DECISION_CUTOFF_INCLUSIVE` (`true`), `MAPE_MIN_ACTUAL_MW`
(`1`), `DATA_SOURCE` (`auto` | `live` | `snapshot`), `CORS_ORIGINS`, and `VITE_API_BASE_URL` for a
frontend hosted apart from the API. No secrets are required.

## 8. Tests

```bash
cd backend && python -m pytest          # 56 tests: selection/leakage, ingestion, metrics, API, client
cd frontend && npm test                 # formatting, validation, URL building
cd frontend && npm run typecheck && npm run build
```

Results from the latest run are recorded in [docs/submission-checklist.md](docs/submission-checklist.md).

## 9. Deployment

One Vercel project serves both parts. The Vite build is the static site, and `api/index.py` runs the
FastAPI app as a Python function. Requests to `/api/*` are rewritten to it, so the API is same-origin
and needs no CORS. Steps:

```bash
npx vercel login
npx vercel --prod             # from the repository root; vercel.json holds the build settings
```

No environment variables are required. Optionally set `DATA_SOURCE=auto`, which is the default.

## 10. Reproducing the analysis

1. `cd backend && python -m scripts.build_snapshot`. This downloads the same rows again and prints the
   matched count (744).
2. `DATA_SOURCE=live uvicorn app.main:app` and `GET /api/analysis/summary`. The figures above come
   from this endpoint.
3. Change `DECISION_CUTOFF_LOCAL` (for example to `00:00`) to see how the cutoff choice moves accuracy.

## 11. Known limitations

- The decision cutoff is an assumption (11:00 UK, D−1). The client's real timing may differ.
- WINDFOR is hourly and FUELHH is half-hourly. Only on-the-hour half-hours are scored, and a single
  half-hour stands in for the hour.
- FUELHH may revise values. The latest published value is used, and revisions after the download are
  not tracked.
- Wind only, national level. No demand, prices or other fuel types, so this is not a procurement volume.
- The positive bias is measured, but its cause cannot be established from these datasets.
- The cache lives per server instance. A cold serverless start downloads again, or falls back to the
  snapshot.


