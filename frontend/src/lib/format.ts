// Display formatting only. All figures arrive computed from the API; nothing here derives a metric.

const LONDON = "Europe/London";
const mwFormat = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

export const DASH = "–";

export function mw(value: number | null | undefined): string {
  return value == null ? DASH : mwFormat.format(Math.round(value));
}

export function signedMw(value: number | null | undefined): string {
  if (value == null) return DASH;
  const rounded = Math.round(value);
  if (rounded === 0) return "0";
  return `${rounded > 0 ? "+" : "−"}${mwFormat.format(Math.abs(rounded))}`;
}

export function pct(value: number | null | undefined, digits = 1): string {
  return value == null ? DASH : `${value.toFixed(digits)}%`;
}

export function count(value: number): string {
  return mwFormat.format(value);
}

/** "Thu 1 Jan, 00:00" in UK time (GMT throughout January). */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: LONDON, weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));
}

export function time(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: LONDON, hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

export function dayLabel(isoDate: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", day: "numeric", month: "short" }).format(new Date(`${isoDate}T00:00:00Z`));
}

export function hours(value: number | null): string {
  return value == null ? DASH : `${value.toFixed(1)} h`;
}

export function direction(error: number | null): "over" | "under" | "exact" | null {
  if (error == null) return null;
  return error > 0 ? "over" : error < 0 ? "under" : "exact";
}

export function isValidRange(start: string, end: string, min: string, max: string): string | null {
  if (!start || !end) return "Choose both a start and an end date.";
  if (start > end) return "The start date must be on or before the end date.";
  if (start < min || end > max) return `Dates must fall between ${dayLabel(min)} and ${dayLabel(max)} 2026.`;
  return null;
}
