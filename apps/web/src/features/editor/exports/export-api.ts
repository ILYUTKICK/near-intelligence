import { createApiClient, type components } from "@near-intelligence/shared-types";
import { privateFetch } from "@/lib/auth/private-fetch";
import { apiErrorResponseSchema } from "@/features/documents/list/documents-schema";

/**
 * Same-origin client for the Markdown ZIP export routes (NI-058). The
 * contract lives in API_SPECIFICATION.md "Export": the create POST names the
 * exact acknowledged revision and carries a client `Idempotency-Key: UUID`
 * (a repeated identical request replays the SAME job instead of creating a
 * second one), polling returns the typed lifecycle state, and the download
 * streams the stored ZIP — owner-checked, never a stale file (expired is a
 * typed 410).
 *
 * Render-boundary rule (NI-023 pattern): job responses are mirrored with the
 * generated contract types only (no second DTO), and error bodies are parsed
 * into the shared error envelope shape. Any failure that is not an API error
 * envelope (fetch TypeError, abort) stays a transport failure for the caller
 * to surface honestly.
 */

export type ExportJob = components["schemas"]["ExportJobResponse"];
export type ExportJobStatus = NonNullable<ExportJob["status"]>;

const api = () => createApiClient(window.location.origin, privateFetch);

/** A typed refusal or failure of the export API (status + error code). */
export class ExportApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ExportApiError";
    this.status = status;
    this.code = code;
  }
}

async function readError(response: Response): Promise<ExportApiError> {
  const fallback = new ExportApiError(response.status, "UNKNOWN_ERROR",
    "The export request could not be completed.");
  try {
    const parsed = apiErrorResponseSchema.safeParse(await response.json());
    if (!parsed.success) return fallback;
    return new ExportApiError(response.status, parsed.data.error.code,
      parsed.data.error.message || fallback.message);
  } catch {
    // A non-JSON error body stays the typed fallback.
    return fallback;
  }
}

export function newExportIdempotencyKey(): string {
  return crypto.randomUUID();
}

export async function createExport(documentId: string, versionId: string,
                                   idempotencyKey: string,
                                   signal: AbortSignal): Promise<ExportJob> {
  const { data, response } = await api().POST("/api/documents/{document_id}/exports", {
    params: { path: { document_id: documentId } },
    headers: { "Idempotency-Key": idempotencyKey },
    body: { document_version_id: versionId, format: "markdown_zip" },
    signal,
  });
  if (!response.ok || !data) throw await readError(response);
  return data;
}

export async function pollExport(documentId: string, jobId: string,
                                 signal: AbortSignal): Promise<ExportJob> {
  const { data, response } = await api().GET("/api/documents/{document_id}/exports/{job_id}", {
    params: { path: { document_id: documentId, job_id: jobId } }, signal,
  });
  if (!response.ok || !data) throw await readError(response);
  return data;
}

export async function downloadExportBundle(documentId: string, jobId: string,
                                           signal: AbortSignal): Promise<Blob> {
  const { data, response } = await api().GET(
    "/api/documents/{document_id}/exports/{job_id}/download", {
      params: { path: { document_id: documentId, job_id: jobId } },
      parseAs: "blob", signal,
    });
  if (!response.ok || !(data instanceof Blob)) throw await readError(response);
  return data;
}
