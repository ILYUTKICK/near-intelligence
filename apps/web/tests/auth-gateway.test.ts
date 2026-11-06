/**
 * NI-017 gateway tests against a mocked Supabase Auth provider.
 * All credentials/tokens below are synthetic; the real provider round trip
 * is a separate open criterion (NI-016 operator handoff, NI-020 E2E).
 */
import { NextRequest, NextResponse } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST as loginPost } from "@/app/api/auth/login/route";
import { POST as logoutPost } from "@/app/api/auth/logout/route";
import { GET as csrfGet } from "@/app/api/auth/csrf/route";
import { GET as callbackGet } from "@/app/auth/callback/route";
import { CSRF_COOKIE, SESSION_COOKIE, encodeSessionCookie } from "@/lib/auth/session";

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

function providerReply(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

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

function loginRequest(options: {
  origin?: string | null;
  csrfCookie?: string;
  csrfHeader?: string | null;
  body?: unknown;
  rawBody?: string;
}): NextRequest {
  const headers = new Headers({ "content-type": "application/json" });
  if (options.origin !== null) {
    headers.set("origin", options.origin ?? "http://localhost:3000");
  }
  const cookies: string[] = [];
  if (options.csrfCookie) {
    cookies.push(`${CSRF_COOKIE}=${options.csrfCookie}`);
  }
  if (cookies.length > 0) {
    headers.set("cookie", cookies.join("; "));
  }
  if (options.csrfHeader !== null) {
    headers.set("x-csrf-token", options.csrfHeader ?? options.csrfCookie ?? "");
  }
  return new NextRequest("http://localhost:3000/api/auth/login", {
    method: "POST",
    headers,
    body: options.rawBody ?? JSON.stringify(options.body ?? { email: "a@b.c", password: "secret" }),
  });
}

function setCookies(response: NextResponse): string[] {
  return response.headers.getSetCookie();
}

function findCookie(cookies: string[], name: string): string | null {
  return cookies.find((cookie) => cookie.startsWith(`${name}=`)) ?? null;
}

describe("CSRF minting", () => {
  it("sets a readable double-submit cookie and returns the token", async () => {
    const response = await csrfGet();
    expect(response.status).toBe(200);
    const cookie = findCookie(setCookies(response), CSRF_COOKIE);
    expect(cookie).toMatch(/samesite=lax/i);
    expect(cookie).not.toContain("HttpOnly");
    const body = await response.json();
    expect(cookie).toContain(body.token);
  });
});

describe("Login gateway", () => {
  it("mints a token then accepts a same-origin login with valid CSRF and sets HttpOnly cookies", async () => {
    const minted = await csrfGet();
    const { token } = (await minted.json()) as { token: string };
    providerFetchMock.mockResolvedValueOnce(
      providerReply(200, { access_token: "access.jwt.sig", refresh_token: "refresh-1", expires_in: 600 }),
    );
    const response = await loginPost(
      loginRequest({ csrfCookie: token, body: { email: "alice@example.test", password: "pw" } }),
    );
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.returnTo).toBe("/");

    const cookies = setCookies(response);
    const session = findCookie(cookies, SESSION_COOKIE);
    expect(session).toBeTruthy();
    expect(session).toContain("HttpOnly");
    expect(session).toMatch(/samesite=lax/i);
    expect(session).toContain("Path=/");
    // Provider calls carried the publishable key, never a service credential.
    const [url, init] = providerFetchMock.mock.calls[0];
    expect(String(url)).toBe("https://dev.supabase.co/auth/v1/token?grant_type=password");
    expect((init.headers as Record<string, string>).apikey).toMatch(/^sb_publishable_/);
  });

  it("preserves a safe internal returnTo and rejects external redirects", async () => {
    providerFetchMock.mockResolvedValue(
      providerReply(200, { access_token: "a", refresh_token: "r", expires_in: 600 }),
    );
    const minted = await csrfGet();
    const { token } = (await minted.json()) as { token: string };

    const internal = await loginPost(
      loginRequest({ csrfCookie: token, body: { email: "a@b.c", password: "pw", returnTo: "/workspace/research" } }),
    );
    expect((await internal.json()).returnTo).toBe("/workspace/research");

    const external = await loginPost(
      loginRequest({ csrfCookie: token, body: { email: "a@b.c", password: "pw", returnTo: "https://evil.example" } }),
    );
    expect((await external.json()).returnTo).toBe("/");

    const protocolRelative = await loginPost(
      loginRequest({ csrfCookie: token, body: { email: "a@b.c", password: "pw", returnTo: "//evil.example" } }),
    );
    expect((await protocolRelative.json()).returnTo).toBe("/");
  });

  it("rejects cross-origin, missing CSRF and malformed requests before the provider", async () => {
    providerFetchMock.mockResolvedValue(providerReply(200, {}));
    const cases: Array<[string, NextRequest]> = [
      ["cross origin", loginRequest({ origin: "https://evil.example" })],
      ["no origin", loginRequest({ origin: null })],
      ["no csrf pair", loginRequest({})],
      ["csrf mismatch", loginRequest({ csrfCookie: "aaa.bbb", csrfHeader: "ccc.ddd" })],
      ["malformed body", loginRequest({ csrfCookie: "x", rawBody: "not-json" })],
      ["missing fields", loginRequest({ csrfCookie: "x", body: { email: "a@b.c" } })],
    ];
    for (const [name, request] of cases) {
      const response = await loginPost(request);
      expect(response.status, name).toBe(403);
      expect(providerFetchMock, name).not.toHaveBeenCalled();
    }
  });

  it("returns one generic error for wrong password and unknown email", async () => {
    const minted = await csrfGet();
    const { token } = (await minted.json()) as { token: string };
    providerFetchMock.mockResolvedValueOnce(providerReply(400, { msg: "Invalid login credentials" }));
    const wrongPassword = await loginPost(
      loginRequest({ csrfCookie: token, body: { email: "alice@example.test", password: "wrong" } }),
    );
    expect(wrongPassword.status).toBe(401);
    expect((await wrongPassword.json()).error).toBe("Invalid email or password.");

    providerFetchMock.mockResolvedValueOnce(providerReply(400, { msg: "Email not confirmed" }));
    const unknownUser = await loginPost(
      loginRequest({ csrfCookie: token, body: { email: "nobody@example.test", password: "whatever" } }),
    );
    expect(unknownUser.status).toBe(401);
    expect((await unknownUser.json()).error).toBe("Invalid email or password.");
  });

  it("maps provider rate limits and outages to honest statuses", async () => {
    const minted = await csrfGet();
    const { token } = (await minted.json()) as { token: string };
    providerFetchMock.mockResolvedValueOnce(providerReply(429, {}));
    const limited = await loginPost(loginRequest({ csrfCookie: token }));
    expect(limited.status).toBe(429);

    providerFetchMock.mockRejectedValueOnce(new Error("network down"));
    const unreachable = await loginPost(loginRequest({ csrfCookie: token }));
    expect(unreachable.status).toBe(503);
  });
});

