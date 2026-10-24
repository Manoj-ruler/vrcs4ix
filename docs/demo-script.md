# Demo video script (two parts, ≤ 10 min in total)

Record at 1440×900 or larger, browser zoom 100 %, on the deployed app. Every number below is from the
real January 2026 analysis; read it off the screen while recording rather than from this page.

---

## Part 1 — Customer presentation (target 4:30, hard limit 5:00)

| Time | Screen | Talking points |
| --- | --- | --- |
| 0:00–0:35 | Title row and headline sentence | "You buy power a day ahead and have to trust a wind forecast for what you don't buy. We took every hour of January 2026 and asked: what did the forecast you could actually see at decision time say, and how far off was it?" |
| 0:35–1:20 | Hover the chart near 1 Jan 00:00; point at the tooltip's *Published* and *Cutoff* | "Each hour has about 24 forecast versions; later ones are better, but you can't use what wasn't published yet. We take the newest forecast published by 11:00 UK time the day before, when the day-ahead auction closes. Here, 1 January used the forecast published 31 December at 09:30." |
| 1:20–2:20 | KPI strip | "On average the forecast missed by **2,107 MW** an hour; RMSE 2,611 MW. The important part is the direction: it was **too high by 1,840 MW on average**, in **628 of 744 hours**. In 9 hours out of 10 the miss was under **4,377 MW**." |
| 2:20–3:10 | Daily error chart (Bias), then click 28 Jan | "Almost every day leans the same way. The worst day was 28 January, about 5,300 MW out on average. Only four days came in under." Click 28 Jan: "You can drill into any day." |
| 3:10–3:50 | Hour-of-day chart | "Errors are largest overnight and early morning, around 2,400–2,500 MW at 03:00–06:00, and lowest in the evening, about 1,900 MW." |
| 3:50–4:30 | Method and coverage panels | "What this means for planning: a systematic high bias means relying on the raw forecast leads to buying too little other power. A team could plan against a wind figure about 1.8 GW lower, and keep a buffer near the P90 miss. Limits: this is national wind only, not demand or other plants; 11:00 is our assumed decision time, and we can change it to yours; coverage was 100 %, all from Elexon." |

## Part 2 — Technical review (target 4:40, hard limit 5:00)

| Time | Screen | Talking points |
| --- | --- | --- |
| 0:00–0:35 | README architecture diagram | "React and TypeScript front end, FastAPI back end, Elexon's FUELHH and WINDFOR stream endpoints. One Vercel project: the static build plus FastAPI as a Python function, same origin. Docker Compose for local runs." |
| 0:35–1:20 | `clients/elexon.py`, `docs/data-methodology.md` §1 | "WINDFOR is fetched by **publish** time in one-day windows, which returns every forecast version. 39 bounded requests, timeouts, three retries with backoff, fail fast on bad responses." |
| 1:20–2:20 | `services/forecast_selection.py` | "The core is pure functions: the delivery day is the local UK date, the cutoff is 11:00 UK on the day before, keep `publishTime ≤ cutoff`, take the latest. Nothing after the cutoff can leak. The cache holds raw rows and the rule is re-applied on every build." Show `test_selects_newest_eligible_and_rejects_post_cutoff` and the BST test. |
| 2:20–3:05 | `services/alignment.py`, `metrics.py` | "Join on exact `startTime`. WINDFOR is hourly, so :30 half-hours are marked, not interpolated. Error is forecast minus actual. Every aggregate is recomputed from interval errors; there is a test that monthly RMSE is not the mean of daily RMSE. MAPE skips near-zero actuals and reports its own n. Missing never becomes zero." |
| 3:05–3:45 | Terminal: `pytest -q` (55 passed), `npm test`, `npm run build` | "55 backend tests: leakage, ingestion, metrics against hand-worked numbers, API with a mocked upstream, retries, snapshot fallback." |
| 3:45–4:20 | Browser: select an hour, publication strip; `/docs` | "The API is typed with Pydantic and mirrored in TypeScript. The front end never recomputes metrics. Every block has loading, error-with-retry and empty states." |
| 4:20–4:40 | README limitations | "Trade-offs: no database, because about 21k immutable rows fit in memory; a real-data snapshot as an outage fallback, labelled in the UI; the cutoff is configurable. Next steps: confirm the client's decision time, add demand data, and track FUELHH revisions." |

Total target: about 9:10.
