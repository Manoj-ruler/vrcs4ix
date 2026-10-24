# Submission checklist

Only items that were actually done and checked are ticked. Form:
<https://forms.cloud.microsoft/r/Ljmf1aWESK> ("Full Stack SWE challenge submission v4", linked from the brief).

## Repository
- [x] Public GitHub repository with an anonymous name: <https://github.com/Manoj-ruler/vrcs4ix>
- [x] Opens without authentication (HTTP 200 unauthenticated; API reports `private: false`)
- [x] Commits authored as the configured repository identity; no AI co-author trailers
- [x] No secrets committed (no keys are needed; staged diff scanned before each commit)
- [x] README: files and directories, how to start, AI-tool disclosure
- [ ] README: link to the deployed app (added once the deployment is verified)

## Application
- [x] Backend tests: `python -m pytest`, **55 passed** (2026-10-24)
- [x] Frontend: `npm run typecheck` clean, `npm test` **6 passed**, `npm run build` succeeds
- [x] Frontend and backend run together locally (Vite proxy → FastAPI); real Elexon data; 744/744 hours matched
- [x] Interval inspection, sorting, CSV export and error states (API stopped) checked in the browser
- [ ] Docker: `docker compose up --build`. **Not verified.** Docker Desktop on the development
      machine fails to start ("initializing Inference manager … remove …\Docker\run\dockerInference"),
      a pre-existing local issue. The Dockerfiles and Compose file are written but have not been run.
- [ ] Deployed on Vercel. **Blocked on a Vercel login** (`npx vercel login`, then `npx vercel --prod`).
- [ ] Deployed app checked: page loads, `/api/health`, `/api/analysis/summary`, interval panel

## Video
- [x] Script with timings and real figures: `docs/demo-script.md`; checklist: `docs/demo-checklist.md`
- [ ] Recorded (part 1 ≤ 5 min, part 2 ≤ 5 min, total ≤ 10 min)
- [ ] Uploaded to YouTube as **Unlisted**; duration checked

## Final checks (manual)
- [ ] Repo URL opens in an incognito window
- [ ] Deployed app URL opens in an incognito window
- [ ] YouTube URL plays in an incognito window
- [ ] Submission form completed and submitted
