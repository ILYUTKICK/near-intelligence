import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * NI-062 security-audit runner (apps/web/e2e/security — the A-zone security
 * dispatch). Deliberately a LOCAL config so the shared root vitest.config.ts
 * (and the shared Playwright harness owned by NI-063) stay untouched: run
 * with `pnpm --filter web exec vitest run --config e2e/security/vitest.config.ts`.
 * The suites here are jsdom/node boundary checks (gateway route handlers,
 * storage, static source audits) — not a browser-automation harness; the
 * desktop-browser release checks remain NI-063/NI-064 scope.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "../../src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: [path.resolve(import.meta.dirname, "../../vitest.setup.ts")],
    include: [path.resolve(import.meta.dirname, "**/*.test.{ts,tsx}")],
  },
});
