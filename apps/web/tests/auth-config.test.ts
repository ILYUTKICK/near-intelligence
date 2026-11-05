/**
 * NI-016 auth configuration validation matrix (unit tests, no fixtures).
 * Env values are per-test synthetic strings — never real credentials.
 */
import { afterEach, describe, expect, it } from "vitest";

import {
  AuthConfigError,
  loadPublicAuthConfig,
  loadServerAuthConfig,
} from "@/lib/auth/config";

const VALID_PUBLIC = {
  NEXT_PUBLIC_SUPABASE_URL: "https://dev-project.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_synthetic_test_key_0123456789",
};

const VALID_SERVER = {
  SUPABASE_JWT_ISSUER: "https://dev-project.supabase.co/auth/v1",
  SUPABASE_JWKS_URL: "https://dev-project.supabase.co/auth/v1/.well-known/jwks.json",
  SUPABASE_JWT_AUDIENCE: "authenticated",
  SUPABASE_JWT_ALGORITHM: "ES256",
  AUTH_ALLOWED_REDIRECT_ORIGINS: "http://localhost:3000, https://staging.example.com",
  AUTH_COOKIE_SIGNING_SECRET: "a".repeat(40),
  CSRF_SIGNING_SECRET: "b".repeat(40),
};

function withEnv(values: Record<string, string | undefined>, run: () => void) {
  const saved = Object.entries(values).map(([key]) => [key, process.env[key]]);
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
  try {
    run();
  } finally {
    for (const [key, value] of saved) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
}

afterEach(() => {
  for (const key of [
    ...Object.keys(VALID_PUBLIC),
    ...Object.keys(VALID_SERVER),
  ]) {
    delete process.env[key];
  }
});

describe("Public auth config", () => {
  it("accepts publishable values", () => {
    withEnv({ ...VALID_PUBLIC }, () => {
      expect(loadPublicAuthConfig()).toMatchObject(VALID_PUBLIC);
    });
  });

  it("fails readably on placeholder values", () => {
    withEnv(
      { ...VALID_PUBLIC, NEXT_PUBLIC_SUPABASE_URL: "https://REPLACE_PROJECT.supabase.co" },
      () => {
        expect(() => loadPublicAuthConfig()).toThrow(AuthConfigError);
        expect(() => loadPublicAuthConfig()).toThrow(/NEXT_PUBLIC_SUPABASE_URL/);
        expect(() => loadPublicAuthConfig()).toThrow(/placeholder/);
      },
    );
  });

  it("rejects a service-role credential in the browser key slot", () => {
    withEnv(
      {
        ...VALID_PUBLIC,
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "eyJhbGciOi.service_role_synthetic_key_xxxxxxxx",
      },
      () => {
        expect(() => loadPublicAuthConfig()).toThrow(/service-role/);
      },
    );
  });
});

describe("Server auth config", () => {
  it("accepts a valid asymmetric configuration and parses origins", () => {
    withEnv({ ...VALID_SERVER }, () => {
      const config = loadServerAuthConfig();
      expect(config.AUTH_ALLOWED_REDIRECT_ORIGINS).toEqual([
        "http://localhost:3000",
        "https://staging.example.com",
      ]);
      expect(config.SUPABASE_JWT_ALGORITHM).toBe("ES256");
    });
  });

  it("rejects HS256 — shared secrets are not accepted", () => {
    withEnv({ ...VALID_SERVER, SUPABASE_JWT_ALGORITHM: "HS256" }, () => {
      expect(() => loadServerAuthConfig()).toThrow(/asymmetric/);
    });
  });

  it("rejects http JWKS URLs", () => {
    withEnv(
      { ...VALID_SERVER, SUPABASE_JWKS_URL: "http://dev-project.supabase.co/auth/v1/.well-known/jwks.json" },
      () => {
        expect(() => loadServerAuthConfig()).toThrow(/https/);
      },
    );
  });

  it("fails readably naming each missing or placeholder variable", () => {
    withEnv(
      {
        SUPABASE_JWT_ISSUER: undefined,
        SUPABASE_JWKS_URL: undefined,
        SUPABASE_JWT_AUDIENCE: "REPLACE_X",
        SUPABASE_JWT_ALGORITHM: "ES256",
        AUTH_ALLOWED_REDIRECT_ORIGINS: undefined,
        AUTH_COOKIE_SIGNING_SECRET: undefined,
        CSRF_SIGNING_SECRET: undefined,
      },
      () => {
        try {
          loadServerAuthConfig();
          expect.unreachable("configuration should have failed");
        } catch (error) {
          expect(error).toBeInstanceOf(AuthConfigError);
          const message = (error as Error).message;
          for (const name of [
            "SUPABASE_JWT_ISSUER",
            "SUPABASE_JWKS_URL",
            "SUPABASE_JWT_AUDIENCE",
            "AUTH_ALLOWED_REDIRECT_ORIGINS",
            "AUTH_COOKIE_SIGNING_SECRET",
            "CSRF_SIGNING_SECRET",
          ]) {
            expect(message).toContain(name);
          }
        }
      },
    );
  });

  it("rejects short signing secrets", () => {
    withEnv({ ...VALID_SERVER, AUTH_COOKIE_SIGNING_SECRET: "short" }, () => {
      expect(() => loadServerAuthConfig()).toThrow(/AUTH_COOKIE_SIGNING_SECRET/);
    });
  });
});
