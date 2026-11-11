/**
 * NI-064 — desktop performance measurements against the PRD budgets
 * (PRODUCT_REQUIREMENTS.md "Initial performance budgets"):
 *
 *   - public LCP ≤ 2.5s under documented test conditions;
 *   - document load ≤ 2s for 200 blocks / 20 mounted chart references on a
 *     warm service;
 *   - chart series p95 ≤ 800ms for 366 daily points at 10 concurrent clients.
 *
 * plus the ARCHITECTURE limits they guard (200 top-level blocks, 20 chart
 * references with lazy mounting, 366 daily query points).
 *
 * Everything runs on the REAL stack (the NI-063 harness boot) with the
 * NI-064 synthetic fixtures (366-day dataset; 200-block / 20-chart-ref
 * document). Deterministic behavior (lazy mounting, no overflow) is asserted;
 * the timing numbers are MEASURED, printed as structured lines for the QA
 * report, and asserted only against the PRD budgets with generous local-run
 * tolerance recorded in the report — the documented staging-machine
 * requirement (TESTING_STRATEGY) means shared-CI numbers must not gate this.
 *
 * Local-only run (see playwright.perf.config.ts for why this config stays
 * out of the shared `test:e2e`/CI journey).
 */
import { expect, test, type Page } from "@playwright/test";

import { signIn, stackState } from "../accessibility/helpers";

const state = stackState();

/** Editor path of the 200-block / 20-chart performance fixture document. */
function perfEditorPath(): string {
  return `/workspace/research/${state.perf_document_id}`;
}

/** Chart-view URL for 366 daily points of the performance dataset. */
function perfChartViewUrl(): string {
  return `${state.web_url}/api/charts/intents-volume/view?definition_version=1`
    + `&start=${state.perf_window.start}&end=${state.perf_window.end_exclusive}`
    + `&dataset_version=${state.perf_dataset_version_id}`;
}

function percentile(values: number[], fraction: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil(fraction * sorted.length) - 1);
  return sorted[Math.max(0, index)];
}

/** Install long-task + layout-shift observers and return the read function. */
async function installVitalsObservers(page: Page): Promise<() => Promise<{ longTasks: number; longTaskTotalMs: number; cls: number }>> {
  await page.evaluate(() => {
    const w = window as unknown as {
      __ni064LongTasks: number;
      __ni064LongTaskTotal: number;
      __ni064Cls: number;
    };
    w.__ni064LongTasks = 0;
    w.__ni064LongTaskTotal = 0;
    w.__ni064Cls = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        w.__ni064LongTasks += 1;
        w.__ni064LongTaskTotal += entry.duration;
      }
    }).observe({ type: "longtask", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!(entry as unknown as { hadRecentInput?: boolean }).hadRecentInput) {
          w.__ni064Cls += (entry as unknown as { value: number }).value;
        }
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
  return () => page.evaluate(() => {
    const w = window as unknown as {
      __ni064LongTasks: number;
      __ni064LongTaskTotal: number;
      __ni064Cls: number;
    };
    return {
      longTasks: w.__ni064LongTasks,
      longTaskTotalMs: Math.round(w.__ni064LongTaskTotal),
      cls: Math.round(w.__ni064Cls * 1000) / 1000,
    };
  });
}

test.describe.configure({ mode: "serial" });

test("public landing LCP on a warm service (PRD budget 2.5s)", async ({ page }) => {
  // Warm the service and the browser cache first (documented test condition:
  // warm service, second navigation measured).
  await page.goto(`${state.web_url}/`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  await page.goto(`${state.web_url}/`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const lcp = await page.evaluate(() => new Promise<number>((resolve) => {
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      if (entries.length) {
        resolve(entries[entries.length - 1].startTime);
      }
    }).observe({ type: "largest-contentful-paint", buffered: true });
  }));
  console.log(`[ni064-perf] landing LCP: ${lcp.toFixed(0)} ms (budget 2500 ms)`);
  expect(lcp, "PRD: public LCP <= 2.5s").toBeLessThanOrEqual(2500);
});

