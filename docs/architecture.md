# Architecture

## Components

```
┌────────────────────── Browser ──────────────────────┐
│ React + TS (Vite)                                    │
│  App.tsx ── useApi() ── api/client.ts (typed fetch)  │
│  KpiStrip · ForecastChart · DailyErrorChart ·        │
│  HourlyChart · RecordsTable · IntervalPanel ·        │
│  CoveragePanel                                       │
└──────────────┬───────────────────────────────────────┘
               │ GET /api/analysis/*  (same origin on Vercel; Vite proxy / nginx locally)
┌──────────────▼───────────────────────────────────────┐
│ FastAPI  app/main.py                                  │
│  routes/analysis.py ─ validation, paging (query.py)   │
│  serializers.py ─ dataclasses → Pydantic schemas      │
│  AnalysisService (services/analysis.py)               │
│    load raw: memory → /tmp cache → Elexon → snapshot  │
│    build_dataset(raw, settings)  [pure]               │
│      ingestion → forecast_selection → alignment       │
│      → metrics (overall, daily, hourly) + quality     │
│  clients/elexon.py ─ httpx, windows, retries          │
└──────────────┬───────────────────────────────────────┘
               ▼
        Elexon BMRS Insights API (FUELHH, WINDFOR stream)
```

## Responsibilities

| Concern | Where | Notes |
| --- | --- | --- |
| External API | `clients/elexon.py` | bounded windows, 30 s timeout, up to 3 retries with exponential backoff on network errors, 429 and 5xx; fails fast on other 4xx and on malformed bodies |
| Normalisation | `services/ingestion.py` | typed frozen dataclasses; invalid rows counted, never repaired |
| Decision-time selection | `services/forecast_selection.py` | pure functions, no I/O |
| Alignment | `services/alignment.py` | one record per expected half-hour |
| Metrics | `services/metrics.py` | one implementation used for every aggregate |
| Orchestration and cache | `services/analysis.py` | dataset built once per process behind an asyncio lock |
| Request handling | `api/routes/*`, `services/query.py` | date validation (422), filtering, sorting, paging |
| Response contracts | `schemas/analysis.py` | camelCase Pydantic models, mirrored in `frontend/src/api/types.ts` |
| UI state | `frontend/src/App.tsx`, `lib/useApi.ts` | each block has its own loading, error and retry; requests are aborted when filters change |

The frontend does not recompute any metric. It formats what the API returns. The only derived text is
the headline sentence, built from the API's bias, counts and P90.

## Key decisions and trade-offs

- **No database.** The analysis covers about 21k immutable historical rows (about 2 MB raw). They fit in
  memory, and the whole build takes well under a second. A database would add hosting and migrations
  for no gain.
- **No pandas.** The pipeline is plain Python with `math`. At this volume it is fast. It keeps the
  Vercel function small and makes each formula easy to read in review. NumPy's percentile definition is
  reproduced and tested.
- **Raw-row cache, not a results cache.** The cutoff rule is applied after the cache, so a configuration
  change or a later download can never reuse leaked selections.
- **Snapshot fallback.** Serverless cold starts depend on Elexon being reachable. The bundled real
  snapshot keeps the demo working through an outage, and responses say when it is used.
- **Single Vercel project.** The brief names Vercel or Heroku. Vercel can run the static React build and
  FastAPI as a Python function together, with no extra host and same-origin API calls. Docker is used
  for local runs (`docker compose`) and proves the backend works in a container.
- **Recharts with tuned styling.** It is a maintained library (3.x) that is enough for the line and bar
  charts here. The decision-time "publication strip" is hand-drawn SVG because no library has that view.

## Error handling

| Situation | Response |
| --- | --- |
| Elexon unreachable or 5xx after retries | snapshot if available; otherwise HTTP 502 `{"code": "upstream_unavailable"}` |
| No data source available | 503 `data_unavailable` |
| Bad dates, page or sort | 422 with a readable `detail` |
| Unknown interval | 404 |
| Anything else | 500 with a generic message; the stack trace is only logged |

Logs are single-line `key=value` records. Request parameters, secrets and environment values are not
logged.
