/**
 * NI-020 session boundary tests: session endpoint honesty, refresh
 * rotation/revocation, and the per-IP rate guard. Provider mocked; all
 * credentials synthetic.
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET as sessionGet } from "@/app/api/auth/session/route";
import { POST as refreshPost } from "@/app/api/auth/refresh/route";
import { SESSION_COOKIE, encodeSessionCookie } from "@/lib/auth/session";
import { checkRateLimit, resetRateLimitForTests } from "@/lib/auth/rate-limit";

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

// A JWT-shaped access token whose payload carries a UUID sub (signature is
// irrelevant to the gateway session check — the HMAC cookie is the boundary).
const SUB = "3416c49d-6e73-4397-bac2-1a53c3e31af6";
const ACCESS_TOKEN = `eyJhbGciOiJFUzI1NiJ9.${Buffer.from(JSON.stringify({ sub: SUB })).toString("base64url")}.sig`;

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

function sessionRequest(sessionValue?: string): NextRequest {
  const headers = new Headers();
  if (sessionValue) {
    headers.set("cookie", `${SESSION_COOKIE}=${sessionValue}`);
  }
  return new NextRequest("http://localhost:3000/api/auth/session", { headers });
}

describe("Session endpoint", () => {
  it("returns the subject and expiry for a valid signed session", async () => {
    const value = encodeSessionCookie({
      accessToken: ACCESS_TOKEN,
      refreshToken: "r",
      expiresAt: Date.now() + 600_000,
    });
    const response = await sessionGet(sessionRequest(value));
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.subject).toBe(SUB);
    expect(body.status).toBe("ok");
  });

  it("clears an expired or tampered cookie and answers 401", async () => {
    const expired = encodeSessionCookie({
      accessToken: ACCESS_TOKEN,
      refreshToken: "r",
      expiresAt: Date.now() - 1000,
    });
    const response = await sessionGet(sessionRequest(expired));
    expect(response.status).toBe(401);
    expect(response.headers.getSetCookie().find((c) => c.startsWith("ni_session="))).toContain("Max-Age=0");

    const tampered = await sessionGet(sessionRequest("tampered.payload.sig"));
    expect(tampered.status).toBe(401);
  });

  it("answers 401 without a cookie and sets nothing", async () => {
    const response = await sessionGet(sessionRequest());
    expect(response.status).toBe(401);
    expect(response.headers.getSetCookie()).toHaveLength(0);
  });
});

describe("Refresh rotation", () => {
  function refreshRequest(sessionValue?: string): NextRequest {
    const headers = new Headers({ origin: "http://localhost:3000" });
    if (sessionValue) {
      headers.set("cookie", `${SESSION_COOKIE}=${sessionValue}`);
    }
    return new NextRequest("http://localhost:3000/api/auth/refresh", { method: "POST", headers });
  }

  it("rotates both tokens and re-signs the session cookie", async () => {
    const value = encodeSessionCookie({
      accessToken: "old",
      refreshToken: "old-refresh",
      expiresAt: Date.now() + 600_000,
    });
    providerFetchMock.mockResolvedValueOnce(
      providerReply(200, { access_token: "new", refresh_token: "new-refresh", expires_in: 3600 }),
    );
    const response = await refreshPost(refreshRequest(value));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "refreshed" });
    expect(String(providerFetchMock.mock.calls[0][0])).toContain("grant_type=refresh_token");
    const cookie = response.headers
      .getSetCookie()
      .find((c) => c.startsWith("ni_session="));
    expect(cookie).toContain("HttpOnly");
    // The rotated cookie must decode to the NEW refresh token.
    const raw = (cookie as string).split(";")[0].split("=").slice(1).join("=");
    const payload = JSON.parse(Buffer.from(raw.split(".")[0], "base64url").toString("utf8"));
    expect(payload.refreshToken).toBe("new-refresh");
  });

  it("clears the session honestly when the refresh token is revoked", async () => {
    const value = encodeSessionCookie({
      accessToken: "old",
      refreshToken: "revoked",
      expiresAt: Date.now() + 600_000,
    });
    providerFetchMock.mockResolvedValueOnce(
      providerReply(400, { error: "invalid_grant", error_description: "Refresh Token Not Found" }),
    );
    const response = await refreshPost(refreshRequest(value));
    expect(response.status).toBe(401);
    expect((await response.json()).error).toMatch(/sign in again/i);
    expect(response.headers.getSetCookie().find((c) => c.startsWith("ni_session="))).toContain("Max-Age=0");
  });

  it("keeps the cookie on provider outage and reports 503", async () => {
    const value = encodeSessionCookie({
      accessToken: "old",
      refreshToken: "r",
      expiresAt: Date.now() + 600_000,
    });
    providerFetchMock.mockRejectedValueOnce(new Error("network down"));
    const response = await refreshPost(refreshRequest(value));
    expect(response.status).toBe(503);
    // No clearing: the client can retry once the provider recovers.
    expect(response.headers.getSetCookie().find((c) => c.startsWith("ni_session="))).toBeUndefined();
  });
});

describe("Per-IP rate guard", () => {
  it("allows five login attempts per minute and blocks the sixth", () => {
    const key = "login:203.0.113.9";
    for (let i = 0; i < 5; i += 1) {
      expect(checkRateLimit(key, 5, 60_000).allowed).toBe(true);
    }
    const blocked = checkRateLimit(key, 5, 60_000);
    expect(blocked.allowed).toBe(false);
    expect(blocked.retryAfterSeconds).toBeGreaterThan(0);
    // Another IP is unaffected.
    expect(checkRateLimit("login:198.51.100.7", 5, 60_000).allowed).toBe(true);
  });
});

function providerReply(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}
