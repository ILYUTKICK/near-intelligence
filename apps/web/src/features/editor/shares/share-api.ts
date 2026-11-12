import { createApiClient, type components } from "@near-intelligence/shared-types";
import { privateFetch } from "@/lib/auth/private-fetch";
import { apiErrorResponseSchema } from "@/features/documents/list/documents-schema";

/**
 * Same-origin client for the revocable read-only share routes (NI-060,
 * API_SPECIFICATION "Document shares", ADR-021). The contract types are
 * mirrored from the generated client only (no second DTO) and error bodies
 * are parsed into the shared error envelope shape (the openapi-fetch body
 * consumption rule recorded by NI-058/NI-063 applies here identically).
 *
 * Capability rule: the create response carries the share token EXACTLY once
 * (the API stores only its SHA-256 digest); a replay or a later list never
 * returns it. The UI must show the token once and make copying explicit —
 * it is never rendered again after the dialog state is gone.
 */

export type SharePreviewResponse = components["schemas"]["SharePreviewResponse"];
export type ShareProjection = components["schemas"]["ShareProjection"];
export type ShareScopeSummary = components["schemas"]["ShareScopeSummary"];
export type ShareCreatedResponse = components["schemas"]["ShareCreatedResponse"];
export type ShareSummaryResponse = components["schemas"]["ShareSummaryResponse"];
export type ShareListResponse = components["schemas"]["DocumentShareListResponse"];

const api = () => createApiClient(window.location.origin, privateFetch);

/** A typed refusal or failure of the share API (status + error code). */
export class ShareApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ShareApiError";
    this.status = status;
    this.code = code;
  }
}

function readError(status: number, clientError: unknown): ShareApiError {
  const fallback = new ShareApiError(status, "UNKNOWN_ERROR",
    "The share request could not be completed.");
  const parsed = apiErrorResponseSchema.safeParse(clientError);
  if (!parsed.success) return fallback;
  return new ShareApiError(status, parsed.data.error.code,
    parsed.data.error.message || fallback.message);
}

export async function previewShare(documentId: string,
                                   signal: AbortSignal): Promise<SharePreviewResponse> {
  const { data, response, error } = await api().GET(
    "/api/documents/{document_id}/shares/preview", {
      params: { path: { document_id: documentId } }, signal,
    });
  if (!response.ok || !data) throw readError(response.status, error);
  return data;
}

export async function createShare(documentId: string,
                                  consent: {
                                    acknowledged_revision: number;
                                    preview_sha256: string;
                                    visible_scope: ShareScopeSummary;
                                    expires_at?: string | null;
                                  },
                                  idempotencyKey: string,
                                  signal: AbortSignal): Promise<ShareCreatedResponse> {
  const { data, response, error } = await api().POST(
    "/api/documents/{document_id}/shares", {
      params: { path: { document_id: documentId } },
      headers: { "Idempotency-Key": idempotencyKey },
      body: consent,
      signal,
    });
  if (!response.ok || !data) throw readError(response.status, error);
  return data;
}

export async function listShares(documentId: string,
                                 signal: AbortSignal): Promise<ShareSummaryResponse[]> {
  const { data, response, error } = await api().GET(
    "/api/documents/{document_id}/shares", {
      params: { path: { document_id: documentId } }, signal,
    });
  if (!response.ok || !data) throw readError(response.status, error);
  return data.items;
}

export async function revokeShare(documentId: string, shareId: string,
                                  signal: AbortSignal): Promise<void> {
  const { response, error } = await api().DELETE(
    "/api/documents/{document_id}/shares/{share_id}", {
      params: { path: { document_id: documentId, share_id: shareId } }, signal,
    });
  if (!response.ok) throw readError(response.status, error);
}
