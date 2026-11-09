import type { components } from "@near-intelligence/shared-types";
import type { ChartViewResponse } from "./view-types";
import type { ChartSelection } from "./ChartView";

export function inspectionKey(definitionId: string, selection: ChartSelection, datasetId: string) {
  return JSON.stringify([definitionId, selection.start, selection.end, Object.entries(selection.filters ?? {}).sort(), datasetId]);
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
