import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";
import { privateFetch } from "@/lib/auth/private-fetch";
import { documentSummarySchema } from "@/features/documents/list/documents-schema";

export type InsertModelInput = components["schemas"]["ModelBlockInsertRequest"];

const resultSchema: z.ZodType<components["schemas"]["ModelBlockMutationResponse"]> = z.object({
  document: documentSummarySchema,
  value: z.object({ block_id: z.uuid() }),
});

/**
 * POST /api/documents/{id}/model-blocks (NI-055): one confirmed "Add Model"
 * selection appends exactly one pinned modelResult block through the same
 * CAS + Idempotency-Key protocol as the chart-block insertion — If-Match
 * carries the destination revision and a timeout-after-commit retry with the
 * same key replays the original 201 instead of adding a second block.
 */
export async function insertModel(documentId: string, revision: number, input: InsertModelInput, key: string, signal?: AbortSignal) {
  const response = await privateFetch(`/api/documents/${documentId}/model-blocks`, {
    method: "POST", headers: { "content-type": "application/json", "if-match": `"${revision}"`, "idempotency-key": key },
    body: JSON.stringify(input), signal,
  });
  if (!response.ok) throw new Error(response.status === 409
    ? "The research changed. Confirm again to append to its current revision; existing work will be retained."
    : response.status === 404 ? "The selected research or pinned model data is no longer available."
      : response.status === 401 || response.status === 403 ? "Your session changed. Sign in again."
        : "The model result could not be added. The pinned run and dataset are verified server-side; retry with the same pins.");
  return resultSchema.parse(await response.json());
}
