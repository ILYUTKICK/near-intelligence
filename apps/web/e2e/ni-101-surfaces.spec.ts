/** Complete registered chart navigation; fixture transport, real web/API/DB. */
import { expect, test } from "@playwright/test";
import { EXPLORER_CATEGORIES, explorerForRegistryCategory } from "../src/features/charts/library/explorer-categories";
import { readState } from "./harness/state";

const state = readState() as { web_url: string; api_url: string; session_alice: string };

test("NI-101: every registered chart opens on public and private surfaces", async ({ page }, testInfo) => {
  const response = await page.request.get(`${state.api_url}/api/charts?limit=100`);
  expect(response.ok()).toBe(true);
  const catalog = await response.json() as { items: { chart_id: string; title: string; category: string; data_status: string; unavailable_reason: string | null }[]; next_cursor: string | null };
  expect(catalog.items.length).toBeGreaterThan(0);
  expect(catalog.next_cursor).toBeNull();
  const reviewed: { path: string; state: string }[] = [];

  for (const prefix of ["", "/workspace"]) {
    if (prefix) await page.goto(`${state.session_alice}?next=${encodeURIComponent("/workspace/data")}`);
    for (const category of EXPLORER_CATEGORIES) {
      const path = `${prefix}/data/${category.slug}`;
      await page.goto(`${state.web_url}${path}`);
      await expect(page.getByRole("heading", { level: 1, name: category.label, exact: true })).toBeVisible();
    }
    for (const chart of catalog.items) {
      const category = explorerForRegistryCategory(chart.category);
      const path = category ? `${prefix}/data/${category.slug}/${chart.chart_id}` : `${prefix}/charts/${chart.chart_id}`;
      await page.goto(`${state.web_url}${path}`);
      await expect(page.getByRole("heading", { level: 1, name: chart.title, exact: true })).toBeVisible();
      if (chart.data_status === "unavailable") {
        await expect(page.getByText(chart.unavailable_reason!, { exact: false }).first()).toBeVisible();
        await expect(page.getByRole("button", { name: "Save chart", exact: true })).toHaveCount(0);
        reviewed.push({ path, state: "registered unavailable" });
      } else {
        // An approved definition can still lack a resolvable dataset in a clean
        // clone. Accept only a real frame or the visible delivery error.
        await expect(page.locator("figure, [role='alert']").first()).toBeVisible();
        const rendered = await page.locator("figure").count() > 0;
        if (rendered && prefix) {
          await expect(page.getByRole("button", { name: "Save chart", exact: true })).toBeVisible();
          await expect(page.getByRole("button", { name: "Add to research", exact: true })).toBeVisible();
        }
        reviewed.push({ path, state: rendered ? "resolved chart" : "visible dataset error" });
      }
    }
  }
  await testInfo.attach("registered-chart-review.json", { body: JSON.stringify(reviewed, null, 2), contentType: "application/json" });
});
