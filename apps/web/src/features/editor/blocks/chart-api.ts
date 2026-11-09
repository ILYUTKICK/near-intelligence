import { createApiClient } from "@near-intelligence/shared-types";
import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";
import { privateFetch } from "@/lib/auth/private-fetch";
import { chartViewResponseSchema } from "@/features/charts/library/catalog-schema";
import type { ChartSelection } from "@/features/charts/renderer/ChartView";

export type DocumentChartView = Omit<components["schemas"]["DocumentChartViewResponse"], "latest_approved_dataset_version_id">
  & Partial<Pick<components["schemas"]["DocumentChartViewResponse"], "latest_approved_dataset_version_id">>;
const documentChartViewSchema = chartViewResponseSchema.extend({ latest_approved_dataset_version_id: z.uuid().nullish() });

/** A fixed same-origin owner-checked route; never forwards an input URL. */
export async function loadDocumentChart(documentId: string, definitionId: string,
  selection: ChartSelection, datasetVersion: string, signal: AbortSignal): Promise<DocumentChartView> {
  const client = createApiClient("", privateFetch);
  const result = await client.GET("/api/documents/{document_id}/chart-view", { signal,
    params: { path: { document_id: documentId }, query: {
      chart_definition_version_id: definitionId, start: selection.start, end: selection.end,
      dataset_version: datasetVersion, filters: JSON.stringify(selection.filters ?? {}),
    } } });
  if (!result.response.ok) throw new Error("The chart could not be resolved. Your prose and saved evidence are retained; retry the chart separately.");
  const view = documentChartViewSchema.parse(result.data) as DocumentChartView;
  if (view.definition.id !== definitionId || (datasetVersion !== "latest" && view.dataset.id !== datasetVersion)
    || view.selection.start !== selection.start || view.selection.end !== selection.end
    || JSON.stringify(Object.entries(view.selection.filters).sort()) !== JSON.stringify(Object.entries(selection.filters ?? {}).sort())) {
    throw new Error("The returned chart context does not match the requested inspection. Nothing was changed.");
  }
  return view;
}
