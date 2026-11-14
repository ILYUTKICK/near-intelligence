/**
 * NI-064 — chart data is accessible WITHOUT hover (desktop 1440x900; the
 * NI-033 contract verified against the real stack at the documented desktop
 * viewport).
 *
 * The exact-values table is the hover-free alternative: every date/value of
 * the resolved series, with the original decimal strings, bound prefixes and
 * "not observed" reason rows — plus the manual "Accessible summary" details
 * and the keyboard-operable range presets. Verified on the public chart
 * detail page and on the editor's chart node.
 */
import { expect, test } from "@playwright/test";

import { signIn, stackState } from "./helpers";

const state = stackState();

/** Pinned full-coverage selection of the NI-063 journey dataset. */
function chartDetailUrl(): string {
  return `${state.web_url}/data/intents/intents-volume?version=1`
    + `&start=${state.window.start}&end=${state.window.end}`
    + `&dataset_version=${state.dataset_version_id}`;
}

/** Days of the dataset inside a half-open [start, end) window. */
function coveredDays(start: string, endExclusive: string): Array<[string, string]> {
  return Object.entries(state.day_values)
    .filter(([day]) => day >= start && day < endExclusive);
}

/** Same window over the NI-064 performance dataset's own day map. */
function perfCoveredDays(start: string, endExclusive: string): Array<[string, string]> {
  return Object.entries(state.perf_day_values)
    .filter(([day]) => day >= start && day < endExclusive);
}

/**
 * The exact-value renderer keeps every significant digit but trims trailing
 * fractional zeros ("100.00" renders as "100"); normalize the stored string
 * the same way for the assertion (the exactness contract itself — no float
 * round-trip — is covered by the NI-033 unit tests incl. the 31-digit case).
 */
function trimmedForDisplay(value: string): string {
  return value.includes(".")
    ? value.replace(/0+$/, "").replace(/\.$/, "")
    : value;
}

test.describe.configure({ mode: "serial" });

test("public chart detail: exact-values table renders every covered day without hover", async ({ page }) => {
  await page.goto(chartDetailUrl());
  // NI-096: the exact table is announced nonvisually (sr-only) — attached to
  // the DOM, never hidden behind a hover or an accordion.
  const tableRegion = page.getByRole("region", { name: /exact data table/ });
  await expect(tableRegion).toBeAttached();
  await expect(page.getByText(state.pin_value).first()).toBeAttached();

  // Every covered day (half-open [start, end)) appears with its exact
  // persisted decimal string; nothing is zero-filled or rounded.
  const covered = coveredDays(state.window.start, state.window.end);
  expect(covered.length).toBeGreaterThan(10);
  for (const [day, value] of covered) {
    await expect(tableRegion.locator("tr", { hasText: day }), `row for ${day}`)
      .toContainText(value);
  }
  await expect(tableRegion.locator("tbody tr")).toHaveCount(covered.length);

  // The manual accessible summary stays announced nonvisually.
  await expect(page.getByText(/periods from .* \(UTC\)/).first()).toBeAttached();
});

test("range presets operate from the keyboard and the table follows without hover", async ({ page }) => {
  await page.goto(chartDetailUrl());
  const tableRegion = page.getByRole("region", { name: /exact data table/ });
  await expect(tableRegion).toBeAttached();

  const sevenDays = page.getByRole("group", { name: "Time range" })
    .getByRole("button", { name: "Last 7 days" });
  await sevenDays.focus();
  await expect(sevenDays).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(sevenDays).toHaveAttribute("aria-pressed", "true");
  // Anchored to the pinned selection end (2026-01-14), not the wall clock.
  await expect.poll(() => page.url(), { timeout: 15_000 })
    .toContain("start=2026-01-07");

  // The exact table now carries exactly the seven covered days
  // ([2026-01-07, 2026-01-14)), still with the original decimal strings.
  const covered = coveredDays("2026-01-07", state.window.end);
  expect(covered.length).toBe(7);
  await expect(tableRegion.locator("tbody tr")).toHaveCount(7);
  for (const [day, value] of covered) {
    await expect(tableRegion.locator("tr", { hasText: day })).toContainText(value);
  }
  // Units survive the range change (NI-033 contract).
  await expect(page.getByText("USD").first()).toBeVisible();
});

test("editor chart node: exact values visible without hover", async ({ page }) => {
  await signIn(page, state, `/workspace/research/${state.perf_document_id}`);
  const editor = page.getByLabel("Research paper editor");
  await expect(editor.getByText("NI-064 performance fixture paragraph 160").first())
    .toBeVisible({ timeout: 30_000 });
  const firstChart = editor.locator("[data-live-chart-block]").first();
  await firstChart.scrollIntoViewIfNeeded();
  // The pin disclosure identifies the performance fixture's dataset.
  await firstChart.getByText("Chart definition and pinned context").click();
  await expect(firstChart.getByText(`Observed dataset: ${state.perf_dataset_version_id}`))
    .toBeVisible({ timeout: 30_000 });
  await firstChart.getByText("Chart definition and pinned context").click();

  // The chart node embeds the same hover-free exact table; its pinned
  // selection is [2026-01-01, 2026-01-08) — seven covered days.
  const tableRegion = firstChart.getByRole("region", { name: /exact data table/ });
  await expect(tableRegion).toBeVisible();
  const covered = perfCoveredDays("2026-01-01", "2026-01-08");
  expect(covered.length).toBe(7);
  for (const [day, value] of covered) {
    await expect(tableRegion.locator("tr", { hasText: day }))
      .toContainText(trimmedForDisplay(value));
  }
  // Keyboard reachability inside the node: the table region takes focus.
  await tableRegion.focus();
  await expect(tableRegion).toBeFocused();
});
