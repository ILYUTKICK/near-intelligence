import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";
import { privateFetch } from "@/lib/auth/private-fetch";
import { DocumentApiError } from "@/features/documents/list/documents-api";
import { apiErrorResponseSchema, documentSummarySchema } from "@/features/documents/list/documents-schema";

export type InsertModelInput = components["schemas"]["ModelBlockInsertRequest"];

export function interpretationLines(text: string): InsertModelInput["interpretation"] {
  return text.split(/\r?\n/).map(line => ({
    type: "paragraph",
    content: line ? [{ type: "text", text: line, marks: [] }] : [],
  }));
}

const resultSchema: z.ZodType<components["schemas"]["ModelBlockMutationResponse"]> = z.object({
  document: documentSummarySchema,
  value: z.object({ block_id: z.uuid() }),
});

/**
 * POST /api/documents/{id}/model-blocks (NI-055): one confirmed "Add Model"
 * selection appends exactly one pinned modelResult block through the same
 * CAS + Idempotency-Key protocol as the chart-block insertion — If-Match
 * carries the destination revision and a timeout-after-commit retry with the
 * same key replays the original 201 instead of adding a second block. Typed
 * server refusals (an unknown run, an unapproved dataset, a stale CAS) are
 * surfaced with their recorded message — never softened into a generic one.
 */
export async function insertModel(documentId: string, revision: number, input: InsertModelInput, key: string, signal?: AbortSignal) {
  const response = await privateFetch(`/api/documents/${documentId}/model-blocks`, {
    method: "POST", headers: { "content-type": "application/json", "if-match": `"${revision}"`, "idempotency-key": key },
    body: JSON.stringify(input), signal,
  });
  if (!response.ok) {
    const parsed = apiErrorResponseSchema.safeParse(await response.json().catch(() => null));
    const error = parsed.success ? parsed.data.error : null;
    const message = error?.code === "REVISION_CONFLICT" ? "The research changed. Review its current revision before confirming again."
      : response.status === 404 ? "The selected research or pinned model data is no longer available."
        : response.status === 401 || response.status === 403 ? "Your session changed. Sign in again."
          : error?.message ?? "The model result could not be added. Retry with the same pins.";
    throw new DocumentApiError(response.status, error?.code ?? "UNKNOWN_ERROR", message);
  }
  const result = resultSchema.parse(await response.json());
  if (result.document.id !== documentId) throw new Error("The insertion response did not match the selected research.");
  return result;
}
