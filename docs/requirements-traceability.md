# Requirements traceability

Source: *REint Full Stack SWE challenge v4* (the brief). "Assumption" marks a decision the brief does
not make; each one is explained in [data-methodology.md](data-methodology.md).

| # | Requirement (brief) | Implementation | Verified by |
| --- | --- | --- | --- |
| 1 | UK utility, day-ahead purchasing; decide one day before delivery | Decision cutoff per delivery day (`services/forecast_selection.py`) | `tests/test_forecast_selection.py` |
| 2 | Show the latest forecast available at decision time | Latest `publishTime ≤ cutoff`; "Selected hour" panel with all versions | selection tests; `test_interval_detail_explains_selection` |
| 3 | Evaluate forecast accuracy quantitatively | MAE, RMSE, bias, MAPE, P50/P90, daily, hourly (`services/metrics.py`) | `tests/test_alignment_metrics.py` (hand-calculated) |
| 4 | National wind only, Elexon only | FUELHH `fuelType=WIND`, WINDFOR; nothing else is fetched | `test_only_wind_rows_are_kept`; `clients/elexon.py` |
| 5 | FUELHH: `startTime`, `generation`, fuelType WIND | `normalize_actuals` | `tests/test_ingestion.py` |
| 6 | WINDFOR: `startTime`, `publishTime`, `generation` | `normalize_forecasts` keeps every version | `test_forecast_versions_are_all_preserved_and_sorted` |
| 7 | Data for purchase decisions in January 2026 | Delivery 1–31 Jan 2026 (UK days). Forecasts published from 27 Dec 2025. **Assumption**: "decisions in January" read as January delivery days; confirmed with the user | `test_january_first_uses_december_forecast`; live run: 744/744 matched |
| 8 | React frontend | `frontend/` (React 18, TypeScript strict, Vite, Recharts 3) | `npm run typecheck`, `npm run build`, `npm test` |
| 9 | Python backend | `backend/` (FastAPI, Pydantic, httpx) | `pytest` (55 tests) |
| 10 | Use Docker | `backend/Dockerfile`, `frontend/Dockerfile` + nginx, `docker-compose.yml` | see submission checklist (Docker run status) |
| 11 | Deploy on Vercel or Heroku | `vercel.json`, `api/index.py` (single Vercel project) | see submission checklist (deployment status) |
| 12 | AI tools mentioned in README | README §12 | README |
| 13 | ≤ 16 hours | Scope kept to the brief; no database or extra services | — |
| 14 | Video: part 1 customer pitch ≤ 5 min | `docs/demo-script.md` part 1 | recording is a manual step |
| 15 | Video: part 2 technical review ≤ 5 min; total ≤ 10 min | `docs/demo-script.md` part 2, `docs/demo-checklist.md` | recording is a manual step |
| 16 | Public GitHub repo, anonymous name | random repository name, no personal identifiers in the name | `docs/submission-checklist.md` |
| 17 | README: files and directories, how to start, app link | README §6, §7, top link | README |
| 18 | Submit the form; check every URL in incognito | `docs/submission-checklist.md` | manual step |

## Engineering requirements from the master prompt

| Requirement | Where |
| --- | --- |
| Leakage prevention (no post-cutoff info) | `forecast_selection.py`; raw-row cache re-applies the cutoff; 11 selection tests |
| Missing values never become zero | `ingestion._generation`; alignment statuses; `test_missing_or_bad_generation_is_invalid_not_zero` |
| Error sign convention F − A | `alignment.py`, API `conventions.error`, UI labels, docs |
| RMSE not averaged across days | `test_monthly_rmse_is_not_mean_of_daily_rmse` |
| MAPE zero handling and its own n | `test_mape_skips_zero_actuals_and_reports_its_own_n` |
| Empty data gives no fake zeros | `test_empty_data_returns_null_metrics`; UI `EmptyState` |
| Bounded retries; upstream failure handling | `clients/elexon.py`; `tests/test_elexon_client.py`; `test_upstream_failure_is_502_without_internals` |
| Pagination, sorting, filtering, CSV | `services/query.py`; `test_records_pagination_sort_filter`; `test_csv_export` |
| Health check without a download | `test_health_does_not_load_data` |
| Loading, error, empty, partial and invalid-filter states | `components/States.tsx`, `App.tsx` notice and date validation; checked in the browser with the API stopped |
| No mock data shown as real | fixtures only in `backend/tests/`; the snapshot is real API rows, labelled in the UI |
