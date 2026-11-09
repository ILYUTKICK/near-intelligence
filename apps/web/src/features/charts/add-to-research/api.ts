import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";
import { privateFetch } from "@/lib/auth/private-fetch";
import { documentSummarySchema } from "@/features/documents/list/documents-schema";
export type InsertChartInput = components["schemas"]["ChartBlockInsertRequest"];
const resultSchema: z.ZodType<components["schemas"]["ChartBlockMutationResponse"]> = z.object({
  document: documentSummarySchema, value: z.object({ block_id: z.uuid() }),
});
export async function insertChart(documentId: string, revision: number, input: InsertChartInput, key: string, signal?: AbortSignal) {
  const response = await privateFetch(`/api/documents/${documentId}/chart-blocks`, {
    method: "POST", headers: { "content-type": "application/json", "if-match": `"${revision}"`, "idempotency-key": key },
    body: JSON.stringify(input), signal,
  });
  if (!response.ok) throw new Error(response.status === 409
    ? "The research changed. Confirm again to append to its current revision; existing work will be retained."
    : response.status === 404 ? "The selected research or inspected data is no longer available."
      : response.status === 401 || response.status === 403 ? "Your session changed. Sign in again."
        : "The chart could not be added. Retry with the same inspected context.");
  return resultSchema.parse(await response.json());
}
