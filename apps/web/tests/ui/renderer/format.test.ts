/**
 * Formatter tests for the NI-033 chart renderer.
 *
 * The critical rule (ADR-014/ADR-019): decimal strings are formatted as pure
 * strings — grouping separators only, never a float round-trip — so 29+
 * significant digits survive display verbatim.
 */
import { describe, expect, it } from "vitest";

import { boundPrefix, compactAxisNumber, formatDecimal, utcDateLabel } from "@/features/charts/renderer/format";
import { HUGE_DECIMAL } from "./fixtures";

describe("formatDecimal — exact decimal strings", () => {
  it("preserves 29+ significant digits exactly (no float conversion)", () => {
    const huge = "12345678901234567890123456789"; // 29 digits
    const formatted = formatDecimal(huge);
    expect(formatted.replace(/[\u202f]/g, "")).toBe(huge);
    expect(formatted).toContain("\u202f"); // grouped for readability
    // The Number() coordinate path would collapse these digits; the display
    // path must never agree with it.
    expect(formatted).not.toBe(String(Number(huge)));
  });

  it("formats the 31-digit fixture value with fraction intact", () => {
    const formatted = formatDecimal(HUGE_DECIMAL);
    expect(formatted.replace(/[\u202f]/g, "")).toBe(HUGE_DECIMAL);
    expect(formatted.endsWith(".5")).toBe(true);
  });

  it("keeps very small decimals verbatim", () => {
    const tiny = "0.000000000000000000000000000001";
    expect(formatDecimal(tiny)).toBe(tiny);
  });

  it("groups the integer part only, keeps negatives", () => {
    expect(formatDecimal("1234567.890123")).toBe("1\u202f234\u202f567.890123");
    expect(formatDecimal("-1234.5")).toBe("-1\u202f234.5");
    expect(formatDecimal("0")).toBe("0");
    expect(formatDecimal("42")).toBe("42");
  });

  it("passes non-plain forms through unchanged instead of reinterpreting", () => {
    expect(formatDecimal("1e5")).toBe("1e5");
    expect(formatDecimal("")).toBe("");
    expect(formatDecimal("not a number")).toBe("not a number");
  });
});

describe("utcDateLabel", () => {
  it("extracts the UTC calendar date from an API timestamp", () => {
    expect(utcDateLabel("2026-11-01T00:00:00Z")).toBe("2026-11-01");
    expect(utcDateLabel("2026-02-28T23:59:59Z")).toBe("2026-02-28");
  });

  it("passes unexpected input through honestly", () => {
    expect(utcDateLabel("unknown")).toBe("unknown");
  });
});

describe("compactAxisNumber — axis scale only, never exact values", () => {
  it("compresses large magnitudes with a scale suffix", () => {
    expect(compactAxisNumber(1500)).toBe("1500");
    expect(compactAxisNumber(12_345)).toBe("12.35k");
    expect(compactAxisNumber(2_500_000)).toBe("2.5M");
    expect(compactAxisNumber(3_400_000_000)).toBe("3.4B");
  });

  it("handles the non-finite coordinate defensively", () => {
    expect(compactAxisNumber(Number.NaN)).toBe("—");
  });
});

describe("boundPrefix — bounds stay bounds, never exact", () => {
  it("maps bound kinds to visible prefixes", () => {
    expect(boundPrefix("lower")).toBe("\u2265");
    expect(boundPrefix("upper")).toBe("\u2264");
    expect(boundPrefix("estimate")).toBe("\u2248");
    expect(boundPrefix("exact")).toBe("");
    expect(boundPrefix(null)).toBe("");
  });
});
