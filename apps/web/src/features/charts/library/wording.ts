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

/** Reader-facing delivery errors; the raw diagnostic remains in a disclosure. */
export function chartFailureWording(failure: { status: number; code: string | null }): { title: string; description: string } {
  if (failure.code === "DATA_NOT_READY") {
    return { title: "Data unavailable", description: "No approved dataset is available for this chart yet." };
  }
  if (failure.status === 422) {
    return { title: "Selection unavailable", description: "This chart does not support the selected range or filters. Choose another selection." };
  }
  if (failure.status === 401) {
    return { title: "Sign-in required", description: "Sign in again to access this chart data." };
  }
  if (failure.status === 403) {
    return { title: "Access restricted", description: "You do not have permission to access this chart data." };
  }
  if (failure.status === 404) {
    return { title: "Data not found", description: "The requested chart data could not be found." };
  }
  return { title: "Data unavailable", description: "The chart data could not be loaded. Try again in a moment." };
}
