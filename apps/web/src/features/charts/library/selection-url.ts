/**
 * Validated selection URLs for the chart library and chart detail (NI-034).
 *
 * The URL is the only persistence of a chart selection: `version` pins the
 * immutable definition version, `start`/`end` carry the half-open UTC window,
 * `dataset_version` pins a historical dataset and `filters` is a JSON object
 * of chart-version-validated filter values (INFORMATION_ARCHITECTURE.md "Data
 * query parameters"). This module is the single gate between URL and fetch:
 *
 * - Only the approved parameters listed below are ever forwarded to the API.
 *   Anything else is DROPPED with an honest reason that the page renders —
 *   never silently ignored, never forwarded (acceptance: "no arbitrary URL
 *   fetch fields").
 * - `start`/`end` are validated as real ISO calendar dates and against the
 *   definition's bounded `available_ranges` (`max_days`); an unsupported
 *   range falls back to the closest supported preset with the available
 *   presets named — never the nearest silently.
 * - `filters` keys/values are validated against the definition version's
 *   closed `filter_schema` (the NI-031 registry allowlist); offending keys
 *   are dropped individually so the forwarded document only ever contains
 *   approved values. NI-071: a schema property marked `multi_value` also
 *   admits a non-empty JSON array of approved strings (the comparison
 *   form); the stored per-key order is the schema's declared enum order,
 *   never the request order.
 * - Serialization is deterministic (sorted filter keys), so the same
 *   selection always produces the same URL and the same request.
 *
 * Pure module: no React, no DOM, no network. The dates stay strings so the
 * caller controls the "today" anchor (live views anchor presets to the
 * current UTC day; pinned historical views anchor to the dataset coverage —
 * CHART_SYSTEM.md "presets relative to the latest complete observation").
 */
import type { ChartDefinitionResponse } from "../renderer/view-types";

import {
  canonicalValueOrder,
  isMultiValueProperty,
  type FiltersSelection,
} from "../filters/filter-values";

/** The only URL parameters this feature ever reads or forwards to the API. */
export const APPROVED_SELECTION_PARAMS = [
  "version",
  "start",
  "end",
  "dataset_version",
  "filters",
  "frequency",
] as const;

export type ApprovedSelectionParam = (typeof APPROVED_SELECTION_PARAMS)[number];

/** One honestly rendered "this URL fragment was not used" note. */
export interface DroppedParam {
  param: string;
  reason: string;
}

export interface UrlRange {
  start: string;
  end: string;
}

export interface SelectionParse {
  /** Pinned definition version from the URL; null = latest version. */
  version: number | null;
  /** "latest" (or null when absent) or a pinned immutable dataset version id. */
  datasetVersion: string | null;
  /** Explicit range when the URL carried a valid one; null = caller resolves the default. */
  range: UrlRange | null;
  /** Filter values validated against the definition version's closed schema. */
  filters: FiltersSelection;
  dropped: DroppedParam[];
}

export interface SerializedSelection {
  version: number;
  start: string;
  end: string;
  /** "latest" or a pinned dataset version id. */
  datasetVersion: string;
  filters: FiltersSelection;
}

const ISO_DATE_PATTERN = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** Mirrors the delivery contract bounds (apps/api datasets/delivery.py). */
const MAX_FILTER_ENTRIES = 32;
const MAX_FILTER_KEY_LENGTH = 120;
const MAX_FILTER_VALUE_LENGTH = 120;
/** NI-071 per-key multi-value bound (charts/filter_registry.py). */
const MAX_FILTER_VALUES_PER_KEY = 32;

/** True for a real ISO calendar date ("YYYY-MM-DD", calendar-valid, UTC). */
export function isIsoCalendarDate(value: string): boolean {
  if (!ISO_DATE_PATTERN.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime())
    && parsed.toISOString().slice(0, 10) === value;
}

