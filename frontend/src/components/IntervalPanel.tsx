import type { IntervalDetail } from "../api/types";
import { dateTime, hours, mw, signedMw, time } from "../lib/format";
import { COLORS } from "./chartUtils";

/** Publication strip: every forecast version for this hour on one time axis, with the decision cutoff. */
function PublicationStrip({ detail }: { detail: IntervalDetail }) {
  const { record, candidates } = detail;
  if (!candidates.length || !record.decisionCutoff) return null;
  const delivery = Date.parse(record.startTime);
  const cutoff = Date.parse(record.decisionCutoff);
  const times = candidates.map((c) => Date.parse(c.publishTime));
  const start = Math.min(...times, cutoff);
  const end = Math.max(delivery, ...times);
  const W = 320, H = 64, pad = 8;
  const x = (t: number) => pad + ((t - start) / (end - start || 1)) * (W - 2 * pad);
  return (
    <figure className="strip">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`${candidates.length} forecast versions; ${candidates.filter((c) => c.eligible).length} published before the cutoff`}>
        <line x1={pad} x2={W - pad} y1={36} y2={36} stroke={COLORS.grid} strokeWidth={2} />
        <line x1={x(cutoff)} x2={x(cutoff)} y1={12} y2={52} stroke={COLORS.ink} strokeDasharray="3 2" />
        <text x={x(cutoff)} y={9} fontSize={11} textAnchor="middle" fill={COLORS.ink}>Cutoff {time(record.decisionCutoff)}</text>
        <line x1={x(delivery)} x2={x(delivery)} y1={24} y2={48} stroke={COLORS.grey} />
        <text x={Math.min(x(delivery), W - pad)} y={62} fontSize={11} textAnchor="end" fill="#6b6b6b">Delivery</text>
        {candidates.map((c) => {
          const cx = x(Date.parse(c.publishTime));
          return c.selected
            ? <circle key={c.publishTime} cx={cx} cy={36} r={5} fill={COLORS.hue} />
            : <circle key={c.publishTime} cx={cx} cy={36} r={3} fill={c.eligible ? COLORS.ink : "#fff"} stroke={c.eligible ? COLORS.ink : COLORS.grey} />;
        })}
      </svg>
      <figcaption>
        <span className="dot" style={{ background: COLORS.hue }} />Selected
        <span className="dot" style={{ background: COLORS.ink }} />Before cutoff
        <span className="dot dot-hollow" />After cutoff (not used)
      </figcaption>
    </figure>
  );
}

export function IntervalPanel({ detail }: { detail: IntervalDetail }) {
  const r = detail.record;
  return (
    <div className="interval">
      <h3>{dateTime(r.startTime)}</h3>
      <dl className="facts">
        <dt>Decision-time forecast</dt><dd className="num">{mw(r.forecastGeneration)} MW</dd>
        <dt>Actual generation</dt><dd className="num">{mw(r.actualGeneration)} MW</dd>
        <dt>Error (forecast − actual)</dt><dd className="num">{signedMw(r.forecastError)} MW</dd>
        <dt>Published</dt><dd>{dateTime(r.publishTime)}</dd>
        <dt>Decision cutoff</dt><dd>{dateTime(r.decisionCutoff)}</dd>
        <dt>Lead time</dt><dd className="num">{hours(r.horizonHours)}</dd>
      </dl>
      <p className="explain">{detail.explanation}</p>
      <PublicationStrip detail={detail} />
      {detail.candidates.length > 0 && (
        <details>
          <summary>All {detail.candidates.length} forecast versions for this hour</summary>
          <table className="compact">
            <thead><tr><th>Published</th><th className="num">MW</th><th>Used?</th></tr></thead>
            <tbody>
              {detail.candidates.map((c) => (
                <tr key={c.publishTime} className={c.selected ? "selected" : undefined}>
                  <td>{dateTime(c.publishTime)}</td>
                  <td className="num">{mw(c.generation)}</td>
                  <td>{c.selected ? "Selected" : c.eligible ? "Older" : "After cutoff"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}
