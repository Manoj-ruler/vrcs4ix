import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { HourlyRow } from "../api/types";
import { count, mw, signedMw } from "../lib/format";
import { COLORS, niceTicks } from "./chartUtils";
import { EmptyState } from "./States";

export function HourlyChart({ rows }: { rows: HourlyRow[] }) {
  const data = rows.map((r) => ({ ...r, mae: r.metrics?.mae ?? null, label: `${String(r.hour).padStart(2, "0")}:00` }));
  const values = data.map((d) => d.mae).filter((v): v is number => v != null);
  const ticks = values.length ? niceTicks(0, Math.max(...values)) : [0, 1];
  return (
    <section className="panel">
      <header className="panel-head">
        <div>
          <h2>Error by hour of day</h2>
          <p className="panel-sub">MAE for each delivery hour (UK time), all of January.</p>
        </div>
      </header>
      {values.length === 0 ? <EmptyState>No matched intervals.</EmptyState> : (
        <div className="chart" style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
              <CartesianGrid vertical={false} stroke={COLORS.grid} />
              <XAxis dataKey="label" ticks={["00:00", "06:00", "12:00", "18:00"]} tick={{ fontSize: 12, fill: "#6b6b6b" }} tickLine={false} axisLine={{ stroke: COLORS.ink }} />
              <YAxis ticks={ticks} domain={[0, ticks.at(-1)!]} tickFormatter={(v: number) => mw(v)} tick={{ fontSize: 12, fill: "#6b6b6b" }} tickLine={false} axisLine={false} width={48} />
              <Tooltip cursor={{ fill: "rgba(0,0,0,0.04)" }} content={(props) => {
                const d = props.payload?.[0]?.payload as (typeof data)[number] | undefined;
                if (!props.active || !d) return null;
                return (
                  <div className="tooltip">
                    <strong>{d.label} delivery hour</strong>
                    {d.metrics ? (
                      <dl>
                        <dt>MAE</dt><dd className="num">{mw(d.metrics.mae)} MW</dd>
                        <dt>Bias</dt><dd className="num">{signedMw(d.metrics.bias)} MW</dd>
                        <dt>Days</dt><dd className="num">{count(d.matched)}</dd>
                      </dl>
                    ) : <p>No matched days</p>}
                  </div>
                );
              }} />
              <Bar dataKey="mae" fill={COLORS.ink} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