/** Whole UTC days in a half-open [start, end) window. */
export function windowDays(start: string, end: string): number {
  return Math.round((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000);
}

/** Calendar-safe UTC day shift on a "YYYY-MM-DD" string. */
export function shiftIsoDate(isoDate: string, days: number): string {
  const shifted = new Date(`${isoDate}T00:00:00Z`);
  shifted.setUTCDate(shifted.getUTCDate() + days);
  return shifted.toISOString().slice(0, 10);
}

/** Current UTC day as "YYYY-MM-DD" (used only to bootstrap latest coverage). */
export function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * The default range for a chart version: its largest preset anchored to the
 * caller-provided selection end (the latest complete observation context the
 * page resolves — approved dataset coverage end for live and historical
 * views). Explicit URL ranges are never shifted (CHART_SYSTEM.md query/render contract).
 */
export function defaultRangeFor(definition: ChartDefinitionResponse, anchorEnd: string): UrlRange {
  const presets = [...definition.available_ranges.presets_days].sort((a, b) => b - a);
  const days = presets[0] ?? 1;
  return { start: shiftIsoDate(anchorEnd, -days), end: anchorEnd };
}

interface FilterProperty {
  enum?: unknown;
}

function filterProperties(definition: ChartDefinitionResponse): Record<string, FilterProperty> {
  const properties = definition.filter_schema["properties"];
  return typeof properties === "object" && properties !== null && !Array.isArray(properties)
    ? properties as Record<string, FilterProperty>
    : {};
}

/** True when this chart version registers no filters at all. */
export function hasNoFilterDomain(definition: ChartDefinitionResponse): boolean {
  return Object.keys(filterProperties(definition)).length === 0;
}

/**
 * Deterministic preselection for an implicit default view (NI-092): the first
 * approved option of every registered filter dimension. The chart discloses
 * the preselection through its filter chips — providers are never summed; an
 * explicit `filters` URL parameter always wins over these defaults.
 */
export function defaultFiltersFor(definition: ChartDefinitionResponse): FiltersSelection {
  const filters: FiltersSelection = {};
  for (const [key, property] of Object.entries(filterProperties(definition))) {
    const options = Array.isArray(property.enum)
      ? property.enum.filter((value): value is string => typeof value === "string")
      : [];
    if (options.length > 0) filters[key] = options[0];
  }
  return filters;
}

/** True when the selection carries no explicit filter choice. */
export function hasNoExplicitFilters(filters: FiltersSelection): boolean {
  return Object.keys(filters).length === 0;
}

function parseFiltersParam(
  raw: string,
  definition: ChartDefinitionResponse,
  dropped: DroppedParam[],
): FiltersSelection {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw) as unknown;
  } catch {
    dropped.push({
      param: "filters",
      reason: "the filters value must be a JSON object of approved string values; it was not used",
    });
    return {};
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    dropped.push({
      param: "filters",
      reason: "the filters value must be a JSON object of approved string values; it was not used",
    });
    return {};
  }
  const entries = Object.entries(parsed as Record<string, unknown>);
  if (entries.length > MAX_FILTER_ENTRIES) {
    dropped.push({
      param: "filters",
      reason: `the filters object carries more than ${MAX_FILTER_ENTRIES} entries; it was not used`,
    });
    return {};
  }
  const properties = filterProperties(definition);
  const accepted: FiltersSelection = {};
  for (const [key, value] of entries) {
    const property = properties[key];
    if (property === undefined) {
      dropped.push({
        param: `filters.${key}`,
        reason: hasNoFilterDomain(definition)
          ? "this chart version registers no filters, so this value was not used"
          : "this filter is not supported by this chart version; it was not used",
      });
      continue;
    }
    if (key.length > MAX_FILTER_KEY_LENGTH) {
      dropped.push({ param: `filters.${key}`, reason: "filter keys are limited to 120 characters; this value was not used" });
      continue;
    }
    const options = Array.isArray(property.enum) ? property.enum : [];
    // NI-071: one approved string, or (for multi_value dimensions only) a
    // non-empty list of approved strings. Duplicates collapse once and the
    // stored order is the schema's declared enum order, never the request
    // order — the same canonicalization the server applies.
    const rawValues = Array.isArray(value) ? value : [value];
    const invalidEntry = rawValues.some(
      (item) => typeof item !== "string" || item.length === 0 || item.length > MAX_FILTER_VALUE_LENGTH,
    );
    if (invalidEntry || rawValues.length === 0) {
      dropped.push({
        param: `filters.${key}`,
        reason: "filter values must be non-empty strings of at most 120 characters; this value was not used",
      });
      continue;
    }
    if (Array.isArray(value) && !isMultiValueProperty(property)) {
      dropped.push({
        param: `filters.${key}`,
        reason: "this filter accepts one selected value only; the list was not used",
      });
      continue;
    }
    if (rawValues.length > MAX_FILTER_VALUES_PER_KEY) {
      dropped.push({
        param: `filters.${key}`,
        reason: `this filter accepts at most ${MAX_FILTER_VALUES_PER_KEY} selected values; it was not used`,
      });
      continue;
    }
    const unknown = rawValues.filter((item) => !options.includes(item));
    if (unknown.length > 0) {
      dropped.push({
        param: `filters.${key}`,
        reason: `"${unknown.join('", "')}" ${unknown.length === 1 ? "is not an approved option for this filter" : "are not approved options for this filter"}; ${unknown.length === 1 ? "it was" : "they were"} not used`,
      });
      continue;
    }
    if (!Array.isArray(value)) {
      accepted[key] = value as string;
      continue;
    }
    const unique = [...new Set(value as string[])];
    accepted[key] = canonicalValueOrder(unique, options);
  }
  return accepted;
}

