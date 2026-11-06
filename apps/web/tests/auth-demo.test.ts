/**
 * NI-017 demo sign-in tests against a mocked provider (anonymous sign-ins).
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST as demoPost } from "@/app/api/auth/demo/route";
import { GET as csrfGet } from "@/app/api/auth/csrf/route";
import { SESSION_COOKIE } from "@/lib/auth/session";

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

function providerReply(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

async function demoRequest(options: {
  origin?: string | null;
  displayEmail?: string;
  withoutCsrf?: boolean;
}): Promise<NextRequest> {
  const headers = new Headers({ "content-type": "application/json" });
  if (options.origin !== null) {
    headers.set("origin", options.origin ?? "http://localhost:3000");
  }
  if (!options.withoutCsrf) {
    const minted = await csrfGet();
    const token = ((await minted.json()) as { token: string }).token;
    headers.set("cookie", `${SESSION_COOKIE === "ni_session" ? "ni_csrf" : "ni_csrf"}=${token}`);
    headers.set("x-csrf-token", token);
  }
  return new NextRequest("http://localhost:3000/api/auth/demo", {
    method: "POST",
    headers,
    body: JSON.stringify({ displayEmail: options.displayEmail ?? "visitor@example.test" }),
  });
}

describe("Demo sign-in", () => {
  it("creates a real anonymous provider session and sets HttpOnly cookies", async () => {
    providerFetchMock.mockResolvedValueOnce(
      providerReply(200, { access_token: "access", refresh_token: "refresh", expires_in: 600 }),
    );
    const response = await demoPost(await demoRequest({ displayEmail: "visitor@example.test" }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "session", demo: true });
    const session = response.headers.getSetCookie().find((c) => c.startsWith("ni_session="));
    expect(session).toContain("HttpOnly");
    const [url, init] = providerFetchMock.mock.calls[0];
    expect(String(url)).toContain("/auth/v1/signup");
    const sentBody = JSON.parse(init.body as string);
    expect(sentBody.is_anonymous).toBe(true);
    expect(sentBody.data.demo_email_label).toBe("visitor@example.test");
  });

  it("treats the email as a display label only — absent labels are fine", async () => {
    providerFetchMock.mockResolvedValueOnce(
      providerReply(200, { access_token: "a", refresh_token: "r", expires_in: 600 }),
    );
    const response = await demoPost(await demoRequest({ displayEmail: "" }));
    expect(response.status).toBe(200);
    const sentBody = JSON.parse(providerFetchMock.mock.calls[0][1].body as string);
    expect(sentBody.data).toEqual({});
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
