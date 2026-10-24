import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { DailyRow } from "../api/types";
import { count, dayLabel, mw, signedMw } from "../lib/format";
import { COLORS, niceTicks } from "./chartUtils";
import { EmptyState } from "./States";

type Metric = "bias" | "mae" | "rmse";
const LABELS: Record<Metric, string> = { bias: "Bias", mae: "MAE", rmse: "RMSE" };

export function DailyErrorChart({ rows, onPickDay }: { rows: DailyRow[]; onPickDay: (date: string) => void }) {
  const [metric, setMetric] = useState<Metric>("bias");
  const data = rows.map((r) => ({ ...r, value: r.metrics ? r.metrics[metric] : null, label: dayLabel(r.date) }));
  const values = data.map((d) => d.value).filter((v): v is number => v != null);
  const worst = [...data].filter((d) => d.metrics).sort((a, b) => b.metrics!.mae - a.metrics!.mae)[0];
  const ticks = values.length ? niceTicks(Math.min(...values), Math.max(...values)) : [0, 1];

  return (
    <section className="panel">
      <header className="panel-head">
        <div>
          <h2>Daily error</h2>
          <p className="panel-sub">
            {metric === "bias" ? "Above zero: forecast higher than actual. Below: lower." : `${LABELS[metric]} per delivery day, MW.`}
            {worst && ` Largest MAE: ${dayLabel(worst.date)} (${mw(worst.metrics!.mae)} MW).`}
          </p>
        </div>
        <div className="segmented" role="group" aria-label="Daily metric">
          {(Object.keys(LABELS) as Metric[]).map((m) => (
            <button key={m} type="button" aria-pressed={metric === m} onClick={() => setMetric(m)}>{LABELS[m]}</button>
          ))}
        </div>
      </header>
      {values.length === 0 ? <EmptyState>No matched intervals on these days.</EmptyState> : (
        <div className="chart" style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}
              onClick={(state) => { const d = data[Number(state?.activeIndex)]; if (d) onPickDay(d.date); }}>
              <CartesianGrid vertical={false} stroke={COLORS.grid} />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#6b6b6b" }} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={24} />
              <YAxis ticks={ticks} domain={[ticks[0]!, ticks.at(-1)!]} tickFormatter={(v: number) => (metric === "bias" ? signedMw(v) : mw(v))}
                tick={{ fontSize: 12, fill: "#6b6b6b" }} tickLine={false} axisLine={false} width={56} />
              <ReferenceLine y={0} stroke={COLORS.ink} />
              <Tooltip cursor={{ fill: "rgba(0,0,0,0.04)" }} content={(props) => {
                const d = props.payload?.[0]?.payload as (typeof data)[number] | undefined;
                if (!props.active || !d) return null;
                return (
                  <div className="tooltip">
                    <strong>{dayLabel(d.date)} 2026</strong>
                    {d.metrics ? (
                      <dl>
                        <dt>MAE</dt><dd className="num">{mw(d.metrics.mae)} MW</dd>
                        <dt>RMSE</dt><dd className="num">{mw(d.metrics.rmse)} MW</dd>
                        <dt>Bias</dt><dd className="num">{signedMw(d.metrics.bias)} MW</dd>
                        <dt>Hours</dt><dd className="num">{count(d.matched)} of {count(d.expectedForecastIntervals)}</dd>
                      </dl>
                    ) : <p>No matched hours</p>}
                    <p className="tooltip-hint">Click to show this day</p>
                  </div>
                );
              }} />
              <Bar dataKey="value" isAnimationActive={false} cursor="pointer">
                {data.map((d) => (
                  <Cell key={d.date} fill={metric === "bias" && (d.value ?? 0) < 0 ? COLORS.grey : COLORS.hue} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {metric === "bias" && <p className="legend"><span className="dot" style={{ background: COLORS.hue }} />Overforecast<span className="dot" style={{ background: COLORS.grey }} />Underforecast</p>}
    </section>
  );
}