/**
 * Parse raw URL search parameters against one loaded chart definition
 * version. Every parameter outside {@link APPROVED_SELECTION_PARAMS} — and
 * every value that fails validation — produces an honest drop note and is
 * never forwarded to the API.
 */
export function parseSelectionUrl(
  searchParams: Iterable<[string, string]> | { keys(): Iterable<string>; get(key: string): string | null },
  definition: ChartDefinitionResponse,
): SelectionParse {
  // Normalize Next.js' ReadonlyURLSearchParams or plain entries into pairs.
  const pairs: Array<[string, string]> = Array.isArray(searchParams) || Symbol.iterator in searchParams
    ? [...(searchParams as Iterable<[string, string]>)]
    : [...(searchParams as { keys(): Iterable<string>; get(key: string): string | null }).keys()]
      .map((key) => [key, searchParams.get(key) ?? ""]);

  const dropped: DroppedParam[] = [];
  const approved = new Set<string>(APPROVED_SELECTION_PARAMS);
  for (const [key] of pairs) {
    if (!approved.has(key)) {
      dropped.push({
        param: key,
        reason: "unsupported URL parameter; it was not sent to the chart API",
      });
    }
  }

  const valueOf = (key: ApprovedSelectionParam): string | null => {
    const raw = pairs.filter(([name]) => name === key).map(([, value]) => value);
    if (raw.length === 0) {
      return null;
    }
    if (raw.length > 1) {
      dropped.push({
        param: key,
        reason: `the URL carries ${raw.length} conflicting values for this parameter; none was used`,
      });
      return null;
    }
    return raw[0];
  };

  // version: pinned immutable definition version.
  let version: number | null = null;
  const rawVersion = valueOf("version");
  if (rawVersion !== null) {
    if (/^[0-9]+$/.test(rawVersion) && Number(rawVersion) >= 1) {
      version = Number(rawVersion);
    } else {
      dropped.push({
        param: "version",
        reason: "the chart version must be a positive integer; the latest registered version is shown instead",
      });
    }
  }

  // dataset_version: "latest" or an immutable dataset version id.
  let datasetVersion: string | null = null;
  const rawDatasetVersion = valueOf("dataset_version");
  if (rawDatasetVersion !== null && rawDatasetVersion !== "latest") {
    if (UUID_PATTERN.test(rawDatasetVersion)) {
      datasetVersion = rawDatasetVersion;
    } else {
      dropped.push({
        param: "dataset_version",
        reason: "dataset_version must be 'latest' or a dataset version id; the latest approved dataset is used instead",
      });
    }
  } else if (rawDatasetVersion === "latest") {
    datasetVersion = "latest";
  }

  // start/end: an explicit half-open window within the version's bound.
  let range: UrlRange | null = null;
  const rawStart = valueOf("start");
  const rawEnd = valueOf("end");
  if (rawStart !== null || rawEnd !== null) {
    if (rawStart === null || rawEnd === null) {
      dropped.push({
        param: "start",
        reason: "a custom range needs both start and end dates; the default range is shown instead",
      });
      dropped.push({
        param: "end",
        reason: "a custom range needs both start and end dates; the default range is shown instead",
      });
    } else if (!isIsoCalendarDate(rawStart) || !isIsoCalendarDate(rawEnd)) {
      dropped.push({
        param: "start",
        reason: "range dates must be ISO calendar dates (YYYY-MM-DD); the default range is shown instead",
      });
      dropped.push({
        param: "end",
        reason: "range dates must be ISO calendar dates (YYYY-MM-DD); the default range is shown instead",
      });
    } else {
      const days = windowDays(rawStart, rawEnd);
      const maxDays = definition.available_ranges.max_days;
      if (days < 1) {
        dropped.push({
          param: "start",
          reason: "the selection window must be non-empty (end after start); the default range is shown instead",
        });
        dropped.push({
          param: "end",
          reason: "the selection window must be non-empty (end after start); the default range is shown instead",
        });
      } else if (days > maxDays) {
        const presets = [...definition.available_ranges.presets_days].sort((a, b) => a - b);
        dropped.push({
          param: "start",
          reason: `the requested range covers ${days} days, but this chart version allows at most ${maxDays}; `
            + `the closest supported preset (${presets.at(-1)} days) is shown instead`,
        });
        dropped.push({
          param: "end",
          reason: `the requested range covers ${days} days, but this chart version allows at most ${maxDays}; `
            + `the closest supported preset (${presets.at(-1)} days) is shown instead`,
        });
      } else {
        range = { start: rawStart, end: rawEnd };
      }
    }
  }

  // filters: a JSON object validated against the closed schema.
  let filters: FiltersSelection = {};
  const rawFilters = valueOf("filters");
  if (rawFilters !== null && rawFilters !== "") {
    filters = parseFiltersParam(rawFilters, definition, dropped);
  }

  // frequency: only "day" is supported; anything else is dropped, and the
  // server default (day) is never overridden.
  const rawFrequency = valueOf("frequency");
  if (rawFrequency !== null && rawFrequency !== "day") {
    dropped.push({
      param: "frequency",
      reason: "only the daily frequency is supported in this release; the chart uses daily observations",
    });
  }

  return { version, datasetVersion, range, filters, dropped };
}

