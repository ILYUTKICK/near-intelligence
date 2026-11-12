import { NextRequest } from "next/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/publications/[[...segments]]/route";
import { privateFetch } from "@/lib/auth/private-fetch";
import { CSRF_COOKIE, SESSION_COOKIE, encodeSessionCookie, mintCsrfToken } from "@/lib/auth/session";

const web = "http://localhost:3000";
const api = "http://localhost:8000";
const slug = "synthetic-release";
const path = `/api/publications/${slug}`;
const duplicate = `${path}/duplicate`;
const publicContext = { params: Promise.resolve({ segments: [slug] }) };
const privateContext = { params: Promise.resolve({ segments: [slug, "duplicate"] }) };

beforeEach(() => {
  const environment = {
    APP_ENV: "test", APP_ORIGIN: web, API_INTERNAL_URL: api,
    NEXT_PUBLIC_SUPABASE_URL: "https://synthetic.supabase.co",
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_synthetic_key_0123456789",
    SUPABASE_JWT_ISSUER: "https://synthetic.supabase.co/auth/v1",
    SUPABASE_JWKS_URL: "https://synthetic.supabase.co/auth/v1/.well-known/jwks.json",
    SUPABASE_JWT_AUDIENCE: "authenticated", SUPABASE_JWT_ALGORITHM: "ES256",
    AUTH_ALLOWED_REDIRECT_ORIGINS: web,
    AUTH_COOKIE_SIGNING_SECRET: "synthetic-cookie-secret-01234567890123456789",
    CSRF_SIGNING_SECRET: "synthetic-csrf-secret-01234567890123456789",
  };
  for (const [name, value] of Object.entries(environment)) vi.stubEnv(name, value);
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

it("serves an exact public version without forwarding account headers", async () => {
  const cache = "public, max-age=31536000, immutable";
  const upstream = vi.fn<(url: URL, init: RequestInit) => Promise<Response>>(async () =>
    Response.json({ version: 2 }, { headers: { "cache-control": cache, etag: '"synthetic-pin"' } }));
  vi.stubGlobal("fetch", upstream);
  const response = await GET(new NextRequest(`${web}${path}?version=2`, {
    headers: { authorization: "Bearer synthetic", cookie: "synthetic=private" },
  }), publicContext);
  expect(await response.json()).toEqual({ version: 2 });
  expect(response.headers.get("cache-control")).toBe(cache);
  expect(response.headers.get("etag")).toBe('"synthetic-pin"');
  const [[url, init]] = upstream.mock.calls;
  expect(url.href).toBe(`${api}${path}?version=2`);
  expect(new Headers(init.headers).has("authorization")).toBe(false);
  expect(new Headers(init.headers).has("cookie")).toBe(false);
  expect((await GET(new NextRequest(`${web}${path}?version=2&version=3`), publicContext)).status).toBe(422);
  expect(upstream).toHaveBeenCalledOnce();
});

it("requires CSRF and forwards a confirmed copy with the verified bearer and exact body", async () => {
  const token = mintCsrfToken();
  const bearer = (sub: string) => `synthetic.${Buffer.from(JSON.stringify({ sub })).toString("base64url")}.synthetic`;
  const sessionCookie = (sub: string) => {
    const session = encodeSessionCookie({ accessToken: bearer(sub), refreshToken: "synthetic-refresh", expiresAt: Date.now() + 60_000 });
    return `${SESSION_COOKIE}=${session}; ${CSRF_COOKIE}=${token}`;
  };
  const cookie = sessionCookie("synthetic-alice");
  const upstream = vi.fn<(url: URL, init: RequestInit) => Promise<Response>>(async () =>
    Response.json({}, { status: 201, headers: { etag: '"2"' } }));
  vi.stubGlobal("fetch", vi.fn(async (input: string | URL, init: RequestInit = {}) => {
    if (input === "/api/auth/csrf") return Response.json({ token });
    if (input === duplicate) {
      const headers = new Headers(init.headers);
      headers.set("origin", web);
      headers.set("cookie", cookie);
      return POST(new NextRequest(`${web}${duplicate}`, {
        method: init.method, headers, body: init.body, signal: init.signal ?? undefined,
      }), privateContext);
    }
    if (input instanceof URL) return upstream(input, init);
    throw new Error(`Unexpected synthetic request ${input}`);
  }));

  const body = JSON.stringify({ publication_version: 2, title: "Synthetic private copy" });
  const key = "44444444-4444-4444-8444-444444444444";
  const headers = { "content-type": "application/json", "idempotency-key": key,
    "x-session-subject": "synthetic-alice", authorization: "Bearer synthetic-other" };
  expect((await POST(new NextRequest(`${web}${duplicate}`, {
    method: "POST", headers: { ...headers, origin: web, cookie }, body,
  }), privateContext)).status).toBe(403);
  expect((await POST(new NextRequest(`${web}${duplicate}?version=3`, {
    method: "POST", headers: { ...headers, origin: web, cookie, "x-csrf-token": token }, body,
  }), privateContext)).status).toBe(422);
  const switched = await POST(new NextRequest(`${web}${duplicate}`, {
    method: "POST", headers: { ...headers, origin: web, cookie: sessionCookie("synthetic-bob"), "x-csrf-token": token }, body,
  }), privateContext);
  expect(switched.status).toBe(409);
  expect(upstream).not.toHaveBeenCalled();
  const response = await privateFetch(duplicate, { method: "POST", headers, body });
  expect(response.status).toBe(201);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(response.headers.get("etag")).toBe('"2"');
  expect(upstream).toHaveBeenCalledOnce();
  const [[url, init]] = upstream.mock.calls;
  expect(url.href).toBe(`${api}${duplicate}`);
  expect(init.body).toBe(body);
  const forwarded = new Headers(init.headers);
  expect(forwarded.get("authorization")).toBe(`Bearer ${bearer("synthetic-alice")}`);
  expect(forwarded.get("idempotency-key")).toBe(key);
  expect(forwarded.has("cookie")).toBe(false);
  expect(forwarded.has("x-session-subject")).toBe(false);
});
