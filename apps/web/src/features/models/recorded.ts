/**
 * Verbatim rendering of recorded statistical values (NI-054 page contract).
 *
 * Published model results are exact recorded evidence. Every helper here
 * renders the recorded value as it was served — never re-formatted, never
 * rounded, never converted through a locale formatter:
 *
 * - `recordedFloat` uses the ECMAScript number-to-string conversion, which
 *   is the shortest decimal string that round-trips to the same float64 —
 *   the same conversion the backend's canonical JSON rendering used, so the
 *   page shows the recorded number itself (no toFixed, no Intl rounding).
 * - `recordedJson` pretty-prints the recorded object with an invariant key
 *   order, so a verbatim block (specification/design/estimation/diagnostics/
 *   environment/reproduction) is readable without being rewritten.
 * - Recorded strings (tolerances, timestamps, ids, limit codes) are shown as
 *   they arrived; the page never parses them into numbers.
 */

/** The exact recorded float64 as text, without rounding. */
export function recordedFloat(value: number): string {
  return String(value);
}

/** A recorded object rendered verbatim with stable key order. */
export function recordedJson(value: unknown): string {
  return JSON.stringify(value, replacer, 2) ?? "";
}

/**
 * JSON.stringify replacer that keeps the record readable and honest:
 * finite numbers render through the same conversion as `recordedFloat`,
 * and anything JSON cannot represent is rendered as its inspectable string
 * form instead of being silently dropped (null) or invented.
 */
function replacer(_key: string, value: unknown): unknown {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : String(value);
  }
  if (typeof value === "bigint") {
    return String(value);
  }
  return value;
}

/** Severity in words (OQ-06 English-only UI; codes themselves stay verbatim). */
export function severityWording(severity: "rejecting" | "limit" | "informational"): string {
  switch (severity) {
    case "rejecting":
      return "Rejecting";
    case "limit":
      return "Limit";
    case "informational":
      return "Informational";
  }
}

/** The gate verdict in words, never a bare token without context. */
export function gateVerdictWording(verdict: "READY" | "READY_WITH_LIMITS"): string {
  switch (verdict) {
    case "READY":
      return "Gate verdict: READY (admitted without recorded limits)";
    case "READY_WITH_LIMITS":
      return "Gate verdict: READY WITH LIMITS (admitted with recorded limits)";
  }
}
