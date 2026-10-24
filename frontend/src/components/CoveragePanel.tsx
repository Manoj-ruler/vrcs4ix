import type { Summary } from "../api/types";
import { count, dateTime, pct } from "../lib/format";

export function CoveragePanel({ summary }: { summary: Summary }) {
  const q = summary.quality;
  const rows: [string, string][] = [
    ["Half-hour delivery intervals in January", count(q.expectedIntervals)],
    ["Valid actuals (FUELHH, WIND)", `${count(q.validActualIntervals)} · ${count(q.missingActualIntervals)} missing`],
    ["Forecast hours expected (WINDFOR is hourly)", count(q.expectedForecastIntervals)],
    ["Forecast rows downloaded", `${count(q.forecastRecordsReceived)} from ${count(q.forecastPublications)} publications`],
    ["Hours with an eligible forecast", `${count(q.eligibleForecastsSelected)} · ${count(q.missingEligibleForecasts)} missing`],
    ["Matched forecast–actual pairs", `${count(q.matchedPairs)} (${pct(q.coveragePct, 1)})`],
    ["Invalid / duplicate rows", `${count(q.invalidActualRecords + q.invalidForecastRecords)} / ${count(q.duplicateActualRecords + q.duplicateForecastRecords)}`],
  ];
  return (
    <section className="panel" aria-labelledby="coverage-title">
      <header className="panel-head">
        <div>
          <h2 id="coverage-title">Data coverage</h2>
          <p className="panel-sub">Whole analysis window. Missing values are reported, never filled.</p>
        </div>
      </header>
      <dl className="facts facts-wide">
        {rows.map(([k, v]) => (<div key={k}><dt>{k}</dt><dd className="num">{v}</dd></div>))}
      </dl>
      <p className="meta">
        Source: {summary.dataSource.provider} ({summary.dataSource.mode === "live" ? "fetched live" : summary.dataSource.mode === "cache" ? "cached download" : "bundled snapshot of the API rows"}),{" "}
        {dateTime(summary.dataSource.fetchedAt)}.
      </p>
    </section>
  );
}

export function MethodPanel({ summary }: { summary: Summary }) {
  return (
    <section className="panel" aria-labelledby="method-title">
      <header className="panel-head"><div><h2 id="method-title">How the numbers are made</h2></div></header>
      <ul className="method">
        <li><strong>Which forecast.</strong> {summary.cutoff.description}. This mirrors the GB day-ahead auction gate closure and is a pilot assumption, configurable on the server.</li>
        <li><strong>Matching.</strong> Each hourly forecast is paired with the actual half-hour that starts at the same time. Half-hours starting at :30 have no forecast and are not scored.</li>
        <li><strong>Error.</strong> {summary.conventions.error}.</li>
        <li><strong>MAPE.</strong> {summary.conventions.mape}.</li>
        <li><strong>Scope.</strong> National wind only. This is not a full demand and supply balance: demand, solar, interconnectors and other plant are outside these datasets.</li>
      </ul>
    </section>
  );
}
