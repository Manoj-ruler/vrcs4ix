import { useState } from "react";

import { api } from "./api/client";
import type { DateRange, RecordQuery, Summary } from "./api/types";
import { CoveragePanel, MethodPanel } from "./components/CoveragePanel";
import { DailyErrorChart } from "./components/DailyErrorChart";
import { ForecastChart } from "./components/ForecastChart";
import { HourlyChart } from "./components/HourlyChart";
import { IntervalPanel } from "./components/IntervalPanel";
import { KpiStrip } from "./components/KpiStrip";
import { RecordsTable } from "./components/RecordsTable";
import { EmptyState, ErrorState, Loadable, Skeleton } from "./components/States";
import { COLORS } from "./components/chartUtils";
import { count, dayLabel, isValidRange, mw } from "./lib/format";
import { useApi } from "./lib/useApi";

// The analysis window is fixed by the brief; the API rejects anything outside it.
const WINDOW: DateRange = { startDate: "2026-01-01", endDate: "2026-01-31" };

function finding(s: Summary): string {
  const m = s.metrics;
  if (!m) return s.emptyReason ?? "No matched data in the selected dates.";
  const side = m.bias >= 0 ? "above" : "below";
  return `The forecast available at the ${s.cutoff.localTime} cutoff ran ${mw(Math.abs(m.bias))} MW ${side} actual wind on average, `
    + `and was too high in ${count(m.nOverforecast)} of ${count(m.n)} hours. Plan for misses of up to ${mw(m.p90AbsoluteError)} MW in 9 hours out of 10.`;
}

export default function App() {
  const [range, setRange] = useState<DateRange>(WINDOW);
  const [draft, setDraft] = useState<DateRange>(WINDOW);
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState<Omit<RecordQuery, keyof DateRange>>({
    sort: "startTime", order: "asc", status: "any", page: 1, pageSize: 15,
  });
  const rangeKey = `${range.startDate}/${range.endDate}`;
  const recordQuery: RecordQuery = { ...range, ...query };

  const [summary, retrySummary] = useApi((s) => api.summary(range, s), rangeKey);
  const [series, retrySeries] = useApi((s) => api.timeseries(range, s), rangeKey);
  const [daily, retryDaily] = useApi((s) => api.daily(range, s), rangeKey);
  const [hourly, retryHourly] = useApi((s) => api.hourly(s), "hourly");
  const [records, retryRecords] = useApi((s) => api.records(recordQuery, s), JSON.stringify(recordQuery));
  const [detail, retryDetail] = useApi(
    (s) => (selected ? api.interval(selected, s) : Promise.resolve(null)), selected ?? "none",
  );

  const draftError = isValidRange(draft.startDate, draft.endDate, WINDOW.startDate, WINDOW.endDate);
  const apply = (next: DateRange) => {
    setRange(next);
    setDraft(next);
    setQuery((q) => ({ ...q, page: 1 }));
  };
  const isWholeWindow = range.startDate === WINDOW.startDate && range.endDate === WINDOW.endDate;

  return (
    <div className="app">
      <header className="topbar">
        <span className="wordmark">Wind Forecast Desk</span>
        <span className="scope">GB national wind · Elexon BMRS · day-ahead purchasing</span>
      </header>

      <main className="canvas">
        <div className="title-row">
          <h1>January 2026 wind forecast accuracy</h1>
          <p className="finding">{summary.status === "ready" ? finding(summary.data) : summary.status === "loading" ? "Loading the January analysis…" : "The analysis could not be loaded."}</p>
        </div>

        <form className="filters" onSubmit={(e) => { e.preventDefault(); if (!draftError) apply(draft); }}>
          <label className="field">
            <span>From</span>
            <input type="date" value={draft.startDate} min={WINDOW.startDate} max={WINDOW.endDate}
              onChange={(e) => setDraft({ ...draft, startDate: e.target.value })} aria-invalid={Boolean(draftError)} />
          </label>
          <label className="field">
            <span>To</span>
            <input type="date" value={draft.endDate} min={WINDOW.startDate} max={WINDOW.endDate}
              onChange={(e) => setDraft({ ...draft, endDate: e.target.value })} aria-invalid={Boolean(draftError)} />
          </label>
          <button type="submit" className="btn btn-primary" disabled={Boolean(draftError)}>Show dates</button>
          {!isWholeWindow && <button type="button" className="btn-link" onClick={() => apply(WINDOW)}>Whole of January</button>}
          <span className="filter-note">Delivery dates, UK time. Hour-of-day and coverage always use all of January.</span>
          {draftError && <p className="field-error" role="alert">{draftError}</p>}
        </form>

        {summary.status === "ready" && summary.data.selection.matched < summary.data.selection.expectedForecastIntervals && (
          <p className="notice" role="status">
            Partial coverage: {count(summary.data.selection.matched)} of {count(summary.data.selection.expectedForecastIntervals)} forecast
            hours in these dates have both an actual and an eligible forecast. Metrics use matched hours only.
          </p>
        )}

        <Loadable state={summary} onRetry={retrySummary} height={108}>{(s) => <KpiStrip summary={s} />}</Loadable>

        <section className="panel" aria-labelledby="series-title">
          <header className="panel-head">
            <div>
              <h2 id="series-title">Forecast at decision time vs actual</h2>
              <p className="panel-sub">
                {isWholeWindow ? "1–31 January" : `${dayLabel(range.startDate)} – ${dayLabel(range.endDate)}`}, MW. Hover for the publication time; click to inspect an hour.
              </p>
            </div>
            <p className="legend">
              <span className="dot" style={{ background: COLORS.hue }} />Forecast used for the purchase
              <span className="dot" style={{ background: COLORS.ink }} />Actual (half-hourly)
            </p>
          </header>
          <Loadable state={series} onRetry={retrySeries} height={300}>
            {(t) => <ForecastChart data={t} selected={selected} onSelect={setSelected} />}
          </Loadable>
        </section>

        <div className="grid-2-1">
          <Loadable state={daily} onRetry={retryDaily} height={300}>
            {(d) => <DailyErrorChart rows={d} onPickDay={(date) => apply({ startDate: date, endDate: date })} />}
          </Loadable>
          <Loadable state={hourly} onRetry={retryHourly} height={300}>{(h) => <HourlyChart rows={h} />}</Loadable>
        </div>

        <div className="grid-2-1 align-start">
          <Loadable state={records} onRetry={retryRecords} height={480}>
            {(p) => (
              <RecordsTable page={p} query={recordQuery} selected={selected} onSelect={setSelected}
                onQuery={(patch) => setQuery((q) => ({ ...q, ...patch }))}
                csvHref={api.csvUrl({ ...range, sort: query.sort, order: query.order, status: query.status })} />
            )}
          </Loadable>
          <section className="panel sticky" aria-labelledby="interval-title">
            <header className="panel-head"><div><h2 id="interval-title">Selected hour</h2></div></header>
            {!selected ? <EmptyState>Select an hour in the chart or the table to see every forecast version and which one the cutoff allowed.</EmptyState>
              : detail.status === "loading" ? <Skeleton height={240} />
              : detail.status === "error" ? <ErrorState message={detail.message} onRetry={retryDetail} />
              : detail.data && <IntervalPanel detail={detail.data} />}
          </section>
        </div>

        <div className="grid-1-1">
          <Loadable state={summary} onRetry={retrySummary}>{(s) => <CoveragePanel summary={s} />}</Loadable>
          <Loadable state={summary} onRetry={retrySummary}>{(s) => <MethodPanel summary={s} />}</Loadable>
        </div>
      </main>
    </div>
  );
}
