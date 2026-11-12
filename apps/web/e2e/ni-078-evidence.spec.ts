/**
 * NI-078 — after-state desktop evidence for the NI-076 findings D1–D5,
 * captured against the real stack booted by the NI-063 harness (production
 * Next.js + real FastAPI + disposable PostgreSQL).
 *
 * Runs after the custom-range spec (alphabetical file order, one worker), so
 * at least one saved chart exists for the Saved Charts evidence. The before
 * evidence is the committed NI-076 review set (output/ni-076-review/screens/
 * at PR #87 head 0b80bf2). This spec writes the after screenshots to
 * docs/verification/ni-078/screens/ and prints the measured plot/paper
 * positions that the verification README records.
 *
 * Desktop-only (the 8 November 2026 override): 1440x900 and 1280x800.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { readState, repoRoot } from "./harness/state";

interface StackState {
  web_url: string;
  window: { start: string; end: string };
  perf_document_id: string;
  session_alice: string;
}

const state = readState() as StackState;
const outDir = path.join(repoRoot, "docs", "verification", "ni-078", "screens");
mkdirSync(outDir, { recursive: true });

const measurements: Record<string, unknown> = {};

/** Y offset (document coordinates) of an element's bounding box. */
async function documentY(page: Page, selector: string): Promise<number> {
  return page.locator(selector).first().evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return Math.round(rect.top + window.scrollY);
  });
}

async function shoot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: path.join(outDir, name), type: "jpeg", quality: 70 });
}

test.describe.configure({ mode: "serial" });

test("D1/D2 evidence: research opening with compact assessment and recorded figures", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${state.web_url}/research`);
  const assessment = page.locator("#hypothesis-assessment");
  await expect(assessment).toBeVisible();
  const assessmentY = await documentY(page, "#hypothesis-assessment");
  measurements.research_assessment_y_1440 = assessmentY;
  measurements.research_document_height = await page.evaluate(() => document.body.scrollHeight);
  measurements.research_word_count = await page.evaluate(
    () => (document.body.innerText.match(/\S+/g) ?? []).length,
  );
  // The two NI-076 D2 figures are present and inside their owning sections.
  const usdFigure = page.locator("#thesis-usd-windows");
  const supplyFigure = page.locator("#thesis-supply-scale");
  await usdFigure.scrollIntoViewIfNeeded();
  await expect(usdFigure).toBeVisible();
  await expect(supplyFigure).toBeAttached();
  measurements.research_figure_count = await page.locator("figure").count();
  await page.evaluate(() => window.scrollTo(0, 0));
  await shoot(page, "research-opening-after-1440.jpg");
  await usdFigure.scrollIntoViewIfNeeded();
  await shoot(page, "research-figures-usd-after-1440.jpg");
  await supplyFigure.scrollIntoViewIfNeeded();
  await shoot(page, "research-figures-supply-after-1440.jpg");
});

test("D3 evidence: the chart plot starts well inside the first viewport", async ({ page }) => {
  const filters = encodeURIComponent(JSON.stringify({ source: "SRC-LLAMA" }));
  const detailUrl = `${state.web_url}/data/intents/intents-volume?version=1`
    + `&start=${state.window.start}&end=${state.window.end}&filters=${filters}`;

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(detailUrl);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const plot = page.locator("[role='img']").first();
  await expect(plot).toBeVisible();
  await page.waitForTimeout(500); // ECharts canvas paint
  measurements.chart_plot_y_1440x900 = await documentY(page, "[role='img']");
  measurements.chart_viewport_height = 900;
  await shoot(page, "chart-loaded-after-1440x900.jpg");

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(300);
  measurements.chart_plot_y_1280x800 = await documentY(page, "[role='img']");
  await shoot(page, "chart-loaded-after-1280x800.jpg");

  // The acceptance criterion: a meaningful plot appears in the first viewport.
  expect(measurements.chart_plot_y_1440x900 as number).toBeLessThan(900);
  expect(measurements.chart_plot_y_1280x800 as number).toBeLessThan(800);
});

test("D4 evidence: Saved Charts cards are compact and render through the shared renderer", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${state.session_alice}?next=${encodeURIComponent("/workspace/saved-charts")}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  // The custom-range test saved a card; its compact context line is present.
  // Card list items are the only `li` elements carrying an h2 heading link
  // (breadcrumbs also render li elements).
  const card = page.locator("li:has(h2 a)").first();
  await expect(card).toBeVisible();
  const cardPlot = card.locator("figure [role='img']").first();
  await expect(cardPlot).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(500);
  measurements.saved_card_plot_y_1440 = await documentY(page, "li:has(h2 a) figure [role='img']");
  measurements.saved_card_height = await card.evaluate((element) => element.getBoundingClientRect().height);
  await shoot(page, "saved-charts-after-1440.jpg");
  expect(measurements.saved_card_plot_y_1440 as number).toBeLessThan(900);
});

test("D5 evidence: the editor prioritizes the paper", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${state.session_alice}?next=${encodeURIComponent(`/workspace/research/${state.perf_document_id}`)}`);
  const editor = page.getByLabel("Research paper editor");
  await expect(editor).toBeVisible({ timeout: 30_000 });
  // The paper surface and the first prose block position on the first screen.
  const paper = page.locator("[data-pane='paper'] .paper-panel");
  await expect(paper).toBeVisible();
  measurements.editor_paper_y_1440 = await documentY(page, "[data-pane='paper'] .paper-panel");
  measurements.editor_first_paragraph_y = await documentY(
    page,
    "[data-pane='paper'] .editor-paper > *:first-child",
  );
  // One compact header: exactly one breadcrumb trail (the workspace header's).
  measurements.editor_breadcrumb_count = await page.locator("nav[aria-label='Workspace breadcrumb']").count();
  measurements.editor_page_breadcrumb_count = await page.locator("nav[aria-label='Breadcrumb']").count();
  await shoot(page, "editor-after-1440.jpg");
  expect(measurements.editor_paper_y_1440 as number).toBeLessThan(386 + 40);
});

test.afterAll(async () => {
  // Record the measurements next to the screenshots for the README.
  const { writeFileSync } = await import("node:fs");
  writeFileSync(
    path.join(outDir, "measurements.json"),
    JSON.stringify(measurements, null, 2),
  );
  console.log("[ni-078-evidence]", JSON.stringify(measurements));
});
