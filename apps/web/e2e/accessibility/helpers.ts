/**
 * Shared helpers for the NI-064 desktop accessibility suites (harness-only
 * code, never part of the application). Desktop 1440x900 only — no
 * mobile/tablet passes are required or authorized (8 November 2026 scope).
 *
 * The suites run under the NI-063 Playwright config: the global setup boots
 * the REAL stack (disposable PostgreSQL 18 + FastAPI + production next start
 * + export worker), so every scanned surface is the production application.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

import { readState } from "../harness/state";

export interface StackState {
  web_url: string;
  api_url: string;
  dataset_version_id: string;
  dataset_key: string;
  window: { start: string; end: string };
  day_values: Record<string, string>;
  pin_value: string;
  session_alice: string;
  session_bob: string;
  outage: string;
  inspect_document: string;
  inspect_dataset: string;
  perf_dataset_version_id: string;
  perf_dataset_key: string;
  perf_day_values: Record<string, string>;
  perf_window: { start: string; end: string; end_exclusive: string };
  perf_document_id: string;
  cluster_dir: string;
}

export function stackState(): StackState {
  return readState() as StackState;
}

/** Land on the web origin with the synthetic alice session cookie set. */
export async function signIn(page: Page, state: StackState, nextPath = "/workspace"): Promise<void> {
  await page.goto(`${state.session_alice}?next=${encodeURIComponent(nextPath)}`);
  await expect(page).toHaveURL(new RegExp(nextPath.replace(/[/?]/g, "\\$&")));
}

export interface ViolationSummary {
  id: string;
  impact: string | null | undefined;
  nodes: number;
}

/**
 * Run axe over the current page and hard-assert ZERO serious/critical
 * violations (the NI-064 acceptance gate). Lower-impact violations are
 * returned so the QA report can record each one with its justification
 * instead of silently passing.
 */
/** Duration of `--transition-fast` (tokens.css); used to outlast color transitions. */
const TRANSITION_FAST_MS = 200;

export async function expectNoSeriousViolations(
  page: Page,
  surface: string,
): Promise<ViolationSummary[]> {
  // Color-contrast scans must see a STATIC frame: controls animate their
  // colors (`transition-colors`, --transition-fast) and variant swaps
  // interpolate between token pairs mid-flight — an animation frame can
  // blend two individually-passing pairs into a failing one (observed in CI
  // on workspace home, where the Create button flips primary→secondary when
  // the data arrives). Wait for the network to settle plus one transition
  // window, then double-rAF so the last painted frame is committed.
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(TRANSITION_FAST_MS);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(
    () => requestAnimationFrame(resolve))));
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical");
  const recorded: ViolationSummary[] = results.violations
    .filter((violation) => violation.impact !== "serious" && violation.impact !== "critical")
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.length,
    }));
  expect(
    blocking,
    `${surface}: serious/critical axe violations — ${
      blocking.map((violation) => `${violation.id} (${violation.impact}, ${violation.nodes.length} nodes)`).join("; ")
    }`,
  ).toEqual([]);
  console.log(`[ni064-axe] ${surface}: 0 serious/critical; lower-impact: ${
    recorded.length ? JSON.stringify(recorded) : "none"}`);
  for (const violation of results.violations.filter(
    (item) => item.impact !== "serious" && item.impact !== "critical")) {
    // Keep actionable evidence for the report's lower-impact disposition;
    // an id/count alone cannot identify the affected landmark or control.
    console.log(`[ni064-axe-detail] ${surface}: ${JSON.stringify({
      id: violation.id, impact: violation.impact, help: violation.help,
      targets: violation.nodes.map((node) => node.target),
    })}`);
  }
  return recorded;
}

/** Convert a hex token value to the rgb() string computed styles report. */
export function hexToRgbString(hex: string): string {
  const value = hex.trim().replace(/^#/, "");
  const channels = [0, 2, 4].map((offset) => parseInt(value.slice(offset, offset + 2), 16));
  return `rgb(${channels.join(", ")})`;
}
