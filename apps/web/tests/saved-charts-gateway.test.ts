import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/saved-charts/[[...segments]]/route";
import { GET as getDocument, POST as postDocument } from "@/app/api/documents/[[...segments]]/route";
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
const context = { params: Promise.resolve({ segments: [] }) };
function request(method = "GET", csrf = false, origin = "http://localhost:3000") {
  const token = mintCsrfToken();
  const session = encodeSessionCookie({ accessToken: "synthetic-access-token", refreshToken: "synthetic-refresh-token", expiresAt: Date.now() + 60_000 });
  return new NextRequest("http://localhost:3000/api/saved-charts", { method,
    headers: { origin, cookie: `${SESSION_COOKIE}=${session}; ${CSRF_COOKIE}=${token}`,
      ...(csrf ? { "x-csrf-token": token } : {}), "content-type": "application/json", authorization: "Bearer injected-browser-token" },
    ...(method === "POST" ? { body: "{}" } : {}) });
}
describe("Saved charts same-origin gateway", () => {
  it("forwards only the signed-cookie bearer, without cookies, and forces no-store", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ items: [], next_cursor: null }), { headers: { "content-type": "application/json", "cache-control": "public" } }));
    vi.stubGlobal("fetch", fetcher);
    const response = await GET(request(), context);
    expect(response.status).toBe(200); expect(response.headers.get("cache-control")).toBe("no-store");
    const [url, options] = fetcher.mock.calls[0] as unknown as [URL, RequestInit];
    expect(url.pathname).toBe("/api/saved-charts");
    expect(new Headers(options.headers).get("authorization")).toBe("Bearer synthetic-access-token");
    expect(new Headers(options.headers).get("cookie")).toBeNull();
    expect(JSON.stringify(await response.json())).not.toContain("token");
  });
  it("rejects missing CSRF and foreign origins before forwarding a mutation", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    expect((await POST(request("POST"), context)).status).toBe(403);
    expect((await POST(request("POST", true, "https://foreign.example"), context)).status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("allows a verified CSRF pair and rejects unsigned sessions and non-UUID paths", async () => {
    const fetcher = vi.fn(async () => new Response("{}", { status: 201 })); vi.stubGlobal("fetch", fetcher);
    expect((await POST(request("POST", true), context)).status).toBe(201);
    const absent = new NextRequest("http://localhost:3000/api/saved-charts");
    expect((await GET(absent, context)).status).toBe(401);
    expect((await GET(request(), { params: Promise.resolve({ segments: ["https://evil.example"] }) })).status).toBe(404);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("rejects an oversized body before sending it upstream", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const valid = request("POST", true);
    const large = new NextRequest(valid.url, { method: "POST", headers: valid.headers,
      body: "x".repeat(2_000_001) });
    expect((await POST(large, context)).status).toBe(413);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("limits document forwarding to registered paths and preserves CAS/ETag", async () => {
    const id = "44444444-4444-4444-8444-444444444444";
    const fetcher = vi.fn(async () => new Response("{}", { status: 201, headers: { etag: '"4"' } }));
    vi.stubGlobal("fetch", fetcher);
    const valid = request("POST", true);
    valid.headers.set("if-match", '"3"');
    valid.headers.set("idempotency-key", id);
    const incoming = new NextRequest(`http://localhost:3000/api/documents/${id}/chart-blocks`, {
      method: "POST", headers: valid.headers, body: "{}",
    });
    const response = await postDocument(incoming, { params: Promise.resolve({ segments: [id, "chart-blocks"] }) });
    expect(response.status).toBe(201); expect(response.headers.get("etag")).toBe('"4"');
    const [url, options] = fetcher.mock.calls[0] as unknown as [URL, RequestInit];
    expect(url.pathname).toBe(`/api/documents/${id}/chart-blocks`);
    expect(new Headers(options.headers).get("if-match")).toBe('"3"');
    expect(new Headers(options.headers).get("idempotency-key")).toBe(id);
    expect((await getDocument(request(), { params: Promise.resolve({ segments: [id, "arbitrary-path"] }) })).status).toBe(404);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("forwards only the fixed chart-view read path, preserves pins and refuses arbitrary query fields", async () => {
    const id = "44444444-4444-4444-8444-444444444444";
    const fetcher = vi.fn(async () => new Response("{}", { status: 200 })); vi.stubGlobal("fetch", fetcher);
    const path = { params: Promise.resolve({ segments: [id, "chart-view"] }) };
    const incoming = new NextRequest(`http://localhost:3000/api/documents/${id}/chart-view?chart_definition_version_id=${id}&dataset_version=${id}&start=2026-11-01&end=2026-11-02`, { headers: request().headers });
    const response = await getDocument(incoming, path);
    expect(response.status).toBe(200); expect(response.headers.get("cache-control")).toBe("no-store");
    const url = (fetcher.mock.calls[0] as unknown as [URL])[0];
    expect(url.pathname).toBe(`/api/documents/${id}/chart-view`); expect(url.searchParams.get("dataset_version")).toBe(id);
    const arbitrary = new NextRequest(`${incoming.url}&url=https://evil.example`, { headers: incoming.headers });
    expect((await getDocument(arbitrary, path)).status).toBe(422);
    expect((await postDocument(new NextRequest(incoming.url, { method: "POST", headers: incoming.headers }), path)).status).toBe(405);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

});
