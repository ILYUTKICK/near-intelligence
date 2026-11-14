/**
 * NI-064 — desktop axe scans of the core public and private surfaces
 * (1440x900 desktop baseline; desktop-only scope per the 8 November 2026
 * override).
 *
 * Gate: ZERO serious/critical axe violations on every scanned surface.
 * Lower-impact violations are logged per surface and recorded in the QA
 * report with their justification instead of silently passing.
 *
 * The scans run against the REAL stack booted by the NI-063 harness (the
 * production `next start` bundle + real FastAPI + disposable PostgreSQL), so
 * the scanned DOM is the production application, not a storybook stand-in.
 *
 * The suite also closes two of the recorded NI-024 regressions in the real
 * browser: every workspace sidebar destination must resolve while retaining
 * the cabinet (NI-080 now implements the former data/model aliases), and
 * the primary Continue link's foreground must come from the layered
 * `text-on-accent` utility, not from the global anchor rule.
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousViolations, hexToRgbString, signIn, stackState } from "./helpers";

const state = stackState();

/** Pinned selection of the NI-063 journey dataset (exact values resolve). */
function chartDetailUrl(): string {
  return `${state.web_url}/data/intents/intents-volume?version=1`
    + `&start=${state.window.start}&end=${state.window.end}`
    + `&dataset_version=${state.dataset_version_id}`;
}

test.describe.configure({ mode: "serial" });

test("public surfaces: landing, research, methodology, data explorer, chart detail, models, login", async ({ page }) => {
  await page.goto(`${state.web_url}/`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page, "public / (landing)");

  await page.goto(`${state.web_url}/research`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page, "public /research");

  await page.goto(`${state.web_url}/methodology`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page, "public /methodology");

  await page.goto(`${state.web_url}/data`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page, "public /data explorer overview");

  await page.goto(chartDetailUrl());
  // The chart resolved its approved data: the exact persisted value is in the
  // DOM (table + accessible alternatives), not a fabricated stand-in.
  await expect(page.getByText(state.pin_value).first()).toBeVisible();
  await expectNoSeriousViolations(page, "public chart detail (resolved data)");

  await page.goto(`${state.web_url}/models`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page, "public /models");

  await page.goto(`${state.web_url}/login`);
  await expect(page.getByRole("textbox", { name: "Email", exact: true })).toBeVisible();
  await expectNoSeriousViolations(page, "auth /login");
});

test("workspace surfaces: home, my research, saved charts (alice session)", async ({ page }) => {
  await signIn(page, state, "/workspace");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page, "workspace home");

  await page.goto(`${state.web_url}/workspace/research`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page, "workspace my research");

  await page.goto(`${state.web_url}/workspace/saved-charts`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousViolations(page, "workspace saved charts");
});

test("research editor with the 200-block synthetic performance fixture document", async ({ page }) => {
  await signIn(page, state, `/workspace/research/${state.perf_document_id}`);
  const editor = page.getByLabel("Research paper editor");
  await expect(editor).toBeVisible();
  // The last prose block is rendered: the whole document (200 blocks) is in
  // the editor DOM, with 20 liveChart node views attached.
  await expect(editor.getByText("NI-064 performance fixture paragraph 160").first())
    .toBeVisible({ timeout: 30_000 });
  await expect(editor.locator("[data-live-chart-block]")).toHaveCount(20);
  const findings = await expectNoSeriousViolations(page, "editor workbench (200-block synthetic document)");
  // Repeated definitions remain distinct landmarks by their current paper
  // position; do not remove region semantics just to suppress this finding.
  expect(findings.filter((finding) => finding.id === "landmark-unique")).toEqual([]);
});

test("NI-024 regression: every workspace sidebar link resolves (no alias prefetch 404s)", async ({ page }) => {
  await signIn(page, state, "/workspace");
  const sidebar = page.getByRole("navigation", { name: "Workspace", exact: true });
  await expect(sidebar).toBeVisible();
  const hrefs = await sidebar.getByRole("link").evaluateAll(
    (anchors) => anchors.map((anchor) => (anchor as HTMLAnchorElement).getAttribute("href")),
  );
  expect(hrefs.length).toBeGreaterThanOrEqual(11);
  // NI-080 implements these shared-screen routes; all sidebar navigation
  // must now stay within the workspace rather than reaching public layouts.
  for (const href of hrefs) {
    expect(href, "sidebar href").toMatch(/^\/workspace(?:\/|$)/);
  }
  // Each sidebar target must actually exist on the running production server
  // (this is exactly what Next.js prefetches when the sidebar renders).
  for (const href of hrefs) {
    const response = await page.request.get(`${state.web_url}${href}`);
    expect(
      response.status(),
      `sidebar link ${href} must resolve on the production server`,
    ).toBeLessThan(400);
  }
});

test("NI-024 regression: the primary Continue link foreground comes from the layered utility", async ({ page }) => {
  await signIn(page, state, "/workspace");
  const continueLink = page.getByRole("link", { name: /Continue research/ });
  await expect(continueLink).toBeVisible();
  const onAccent = await page.evaluate(
    () => getComputedStyle(document.documentElement).getPropertyValue("--color-on-accent"),
  );
  // The global anchor rule now sits in the base cascade layer, so the
  // primary variant's text-on-accent utility wins (unlayered CSS used to
  // override every layer, which forced an inline-style workaround).
  await expect(continueLink).toHaveCSS("color", hexToRgbString(onAccent));
  // The anchor keeps its default link affordance nowhere: the button styling
  // also carries the accent background from the same layered utility set.
  const accent = await page.evaluate(
    () => getComputedStyle(document.documentElement).getPropertyValue("--color-accent"),
  );
  await expect(continueLink).toHaveCSS("background-color", hexToRgbString(accent));
});