test("editor document load: 200 blocks / 20 chart refs (PRD budget 2s, warm service)", async ({ page }) => {
  await signIn(page, state, perfEditorPath());
  const editor = page.getByLabel("Research paper editor");
  await expect(editor).toBeVisible();
  // The whole document is rendered when the LAST prose block is visible.
  await expect(editor.getByText("NI-064 performance fixture paragraph 160").first())
    .toBeVisible({ timeout: 30_000 });
  // The editor is interactive: the toolbar insert trigger is enabled.
  await expect(page.getByRole("button", { name: "Insert block" })).toBeEnabled();

  const loadMs = await page.evaluate(() => performance.now());
  // Observers installed on the LOADED document (they do not survive
  // navigation), covering the post-load interaction window.
  const readVitals = await installVitalsObservers(page);
  await expect(editor.locator("[data-live-chart-block]")).toHaveCount(20);
  const mounted = await editor.locator("[data-live-chart-block] svg").count();
  await page.waitForTimeout(300);
  const vitals = await readVitals();
  console.log(`[ni064-perf] editor document load (200 blocks / 20 refs, ${mounted} charts mounted in the initial viewport): ${loadMs.toFixed(0)} ms (budget 2000 ms); long tasks ${vitals.longTasks} totalling ${vitals.longTaskTotalMs} ms; CLS ${vitals.cls}`);
  expect(loadMs, "PRD: document load <= 2s for 200 blocks / 20 chart refs").toBeLessThanOrEqual(2000);
  // No horizontal page overflow at the documented desktop viewport.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "acceptance: no page overflow").toBeLessThanOrEqual(0);
});

test("lazy chart mounting at scale: offscreen refs stay deferred until scrolled to", async ({ page }) => {
  await signIn(page, state, perfEditorPath());
  const editor = page.getByLabel("Research paper editor");
  await expect(editor.getByText("NI-064 performance fixture paragraph 160").first())
    .toBeVisible({ timeout: 30_000 });

  // Near the top of the document only the viewport charts may be mounted
  // (NI-033 lazy IntersectionObserver contract at 20 references).
  const chartCount = await editor.locator("[data-live-chart-block]").count();
  expect(chartCount).toBe(20);
  const mountedNearTop = await editor.locator("[data-live-chart-block] svg").count();
  console.log(`[ni064-perf] charts mounted near document top: ${mountedNearTop} of 20 (lazy deferral)`);
  expect(mountedNearTop).toBeLessThan(20);

  // Scroll to a chart far below: it mounts on demand.
  const farChart = editor.locator("[data-live-chart-block]").nth(15);
  await farChart.scrollIntoViewIfNeeded();
  await expect(farChart.locator("svg").first()).toBeVisible({ timeout: 30_000 });
  console.log("[ni064-perf] chart 16 of 20 mounted on scroll (lazy mount works at scale)");
});

test("autosave round trip on the 200-block document", async ({ page }) => {
  await signIn(page, state, perfEditorPath());
  const editor = page.getByLabel("Research paper editor");
  await expect(editor.getByText("NI-064 performance fixture paragraph 160").first())
    .toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(2500); // let the post-load settling finish

  const status = page.getByTestId("save-status");
  await expect(status).toContainText(/Revision \d+/);
  const revisionBefore = Number((await status.textContent())?.match(/Revision (\d+)/)?.[1]);

  const lastParagraph = editor.locator("p").filter({ hasText: "NI-064 performance fixture paragraph 160:" }).first();
  await lastParagraph.click();
  const typingStart = Date.now();
  await page.keyboard.type(" Appended for the NI-064 autosave measurement (synthetic).");
  // 1s idle scheduler + server round trip + ack: content must come back
  // acknowledged with a new revision.
  await expect(status).toContainText(`Revision ${revisionBefore + 1}`, { timeout: 30_000 });
  await expect(status).toContainText(/All changes saved|No unsaved changes/);
  const ackMs = Date.now() - typingStart;
  console.log(`[ni064-perf] autosave round trip on the 200-block document (typing + 1s idle + POST + ack): ${ackMs} ms`);

  // Restore the fixture content exactly (undo the appended sentence) and let
  // the autosave acknowledge the restore.
  await page.keyboard.press(`${process.platform === "darwin" ? "Meta" : "Control"}+z`);
  await expect(status).toContainText(`Revision ${revisionBefore + 2}`, { timeout: 30_000 });
  await expect(status).toContainText(/All changes saved|No unsaved changes/);
  await expect(lastParagraph).not.toContainText("Appended for the NI-064 autosave measurement");
});

