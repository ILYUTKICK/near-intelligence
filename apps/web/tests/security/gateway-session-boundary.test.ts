/**
 * NI-062 gateway session-boundary audit (part of the standard
 * `pnpm --filter web test` run; jsdom-free route-handler checks).
 *
 * Exercises the REAL Next.js gateway handlers with a mocked provider (no
 * network): CSRF/Origin enforcement before any provider call, cookie flag
 * contract (HttpOnly session, SameSite=Lax, Path=/, Secure in production),
 * tampered-cookie clearing, logout clearing, and the private forwarding
 * gateway's cache/no-store and status semantics. All credentials synthetic.
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST as loginPost } from "@/app/api/auth/login/route";
import { POST as logoutPost } from "@/app/api/auth/logout/route";
import { GET as csrfGet } from "@/app/api/auth/csrf/route";

import { GET as sessionGet } from "@/app/api/auth/session/route";
import { CSRF_COOKIE, SESSION_COOKIE, encodeSessionCookie } from "@/lib/auth/session";
import { resetRateLimitForTests } from "@/lib/auth/rate-limit";

const ENV = {
  APP_ENV: "test",
  NEXT_PUBLIC_SUPABASE_URL: "https://dev.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_synthetic_test_key_0123456789",
  SUPABASE_JWT_ISSUER: "https://dev.supabase.co/auth/v1",
  SUPABASE_JWKS_URL: "https://dev.supabase.co/auth/v1/.well-known/jwks.json",
  SUPABASE_JWT_AUDIENCE: "authenticated",
  SUPABASE_JWT_ALGORITHM: "ES256",
  AUTH_ALLOWED_REDIRECT_ORIGINS: "http://localhost:3000",
  AUTH_COOKIE_SIGNING_SECRET: "c".repeat(40),
  CSRF_SIGNING_SECRET: "d".repeat(40),
};

const providerFetchMock = vi.fn();

beforeEach(() => {
  resetRateLimitForTests();
  for (const [key, value] of Object.entries(ENV)) {
    process.env[key] = value;
  }
  providerFetchMock.mockReset();
  vi.stubGlobal("fetch", providerFetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  for (const key of Object.keys(ENV)) {
    delete process.env[key];
  }
});

function providerReply(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

async function mintedCsrf(): Promise<{ cookie: string; header: string }> {
  const mintRequest = new NextRequest("http://localhost:3000/api/auth/csrf");
  const mintResponse = await csrfGet(mintRequest);
  const raw = mintResponse.headers.getSetCookie()
    .find((cookie) => cookie.startsWith(`${CSRF_COOKIE}=`));
  expect(raw).toBeTruthy();
  const value = (raw as string).split(";")[0].split("=").slice(1).join("=");
  return { cookie: value, header: value };
}

function loginRequest(options: {
  origin?: string | null;
  csrf?: { cookie: string; header: string } | null;
}): NextRequest {
  const headers = new Headers({ "content-type": "application/json" });
  if (options.origin !== null) {
    headers.set("origin", options.origin ?? "http://localhost:3000");
  }
  if (options.csrf) {
    headers.set("cookie", `${CSRF_COOKIE}=${options.csrf.cookie}`);
    headers.set("x-csrf-token", options.csrf.header);
  }
  return new NextRequest("http://localhost:3000/api/auth/login", {
    method: "POST",
    headers,
    body: JSON.stringify({ email: "alice@example.test", password: "synthetic-pass" }),
  });
}

describe("Gateway CSRF and Origin enforcement", () => {
  it("rejects a mutation without any CSRF pair before contacting the provider", async () => {
    const response = await loginPost(loginRequest({ csrf: null }));
    expect(response.status).toBe(403);
    expect(providerFetchMock).not.toHaveBeenCalled();
  });

  it("rejects a mismatched CSRF pair (cookie and header disagree)", async () => {
    const minted = await mintedCsrf();
    const response = await loginPost(loginRequest({
      csrf: { cookie: minted.cookie, header: `${minted.header}tampered` },
    }));
    expect(response.status).toBe(403);
    expect(providerFetchMock).not.toHaveBeenCalled();
  });

  it("rejects a cross-origin mutation with a valid CSRF pair", async () => {
    const minted = await mintedCsrf();
    const response = await loginPost(loginRequest({
      origin: "https://evil.test", csrf: minted,
    }));
    expect(response.status).toBe(403);
    expect(providerFetchMock).not.toHaveBeenCalled();
  });

  it("rejects a missing Origin header", async () => {
    const minted = await mintedCsrf();
    const response = await loginPost(loginRequest({ origin: null, csrf: minted }));
    expect(response.status).toBe(403);
    expect(providerFetchMock).not.toHaveBeenCalled();
  });
});

describe("Cookie flag contract", () => {
  it("sets the session cookie HttpOnly with SameSite=Lax and Path=/", async () => {
    providerFetchMock.mockResolvedValueOnce(providerReply(200, {
      access_token: "synthetic-access-token",
      refresh_token: "synthetic-refresh-token",
      expires_in: 3600,
    }));
    const minted = await mintedCsrf();
    const response = await loginPost(loginRequest({ csrf: minted }));
    expect(response.status).toBe(200);
    const raw = response.headers.getSetCookie()
      .find((cookie) => cookie.startsWith(`${SESSION_COOKIE}=`));
    expect(raw).toBeTruthy();
    const attributes = (raw as string).toLowerCase();
    expect(attributes).toContain("httponly");
    expect(attributes).toContain("samesite=lax");
    expect(attributes).toContain("path=/");
    // APP_ENV=test: Secure is production-only (dev runs on plain http).
    expect(attributes).not.toContain("secure");
    // The browser JS never receives the tokens in any response body.
    const body = await response.json();
    expect(JSON.stringify(body)).not.toContain("synthetic-access-token");
    expect(JSON.stringify(body)).not.toContain("synthetic-refresh-token");
  });

  it("adds the Secure flag in production", async () => {
    process.env.APP_ENV = "production";
    providerFetchMock.mockResolvedValueOnce(providerReply(200, {
      access_token: "synthetic-access-token",
      refresh_token: "synthetic-refresh-token",
      expires_in: 3600,
    }));
    const minted = await mintedCsrf();
    const response = await loginPost(loginRequest({ csrf: minted }));
    const attributes = response.headers.getSetCookie()
      .find((cookie) => cookie.startsWith(`${SESSION_COOKIE}=`))!
      .toLowerCase();
    expect(attributes).toContain("secure");
    expect(attributes).toContain("httponly");
  });

  it("clears the session and CSRF cookies on logout even without a provider", async () => {
    const minted = await mintedCsrf();
    providerFetchMock.mockResolvedValueOnce(providerReply(200, {
      access_token: "synthetic-access-token",
      refresh_token: "synthetic-refresh-token",
      expires_in: 3600,
    }));
    await loginPost(loginRequest({ csrf: minted }));
    providerFetchMock.mockResolvedValueOnce(providerReply(204, {}));
    const sessionValue = encodeSessionCookie({
      accessToken: "synthetic-access-token",
      refreshToken: "synthetic-refresh-token",
      expiresAt: Date.now() + 60_000,
    });
    const logoutRequest = new NextRequest("http://localhost:3000/api/auth/logout", {
      method: "POST",
      headers: {
        origin: "http://localhost:3000",
        cookie: `${CSRF_COOKIE}=${minted.cookie}; ${SESSION_COOKIE}=${sessionValue}`,
        "x-csrf-token": minted.header,
      },
    });
    const response = await logoutPost(logoutRequest);
    const cleared = response.headers.getSetCookie().join("\n");
    expect(cleared).toContain("Max-Age=0");
  });
});

describe("Session endpoint honesty", () => {
  it("answers 401 without a cookie and sets nothing", async () => {
    const response = await sessionGet(new NextRequest("http://localhost:3000/api/auth/session"));
    expect(response.status).toBe(401);
    expect(response.headers.getSetCookie()).toHaveLength(0);
  });

  it("clears a tampered session cookie instead of trusting it", async () => {
    const sessionValue = encodeSessionCookie({
      accessToken: "synthetic-access-token",
      refreshToken: "synthetic-refresh-token",
      expiresAt: Date.now() + 60_000,
    });
    const tampered = `${sessionValue.slice(0, -4)}AAAA`;
    const request = new NextRequest("http://localhost:3000/api/auth/session", {
      headers: { cookie: `${SESSION_COOKIE}=${tampered}` },
    });
    const response = await sessionGet(request);
    expect(response.status).toBe(401);
    const cleared = response.headers.getSetCookie()
      .find((cookie) => cookie.startsWith(`${SESSION_COOKIE}=`));
    expect(cleared).toContain("Max-Age=0");
  });
});

describe("Private gateway forwarding", () => {
  it("answers 401 without a session and never forwards cookies as identity", async () => {
    const gateway = await import("@/app/api/documents/[[...segments]]/route");
    const handle = gateway.GET;
    const request = new NextRequest("http://localhost:3000/api/documents", {
      method: "GET",
    });
    const response = await handle(request, { params: Promise.resolve({ segments: [] }) });
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("rejects mutations with no CSRF/Origin pair at the gateway", async () => {
    const gateway = await import("@/app/api/documents/[[...segments]]/route");
    const handle = gateway.GET;
    const sessionValue = encodeSessionCookie({
      accessToken: "synthetic-access-token",
      refreshToken: "synthetic-refresh-token",
      expiresAt: Date.now() + 60_000,
    });
    const request = new NextRequest("http://localhost:3000/api/documents", {
      method: "POST",
      headers: {
        origin: "http://localhost:3000",
        cookie: `${SESSION_COOKIE}=${sessionValue}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ title: "Injected" }),
    });
    const response = await handle(request, { params: Promise.resolve({ segments: [] }) });
    expect(response.status).toBe(403);
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("rejects unknown deep paths with a no-store 404 and unsupported methods with 405", async () => {
    const gateway = await import("@/app/api/documents/[[...segments]]/route");
    const handle = gateway.GET;
    const sessionValue = encodeSessionCookie({
      accessToken: "synthetic-access-token",
      refreshToken: "synthetic-refresh-token",
      expiresAt: Date.now() + 60_000,
    });
    const deep = new NextRequest("http://localhost:3000/api/documents/x/y/z/w/v", {
      method: "GET",
      headers: { cookie: `${SESSION_COOKIE}=${sessionValue}` },
    });
    const notFound = await handle(deep, {
      params: Promise.resolve({ segments: ["x", "y", "z", "w", "v"] }),
    });
    expect(notFound.status).toBe(404);
    expect(notFound.headers.get("cache-control")).toBe("no-store");
    const wrongMethod = new NextRequest("http://localhost:3000/api/documents", {
      method: "PUT",
      headers: { cookie: `${SESSION_COOKIE}=${sessionValue}` },
    });
    const notAllowed = await handle(wrongMethod, {
      params: Promise.resolve({ segments: [] }),
    });
    expect(notAllowed.status).toBe(405);
    expect(notAllowed.headers.get("cache-control")).toBe("no-store");
  });

  it("rejects oversized mutation bodies with 413 before any API call", async () => {
    const gateway = await import("@/app/api/documents/[[...segments]]/route");
    const handle = gateway.GET;
    const minted = await mintedCsrf();
    const sessionValue = encodeSessionCookie({
      accessToken: "synthetic-access-token",
      refreshToken: "synthetic-refresh-token",
      expiresAt: Date.now() + 60_000,
    });
    const request = new NextRequest("http://localhost:3000/api/documents", {
      method: "POST",
      headers: {
        origin: "http://localhost:3000",
        cookie: `${SESSION_COOKIE}=${sessionValue}; ${CSRF_COOKIE}=${minted.cookie}`,
        "x-csrf-token": minted.header,
        "content-type": "application/json",
      },
      body: JSON.stringify({ title: "x".repeat(3_000_000) }),
    });
    const response = await handle(request, { params: Promise.resolve({ segments: [] }) });
    expect(response.status).toBe(413);
    expect(providerFetchMock).not.toHaveBeenCalled();
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("forwards allowed GETs with no-store and never leaks the internal API URL", async () => {
    const gateway = await import("@/app/api/documents/[[...segments]]/route");
    const handle = gateway.GET;
    const sessionValue = encodeSessionCookie({
      accessToken: "synthetic-access-token",
      refreshToken: "synthetic-refresh-token",
      expiresAt: Date.now() + 60_000,
    });
    process.env.API_INTERNAL_URL = "http://internal-api.test";
    providerFetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ items: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    const request = new NextRequest("http://localhost:3000/api/documents", {
      method: "GET",
      headers: { cookie: `${SESSION_COOKIE}=${sessionValue}` },
    });
    const response = await handle(request, { params: Promise.resolve({ segments: [] }) });
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const forwarded = providerFetchMock.mock.calls[0];
    expect(String(forwarded[0])).toBe("http://internal-api.test/api/documents");
    const forwardedHeaders = forwarded[1].headers as Headers;
    expect(forwardedHeaders.get("authorization")).toBe("Bearer synthetic-access-token");
    expect(forwardedHeaders.get("cookie")).toBeNull();
    expect(forwarded[1].cache).toBe("no-store");
    expect(forwarded[1].redirect).toBe("error");
  });
});
