/**
 * Server-side access to the NI-060 token-gated share API for the
 * /share/[token] viewer page (ADR-021).
 *
 * The request goes to the internal API with `cache: "no-store"` — a share is
 * PRIVATE-BY-CONSENT content and is never cached anywhere (AGENTS.md public
 * caching prohibition; every response is no-store end to end). The token
 * arrives only as a path segment and is never logged. The response is
 * validated against the render-boundary schema
 * (features/shares/share-schema.ts) before any rendering; a 404 deny (one
 * generic shape for unknown/revoked/expired) and a validation failure are
 * honest typed results — the viewer never fabricates content.
 *
 * Server module: reads loadServerEnv() and must never be imported from a
 * client component (the internal API URL is not a client value).
 */
import { loadServerEnv } from "@/lib/env";

import { shareProjectionSchema, type ShareProjectionPayload } from "./share-schema";

export interface ShareFetchFailure {
  ok: false;
  status: number;
}

export type ShareFetchResult =
  | { ok: true; projection: ShareProjectionPayload }
  | ShareFetchFailure;

const REQUEST_TIMEOUT_MS = 10_000;
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;

/**
 * GET /api/shares/{token} — the frozen projection behind one share link.
 * Unknown/revoked/expired are the SAME generic 404 (no oracle): the page
 * renders one honest denied state for every failure.
 */
export async function fetchSharedProjection(token: string): Promise<ShareFetchResult> {
  if (!TOKEN_PATTERN.test(token)) return { ok: false, status: 404 };
  let response: Response;
  try {
    response = await globalThis.fetch(
      new URL(`/api/shares/${encodeURIComponent(token)}`, loadServerEnv().API_INTERNAL_URL),
      { cache: "no-store", redirect: "error",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        headers: { accept: "application/json" } });
  } catch {
    return { ok: false, status: 503 };
  }
  if (!response.ok) {
    return { ok: false, status: response.status };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { ok: false, status: 502 };
  }
  const parsed = shareProjectionSchema.safeParse(body);
  return parsed.success ? { ok: true, projection: parsed.data } : { ok: false, status: 502 };
}
