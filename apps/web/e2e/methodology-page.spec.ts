/** NI-081: public reading path, source transparency without technical appendices. */
import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

import { readState } from "./harness/state";
import { expectNoSeriousViolations } from "./accessibility/helpers";

const state = readState() as { web_url: string };

test("methodology keeps readable evidence, stable chapters without technical disclosure blocks", async ({ page }, testInfo) => {
  await page.goto(`${state.web_url}/methodology`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const chapters = page.getByRole("navigation", { name: "On this page" });
  await expect(chapters).toBeVisible();
  const primary = await page.getByRole("main").innerText();
  expect(primary).not.toMatch(/\bNI-\d{3}\b/);
  expect(primary).not.toContain("Not implemented yet");
  expect(primary).toMatch(/gross fees/i);
  expect(primary).toMatch(/payouts/i);
  expect(primary).toMatch(/purchases/i);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await expectNoSeriousViolations(page, "NI-081 public methodology");

  const output = process.env.NI081_EVIDENCE_DIR ?? testInfo.outputPath("methodology-evidence");
  mkdirSync(output, { recursive: true });
  await page.screenshot({ path: path.join(output, "methodology-desktop.png") });

  for (const anchor of ["sources", "definitions", "collection", "readiness", "reproduce"]) {
    await chapters.locator(`a[href="#${anchor}"]`).click();
    await expect(page).toHaveURL(new RegExp(`#${anchor}$`));
    await expect(page.locator(`#${anchor}`)).toBeVisible();
  }

  await expect(page.getByRole("main").locator("details, summary")).toHaveCount(0);
  for (const removed of [
    "Full source register & access notes", "Definition versions & availability labels",
    "Validation rules & recorded calculation path", "Model readiness policy & recorded verdicts",
    "Reproduction commands & environment", "near_api.research verify", "PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01",
  ]) {
    await expect(page.getByRole("main")).not.toContainText(removed);
  }

  await chapters.locator('a[href="#definitions"]').click();
  await page.screenshot({ path: path.join(output, "methodology-definitions.png") });
});
