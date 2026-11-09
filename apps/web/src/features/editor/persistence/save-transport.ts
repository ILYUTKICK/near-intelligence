import { privateFetch } from "@/lib/auth/private-fetch";
import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";

import { DocumentApiError } from "@/features/documents/list/documents-api";
import {
  apiErrorResponseSchema,
  documentSummarySchema,
} from "@/features/documents/list/documents-schema";

/**
 * Same-origin client for `POST /api/documents/{id}/versions` (NI-040). The
 * contract lives in API_SPECIFICATION.md "Research documents and versions":
 * the save carries `If-Match: "<revision>"` (compare-and-set — a stale
 * revision is a typed 409 REVISION_CONFLICT that includes
 * `current_revision:<n>` for the owned document), an `Idempotency-Key: UUID`
 * (a retried identical request replays the original 201 instead of creating
 * a second revision — the timeout-after-commit guarantee), and the canonical
 * document as `{schema_version, content, observed_contexts}`. The server
 * verifies submitted observations and carries unchanged pins forward.
 *
 * The client follows the NI-023 render-boundary pattern: responses are
 * validated against zod mirrors of the generated contracts before use, and
 * error bodies are parsed into the typed {@link DocumentApiError} (imported,
 * not re-declared — one error type for the document API). Any failure that is
 * NOT a {@link DocumentApiError} (fetch `TypeError`, abort, …) is a transport
 * failure: nothing is known about the server state, so callers must retain
 * the payload and retry with the SAME idempotency key (see save-coordinator).
 */

export type SaveRequestBody = Required<components["schemas"]["DocumentSaveRequest"]>;

export interface SaveAttempt {
  documentId: string;
  /** The CAS revision sent as `If-Match: "<revision>"`. */
  revision: number;
  /** Client-generated UUID; retries of THIS attempt reuse the same key. */
  idempotencyKey: string;
  body: SaveRequestBody;
}

export interface SaveAck {
  /** The new current revision — equals the response ETag value. */
  revision: number;
  /** `document.updated_at` of the acknowledged revision (saved-at display). */
  savedAt: string;
}

/** Mirror of the generated DocumentSaveResponse (render-boundary check only). */
const saveResponseSchema = z.object({
  document: documentSummarySchema,
  version: z.object({ revision: z.number().int().positive() }),
});

function assertJsonContentType(response: Response): void {
  const contentType = response.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    throw new DocumentApiError(response.status, "UNEXPECTED_RESPONSE", "The server response was not valid JSON.");
  }
}

function parseSaveErrorResponse(response: Response, body: unknown): DocumentApiError {
  let code = "UNKNOWN_ERROR";
  let message = "The save could not be completed.";
  let currentRevision: number | null = null;
  // The body was already read once by the caller (a Response body can only be
  // consumed once); parse the captured value instead of re-reading (NI-023).
  const parsed = apiErrorResponseSchema.safeParse(body);
  if (parsed.success) {
    code = parsed.data.error.code;
    message = parsed.data.error.message;
    for (const detail of parsed.data.error.details ?? []) {
      // Owned-document 409 carries the server's current revision
      // (`current_revision:<n>`), which drives the conflict recovery UI.
      const match = /^current_revision:(\d+)$/.exec(detail.reason);
      if (match) {
        currentRevision = Number(match[1]);
      }
    }
  }
  return new DocumentApiError(response.status, code, message, currentRevision);
}

/**
 * POST /api/documents/{id}/versions — one immutable revision, compare-and-set
 * via If-Match. Throws DocumentApiError for typed HTTP failures (409/413/422/
 * 428/401/…) and anything else for transport failures.
 */
export async function saveRevision(attempt: SaveAttempt): Promise<SaveAck> {
  const response = await privateFetch(`/api/documents/${attempt.documentId}/versions`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "content-type": "application/json",
      accept: "application/json",
      // Exactly the quoted current revision: bare numbers and weak
      // validators are rejected with 428 by the API.
      "if-match": `"${attempt.revision}"`,
      "idempotency-key": attempt.idempotencyKey,
    },
    body: JSON.stringify(attempt.body),
  });
  assertJsonContentType(response);
  const body: unknown = await response.json();
  if (!response.ok) {
    throw parseSaveErrorResponse(response, body);
  }
  const parsed = saveResponseSchema.safeParse(body);
  if (!parsed.success) {
    throw new DocumentApiError(response.status, "INVALID_RESPONSE", "The save response could not be read.");
  }
  const savedAt = parsed.data.document.updated_at;
  return { revision: parsed.data.document.revision, savedAt };
}

/**
 * True when a thrown error means the request outcome is UNKNOWN (network
 * down, request aborted, response lost). The server may or may not have
 * committed — the retry must therefore reuse the attempt's Idempotency-Key
 * so a committed save replays instead of duplicating a revision.
 */
export function isTransportFailure(error: unknown): boolean {
  return !(error instanceof DocumentApiError);
}

/** Client-generated UUID (same fallback pattern as the document API client). */
export function newIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID: a v4-shaped unique
  // string. Idempotency keys need uniqueness, not cryptographic strength.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    const value = character === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}
