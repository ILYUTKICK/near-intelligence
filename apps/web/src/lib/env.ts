import { existsSync } from "node:fs";
import path from "node:path";
import nextEnv from "@next/env";
import { z } from "zod";

const { loadEnvConfig } = nextEnv;

/**
 * Server-side environment contract for the web runtime (NI-002 skeleton).
 *
 * Values come from the root .env created by the documented
 * `cp .env.example .env` onboarding step and are loaded explicitly and lazily
 * on first server use, so they are read in the same process that serves
 * requests. Compose/CI environments may inject the variables directly; a
 * variable already present in process.env always wins over the .env file.
 * Client bundles must never read server values; NEXT_PUBLIC_* variables are
 * introduced by their own tasks (auth: NI-016).
 */
const serverEnvSchema = z.object({
  APP_ENV: z.enum(["development", "test", "production"]),
  APP_ORIGIN: z.url(),
  API_INTERNAL_URL: z.url(),
});

export type ServerEnv = z.infer<typeof serverEnvSchema>;

let cached: ServerEnv | undefined;
let envLoaded = false;

function findRepoRoot(): string {
  let dir = process.cwd();
  for (let depth = 0; depth < 10; depth += 1) {
    if (existsSync(path.join(dir, "pnpm-workspace.yaml"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      return process.cwd();
    }
    dir = parent;
  }
  return process.cwd();
}

/**
 * Idempotently loads the root .env into process.env (explicit loading; a
 * variable already present wins over the file). Shared with the auth config
 * contract so every server entry point sees the same values.
 */
export function ensureRootEnvLoaded(): void {
  if (envLoaded) {
    return;
  }
  loadEnvConfig(findRepoRoot(), process.env.NODE_ENV !== "production", {
    info: () => {},
    error: console.error,
  });
  envLoaded = true;
}

export function loadServerEnv(): ServerEnv {
  if (cached) {
    return cached;
  }
  ensureRootEnvLoaded();
  const parsed = serverEnvSchema.safeParse({
    APP_ENV: process.env.APP_ENV,
    APP_ORIGIN: process.env.APP_ORIGIN,
    API_INTERNAL_URL: process.env.API_INTERNAL_URL,
  });
  if (!parsed.success) {
    const problems = parsed.error.issues
      .map((issue) => `${issue.path.join(".") || "(unknown)"}: ${issue.message}`)
      .join("; ");
    throw new Error(
      `Invalid web server configuration. Copy .env.example to .env at the repository root and set the required variables. Problems: ${problems}`,
    );
  }
  cached = parsed.data;
  return cached;
}
