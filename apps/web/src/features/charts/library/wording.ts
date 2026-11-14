/**
 * Shared human wording for registry codes rendered by the chart library and
 * detail pages (NI-034). Status is never conveyed by color or raw code
 * alone: every code from the NI-031/NI-032 registries renders with its
 * recorded meaning (docs/METRIC_CATALOG.md availability codes, CHART_SYSTEM
 * data_status). English only (OQ-06).
 */
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
