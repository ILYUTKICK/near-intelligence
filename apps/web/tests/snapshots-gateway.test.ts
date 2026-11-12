import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DELETE, GET, POST } from "@/app/api/snapshots/[[...segments]]/route";
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
const id = "33333333-3333-4333-8333-333333333333";
function context(segments: string[] = []) {
  return { params: Promise.resolve({ segments }) };
}
function request(method = "GET", csrf = false, origin = "http://localhost:3000") {
  const token = mintCsrfToken();
  const session = encodeSessionCookie({ accessToken: "synthetic-access-token", refreshToken: "synthetic-refresh-token", expiresAt: Date.now() + 60_000 });
  return new NextRequest("http://localhost:3000/api/snapshots", { method,
    headers: { origin, cookie: `${SESSION_COOKIE}=${session}; ${CSRF_COOKIE}=${token}`,
      ...(csrf ? { "x-csrf-token": token } : {}), "content-type": "application/json", authorization: "Bearer injected-browser-token" },
    ...(method === "POST" || method === "DELETE" ? { body: "{}" } : {}) });
}
describe("Snapshots same-origin gateway", () => {
  it("forwards only the signed-cookie bearer, without cookies, and forces no-store", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ items: [], next_cursor: null }), { headers: { "content-type": "application/json", "cache-control": "public" } }));
    vi.stubGlobal("fetch", fetcher);
    const response = await GET(request(), context());
    expect(response.status).toBe(200); expect(response.headers.get("cache-control")).toBe("no-store");
    const [url, options] = fetcher.mock.calls[0] as unknown as [URL, RequestInit];
    expect(url.pathname).toBe("/api/snapshots");
    expect(new Headers(options.headers).get("authorization")).toBe("Bearer synthetic-access-token");
    expect(new Headers(options.headers).get("cookie")).toBeNull();
    expect(JSON.stringify(await response.json())).not.toContain("token");
  });
  it("rejects missing CSRF and foreign origins before forwarding a mutation", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    expect((await POST(request("POST"), context())).status).toBe(403);
    expect((await DELETE(request("DELETE"), context([id]))).status).toBe(403);
    expect((await POST(request("POST", true, "https://foreign.example"), context())).status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("forwards item reads and the fixed compare-live path, refusing other shapes", async () => {
    const fetcher = vi.fn(async () => new Response("{}", { status: 200 })); vi.stubGlobal("fetch", fetcher);
    expect((await GET(request(), context([id]))).status).toBe(200);
    expect((fetcher.mock.calls[0] as unknown as [URL])[0].pathname).toBe(`/api/snapshots/${id}`);
    const compare = new NextRequest(`http://localhost:3000/api/snapshots/${id}/compare-live`, { headers: request().headers });
    expect((await GET(compare, context([id, "compare-live"]))).status).toBe(200);
    expect((fetcher.mock.calls[1] as unknown as [URL])[0].pathname).toBe(`/api/snapshots/${id}/compare-live`);
    expect((await GET(request(), context(["https://evil.example"]))).status).toBe(404);
    expect((await GET(request(), context([id, "arbitrary-subpath"]))).status).toBe(404);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it("allows owner-scoped deletes with CSRF and rejects non-UUID and extra methods", async () => {
    const fetcher = vi.fn(async () => new Response(null, { status: 204 })); vi.stubGlobal("fetch", fetcher);
    expect((await DELETE(request("DELETE", true), context([id]))).status).toBe(204);
    expect((fetcher.mock.calls[0] as unknown as [URL, RequestInit])[1].method).toBe("DELETE");
    expect((await DELETE(request("DELETE", true), context(["not-a-uuid"]))).status).toBe(404);
    expect((await POST(request("POST", true), context([id]))).status).toBe(405);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("rejects unsigned sessions and an oversized freeze body before upstream", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    expect((await GET(new NextRequest("http://localhost:3000/api/snapshots"), context())).status).toBe(401);
    const valid = request("POST", true);
    const large = new NextRequest(valid.url, { method: "POST", headers: valid.headers, body: "x".repeat(2_000_001) });
    expect((await POST(large, context())).status).toBe(413);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
