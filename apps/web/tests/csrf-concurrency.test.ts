import { NextRequest } from "next/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { z } from "zod";
import { GET as getCsrf } from "@/app/api/auth/csrf/route";
import { privateFetch } from "@/lib/auth/private-fetch";
import { savedRequest } from "@/features/charts/saved/api";
import { CSRF_COOKIE, SESSION_COOKIE, encodeSessionCookie, mintCsrfToken, verifyCsrfPair } from "@/lib/auth/session";

const environment = {
  APP_ENV: "test", NEXT_PUBLIC_SUPABASE_URL: "https://synthetic.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_synthetic_key_0123456789",
  SUPABASE_JWT_ISSUER: "https://synthetic.supabase.co/auth/v1", SUPABASE_JWKS_URL: "https://synthetic.supabase.co/auth/v1/.well-known/jwks.json",
  SUPABASE_JWT_AUDIENCE: "authenticated", SUPABASE_JWT_ALGORITHM: "ES256",
  AUTH_ALLOWED_REDIRECT_ORIGINS: "http://localhost:3000",
  AUTH_COOKIE_SIGNING_SECRET: "synthetic-cookie-secret-01234567890123456789", CSRF_SIGNING_SECRET: "synthetic-csrf-secret-01234567890123456789",
};
beforeEach(() => { Object.assign(process.env, environment); });
afterEach(() => { vi.unstubAllGlobals(); for (const key of Object.keys(environment)) delete process.env[key]; });
const session = () => encodeSessionCookie({ accessToken: "synthetic-access", refreshToken: "synthetic-refresh", expiresAt: Date.now() + 60_000 });
const request = (cookie: string) => new NextRequest("http://localhost:3000/api/auth/csrf", { headers: { cookie } });

it.each([[false, "saved"], [true, "saved"], [false, "document"], [true, "document"]] as const)("accepts parallel writes (existing cookie: %s, client: %s)", async (existing, client) => {
  const sessionCookie = `${SESSION_COOKIE}=${session()}`;
  let csrfCookie = existing ? mintCsrfToken() : "";
  let release!: () => void;
  let tokens = 0;
  const bothTokens = new Promise<void>((resolve) => { release = resolve; });
  const statuses: number[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url === "/api/auth/csrf") {
      const response = await getCsrf(request(`${sessionCookie}; ${CSRF_COOKIE}=${csrfCookie}`));
      const issued = response.cookies.get(CSRF_COOKIE)?.value;
      if (issued) csrfCookie = issued;
      if (++tokens === 2) release();
      await bothTokens;
      return response;
    }
    const status = verifyCsrfPair(csrfCookie, new Headers(init.headers).get("x-csrf-token")) ? 201 : 403;
    statuses.push(status);
    return new Response("{}", { status });
  }));
  await Promise.all([0, 1].map(() => client === "saved"
    ? savedRequest("/api/saved-charts", z.unknown(), { method: "POST", body: "{}" })
    : privateFetch("/api/documents", { method: "POST", body: "{}" })));
  expect(statuses).toEqual([201, 201]);
});

it("reuses a signed cookie without rotating it and replaces a tampered cookie", async () => {
  const token = mintCsrfToken();
  const reused = await getCsrf(request(`${CSRF_COOKIE}=${token}`));
  expect((await reused.json()).token).toBe(token);
  expect(reused.headers.get("set-cookie")).toBeNull();
  expect(reused.headers.get("cache-control")).toBe("no-store");
  const replaced = await getCsrf(request(`${CSRF_COOKIE}=tampered`));
  const fresh = (await replaced.json()).token;
  expect(fresh).not.toBe("tampered");
  expect(verifyCsrfPair(fresh, fresh)).toBe(true);
  expect(verifyCsrfPair(fresh, token)).toBe(false);
});

it("does not expose the bearer and mints different first tokens for different sessions", async () => {
  const first = await getCsrf(request(`${SESSION_COOKIE}=${session()}`));
  const other = encodeSessionCookie({ accessToken: "synthetic-other", refreshToken: "synthetic-other-refresh", expiresAt: Date.now() + 60_000 });
  const second = await getCsrf(request(`${SESSION_COOKIE}=${other}`));
  const a = (await first.json()).token, b = (await second.json()).token;
  expect(a).not.toBe(b);
  expect(Buffer.from(a.split(".")[0], "base64url").toString()).not.toContain("synthetic-access");
});
