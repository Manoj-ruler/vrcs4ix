// Shared chart scales: round ticks above the maximum, 4-8 time labels on one step.

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

export function niceTicks(min: number, max: number, target = 5): number[] {
  const lo = Math.min(0, min);
  const hi = Math.max(0, max);
  const span = hi - lo || 1;
  const raw = span / (target - 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * magnitude).find((s) => s >= raw) ?? raw;
  const start = Math.floor(lo / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= hi + step * 0.999; v += step) ticks.push(Math.round(v * 1000) / 1000);
  if ((ticks.at(-1) ?? 0) <= hi) ticks.push((ticks.at(-1) ?? 0) + step);
  return ticks;
}

export function timeTicks(startMs: number, endMs: number): number[] {
  const span = endMs - startMs;
  const steps = [3 * HOUR, 6 * HOUR, 12 * HOUR, DAY, 2 * DAY, 4 * DAY, 5 * DAY, 7 * DAY];
  const step = steps.find((s) => span / s <= 7) ?? 7 * DAY;
  const ticks: number[] = [];
  for (let t = Math.ceil(startMs / step) * step; t <= endMs; t += step) ticks.push(t);
  return ticks;
}

export const COLORS = { ink: "#141414", hue: "#1d5fbf", grey: "#8a8a8a", grid: "#e5e5e5", negative: "#c4242a" };
