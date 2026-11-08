/**
 * Shared human wording for registry codes rendered by the chart library and
 * detail pages (NI-034). Status is never conveyed by color or raw code
 * alone: every code from the NI-031/NI-032 registries renders with its
 * recorded meaning (docs/METRIC_CATALOG.md availability codes, CHART_SYSTEM
 * data_status). English only (OQ-06).
 */
import type { MetricResponse } from "../renderer/view-types";

/** METRIC_CATALOG.md: "A saved observed data…; P provider-reported…; B bound…; G gated…". */
export const availabilityWordings: Record<MetricResponse["availability"], { label: string; description: string }> = {
  A: {
    label: "Available",
    description: "Saved observed data, usable after import and rights validation.",
  },
  P: {
    label: "Provider-reported",
    description: "Saved provider-reported data; source-qualified and revisable by the provider.",
  },
  B: {
    label: "Bound or estimate only",
    description: "Shown values are bounds or estimates, never exact amounts.",
  },
  G: {
    label: "Gated",
    description: "Unavailable until the source and definition are verified; missing is never shown as zero.",
  },
};

export const categoryWordings: Record<string, string> = {
  activity: "Activity",
  fees: "Fees",
  treasury: "Treasury",
  supply: "Supply",
  model: "Model",
};

/** The five fixed registry categories in catalog display order. */
export const CATALOG_CATEGORIES = ["activity", "fees", "treasury", "supply", "model"] as const;

export const visualizationWordings: Record<string, string> = {
  line: "Line chart",
  area: "Area chart",
  bar: "Bar chart",
  scatter: "Scatter plot",
  panels: "Aligned panels",
};

export const updateFrequencyWordings: Record<string, string> = {
  daily: "Updated daily",
  weekly: "Updated weekly",
  monthly: "Updated monthly",
  snapshot: "Snapshot periods",
};

export const dataStatusWordings = {
  available: { label: "Available", description: "An approved dataset resolves this chart." },
  unavailable: { label: "Unavailable", description: "This is not zero — no data is rendered." },
} as const;

/** A timestamp or "not recorded" — missing is never fabricated. */
export function recordedOr(value: string | null | undefined, format?: (v: string) => string): string {
  if (value === null || value === undefined || value === "") {
    return "not recorded";
  }
  return format ? format(value) : value;
}
