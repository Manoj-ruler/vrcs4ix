import { describe, expect, it } from "vitest";

import { buildUrl } from "../api/client";
import { dateTime, direction, isValidRange, mw, pct, signedMw } from "./format";

describe("format", () => {
  it("formats MW with separators and a dash for missing values", () => {
    expect(mw(12345.6)).toBe("12,346");
    expect(mw(null)).toBe("–");
  });

  it("signs errors so overforecast reads positive", () => {
    expect(signedMw(1839.9)).toBe("+1,840");
    expect(signedMw(-3967)).toBe("−3,967");
    expect(signedMw(0.2)).toBe("0");
  });

  it("formats percentages and the error direction", () => {
    expect(pct(21.877)).toBe("21.9%");
    expect(pct(null)).toBe("–");
    expect(direction(5)).toBe("over");
    expect(direction(-5)).toBe("under");
    expect(direction(null)).toBeNull();
  });

  it("shows UK local time", () => {
    expect(dateTime("2026-01-01T00:00:00Z")).toBe("Thu 1 Jan, 00:00");
    expect(dateTime("2026-07-01T00:00:00Z")).toBe("Wed 1 Jul, 01:00");
  });

  it("validates date ranges inside the analysis window", () => {
    expect(isValidRange("2026-01-02", "2026-01-05", "2026-01-01", "2026-01-31")).toBeNull();
    expect(isValidRange("2026-01-05", "2026-01-02", "2026-01-01", "2026-01-31")).toMatch(/on or before/);
    expect(isValidRange("2025-12-31", "2026-01-02", "2026-01-01", "2026-01-31")).toMatch(/between/);
    expect(isValidRange("", "2026-01-02", "2026-01-01", "2026-01-31")).toMatch(/both/);
  });
});

describe("api client", () => {
  it("builds query strings against the configured base", () => {
    expect(buildUrl("/api/analysis/summary", { startDate: "2026-01-01", page: 2 }, "https://x.test"))
      .toBe("https://x.test/api/analysis/summary?startDate=2026-01-01&page=2");
    expect(buildUrl("/api/health", {}, "")).toBe("/api/health");
  });
});
