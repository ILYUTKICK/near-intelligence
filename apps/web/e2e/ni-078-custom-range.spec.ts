/**
 * NI-078 — custom-range Apply verification against the real stack (the
 * explicit investigation item from the NI-076 review: "custom-range inputs
 * accepted visible dates, but automated Apply returned to the old selection
 * twice; cause not isolated").
 *
 * This spec reproduces the control end to end with the actual UI: open the
 * chart detail, set a custom range through the real dialog (native date
 * inputs driven by Playwright's fill, which dispatches proper input/change
 * events), click Apply range, and verify that:
 *   1. the URL selection resolves the requested window (replace-state URL);
 *   2. the fetched view re-resolves — the exact table shows the new window;
 *   3. a reload preserves the selection (the URL is the persistence);
 *   4. the sign-in continuation carries the custom range;
 *   5. saving through the real UI and reopening from Saved Charts preserves
 *      the custom window, and the compact card shows it.
 *
 * Only the synthetic-session transport is synthetic (the established harness
 * boundary); everything else — validation, delivery, PostgreSQL, sessions —
 * is the real stack.
 */
import { expect, test } from "@playwright/test";

import { readState } from "./harness/state";

interface StackState {
  web_url: string;
  window: { start: string; end: string };
  dataset_version_id: string;
  day_values: Record<string, string>;
  session_alice: string;
}

const state = readState() as StackState;

/** Full pinned selection URL of the inspected chart (the journey's URL). */
function chartSelectionUrl(): string {
  const filters = encodeURIComponent(JSON.stringify({ source: "SRC-LLAMA" }));
  return `${state.web_url}/data/intents/intents-volume?version=1`
    + `&start=${state.window.start}&end=${state.window.end}&filters=${filters}`;
}

const CUSTOM_START = "2026-01-03";
const CUSTOM_END = "2026-01-12";
const CUSTOM_LINE = `${CUSTOM_START} – ${CUSTOM_END} (UTC, end exclusive)`;

test("custom range: Apply resolves the requested window and survives reload, sign-in, save and reopen", async ({ page }) => {
  test.setTimeout(240_000);

  // -- 1. The actual UI: open the dialog and apply a custom range --------- //
  await page.goto(chartSelectionUrl());
  await expect(page.getByRole("heading", { level: 1, name: "Provider-reported Intents gross volume" }))
    .toBeVisible();
  const beforeTable = page.getByText(state.day_values[state.window.start]).first();
  await expect(beforeTable).toBeVisible(); // the pinned window is resolved

  await page.getByRole("button", { name: "Custom range" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Start date").fill(CUSTOM_START);
  await dialog.getByLabel("End date").fill(CUSTOM_END);
  await dialog.getByRole("button", { name: "Apply range" }).click();

  // -- 2. The URL selection resolves the requested window ------------------ //
  await expect.poll(() => page.url(), { timeout: 15_000 }).toContain(`start=${CUSTOM_START}`);
  await expect(page).toHaveURL(new RegExp(`[?&]end=${CUSTOM_END}(?:&|$)`));
  const table = page.getByRole("region", { name: /exact data table/ });
  await expect(table.getByText(state.day_values[CUSTOM_START], { exact: true })).toBeVisible();
  await expect(table.getByText(state.day_values[CUSTOM_END], { exact: true })).toHaveCount(0);
  await expect(page.getByText(new RegExp(`Custom range: ${CUSTOM_START}`))).toBeVisible();

  // -- 3. Reload: the URL is the selection's persistence ------------------- //
  await page.reload();
  await expect.poll(() => page.url()).toContain(`start=${CUSTOM_START}`);
  await expect(page).toHaveURL(new RegExp(`[?&]end=${CUSTOM_END}(?:&|$)`));
  await expect(page.getByText(state.day_values[CUSTOM_START]).first()).toBeVisible();

  // -- 4. The sign-in continuation carries the custom range ---------------- //
  await page.getByRole("button", { name: "+ Add to research" }).click();
  await expect(page).toHaveURL(/\/login\?next=/);
  const nextPath = new URL(page.url()).searchParams.get("next") ?? "";
  const nextSelection = new URL(nextPath, state.web_url).searchParams;
  expect(nextSelection.get("start")).toBe(CUSTOM_START);
  expect(nextSelection.get("end")).toBe(CUSTOM_END);
  expect(nextSelection.get("dataset_version")).toBe(state.dataset_version_id);
  expect(nextSelection.get("filters")).toBe(JSON.stringify({ source: "SRC-LLAMA" }));
  await page.goto(`${state.session_alice}?next=${encodeURIComponent(nextPath)}`);
  await expect.poll(() => page.url()).toContain(`start=${CUSTOM_START}`);
  await expect(page.getByRole("button", { name: "Save chart", exact: true })).toBeVisible();

  // -- 5. Save through the real UI and reopen it --------------------------- //
  await page.getByRole("button", { name: "Save chart", exact: true }).click();
  await expect(page.getByText("Chart saved. Your range and filters are preserved.")).toBeVisible();
  await page.getByRole("link", { name: "Open saved chart" }).click();
  await expect(page).toHaveURL(/\/workspace\/saved-charts\//);
  await expect(page.getByText(state.day_values[CUSTOM_START]).first()).toBeVisible();

  // -- 6. The compact Saved Charts card shows the custom window ------------ //
  await page.goto(`${state.web_url}/workspace/saved-charts`);
  await expect(page.getByText(CUSTOM_LINE).first()).toBeVisible();
});
