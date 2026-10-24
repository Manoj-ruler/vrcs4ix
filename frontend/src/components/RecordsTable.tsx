import type { IntervalRecord, IntervalStatus, RecordPage, RecordQuery, SortField, StatusFilter } from "../api/types";
import { count, dateTime, hours, mw, signedMw } from "../lib/format";
import { EmptyState } from "./States";

const STATUS_TEXT: Record<IntervalStatus, string> = {
  matched: "Matched",
  missing_actual: "No actual",
  missing_forecast: "No eligible forecast",
  missing_both: "No data",
  no_forecast_scheduled: "Half-hour",
};

const COLUMNS: { key: SortField | null; label: string; numeric: boolean }[] = [
  { key: "startTime", label: "Delivery (UK)", numeric: false },
  { key: "forecastGeneration", label: "Forecast MW", numeric: true },
  { key: "actualGeneration", label: "Actual MW", numeric: true },
  { key: "forecastError", label: "Error MW", numeric: true },
  { key: "absoluteError", label: "Abs. error MW", numeric: true },
  { key: null, label: "Forecast published", numeric: false },
  { key: null, label: "Lead", numeric: true },
  { key: null, label: "Status", numeric: false },
];

interface Props {
  page: RecordPage;
  query: RecordQuery;
  onQuery: (patch: Partial<RecordQuery>) => void;
  selected: string | null;
  onSelect: (startTime: string) => void;
  csvHref: string;
}

export function RecordsTable({ page, query, onQuery, selected, onSelect, csvHref }: Props) {
  const toggleSort = (key: SortField) =>
    onQuery(query.sort === key
      ? { order: query.order === "asc" ? "desc" : "asc", page: 1 }
      : { sort: key, order: key === "startTime" ? "asc" : "desc", page: 1 });

  return (
    <section className="panel" aria-labelledby="records-title">
      <header className="panel-head">
        <div>
          <h2 id="records-title">Hourly records</h2>
          <p className="panel-sub">{count(page.total)} forecast hours in the selected dates. Select a row to see why its forecast was chosen.</p>
        </div>
        <div className="controls">
          <label className="field-inline">
            <span>Show</span>
            <select value={query.status} onChange={(e) => onQuery({ status: e.target.value as StatusFilter, page: 1 })}>
              <option value="any">All hours</option>
              <option value="matched">Matched only</option>
              <option value="missing">Missing data only</option>
            </select>
          </label>
          <a className="btn btn-secondary" href={csvHref} download>Export CSV</a>
        </div>
      </header>
      {page.items.length === 0 ? <EmptyState>No hours match this filter.</EmptyState> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {COLUMNS.map((c) => (
                  <th key={c.label} className={c.numeric ? "num" : undefined}
                    aria-sort={c.key && query.sort === c.key ? (query.order === "asc" ? "ascending" : "descending") : undefined}>
                    {c.key ? (
                      <button type="button" className="th-sort" onClick={() => toggleSort(c.key!)}>
                        {c.label}{query.sort === c.key ? (query.order === "asc" ? " ↑" : " ↓") : ""}
                      </button>
                    ) : c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.items.map((r) => <Row key={r.startTime} r={r} selected={selected === r.startTime} onSelect={onSelect} />)}
            </tbody>
          </table>
        </div>
      )}
      <footer className="pager">
        <span>Page {page.page} of {page.totalPages}</span>
        <button type="button" className="btn btn-secondary" disabled={page.page <= 1} onClick={() => onQuery({ page: page.page - 1 })}>Previous</button>
        <button type="button" className="btn btn-secondary" disabled={page.page >= page.totalPages} onClick={() => onQuery({ page: page.page + 1 })}>Next</button>
      </footer>
    </section>
  );
}

function Row({ r, selected, onSelect }: { r: IntervalRecord; selected: boolean; onSelect: (s: string) => void }) {
  const over = (r.forecastError ?? 0) > 0;
  return (
    <tr className={selected ? "selected" : undefined} onClick={() => onSelect(r.startTime)}
      tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(r.startTime); } }}
      aria-selected={selected}>
      <td>{dateTime(r.startTime)}</td>
      <td className="num">{mw(r.forecastGeneration)}</td>
      <td className="num">{mw(r.actualGeneration)}</td>
      <td className="num">{r.forecastError == null ? "–" : <>{signedMw(r.forecastError)} <span className="muted">{over ? "over" : r.forecastError < 0 ? "under" : ""}</span></>}</td>
      <td className="num">{mw(r.absoluteError)}</td>
      <td>{dateTime(r.publishTime)}</td>
      <td className="num">{hours(r.horizonHours)}</td>
      <td><span className={`pill pill-${r.status === "matched" ? "neutral" : "warning"}`}>{STATUS_TEXT[r.status]}</span></td>
    </tr>
  );
}
