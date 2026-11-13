import type { components } from "@near-intelligence/shared-types";
import { canonicalFilters } from "../filters/filter-values";
import type { ChartViewResponse } from "./view-types";
import type { ChartSelection } from "./ChartView";

export function inspectionKey(definitionId: string, selection: ChartSelection, datasetId: string) {
  // NI-071: the filter document compares in its canonical form (sorted keys,
  // list values), so `"k": "v"` and `"k": ["v"]` are the same inspected
  // selection — the server canonicalizes both identically.
  return JSON.stringify([definitionId, selection.start, selection.end, canonicalFilters(selection.filters ?? {}), datasetId]);
}

export function chartObservation(view: ChartViewResponse): components["schemas"]["ResolvedContext"] {
  return {
    chart_definition_version_id: view.definition.id,
    dataset_version_id: view.dataset.id,
    selection: view.selection,
    context_hash: view.context_hash,
    renderer_version: view.definition.renderer_version,
    metric_definition_versions: view.definition.metric_definition_ids,
    resolved_at: view.resolved_at,
  };
}
