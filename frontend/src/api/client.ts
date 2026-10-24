import type {
  DailyRow, DateRange, HourlyRow, IntervalDetail, RecordPage, RecordQuery, Summary, Timeseries,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

type Params = Record<string, string | number>;

export function buildUrl(path: string, params: Params = {}, base = BASE): string {
  const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
  return `${base}${path}${query ? `?${query}` : ""}`;
}

async function get<T>(path: string, params?: Params, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), { signal: signal ?? null, headers: { Accept: "application/json" } });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError("The analysis service could not be reached.", 0);
  }
  if (!response.ok) {
    let detail = response.status >= 500
      ? `The analysis service is unavailable (HTTP ${response.status}). Please try again shortly.`
      : `Request failed (HTTP ${response.status}).`;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body: keep the generic message */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

const range = (r: DateRange): Params => ({ startDate: r.startDate, endDate: r.endDate });

export const api = {
  summary: (r: DateRange, signal?: AbortSignal) => get<Summary>("/api/analysis/summary", range(r), signal),
  timeseries: (r: DateRange, signal?: AbortSignal) => get<Timeseries>("/api/analysis/timeseries", range(r), signal),
  daily: (r: DateRange, signal?: AbortSignal) => get<DailyRow[]>("/api/analysis/daily", range(r), signal),
  hourly: (signal?: AbortSignal) => get<HourlyRow[]>("/api/analysis/hourly", {}, signal),
  records: (q: RecordQuery, signal?: AbortSignal) =>
    get<RecordPage>("/api/analysis/records", { ...q, scope: "forecast" }, signal),
  interval: (startTime: string, signal?: AbortSignal) =>
    get<IntervalDetail>("/api/analysis/interval", { startTime }, signal),
  csvUrl: (q: Omit<RecordQuery, "page" | "pageSize">) =>
    buildUrl("/api/analysis/records.csv", { ...q, scope: "forecast" }),
};
