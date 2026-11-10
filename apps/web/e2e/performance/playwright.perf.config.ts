/**
 * Playwright config for the NI-064 desktop PERFORMANCE measurements
 * (harness-only code). Desktop 1440x900 only — no mobile/tablet passes are
 * required or authorized (8 November 2026 scope).
 *
 * The perf spec stays LOCAL-ONLY by design: TESTING_STRATEGY requires that
 * PRD performance budgets run on a documented machine/concurrency, not
 * inferred from shared CI runners (noisy, throttled CPU neighbors), and the
 * budgets measured here are recorded in the QA report with the documented
 * environment instead of gating a shared pipeline. The file pattern
 * `*.perf.ts` deliberately does not match the NI-063 journey config's
 * `testMatch: /.*\.spec\.ts/`, so `pnpm --filter web test:e2e` (and the CI e2e
 * job) are unaffected.
 *
 * The same NI-063 harness boots the REAL stack (disposable PostgreSQL 18 +
 * FastAPI + production `next start` + export worker) with the NI-064
 * performance fixtures (366-day synthetic dataset, 200-block / 20-chart-ref
 * document). Run: `pnpm --filter web build` then
 * `pnpm --filter web exec playwright test --config e2e/performance/playwright.perf.config.ts`.
 */
import { defineConfig } from "@playwright/test";

import { statePath } from "../harness/state";

process.env.NI063_STATE ??= statePath();

export default defineConfig({
  testDir: ".",
  testMatch: /.*\.perf\.ts/,
  globalSetup: "../harness/global-setup",
  globalTeardown: "../harness/global-teardown",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 240_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    viewport: { width: 1440, height: 900 },
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { browserName: "chromium" } },
  ],
});
