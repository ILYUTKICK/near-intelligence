/**
 * NI-017 demo sign-in tests against a mocked provider (anonymous sign-ins).
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST as demoPost } from "@/app/api/auth/demo/route";
import { GET as csrfGet } from "@/app/api/auth/csrf/route";
import { SESSION_COOKIE } from "@/lib/auth/session";
import { resetRateLimitForTests } from "@/lib/auth/rate-limit";

const ENV = {
  APP_ENV: "test",
  APP_ORIGIN: "http://localhost:3000",
  API_INTERNAL_URL: "http://localhost:8000",
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
  providerFetchMock.mockResolvedValue(providerReply(201, {}));
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

async function demoRequest(options: {
  origin?: string | null;
  displayEmail?: string;
  returnTo?: string;
  withoutCsrf?: boolean;
}): Promise<NextRequest> {
  const headers = new Headers({ "content-type": "application/json" });
  if (options.origin !== null) {
    headers.set("origin", options.origin ?? "http://localhost:3000");
  }
  if (!options.withoutCsrf) {
    const minted = await csrfGet(new NextRequest("http://localhost:3000/api/auth/csrf"));
    const token = ((await minted.json()) as { token: string }).token;
    headers.set("cookie", `${SESSION_COOKIE === "ni_session" ? "ni_csrf" : "ni_csrf"}=${token}`);
    headers.set("x-csrf-token", token);
  }
  return new NextRequest("http://localhost:3000/api/auth/demo", {
    method: "POST",
    headers,
    body: JSON.stringify({ displayEmail: options.displayEmail ?? "visitor@example.test", returnTo: options.returnTo }),
  });
}

describe("Demo sign-in", () => {
  it("creates a real anonymous provider session and sets HttpOnly cookies", async () => {
    providerFetchMock.mockResolvedValueOnce(
      providerReply(200, { access_token: "access", refresh_token: "refresh", expires_in: 600 }),
    );
    const response = await demoPost(await demoRequest({ displayEmail: "visitor@example.test" }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "session", demo: true, returnTo: "/workspace" });
    const session = response.headers.getSetCookie().find((c) => c.startsWith("ni_session="));
    expect(session).toContain("HttpOnly");
    const [url, init] = providerFetchMock.mock.calls[0];
    expect(String(url)).toContain("/auth/v1/signup");
    const sentBody = JSON.parse(init.body as string);
    expect(sentBody.is_anonymous).toBe(true);
    expect(sentBody.data.demo_email_label).toBe("visitor@example.test");
  });

  it("preserves an internal chart continuation and rejects external targets", async () => {
    for (const [returnTo, expected] of [["/charts/intents-volume?dataset_version=synthetic", "/charts/intents-volume?dataset_version=synthetic"], ["https://foreign.example", "/workspace"], ["//foreign.example", "/workspace"]]) {
      providerFetchMock.mockResolvedValueOnce(providerReply(200, { access_token: "synthetic-access", refresh_token: "synthetic-refresh", expires_in: 600 }));
      const response = await demoPost(await demoRequest({ returnTo }));
      expect((await response.json()).returnTo).toBe(expected);
    }
  });

  it("rejects empty or invalid labels before contacting the provider", async () => {
    for (const displayEmail of ["", "not-an-email", "x".repeat(255) + "@example.test"]) {
      const response = await demoPost(await demoRequest({ displayEmail }));
      expect(response.status).toBe(400);
    }
    expect(providerFetchMock).not.toHaveBeenCalled();
  });

  it("rejects malformed request bodies without an exception or provider call", async () => {
    for (const body of ["null", "[]", "42", "invalid JSON"]) {
      const request = await demoRequest({});
      const response = await demoPost(new NextRequest(request.url, {
        method: "POST", headers: request.headers, body,
      }));
      expect(response.status).toBe(400);
    }
    expect(providerFetchMock).not.toHaveBeenCalled();
  });

  it("creates the starter template under the bearer identity, never an email owner", async () => {
    providerFetchMock.mockResolvedValueOnce(providerReply(200, {
      access_token: "access", refresh_token: "refresh", expires_in: 600,
    }));
    const response = await demoPost(await demoRequest({ displayEmail: " visitor@example.test " }));
    expect(response.status).toBe(200);
    const [url, init] = providerFetchMock.mock.calls[1];
    expect(String(url)).toBe("http://localhost:8000/api/documents");
    expect(init.headers.authorization).toBe("Bearer access");
    expect(JSON.parse(init.body as string)).toEqual({ title: "My demo research", template_id: "investment-v1" });
    expect(init.headers["idempotency-key"]).toMatch(/^[a-f0-9-]{36}$/);
  });

  it("does not issue a browser session when starter creation fails", async () => {
    providerFetchMock.mockResolvedValueOnce(providerReply(200, {
      access_token: "access", refresh_token: "refresh", expires_in: 600,
    })).mockResolvedValueOnce(providerReply(503, {}));
    const response = await demoPost(await demoRequest({}));
    expect(response.status).toBe(503);
    expect(response.headers.getSetCookie()).toEqual([]);
  });

  it("fails honestly when anonymous sign-ins are disabled on the provider", async () => {
    providerFetchMock.mockResolvedValueOnce(providerReply(422, { msg: "Anonymous sign-ins are disabled" }));
    const response = await demoPost(await demoRequest({}));
    expect(response.status).toBe(403);
    expect((await response.json()).error).toMatch(/not enabled/i);
  });

  it("enforces origin and CSRF before the provider", async () => {
    providerFetchMock.mockResolvedValue(providerReply(200, {}));
    const crossOrigin = await demoPost(await demoRequest({ origin: "https://evil.example" }));
    expect(crossOrigin.status).toBe(403);
    const noCsrf = await demoPost(await demoRequest({ withoutCsrf: true }));
    expect(noCsrf.status).toBe(403);
    expect(providerFetchMock).not.toHaveBeenCalled();
  });
});
