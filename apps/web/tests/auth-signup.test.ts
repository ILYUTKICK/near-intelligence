/**
 * NI-017 signup flow tests against a mocked provider. All credentials are
 * synthetic; the real confirmation-email round trip is the operator's E2E.
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST as signupPost } from "@/app/api/auth/signup/route";
import { GET as csrfGet } from "@/app/api/auth/csrf/route";
import { CSRF_COOKIE } from "@/lib/auth/session";

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

async function signupRequest(options: {
  origin?: string | null;
  body?: unknown;
  withoutCsrf?: boolean;
}): Promise<NextRequest> {
  const headers = new Headers({ "content-type": "application/json" });
  if (options.origin !== null) {
    headers.set("origin", options.origin ?? "http://localhost:3000");
  }
  let csrfToken = "";
  if (!options.withoutCsrf) {
    const minted = await csrfGet();
    csrfToken = ((await minted.json()) as { token: string }).token;
    headers.set("cookie", `${CSRF_COOKIE}=${csrfToken}`);
    headers.set("x-csrf-token", csrfToken);
  }
  return new NextRequest("http://localhost:3000/api/auth/signup", {
    method: "POST",
    headers,
    body: JSON.stringify(options.body ?? { email: "real.user@example.test", password: "strong-pass-123" }),
  });
}

function providerReply(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

describe("Signup gateway", () => {
  it("reports confirmation_sent and sets no session when the provider requires email confirmation", async () => {
    providerFetchMock.mockResolvedValueOnce(providerReply(200, { identity_id: "x" }));
    const response = await signupPost(await signupRequest({}));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "confirmation_sent" });
    const session = response.headers.getSetCookie().find((cookie) => cookie.startsWith("ni_session="));
    expect(session).toBeUndefined();
    expect(String(providerFetchMock.mock.calls[0][0])).toContain("/auth/v1/signup");
  });

  it("sets the session immediately when the provider auto-confirms", async () => {
    providerFetchMock.mockResolvedValueOnce(
      providerReply(200, { access_token: "access", refresh_token: "refresh", expires_in: 600 }),
    );
    const response = await signupPost(await signupRequest({}));
    expect(await response.json()).toEqual({ status: "session" });
    const session = response.headers
      .getSetCookie()
      .find((cookie) => cookie.startsWith("ni_session="));
    expect(session).toContain("HttpOnly");
  });

  it("distinguishes an already-registered email with a helpful message", async () => {
    providerFetchMock.mockResolvedValueOnce(providerReply(422, { msg: "User already registered" }));
    const response = await signupPost(await signupRequest({}));
    expect(response.status).toBe(422);
    expect((await response.json()).error).toMatch(/already registered/i);
  });

  it("rejects cross-origin requests and missing CSRF before the provider", async () => {
    providerFetchMock.mockResolvedValue(providerReply(200, {}));
    const crossOrigin = await signupPost(await signupRequest({ origin: "https://evil.example" }));
    expect(crossOrigin.status).toBe(403);
    const noCsrf = await signupPost(await signupRequest({ withoutCsrf: true }));
    expect(noCsrf.status).toBe(403);
    expect(providerFetchMock).not.toHaveBeenCalled();
  });

  it("validates the payload shape before the provider", async () => {
    const weak = await signupPost(
      await signupRequest({ body: { email: "not-an-email", password: "123" } }),
    );
    expect(weak.status).toBe(400);
    expect(providerFetchMock).not.toHaveBeenCalled();
  });

  it("maps provider rate limits and outages honestly", async () => {
    providerFetchMock.mockResolvedValueOnce(providerReply(429, {}));
    const limited = await signupPost(await signupRequest({}));
    expect(limited.status).toBe(429);
    providerFetchMock.mockRejectedValueOnce(new Error("network down"));
    const unreachable = await signupPost(await signupRequest({}));
    expect(unreachable.status).toBe(503);
  });
});
