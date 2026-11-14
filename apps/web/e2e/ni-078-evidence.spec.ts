/** NI-078 desktop evidence against the real NI-063 disposable stack. */
import { writeFileSync } from "node:fs";

import { expect, test, type Locator, type TestInfo } from "@playwright/test";

import { readState } from "./harness/state";

interface StackState {
  web_url: string;
  window: { start: string; end: string };
  dataset_version_id: string;
  perf_document_id: string;
  pin_value: string;
  session_alice: string;
  session_bob: string;
}

const state = readState() as StackState;
const plotSelector = "figure [role='img']:has(svg)";
const filters = encodeURIComponent(JSON.stringify({ source: "SRC-LLAMA" }));
const chartPath = "/data/intents/intents-volume?version=1"
  + `&start=${state.window.start}&end=${state.window.end}&filters=${filters}`;

test.use({ reducedMotion: "reduce" });

async function position(element: Locator) {
  return element.evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return {
      top: Math.round(rect.top + window.scrollY),
      height: Math.round(rect.height),
      visibleHeight: Math.round(Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0))),
    };
  });
}

function record(testInfo: TestInfo, values: object) {
  writeFileSync(testInfo.outputPath("measurements.json"), JSON.stringify(values, null, 2) + "\n");
}

test("D1/D2: the research opening and figures expose hypotheses and claim provenance", async ({ page }, testInfo) => {
  await page.goto(`${state.web_url}/research`);
  const assessment = page.locator("#hypothesis-assessment");
  await expect(assessment.getByRole("link", { name: /^H[1-4] / })).toHaveCount(4);
  const assessmentPosition = await position(assessment);
  await page.screenshot({ path: testInfo.outputPath("research-opening-after-1440.jpg"), type: "jpeg", quality: 70 });
  await assessment.screenshot({ path: testInfo.outputPath("research-assessment-after-1440.jpg"), type: "jpeg", quality: 70 });
  const usd = page.locator("#thesis-usd-windows");
  const supply = page.locator("#thesis-supply-scale");
  await expect(usd.getByRole("link", { name: "Recorded claim CL-004" })).toHaveAttribute("href", "#CL-004-heading");
  await expect(supply.getByRole("link", { name: "Recorded claim CL-007" })).toHaveAttribute("href", "#CL-007-heading");
  await expect(supply.getByRole("link", { name: "Recorded claim CL-001" })).toHaveAttribute("href", "#CL-001-heading");
  await usd.screenshot({ path: testInfo.outputPath("research-figures-usd-after-1440.jpg"), type: "jpeg", quality: 70 });
  await supply.screenshot({ path: testInfo.outputPath("research-figures-supply-after-1440.jpg"), type: "jpeg", quality: 70 });
  record(testInfo, {
    assessment: assessmentPosition,
    figures: await page.locator("figure").count(),
    documentHeight: await page.evaluate(() => document.body.scrollHeight),
  });
});

test("D3: the rendered plot occupies part of the first viewport at both desktop sizes", async ({ page }, testInfo) => {
  const plots: Record<string, Awaited<ReturnType<typeof position>>> = {};
  for (const { width, height } of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }]) {
    await page.setViewportSize({ width, height });
    await page.goto(state.web_url + chartPath);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in to freeze a snapshot" })).toBeVisible();
    const plot = page.locator(plotSelector);
    await expect(plot).toBeVisible();
    const key = `${width}x${height}`;
    plots[key] = await position(plot);
    expect(plots[key].visibleHeight).toBeGreaterThanOrEqual(120);
    await page.screenshot({ path: testInfo.outputPath(`chart-loaded-after-${key}.jpg`), type: "jpeg", quality: 70 });
  }
  record(testInfo, plots);
});

test("D4: a saved preview exposes exact values and sources by keyboard without advancing its pin", async ({ page }, testInfo) => {
  await page.goto(`${state.session_alice}?next=${encodeURIComponent(chartPath)}`);
  await page.getByRole("button", { name: "Save chart", exact: true }).click();
  const savedLink = page.getByRole("link", { name: "Open saved chart" });
  await expect(savedLink).toBeVisible();
  const href = await savedLink.getAttribute("href");
  const savedId = href?.split("/").at(-1);
  expect(savedId).toMatch(/^[0-9a-f-]{36}$/);

  const previewResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/saved-charts/${savedId}`
    && new URL(response.url()).searchParams.get("preview") === "true");
  await page.goto(`${state.web_url}/workspace/saved-charts`);
  const response = await previewResponse;
  expect(response.ok()).toBe(true);
  expect(response.headers()["cache-control"]).toBe("no-store");
  const payload = await response.json();
  expect(payload.saved_chart.last_resolved_dataset_version_id).toBe(state.dataset_version_id);
  expect(payload.view.dataset.id).toBe(state.dataset_version_id);
  const card = page.getByRole("listitem").filter({ has: page.locator(`a[href="${href}"]`) }).first();
  const plot = card.locator(plotSelector);
  await expect(plot).toBeVisible();
  const plotPosition = await position(plot);
  expect(plotPosition.visibleHeight).toBeGreaterThanOrEqual(120);
  await expect(card.getByText("Live selection", { exact: true })).toHaveCount(1);
  await expect(card.getByText("Live — latest approved data")).toHaveCount(0);
  await expect(card.getByText("Accessible summary", { exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("saved-charts-after-1440.jpg"), type: "jpeg", quality: 70 });
  record(testInfo, { plot: plotPosition, card: await position(card) });

  const values = card.getByText("Exact values and summary", { exact: true });
  const table = card.getByRole("region", { name: /exact data table/ });
  await expect(table).toBeHidden();
  await values.focus();
  await page.keyboard.press("Enter");
  await expect(table.getByText(state.pin_value, { exact: true })).toBeVisible();
  const sources = card.getByRole("button", { name: "Sources & definitions" });
  await sources.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Sources and definitions" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sources).toBeFocused();

  await page.goto(`${state.session_bob}?next=${encodeURIComponent("/workspace/saved-charts")}`);
  const foreign = await page.request.get(`${state.web_url}/api/saved-charts/${savedId}?preview=true`);
  expect(foreign.status()).toBe(404);
});

test("D5: the editor prioritizes the paper and exposes one breadcrumb", async ({ page }, testInfo) => {
  await page.goto(`${state.session_alice}?next=${encodeURIComponent(`/workspace/research/${state.perf_document_id}`)}`);
  await expect(page.getByLabel("Research paper editor")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Workspace breadcrumb" })).toHaveCount(1);
  await expect(page.getByRole("navigation", { name: "Breadcrumb", exact: true })).toHaveCount(0);
  const paper = page.locator("[data-pane='paper'] > .paper-panel");
  await expect(paper).toBeVisible();
  await expect(paper.locator("[data-live-chart-block]").first().getByText("Chart definition and pinned context")).toBeVisible();
  const paperPosition = await position(paper);
  expect(paperPosition.top).toBeLessThan(386);
  await page.screenshot({ path: testInfo.outputPath("editor-after-1440.jpg"), type: "jpeg", quality: 70 });
  record(testInfo, { paper: paperPosition, firstBlock: await position(page.locator(".editor-paper > *").first()) });
});
