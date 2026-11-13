/**
 * NI-071 multi-value analytical filter values (shared by the chart detail,
 * the public data explorer and the editor live-chart block).
 *
 * The server's canonical filter document is a JSON object keyed by an
 * approved dimension; every value is either one approved string (the
 * pre-NI-071 single-selection form, still accepted everywhere for stored
 * compatibility) or a non-empty list of approved strings (the multi-value
 * comparison form). A schema property that declares `multi_value: true`
 * admits the list form; the resolved view fans out into one compared series
 * per selected value with the per-series canonical order coming from the
 * chart's declared enum order, never the request order.
 *
 * Pure module: no React, no DOM, no network.
 */

import type { components } from "@near-intelligence/shared-types";

export type FiltersSelection = components["schemas"]["ChartSelection"]["filters"];
export type FilterValue = FiltersSelection[string];

/**
 * True when this closed-schema property admits a multi-value selection.
 * Only properties the chart definition version explicitly marks
 * `multi_value` accept lists; everything else stays strictly single-value.
 */
export function isMultiValueProperty(property: unknown): boolean {
  return typeof property === "object" && property !== null
    && !Array.isArray(property)
    && (property as Record<string, unknown>)["multi_value"] === true;
}

/** The selected values of one key, normalized to the list form. */
export function asValueList(value: FilterValue | undefined): string[] {
  if (value === undefined) {
    return [];
  }
  return Array.isArray(value) ? value : [value];
}

/**
 * Reorder selected values into the schema's declared enum order (the
 * server's canonical form); unknown entries are dropped by the caller's
 * validation, never here.
 */
export function canonicalValueOrder(selected: string[], options: string[]): string[] {
  const chosen = new Set(selected);
  return options.filter((option) => chosen.has(option));
}

/** Whether two filter documents describe the same canonical selection. */
export function filtersEqual(
  left: FiltersSelection | undefined,
  right: FiltersSelection | undefined,
): boolean {
  return JSON.stringify(canonicalFilters(left ?? {})) === JSON.stringify(canonicalFilters(right ?? {}));
}

/**
 * The canonical comparison form: keys sorted, values as lists in their
 * stored (already canonical) order. Used for equality and stable keys, so
 * `"recipient": "a"` and `"recipient": ["a"]` compare equal — the server
 * canonicalizes both to the same resolved selection.
 */
export function canonicalFilters(filters: FiltersSelection): Array<[string, string[]]> {
  return Object.keys(filters).sort()
    .map((key) => [key, asValueList(filters[key])] as [string, string[]]);
}
