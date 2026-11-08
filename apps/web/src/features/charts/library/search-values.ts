/**
 * Shared Next.js searchParams helpers for the chart library, chart detail
 * and data-explorer pages (NI-034/NI-015).
 *
 * These helpers only NORMALIZE Next.js' `Record<string, string | string[] |
 * undefined>` shape — every validation decision stays with the approved
 * parameter gates (selection-url.ts for chart selections, the per-page
 * approved lists for catalog routes). Pages pass their approved parameter
 * names and receive honest drop notes for anything else, which they must
 * render (never silently ignore).
 */

/** One honestly rendered "this URL fragment was not used" note. */
export interface DroppedParam {
  param: string;
  reason: string;
}

/** Next.js page searchParams shape. */
export type SearchValues = Record<string, string | string[] | undefined>;

/** Flatten Next.js search values into explicit URL pairs for the parser. */
export function toPairs(values: SearchValues): Array<[string, string]> {
  return Object.entries(values).flatMap(([key, raw]) =>
    raw === undefined
      ? []
      : Array.isArray(raw)
        ? raw.map((value): [string, string] => [key, value])
        : [[key, raw]],
  );
}

/** The single raw value for `key`, or null; arrays keep only their first entry. */
export function firstValue(values: SearchValues, key: string): string | null {
  const raw = values[key];
  if (raw === undefined) {
    return null;
  }
  return Array.isArray(raw) ? (raw[0] ?? null) : raw;
}

/**
 * A parameter usable as a single value: null when absent; when the URL
 * carries conflicting duplicates an honest drop note is recorded and null
 * returned (a duplicate is never resolved by picking one silently).
 */
export function singleValue(values: SearchValues, key: string, dropped: DroppedParam[]): string | null {
  const raw = values[key];
  if (raw === undefined) {
    return null;
  }
  if (Array.isArray(raw)) {
    dropped.push({
      param: key,
      reason: `the URL carries ${raw.length} conflicting values for this parameter; none was used`,
    });
    return null;
  }
  return raw;
}

/**
 * Honest drop notes for every URL parameter outside `approved`. Pages forward
 * only the approved names to any API request; the notes are rendered by the
 * caller ("no arbitrary URL fetch fields").
 */
export function dropUnknownParams(
  values: SearchValues,
  approved: readonly string[],
  reason = "unsupported URL parameter; it was not sent to the chart API",
): DroppedParam[] {
  const known = new Set(approved);
  return Object.keys(values)
    .filter((key) => !known.has(key))
    .map((param) => ({ param, reason }));
}
