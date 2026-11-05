import { z } from "zod";

/**
 * Auth environment contract (NI-016), mirroring .env.example and
 * docs/AUTHENTICATION_SECURITY.md.
 *
 * Rules enforced here:
 * - Placeholder values from .env.example fail with a readable error naming
 *   the variable ("placeholders fail safely").
 * - The normal browser path only ever reads the two NEXT_PUBLIC_ values;
 *   the publishable key must never be a service-role credential.
 * - The JWT algorithm must be asymmetric (HS256 is rejected — the API
 *   verifies against provider JWKS, never a shared secret).
 * - Server auth values are read server-side only and never inlined into
 *   client bundles (scripts/check-client-secrets.mjs guards the build).
 */

const PLACEHOLDER_PATTERN = /^REPLACE[_A-Z0-9]*$/i;

function rejectPlaceholders(variable: string) {
  return (value: string) => {
    if (PLACEHOLDER_PATTERN.test(value.trim()) || value.trim().length === 0) {
      throw new Error(
        `${variable} still has its placeholder value. Copy .env.example to .env at the repository root and set the real development values (see docs/AUTHENTICATION_SECURITY.md).`,
      );
    }
    return value;
  };
}

const publicSchema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z
    .string()
    .url()
    .transform(rejectPlaceholders("NEXT_PUBLIC_SUPABASE_URL")),
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: z
    .string()
    .min(20)
    .transform(rejectPlaceholders("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"))
    .refine(
      (value) => !value.toLowerCase().includes("service_role"),
      "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY looks like a service-role credential; the browser path must use the publishable key only.",
    ),
});

const serverSchema = z.object({
  SUPABASE_JWT_ISSUER: z.string().url().transform(rejectPlaceholders("SUPABASE_JWT_ISSUER")),
  SUPABASE_JWKS_URL: z
    .string()
    .url()
    .refine((value) => value.startsWith("https://"), "SUPABASE_JWKS_URL must be https.")
    .transform(rejectPlaceholders("SUPABASE_JWKS_URL")),
  SUPABASE_JWT_AUDIENCE: z
    .string()
    .min(1)
    .transform(rejectPlaceholders("SUPABASE_JWT_AUDIENCE")),
  SUPABASE_JWT_ALGORITHM: z.enum(["ES256", "RS256", "EdDSA"], {
    message:
      "SUPABASE_JWT_ALGORITHM must be an asymmetric algorithm (ES256, RS256 or EdDSA). HS256/shared secrets are rejected by the security specification.",
  }),
  AUTH_ALLOWED_REDIRECT_ORIGINS: z
    .string()
    .min(1)
    .transform((value, ctx) => {
      const origins = value
        .split(/[,\s]+/)
        .map((origin) => origin.trim())
        .filter((origin) => origin.length > 0);
      if (origins.length === 0) {
        ctx.addIssue({ code: "custom", message: "AUTH_ALLOWED_REDIRECT_ORIGINS is empty." });
        return z.NEVER;
      }
      for (const origin of origins) {
        const parsed = z.url().safeParse(origin);
        if (!parsed.success) {
          ctx.addIssue({
            code: "custom",
            message: `AUTH_ALLOWED_REDIRECT_ORIGINS contains a non-URL entry: ${origin}`,
          });
          return z.NEVER;
        }
      }
      return origins;
    }),
  AUTH_COOKIE_SIGNING_SECRET: z
    .string()
    .min(32)
    .transform(rejectPlaceholders("AUTH_COOKIE_SIGNING_SECRET")),
  CSRF_SIGNING_SECRET: z
    .string()
    .min(32)
    .transform(rejectPlaceholders("CSRF_SIGNING_SECRET")),
});

export type PublicAuthConfig = z.infer<typeof publicSchema>;
export type ServerAuthConfig = z.infer<typeof serverSchema>;

export class AuthConfigError extends Error {}

function formatProblems(variables: Record<string, unknown>, error: z.ZodError): string {
  return error.issues
    .map((issue) => `${String(issue.path[0] ?? "(unknown)")}: ${issue.message}`)
    .join("; ");
}

function parseOrThrow<Schema extends z.ZodTypeAny>(
  schema: Schema,
  variables: Record<string, unknown>,
  hint: string,
): z.infer<Schema> {
  const parsed = schema.safeParse(variables);
  if (!parsed.success) {
    throw new AuthConfigError(
      `Invalid authentication configuration. ${hint} Problems: ${formatProblems(variables, parsed.error)}`,
    );
  }
  return parsed.data;
}

function readEnv(names: readonly string[]): Record<string, unknown> {
  return Object.fromEntries(names.map((name) => [name, process.env[name]]));
}

const PUBLIC_VARS = ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"] as const;
const SERVER_VARS = [
  "SUPABASE_JWT_ISSUER",
  "SUPABASE_JWKS_URL",
  "SUPABASE_JWT_AUDIENCE",
  "SUPABASE_JWT_ALGORITHM",
  "AUTH_ALLOWED_REDIRECT_ORIGINS",
  "AUTH_COOKIE_SIGNING_SECRET",
  "CSRF_SIGNING_SECRET",
] as const;

/** Browser-safe configuration: publishable values only. Login UI (NI-017) consumes this. */
export function loadPublicAuthConfig(): PublicAuthConfig {
  return parseOrThrow(
    publicSchema,
    readEnv(PUBLIC_VARS),
    "Copy .env.example to .env at the repository root and set the publishable values.",
  );
}

/** Server-only configuration (gateway handlers, NI-017; API verification, NI-018). */
export function loadServerAuthConfig(): ServerAuthConfig {
  return parseOrThrow(
    serverSchema,
    readEnv(SERVER_VARS),
    "Copy .env.example to .env at the repository root and set the server auth values; they must never be exposed to the browser.",
  );
}

/** Convenience: both halves for server-side consumers. */
export function loadAuthConfig(): PublicAuthConfig & ServerAuthConfig {
  return { ...loadPublicAuthConfig(), ...loadServerAuthConfig() };
}