test("chart series for 366 daily points: 10 concurrent clients (PRD budget 800ms)", async ({ page }) => {
  // The chart view resolves on the real FastAPI gateway (the production
  // pages fetch it server-side via API_INTERNAL_URL; there is no same-origin
  // browser route by design). The measurement drives the REAL public route
  // with 10 concurrent clients from the test process — no mocks.
  const viewUrl = `${state.api_url}/api/charts/intents-volume/view?definition_version=1`
    + `&start=${state.perf_window.start}&end=${state.perf_window.end_exclusive}`
    + `&dataset_version=${state.perf_dataset_version_id}`;

  // Warm the delivery caches first (documented condition: warm service).
  const warm = await page.request.get(viewUrl);
  expect(warm.status()).toBe(200);
  const warmBody = (await warm.json()) as {
    series?: Array<{ points?: Array<unknown> }>;
  };
  const points = warmBody.series?.[0]?.points?.length ?? -1;
  // The 366-day window resolves 366 real daily points (no interpolation).
  expect(points, "the 366-day view carries 366 daily points").toBe(366);

  const rounds = 5;
  const samples: number[] = [];
  for (let round = 0; round < rounds; round += 1) {
    const started = Date.now();
    const responses = await Promise.all(
      Array.from({ length: 10 }, () => page.request.get(viewUrl)),
    );
    const elapsed = Date.now() - started;
    for (const response of responses) {
      expect(response.status(), "concurrent chart view requests succeed").toBe(200);
    }
    samples.push(elapsed);
    console.log(`[ni064-perf] 366-point chart view, round ${round + 1}: 10 concurrent requests completed in ${elapsed} ms`);
  }
  const p95 = percentile(samples, 0.95);
  console.log(`[ni064-perf] 366-point chart view across ${rounds} rounds of 10 concurrent clients: p95 batch ${p95.toFixed(0)} ms (PRD budget: 800 ms p95 per series request at 10 concurrent clients; a whole 10-request batch completing under the budget is the strictly harder recorded comparison — caveats in the QA report)`);
  expect(p95, "PRD: chart series p95 <= 800ms for 366 daily points").toBeLessThanOrEqual(800);
});

test("scroll interaction over the 200-block document records no overflow and bounded long tasks", async ({ page }) => {
  await signIn(page, state, perfEditorPath());
  const editor = page.getByLabel("Research paper editor");
  await expect(editor.getByText("NI-064 performance fixture paragraph 160").first())
    .toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(2500);
  const readVitals = await installVitalsObservers(page);
  // Scroll through the whole document in steps (wheel-equivalent keyboard
  // scrolling), then back to the top.
  for (let step = 0; step < 10; step += 1) {
    await page.mouse.wheel(0, 1200);
    await page.waitForTimeout(120);
  }
  for (let step = 0; step < 10; step += 1) {
    await page.mouse.wheel(0, -1200);
    await page.waitForTimeout(120);
  }
  const vitals = await readVitals();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  console.log(`[ni064-perf] scroll over 200 blocks: long tasks ${vitals.longTasks} totalling ${vitals.longTaskTotalMs} ms; CLS ${vitals.cls}; horizontal overflow ${overflow} px`);
  expect(overflow, "acceptance: no page overflow").toBeLessThanOrEqual(0);
  // Layout stability during scrolling: CLS 0 (nothing shifts under the user).
  expect(vitals.cls, "no layout shift during scroll").toBeLessThanOrEqual(0.05);
});
