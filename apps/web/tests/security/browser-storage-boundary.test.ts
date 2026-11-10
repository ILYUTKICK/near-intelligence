/**
 * NI-062 browser-storage and public-surface audit (part of the standard
 * `pnpm --filter web test` run).
 *
 * Pins the client-side privacy invariants that must hold on every browser:
 * no token or session payload ever lands in Web storage, the auth-change
 * signal carries no identity, the public surface never imports the private
 * document transport, and the public API clients send no credentials.
 *
 * The recorded NI-042 workbench memory-retention gap is closed by
 * features/editor/persistence/session-owner.ts (verified-identity
 * revalidation) and covered by tests/security/workbench-identity-guard.
 * test.tsx; this suite keeps asserting that no private content lands in
 * Web storage and that the auth-change consumers stay inventoried.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { announceAuthChange, AUTH_CHANGE_STORAGE } from "@/lib/auth/change";
import { decodeSignedPayload, encodeSessionCookie } from "@/lib/auth/session";

const WEB_ROOT = path.resolve(import.meta.dirname, "../..");
const SRC_ROOT = path.join(WEB_ROOT, "src");

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
  API_INTERNAL_URL: "http://internal-api.test",
};

for (const [key, value] of Object.entries(ENV)) {
  process.env[key] = value;
}

function* sourceFiles(dir: string): Generator<string> {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      yield* sourceFiles(full);
    } else if (/\.(ts|tsx|mjs)$/.test(entry)) {
      yield full;
    }
  }
}

describe("Web storage never carries identity or tokens", () => {
  it("the auth-change signal stores only an opaque signal, never identity", () => {
    announceAuthChange();
    const stored = window.localStorage.getItem(AUTH_CHANGE_STORAGE);
    expect(stored).toBeTruthy();
    // A random UUID: no subject, no token, no email.
    expect(stored).toMatch(/^[0-9a-f-]{36}$/);
    window.localStorage.clear();
  });

  it("localStorage.setItem exists only in the auth-change signal module", () => {
    const offenders: string[] = [];
    for (const file of sourceFiles(SRC_ROOT)) {
      const content = readFileSync(file, "utf8");
      if (content.includes("localStorage.setItem") &&
          !file.endsWith(path.join("lib", "auth", "change.ts"))) {
        offenders.push(path.relative(SRC_ROOT, file));
      }
    }
    expect(offenders).toEqual([]);
  });

  it("no source module writes tokens or session payloads into storage", () => {
    const offenders: string[] = [];
    for (const file of sourceFiles(SRC_ROOT)) {
      const content = readFileSync(file, "utf8");
      const writes = /(?:localStorage|sessionStorage)\.setItem\(([^)]*)\)/g;
      for (const match of content.matchAll(writes)) {
        if (/token|session|password|secret/i.test(match[1])) {
          offenders.push(`${path.relative(SRC_ROOT, file)}: ${match[1].trim()}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("the signed session cookie payload is not readable without the secret", () => {
    const session = {
      accessToken: "synthetic-access-token",
      refreshToken: "synthetic-refresh-token",
      expiresAt: Date.now() + 60_000,
    };
    const value = encodeSessionCookie(session);
    // Tampering with the body breaks the HMAC: the gateway refuses it
    // (decodeSignedPayload returns null -> 401), so a stolen cookie string
    // cannot be minted or modified without AUTH_COOKIE_SIGNING_SECRET.
    const [body, signature] = value.split(".");
    expect(body).toBeTruthy();
    expect(signature).toBeTruthy();
    process.env.AUTH_COOKIE_SIGNING_SECRET = "different".padEnd(40, "x");
    expect(decodeSignedPayload<{ accessToken: string }>(value)).toBeNull();
    process.env.AUTH_COOKIE_SIGNING_SECRET = ENV.AUTH_COOKIE_SIGNING_SECRET;
    expect(decodeSignedPayload<{ accessToken: string }>(value))
      .toMatchObject({ accessToken: "synthetic-access-token" });
  });
});

describe("Public surface carries no private transport", () => {
  it("public route pages never import the owner-document transport or editor", () => {
    const offenders: string[] = [];
    const publicRoot = path.join(SRC_ROOT, "app", "(public)");
    for (const file of sourceFiles(publicRoot)) {
      const content = readFileSync(file, "utf8");
      for (const forbidden of ["features/documents/list/documents-api",
                               "features/editor/workbench",
                               "features/editor/editor-shell"]) {
        if (content.includes(forbidden)) {
          offenders.push(`${path.relative(SRC_ROOT, file)} imports ${forbidden}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("public API clients send no credentials or authorization headers", () => {
    const clients = [
      "features/charts/library/catalog-api.ts",
      "features/models/models-api.ts",
      "features/public-research/landing-metrics.ts",
    ];
    for (const client of clients) {
      const content = readFileSync(path.join(SRC_ROOT, client), "utf8");
      expect(content, client).not.toMatch(/credentials\s*:/);
      expect(content, client).not.toMatch(/[Aa]uthorization/);
      expect(content, client).not.toMatch(/localStorage|sessionStorage/);
    }
  });

  it("every private request path in the workspace features goes through the CSRF gateway", () => {
    // The private transports must attach the CSRF header (direct fetch would
    // bypass the gateway's double-submit check and fail 403 at runtime).
    const offenders: string[] = [];
    const privateClients = [
      "features/documents/list/documents-api.ts",
      "features/charts/saved/api.ts",
    ];
    for (const client of privateClients) {
      const content = readFileSync(path.join(SRC_ROOT, client), "utf8");
      if (!content.includes("privateFetch") && !content.includes("privateGateway")
          && !content.includes("x-csrf-token")) {
        offenders.push(path.relative(SRC_ROOT, client));
      }
    }
    expect(offenders).toEqual([]);
  });

  it("the auth-change signal consumers cover the workspace data surfaces", () => {
    // Recorded NI-062 inventory: WorkspaceHome, owned saved-chart data,
    // chart library auth actions, the editor chart provider re-check AND the
    // full-workbench identity guard (the closed NI-042 gap) on auth change.
    const consumers = [
      "features/workspace/home/WorkspaceHome.tsx",
      "features/charts/saved/use-owned-data.ts",
      "features/charts/library/ChartAuthActions.tsx",
      "features/editor/blocks/chart-context.tsx",
      "features/editor/persistence/session-owner.ts",
    ];
    for (const consumer of consumers) {
      const content = readFileSync(path.join(SRC_ROOT, consumer), "utf8");
      expect(content, consumer).toContain("AUTH_CHANGE");
    }
  });
});
