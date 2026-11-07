/**
 * Display formatting for the chart renderer (NI-033).
 *
 * Rules (AGENTS.md / ADR-019): decimal strings from the API are the only
 * source of exact values. Formatting is pure string manipulation — grouping
 * separators are inserted, but no digit is ever rounded, reordered or passed
 * through a float. `Number()` conversion for plot coordinates lives only in
 * option-builder.ts and is documented there.
 */

/**
 * Groups the integer part of a canonical decimal string with narrow no-break
 * spaces (U+202F) while preserving every significant digit exactly.
 *
 * - "1234567.890123" -> "1 234 567.890123" (29+ digits survive verbatim)
 * - Non-plain forms (exponent notation, already formatted text) pass through
 *   unchanged rather than being reinterpreted.
 */
export function formatDecimal(value: string): string {
  const trimmed = value.trim();
  if (!/^[+-]?\d+(\.\d+)?$/.test(trimmed)) {
    return trimmed;
  }
  const [intPart, fracPart] = trimmed.split(".");
  const sign = intPart.startsWith("-") ? "-" : "";
  const digits = intPart.replace(/^[+-]/, "");
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, "\u202f");
  return `${sign}${grouped}${fracPart === undefined ? "" : `.${fracPart}`}`;
}

/**
 * The UTC calendar date ("YYYY-MM-DD") of an ISO timestamp. The API
 * guarantees UTC ISO-8601 timestamps; the date is the first ten characters.
 * Anything unexpected is returned as-is (honest passthrough, never
 * reinterpreted into another zone).
 */
export function utcDateLabel(timestamp: string): string {
  return /^\d{4}-\d{2}-\d{2}/.test(timestamp) ? timestamp.slice(0, 10) : timestamp;
}

/**
 * Compact axis-label formatting for plot coordinates. This is the one
 * documented place where float rounding is acceptable: axis tick labels
 * describe scale, not exact values (the table and tooltips carry exact
 * strings). Pure, deterministic, and locale-independent.
 */
export function compactAxisNumber(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) {
    return `${trimFloat(value / 1_000_000_000)}B`;
  }
  if (abs >= 1_000_000) {
    return `${trimFloat(value / 1_000_000)}M`;
  }
  if (abs >= 10_000) {
    return `${trimFloat(value / 1_000)}k`;
  }
  return trimFloat(value);
}

function trimFloat(value: number): string {
  // Drop trailing float noise without comma grouping; scale only.
  return String(Math.round(value * 100) / 100);
}

/** The visible prefix for a bounded value: bounds stay bounds, never exact. */
export function boundPrefix(kind: "exact" | "estimate" | "lower" | "upper" | null): string {
  switch (kind) {
    case "lower":
      return "\u2265"; // ≥
    case "upper":
      return "\u2264"; // ≤
    case "estimate":
      return "\u2248"; // ≈
    default:
      return "";
  }
}
