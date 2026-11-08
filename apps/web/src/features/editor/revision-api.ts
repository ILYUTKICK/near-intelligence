import { createApiClient } from "@near-intelligence/shared-types";
import { chartViewResponseSchema } from "@/features/charts/library/catalog-schema";
import { apiErrorResponseSchema } from "@/features/documents/list/documents-schema";
import { privateFetch } from "@/lib/auth/private-fetch";

const api = () => createApiClient(window.location.origin, privateFetch);

function readError(response: Response, error?: unknown) {
  if (response.status === 404) return new Error("This saved research could not be found for your account.");
  if (response.status === 401) return new Error("Sign in again to open saved research.");
  const parsed = apiErrorResponseSchema.safeParse(error);
  if (parsed.success && parsed.data.error.code === "RECONSTRUCTION_ERROR") {
    return new Error("Chart reconstruction failed. A saved artifact is missing or inconsistent.");
  }
  return new Error("Saved research could not be loaded. Try again.");
}

export async function listRevisions(documentId: string, cursor: string | undefined, signal: AbortSignal) {
  const { data, response } = await api().GET("/api/documents/{document_id}/versions", {
    params: { path: { document_id: documentId }, query: { cursor } }, signal,
  });
  if (!data || !response.ok) throw readError(response);
  return data;
}

export async function getRevision(documentId: string, versionId: string, signal: AbortSignal) {
  const { data, response } = await api().GET("/api/documents/{document_id}/versions/{version_id}", {
    params: { path: { document_id: documentId, version_id: versionId } }, signal,
  });
  if (!data || !response.ok || data.document_id !== documentId || data.id !== versionId) throw readError(response);
  return data;
}

export async function getRevisionChart(documentId: string, versionId: string, blockId: string, signal: AbortSignal) {
  const { data, error, response } = await api().GET("/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/view", {
    params: { path: { document_id: documentId, version_id: versionId, block_id: blockId } }, signal,
  });
  if (!data || !response.ok) throw readError(response, error);
  return chartViewResponseSchema.parse(data);
}

export async function getRevisionCsv(documentId: string, versionId: string, blockId: string, signal: AbortSignal) {
  const { data, error, response } = await api().GET("/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/csv", {
    params: { path: { document_id: documentId, version_id: versionId, block_id: blockId } }, parseAs: "blob", signal,
  });
  if (!response.ok || !data?.type.startsWith("text/csv")) throw readError(response, error);
  return data;
}
