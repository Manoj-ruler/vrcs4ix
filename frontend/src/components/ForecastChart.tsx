import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Timeseries, TimeseriesPoint } from "../api/types";
import { dateTime, dayLabel, mw, signedMw, time } from "../lib/format";
import { COLORS, niceTicks, timeTicks } from "./chartUtils";
import { EmptyState } from "./States";

interface Row extends TimeseriesPoint {
  t: number;
}

function Tip({ row }: { row: Row }) {
  return (
    <div className="tooltip">
      <strong>{dateTime(row.startTime)}</strong>
      <dl>
        <dt>Forecast</dt><dd className="num">{row.forecast == null ? "none (half-hour)" : `${mw(row.forecast)} MW`}</dd>
        <dt>Actual</dt><dd className="num">{row.actual == null ? "missing" : `${mw(row.actual)} MW`}</dd>
        {row.error != null && (<><dt>Error</dt><dd className="num">{signedMw(row.error)} MW {row.error > 0 ? "over" : row.error < 0 ? "under" : ""}</dd></>)}
        {row.publishTime && (<><dt>Published</dt><dd>{dateTime(row.publishTime)}</dd></>)}
        {row.decisionCutoff && (<><dt>Cutoff</dt><dd>{dateTime(row.decisionCutoff)}</dd></>)}
      </dl>
    </div>
  );
}

export function ForecastChart({
  data, selected, onSelect,
}: { data: Timeseries; selected: string | null; onSelect: (startTime: string) => void }) {
  const rows: Row[] = data.points.map((p) => ({ ...p, t: Date.parse(p.startTime) }));
  const values = rows.flatMap((r) => [r.actual, r.forecast]).filter((v): v is number => v != null);
  if (!values.length) return <EmptyState>No generation data in the selected dates.</EmptyState>;
  const first = rows[0]!.t;
  const last = rows.at(-1)!.t;
  const yTicks = niceTicks(0, Math.max(...values));
  const xTicks = timeTicks(first, last);
  const sameDay = last - first < 86_400_000;

  return (
    <div className="chart" style={{ height: 300 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={rows}
          margin={{ top: 8, right: 12, bottom: 0, left: 4 }}
          onClick={(state) => {
            const index = Number(state?.activeIndex);
            // A :30 half-hour has no forecast; select the forecast hour it belongs to.
            const row = rows[index]?.status === "no_forecast_scheduled" ? rows[index - 1] : rows[index];
            if (row) onSelect(row.startTime);
          }}
        >
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis
            dataKey="t" type="number" scale="time" domain={[first, last]} ticks={xTicks}
            tickFormatter={(t: number) => (sameDay ? time(new Date(t).toISOString()) : dayLabel(new Date(t).toISOString().slice(0, 10)))}
            tick={{ fontSize: 12, fill: "#6b6b6b" }} tickLine={false} axisLine={{ stroke: COLORS.ink }}
          />
          <YAxis
            ticks={yTicks} domain={[yTicks[0]!, yTicks.at(-1)!]} tickFormatter={(v: number) => mw(v)}
            tick={{ fontSize: 12, fill: "#6b6b6b" }} tickLine={false} axisLine={false} width={56}
          />
          <Tooltip
            content={(props) => {
              const row = (props.payload?.[0]?.payload ?? null) as Row | null;
              return props.active && row ? <Tip row={row} /> : null;
            }}
          />
          {selected && <ReferenceLine x={Date.parse(selected)} stroke={COLORS.grey} strokeDasharray="3 3" />}
          <Line type="linear" dataKey="actual" name="Actual" stroke={COLORS.ink} strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Line type="linear" dataKey="forecast" name="Decision-time forecast" stroke={COLORS.hue} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
