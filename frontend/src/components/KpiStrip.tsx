import type { Summary } from "../api/types";
import { count, mw, pct, signedMw } from "../lib/format";
import { EmptyState } from "./States";

export function KpiStrip({ summary }: { summary: Summary }) {
  const m = summary.metrics;
  const sel = summary.selection;
  if (!m) return <EmptyState>{summary.emptyReason}</EmptyState>;
  const coverage = sel.expectedForecastIntervals ? (sel.matched / sel.expectedForecastIntervals) * 100 : null;
  return (
    <section className="panel kpis" aria-label="Accuracy metrics">
      <div className="kpi kpi-lead">
        <span className="kpi-label">Mean absolute error</span>
        <span className="kpi-value num">{mw(m.mae)}<small> MW</small></span>
        <span className="kpi-note">typical miss per hour, either direction</span>
      </div>
      <div className="kpi">
        <span className="kpi-label">RMSE</span>
        <span className="kpi-value num">{mw(m.rmse)}<small> MW</small></span>
        <span className="kpi-note">weights large misses more</span>
      </div>
      <div className="kpi">
        <span className="kpi-label">Bias (forecast − actual)</span>
        <span className="kpi-value num">{signedMw(m.bias)}<small> MW</small></span>
        <span className="kpi-note">over in {count(m.nOverforecast)} of {count(m.n)} hours</span>
      </div>
      <div className="kpi">
        <span className="kpi-label">90th percentile miss</span>
        <span className="kpi-value num">{mw(m.p90AbsoluteError)}<small> MW</small></span>
        <span className="kpi-note">9 in 10 hours missed by less</span>
      </div>
      <div className="kpi">
        <span className="kpi-label">MAPE</span>
        <span className="kpi-value num">{pct(m.mape)}</span>
        <span className="kpi-note">over {count(m.nMape)} hours with non-zero actual</span>
      </div>
      <div className="kpi">
        <span className="kpi-label">Coverage</span>
        <span className="kpi-value num">{pct(coverage, 0)}</span>
        <span className="kpi-note">{count(sel.matched)} of {count(sel.expectedForecastIntervals)} forecast hours matched</span>
      </div>
    </section>
  );
}
