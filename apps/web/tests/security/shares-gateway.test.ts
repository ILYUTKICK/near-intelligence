/**
 * NI-060 same-origin gateway tests for the share segments (ADR-021): the
 * owner plane forwards only the registered document-nested share paths with
 * the signed-cookie bearer (never browser cookies/tokens), no share route
 * accepts a query string, unknown segments are a generic 404, and mutations
 * stay behind the verified CSRF pair. The share token NEVER travels through
 * this gateway — it lives on the public /share/[token] page route, whose
 * fetches are server-side only.
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DELETE,
  GET,
  POST,
} from "@/app/api/documents/[[...segments]]/route";
import { CSRF_COOKIE, SESSION_COOKIE, encodeSessionCookie, mintCsrfToken } from "@/lib/auth/session";

const environment = {
  APP_ENV: "test", APP_ORIGIN: "http://localhost:3000", API_INTERNAL_URL: "http://localhost:8000",
  NEXT_PUBLIC_SUPABASE_URL: "https://synthetic.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_synthetic_key_0123456789",
  SUPABASE_JWT_ISSUER: "https://synthetic.supabase.co/auth/v1", SUPABASE_JWKS_URL: "https://synthetic.supabase.co/auth/v1/.well-known/jwks.json",
  SUPABASE_JWT_AUDIENCE: "authenticated", SUPABASE_JWT_ALGORITHM: "ES256",
  AUTH_ALLOWED_REDIRECT_ORIGINS: "http://localhost:3000",
  AUTH_COOKIE_SIGNING_SECRET: "synthetic-cookie-secret-01234567890123456789", CSRF_SIGNING_SECRET: "synthetic-csrf-secret-01234567890123456789",
};
beforeEach(() => { Object.assign(process.env, environment); });
afterEach(() => { vi.unstubAllGlobals(); for (const key of Object.keys(environment)) delete process.env[key]; });

const DOC_ID = "22222222-2222-4222-8222-222222222222";
const SHARE_ID = "77777777-7777-4777-8777-777777777777";

function request(method: string, segments: string[], options: { csrf?: boolean; origin?: string; body?: string; search?: string } = {}) {
  const token = mintCsrfToken();
  const session = encodeSessionCookie({ accessToken: "synthetic-access-token", refreshToken: "synthetic-refresh-token", expiresAt: Date.now() + 60_000 });
  return new NextRequest(`http://localhost:3000/api/documents/${segments.join("/")}${options.search ?? ""}`, {
    method,
    headers: {
      origin: options.origin ?? "http://localhost:3000",
      cookie: `${SESSION_COOKIE}=${session}; ${CSRF_COOKIE}=${token}`,
      ...(options.csrf ? { "x-csrf-token": token } : {}),
      "content-type": "application/json",
      authorization: "Bearer injected-browser-token",
    },
    ...(options.body !== undefined || method === "POST" ? { body: options.body ?? "{}" } : {}),
  });
}

function context(segments: string[]) {
  return { params: Promise.resolve({ segments }) };
}

describe("Share segments of the same-origin document gateway", () => {
  it("forwards the owner share reads with the signed-cookie bearer and no-store", async () => {
    const fetcher = vi.fn(async () => new Response("{}", { headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetcher);
    const preview = await GET(request("GET", [DOC_ID, "shares", "preview"]), context([DOC_ID, "shares", "preview"]));
    expect(preview.status).toBe(200);
    expect(preview.headers.get("cache-control")).toBe("no-store");
    expect(preview.headers.get("referrer-policy")).toBe("no-referrer");
    const list = await GET(request("GET", [DOC_ID, "shares"]), context([DOC_ID, "shares"]));
    expect(list.status).toBe(200);
    const [url, options] = fetcher.mock.calls[0] as unknown as [URL, RequestInit];
    expect(url.pathname).toBe(`/api/documents/${DOC_ID}/shares/preview`);
    const headers = new Headers(options.headers);
    expect(headers.get("authorization")).toBe("Bearer synthetic-access-token");
    expect(headers.get("cookie")).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("requires the verified CSRF pair and same-origin for the consented create and the revoke", async () => {
    const fetcher = vi.fn(async () => new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", fetcher);
    expect((await POST(request("POST", [DOC_ID, "shares"], { body: "{}" }), context([DOC_ID, "shares"]))).status).toBe(403);
    expect((await POST(request("POST", [DOC_ID, "shares"], { body: "{}", origin: "https://foreign.example" }),
      context([DOC_ID, "shares"]))).status).toBe(403);
    expect((await DELETE(request("DELETE", [DOC_ID, "shares", SHARE_ID]), context([DOC_ID, "shares", SHARE_ID]))).status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
    const created = await POST(request("POST", [DOC_ID, "shares"], { csrf: true, body: "{}" }), context([DOC_ID, "shares"]));
    expect(created.status).toBe(201);
    const revoked = await DELETE(request("DELETE", [DOC_ID, "shares", SHARE_ID], { csrf: true }),
      context([DOC_ID, "shares", SHARE_ID]));
    expect(revoked.status).toBe(201); // the fixture answers 201; the gateway forwards the status
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("refuses a query string on every share segment before forwarding", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    for (const segments of [
      [DOC_ID, "shares"],
      [DOC_ID, "shares", "preview"],
      [DOC_ID, "shares", SHARE_ID],
    ]) {
      const response = await GET(request("GET", segments, { search: "?token=leak-attempt" }), context(segments));
      expect(response.status).toBe(422);
      expect(response.headers.get("cache-control")).toBe("no-store");
      expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    }
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("keeps unregistered share segments and methods out with generic responses", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    expect((await GET(request("GET", [DOC_ID, "shares", "not-preview-not-uuid"]), context([DOC_ID, "shares", "not-preview-not-uuid"]))).status).toBe(404);
    expect((await POST(request("POST", [DOC_ID, "shares", "preview"], { csrf: true }), context([DOC_ID, "shares", "preview"]))).status).toBe(405);
    expect((await GET(request("GET", [DOC_ID, "shares", "not-preview-not-uuid"]), context([DOC_ID, "shares", "not-preview-not-uuid"]))).status).toBe(404);
    // The token-shaped segment is never forwarded: a share link lives only
    // on the public /share/[token] page, never in the owner gateway.
    expect((await GET(request("GET", [DOC_ID, "shares", "a-share-token-value"]), context([DOC_ID, "shares", "a-share-token-value"]))).status).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("answers an unsigned session with the generic 401 before anything else", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const absent = new NextRequest(`http://localhost:3000/api/documents/${DOC_ID}/shares`);
    expect((await GET(absent, context([DOC_ID, "shares"]))).status).toBe(401);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
