import { createApiClient, type components } from "@near-intelligence/shared-types";
import { privateFetch } from "@/lib/auth/private-fetch";
import { apiErrorResponseSchema } from "@/features/documents/list/documents-schema";

/**
 * Same-origin client for the export routes (NI-058 Markdown ZIP, NI-059
 * PDF). The contract lives in API_SPECIFICATION.md "Export": the create POST
 * names the exact acknowledged revision and the bundle format, and carries a
 * client `Idempotency-Key: UUID` (a repeated identical request replays the
 * SAME job instead of creating a second one), polling returns the typed
 * lifecycle state, and the download streams the stored artifact —
 * owner-checked, never a stale file (expired is a typed 410). The format is
 * a job property end to end: the response carries it and the download
 * streams the matching media type (`application/zip` or `application/pdf`).
 *
 * Render-boundary rule (NI-023 pattern): job responses are mirrored with the
 * generated contract types only (no second DTO), and error bodies are parsed
 * into the shared error envelope shape. NI-062 correction (the NI-063
 * recorded finding): openapi-fetch CONSUMES the body of a non-ok response
 * itself and hands the parsed value back as `error`, so the typed code comes
 * from that captured object — re-reading `response.json()` here always fails
 * (the body is used) and degraded every typed refusal to the generic
 * fallback.
 */

export type ExportJob = components["schemas"]["ExportJobResponse"];
export type ExportJobStatus = NonNullable<ExportJob["status"]>;
export type ExportFormat = NonNullable<ExportJob["format"]>;

/** The server-controlled download filename of one export job. */
export function exportFilename(job: Pick<ExportJob, "id" | "format">): string {
  return `near-export-${job.id}.${job.format === "pdf" ? "pdf" : "zip"}`;
}

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

function readError(status: number, clientError: unknown): ExportApiError {
  const fallback = new ExportApiError(status, "UNKNOWN_ERROR",
    "The export request could not be completed.");
  // The generated client already read the non-ok body once: `error` is the
  // parsed envelope (or the raw text when it was not JSON). A Response body
  // cannot be consumed twice, so the fallback is the honest degraded state.
  const parsed = apiErrorResponseSchema.safeParse(clientError);
  if (!parsed.success) return fallback;
  return new ExportApiError(status, parsed.data.error.code,
    parsed.data.error.message || fallback.message);
}

export function newExportIdempotencyKey(): string {
  return crypto.randomUUID();
}

export async function createExport(documentId: string, versionId: string,
                                   format: ExportFormat, idempotencyKey: string,
                                   signal: AbortSignal): Promise<ExportJob> {
  const { data, response, error } = await api().POST("/api/documents/{document_id}/exports", {
    params: { path: { document_id: documentId } },
    headers: { "Idempotency-Key": idempotencyKey },
    body: { document_version_id: versionId, format },
    signal,
  });
  if (!response.ok || !data) throw readError(response.status, error);
  return data;
}

export async function pollExport(documentId: string, jobId: string,
                                 signal: AbortSignal): Promise<ExportJob> {
  const { data, response, error } = await api().GET("/api/documents/{document_id}/exports/{job_id}", {
    params: { path: { document_id: documentId, job_id: jobId } }, signal,
  });
  if (!response.ok || !data) throw readError(response.status, error);
  return data;
}

export async function downloadExportBundle(documentId: string, jobId: string,
                                           signal: AbortSignal): Promise<Blob> {
  const { data, response, error } = await api().GET(
    "/api/documents/{document_id}/exports/{job_id}/download", {
      params: { path: { document_id: documentId, job_id: jobId } },
      parseAs: "blob", signal,
    });
  if (!response.ok || !(data instanceof Blob)) throw readError(response.status, error);
  return data;
}