describe("Logout gateway", () => {
  async function logoutRequest(sessionCookie?: string) {
    const headers = new Headers({ origin: "http://localhost:3000" });
    const cookies: string[] = [];
    if (sessionCookie) {
      cookies.push(`${SESSION_COOKIE}=${sessionCookie}`);
    }
    // A real minted token: the gateway verifies the signed payload, not just equality.
    const minted = await csrfGet();
    const csrfToken = ((await minted.json()) as { token: string }).token;
    cookies.push(`${CSRF_COOKIE}=${csrfToken}`);
    headers.set("cookie", cookies.join("; "));
    headers.set("x-csrf-token", csrfToken);
    return new NextRequest("http://localhost:3000/api/auth/logout", { method: "POST", headers });
  }

  it("revokes the provider session and clears cookies", async () => {
    const sessionValue = encodeSessionCookie({
      accessToken: "a",
      refreshToken: "r",
      expiresAt: Date.now() + 600_000,
    });
    providerFetchMock.mockResolvedValueOnce(providerReply(204, {}));
    const response = await logoutPost(await logoutRequest(sessionValue));
    expect(response.status).toBe(200);
    expect(String(providerFetchMock.mock.calls[0][0])).toContain("logout?scope=global");
    const cookies = setCookies(response);
    for (const cookie of [findCookie(cookies, SESSION_COOKIE), findCookie(cookies, CSRF_COOKIE)]) {
      expect(cookie).toContain("Max-Age=0");
    }
  });

  it("clears cookies even when the provider is unreachable and reports honest state", async () => {
    const sessionValue = encodeSessionCookie({
      accessToken: "a",
      refreshToken: "r",
      expiresAt: Date.now() + 600_000,
    });
    providerFetchMock.mockRejectedValueOnce(new Error("network down"));
    const response = await logoutPost(await logoutRequest(sessionValue));
    expect(response.status).toBe(503);
    expect((await response.json()).error).toContain("provider could not be reached");
    const cookies = setCookies(response);
    expect(findCookie(cookies, SESSION_COOKIE)).toContain("Max-Age=0");
  });

  it("succeeds without a session cookie", async () => {
    const response = await logoutPost(await logoutRequest());
    expect(response.status).toBe(200);
    expect(providerFetchMock).not.toHaveBeenCalled();
    expect(findCookie(setCookies(response), SESSION_COOKIE)).toContain("Max-Age=0");
  });
});