/**
 * Sorted-key canonical JSON filter document (the server's accepted wire
 * form): one approved string per single selected value (a one-element list
 * serializes as the bare string, the same convention the server's context
 * hash uses) and the exact list for a genuine multi-value selection.
 * Deterministic, so the same selection always produces the same URL and the
 * same request.
 */
export function serializeFilters(filters: FiltersSelection): string | null {
  const keys = Object.keys(filters).sort();
  if (keys.length === 0) {
    return null;
  }
  return JSON.stringify(Object.fromEntries(keys.map((key) => {
    const value = filters[key];
    return [key, Array.isArray(value) && value.length === 1 ? value[0] : value];
  })));
}

/**
 * Deterministic query string for the chart detail URL. Always pins the
 * definition version; pins the dataset version only when historical; carries
 * validated filters only. This is what range/filter changes write with
 * replace-state and what the sign-in continuation preserves.
 */
export function serializeSelectionQuery(selection: SerializedSelection): string {
  const params = new URLSearchParams();
  params.set("version", String(selection.version));
  params.set("start", selection.start);
  params.set("end", selection.end);
  if (selection.datasetVersion !== "latest") {
    params.set("dataset_version", selection.datasetVersion);
  }
  const filters = serializeFilters(selection.filters);
  if (filters !== null) {
    params.set("filters", filters);
  }
  return params.toString();
}

/**
 * The internal detail URL for a resolved selection under any detail route
 * base (`"/charts"`, `"/data/<category>"`, …). The base only decides where
 * the chart detail is mounted; the serialized selection is identical, so the
 * same selection always produces the same request regardless of route
 * (NI-015 reuses this for the public data explorer).
 */
export function detailHrefFor(base: string, chartId: string, selection: SerializedSelection): string {
  return `${base}/${encodeURIComponent(chartId)}?${serializeSelectionQuery(selection)}`;
}

/** The internal /charts detail URL for a resolved selection (continuation payload). */
export function chartDetailHref(chartId: string, selection: SerializedSelection): string {
  return detailHrefFor("/charts", chartId, selection);
}
