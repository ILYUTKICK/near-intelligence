import { createApiClient, type components } from "@near-intelligence/shared-types";
import { DocumentApiError } from "@/features/documents/list/documents-api";
import { apiErrorResponseSchema } from "@/features/documents/list/documents-schema";
import { privateFetch } from "@/lib/auth/private-fetch";

export type InsightCreateRequest = components["schemas"]["InsightCreateRequest"];
export type InsightPatchRequest = components["schemas"]["InsightPatchRequest"];
export type InsightDeleteRequest = components["schemas"]["InsightDeleteRequest"];
export type InsightSave = components["schemas"]["DocumentSaveResponse"];

const client = () => createApiClient(window.location.origin, privateFetch);
const writeHeaders = (revision: number, key: string) => ({ "if-match": `"${revision}"`, "idempotency-key": key });

function acknowledge<T extends InsightSave>(result: { data?: T; response: Response; error?: unknown }, documentId: string): T {
  const { data, response } = result;
  if (!response.ok) {
    const parsed = apiErrorResponseSchema.safeParse(result.error);
    const error = parsed.success ? parsed.data.error : null;
    const message = error?.code === "REVISION_CONFLICT" ? "The research changed. Your insight draft is still here."
      : response.status === 404 ? "This research or insight is unavailable to your account."
        : response.status === 401 || response.status === 403 ? "Your session changed. Sign in again to continue."
          : error?.message ?? "The insight could not be saved. Retry the same action.";
    throw new DocumentApiError(response.status, error?.code ?? "UNKNOWN_ERROR", message);
  }
  if (!data || data.document.id !== documentId || data.version.document_id !== documentId
    || data.document.current_version_id !== data.version.id || data.document.revision !== data.version.revision) {
    throw new Error("The saved revision could not be verified. Retry the same action.");
  }
  return data;
}

export async function createInsight(documentId: string, revision: number, body: InsightCreateRequest, key: string, signal: AbortSignal) {
  return acknowledge(await client().POST("/api/documents/{document_id}/insights", {
    params: { path: { document_id: documentId } }, headers: writeHeaders(revision, key), body, signal,
  }), documentId);
}

export async function editInsight(documentId: string, insightId: string, revision: number, body: InsightPatchRequest, key: string, signal: AbortSignal) {
  return acknowledge(await client().PATCH("/api/documents/{document_id}/insights/{insight_id}", {
    params: { path: { document_id: documentId, insight_id: insightId } }, headers: writeHeaders(revision, key), body, signal,
  }), documentId);
}

export async function deleteInsight(documentId: string, insightId: string, revision: number, body: InsightDeleteRequest, key: string, signal: AbortSignal) {
  return acknowledge(await client().DELETE("/api/documents/{document_id}/insights/{insight_id}", {
    params: { path: { document_id: documentId, insight_id: insightId } }, headers: writeHeaders(revision, key), body, signal,
  }), documentId);
}