describe("Email-link callback", () => {
  function callbackRequest(params: Record<string, string | undefined>): NextRequest {
    const url = new URL("http://localhost:3000/auth/callback");
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        url.searchParams.set(key, value);
      }
    }
    return new NextRequest(url);
  }

  it("exchanges a valid signup link for HttpOnly cookies and redirects internally", async () => {
    providerFetchMock.mockResolvedValueOnce(
      providerReply(200, { access_token: "access", refresh_token: "refresh", expires_in: 600 }),
    );
    const response = await callbackGet(
      callbackRequest({ token_hash: "hash-1", type: "signup", return_to: "/workspace" }),
    );
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/workspace");
    const session = findCookie(response.headers.getSetCookie(), SESSION_COOKIE);
    expect(session).toContain("HttpOnly");
    expect(String(providerFetchMock.mock.calls[0][0])).toContain("/auth/v1/verify");
  });

  it("rejects missing or invalid link parameters before calling the provider", async () => {
    for (const params of [
      { type: "signup" },
      { token_hash: "hash-1", type: "magiclink" },
    ]) {
      const response = await callbackGet(callbackRequest(params));
      expect(response.status).toBe(307);
      const location = new URL(response.headers.get("location") as string);
      expect(location.pathname).toBe("/login");
      expect(location.search).toBe("?error=invalid_link");
      expect(providerFetchMock).not.toHaveBeenCalled();
    }
  });

  it("sanitizes external return targets to internal paths", async () => {
    providerFetchMock.mockResolvedValue(
      providerReply(200, { access_token: "access", refresh_token: "refresh", expires_in: 600 }),
    );
    for (const return_to of ["https://evil.example", "//evil.example", "/\\evil"]) {
      const response = await callbackGet(callbackRequest({ token_hash: "h", type: "signup", return_to }));
      expect(response.status).toBe(307);
      const location = new URL(response.headers.get("location") as string);
      expect(location.pathname).toBe("/");
      expect(location.host).toBe("localhost:3000");
    }
  });

  it("maps expired or used links to a generic expired error", async () => {
    providerFetchMock.mockResolvedValueOnce(providerReply(400, { msg: "Email link is invalid or has expired" }));
    const response = await callbackGet(callbackRequest({ token_hash: "old", type: "recovery" }));
    expect(response.headers.get("location")).toContain("error=expired_link");
  });
});
