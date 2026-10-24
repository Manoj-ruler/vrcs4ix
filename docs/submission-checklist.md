# Submission checklist

Only items that were actually done and checked are ticked. Form:
<https://forms.cloud.microsoft/r/Ljmf1aWESK> ("Full Stack SWE challenge submission v4", linked from the brief).

## Repository
- [x] Public GitHub repository with an anonymous name: <https://github.com/Manoj-ruler/vrcs4ix>
- [x] Opens without authentication (HTTP 200 unauthenticated; API reports `private: false`)
- [x] Commits authored as the configured repository identity; no AI co-author trailers
- [x] No secrets committed (no keys are needed; staged diff scanned before each commit)
- [x] README: files and directories, how to start, AI-tool disclosure
- [x] README: link to the deployed app

## Application
- [x] Backend tests: `python -m pytest`, **56 passed** (2026-10-24)
- [x] Frontend: `npm run typecheck` clean, `npm test` **6 passed**, `npm run build` succeeds
- [x] Frontend and backend run together locally (Vite proxy → FastAPI); real Elexon data; 744/744 hours matched
- [x] Interval inspection, sorting, CSV export and error states (API stopped) checked in the browser
- [ ] Docker: `docker compose up --build`. **Not verified.** Docker Desktop on the development
      machine fails to start ("initializing Inference manager … remove …\Docker\run\dockerInference"),
      a pre-existing local issue. The Dockerfiles and Compose file are written but have not been run.
- [x] Deployed on Vercel: <https://vrcs4ix.vercel.app> (static build + FastAPI Python function, one project)
- [x] Deployed app checked without authentication (2026-10-24): page 200; `/api/health`, `/summary`,
      `/timeseries`, `/daily`, `/hourly`, `/records`, `/records.csv`, `/interval`, `/api/docs` all 200;
      invalid dates give 422; live Elexon data (`dataSource.mode = live`); same figures as local
      (MAE 2,107, RMSE 2,611, bias +1,840 MW, n = 744); in the browser the KPIs, 3 charts, table and
      interval panel render with no console errors

## Video
- [x] Timed script with real figures (kept outside the repo); recording checklist: `docs/demo-checklist.md`
- [ ] Recorded (part 1 ≤ 5 min, part 2 ≤ 5 min, total ≤ 10 min)
- [ ] Uploaded to YouTube as **Unlisted**; duration checked

## Final checks (manual)
- [ ] Repo URL opens in an incognito window
- [ ] Deployed app URL opens in an incognito window
- [ ] YouTube URL plays in an incognito window
- [ ] Submission form completed and submitted
