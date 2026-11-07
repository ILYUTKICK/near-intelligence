import {
  apiErrorResponseSchema,
  documentListResponseSchema,
  documentResponseSchema,
  documentSummarySchema,
  type DocumentListResponse,
  type DocumentResponse,
  type DocumentSummary,
} from "./documents-schema";

/**
 * Same-origin client for the private document endpoints (NI-036/NI-037) used
 * by My Research (NI-023). Every request rides the HMAC session cookie
 * (credentials: "same-origin"); ownership is never sent or asserted from the
 * client — the API re-verifies the bearer on every call (NI-018/019).
 *
 * Mutations carry the compare-and-set validators exactly as the API defines
 * them: create sends a client-generated UUID Idempotency-Key (retry-safe
 * without a second document), rename/delete send `If-Match: "<revision>"`.
 * Responses are validated against the generated-contract mirrors before use.
 */

export class DocumentApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly currentRevision: number | null = null,
  ) {
    super(message);
    this.name = "DocumentApiError";
  }
}

const REQUESTED_PAGE_SIZE = 20;

async function parseErrorResponse(response: Response, body: unknown): Promise<DocumentApiError> {
  let code = "UNKNOWN_ERROR";
  let message = "The request could not be completed.";
  let currentRevision: number | null = null;
  // The body was already read once by the caller (a Response body can only be
  // consumed once); parse the captured value instead of re-reading.
  const parsed = apiErrorResponseSchema.safeParse(body);
  if (parsed.success) {
    code = parsed.data.error.code;
    message = parsed.data.error.message;
    for (const detail of parsed.data.error.details ?? []) {
      // Owned-document 409 carries the server's current revision
      // (`current_revision:<n>`), used to refresh a stale action.
      const match = /^current_revision:(\d+)$/.exec(detail.reason);
      if (match) {
        currentRevision = Number(match[1]);
      }
    }
  }
  return new DocumentApiError(response.status, code, message, currentRevision);
}

function assertJsonContentType(response: Response): void {
  const contentType = response.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    throw new DocumentApiError(response.status, "UNEXPECTED_RESPONSE", "The server response was not valid JSON.");
  }
}

export interface DocumentPage {
  items: DocumentSummary[];
  nextCursor: string | null;
}

/** GET /api/documents — owner-scoped, newest first (updated_at DESC). */
export async function listDocuments(
  options: { query?: string; cursor?: string | null; limit?: number; signal?: AbortSignal } = {},
): Promise<DocumentPage> {
  const params = new URLSearchParams();
  if (options.query) {
    params.set("q", options.query);
  }
  if (options.cursor) {
    params.set("cursor", options.cursor);
  }
  const limit = options.limit ?? REQUESTED_PAGE_SIZE;
  if (limit !== 20) {
    params.set("limit", String(limit));
  }
  const search = params.toString();
  const response = await fetch(`/api/documents${search ? `?${search}` : ""}`, {
    credentials: "same-origin",
    headers: { accept: "application/json" },
    signal: options.signal,
  });
  assertJsonContentType(response);
  const body: unknown = await response.json();
  if (!response.ok) {
    throw await parseErrorResponse(response, body);
  }
  const parsed = documentListResponseSchema.safeParse(body);
  if (!parsed.success) {
    throw new DocumentApiError(response.status, "INVALID_RESPONSE", "The document list could not be read.");
  }
  const data: DocumentListResponse = parsed.data;
  return { items: data.items, nextCursor: data.next_cursor };
}

/** POST /api/documents — create with a client-generated Idempotency-Key. */
export async function createDocument(input: {
  title: string;
  idempotencyKey: string;
}): Promise<DocumentResponse> {
  const response = await fetch("/api/documents", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "content-type": "application/json",
      accept: "application/json",
      "idempotency-key": input.idempotencyKey,
    },
    body: JSON.stringify({ title: input.title }),
  });
  assertJsonContentType(response);
  const body: unknown = await response.json();
  if (!response.ok) {
    throw await parseErrorResponse(response, body);
  }
  const parsed = documentResponseSchema.safeParse(body);
  if (!parsed.success) {
    throw new DocumentApiError(response.status, "INVALID_RESPONSE", "The created document could not be read.");
  }
  return parsed.data;
}

/** PATCH /api/documents/{id} — rename with the current revision in If-Match. */
export async function renameDocument(input: {
  documentId: string;
  title: string;
  revision: number;
}): Promise<DocumentSummary> {
  const response = await fetch(`/api/documents/${input.documentId}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "content-type": "application/json",
      accept: "application/json",
      "if-match": `"${input.revision}"`,
    },
    body: JSON.stringify({ title: input.title }),
  });
  assertJsonContentType(response);
  const body: unknown = await response.json();
  if (!response.ok) {
    throw await parseErrorResponse(response, body);
  }
  const summary = await validateSummary(body, response.status);
  return summary;
}

/** DELETE /api/documents/{id} — delete with the current revision in If-Match. */
export async function deleteDocument(input: {
  documentId: string;
  revision: number;
}): Promise<void> {
  const response = await fetch(`/api/documents/${input.documentId}`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "if-match": `"${input.revision}"` },
  });
  if (response.status === 204) {
    return;
  }
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // A non-JSON error body keeps the generic message.
  }
  throw await parseErrorResponse(response, body);
}

/** GET /api/documents/{id} — the current document (persisted-editor stub view). */
export async function getDocument(documentId: string, signal?: AbortSignal): Promise<DocumentResponse> {
  const response = await fetch(`/api/documents/${documentId}`, {
    credentials: "same-origin",
    headers: { accept: "application/json" },
    signal,
  });
  assertJsonContentType(response);
  const body: unknown = await response.json();
  if (!response.ok) {
    throw await parseErrorResponse(response, body);
  }
  const parsed = documentResponseSchema.safeParse(body);
  if (!parsed.success) {
    throw new DocumentApiError(response.status, "INVALID_RESPONSE", "The document could not be read.");
  }
  return parsed.data;
}

function validateSummary(body: unknown, status: number): DocumentSummary {
  const parsed = documentSummarySchema.safeParse(body);
  if (!parsed.success) {
    throw new DocumentApiError(status, "INVALID_RESPONSE", "The server response could not be read.");
  }
  return parsed.data;
}
