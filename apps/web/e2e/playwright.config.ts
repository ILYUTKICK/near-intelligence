/**
 * Playwright config for the NI-063 research-workflow e2e journey (NI-063
 * harness). Desktop-only scope per the 8 November 2026 user override: one
 * project at the documented 1440x900 desktop viewport — no mobile/tablet
 * passes are required or authorized.
 *
 * The journey runs against the REAL stack booted by harness/boot.mjs:
 * disposable loopback PostgreSQL 18 + the real FastAPI gateway (synthetic
 * ES256 provider transport, the established harness pattern) + the production
 * `next start` build + the real NI-058 export worker. The primary API is never
 * mocked. Run with `pnpm --filter web test:e2e` after `pnpm --filter web build`.
 */
import { defineConfig } from "@playwright/test";

import { statePath } from "./harness/state";

// The global setup writes the stack handoff here; the spec reads the same
// path through harness/state.mjs (workers inherit this process env).
process.env.NI063_STATE ??= statePath();

export default defineConfig({
  testDir: ".",
  testMatch: /.*\.spec\.ts/,
  globalSetup: "./harness/global-setup",
  globalTeardown: "./harness/global-teardown",
  // One ordered journey on one disposable stack: a single worker, no retries,
  // serial execution so every step sees the persisted state of the previous.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 240_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    viewport: { width: 1440, height: 900 },
    acceptDownloads: true,
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { browserName: "chromium" } },
  ],
});
