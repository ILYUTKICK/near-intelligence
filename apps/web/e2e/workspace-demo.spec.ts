/** NI-080: actual email-label entry, private navigation and visitor isolation. */
import { expect, test, type Page } from "@playwright/test";

import { readState } from "./harness/state";
import { expectNoSeriousViolations } from "./accessibility/helpers";

const state = readState() as { web_url: string; api_url: string };

async function enterDemo(page: Page) {
  await page.goto(`${state.web_url}/login`);
  await page.getByRole("textbox", { name: "Email", exact: true }).fill("visitor@example.test");
  await page.getByRole("button", { name: "Enter demo workspace" }).click();
  await expect(page).toHaveURL(`${state.web_url}/workspace`);
  await expect(page.getByRole("heading", { name: "My demo research" })).toBeVisible();
  const session = await page.request.get(`${state.web_url}/api/auth/session`);
  expect(session.ok()).toBe(true);
  return await session.json() as { subject: string };
}

test("email demo opens starter research, retains the cabinet, rotates and isolates same-label visitors", async ({ page, browser }) => {
  const first = await enterDemo(page);
  await expect(page.getByRole("heading", { name: "Data context" })).toHaveCount(0);
  const documentsResponse = await page.request.get(`${state.web_url}/api/documents`);
  expect(documentsResponse.ok()).toBe(true);
  const documents = await documentsResponse.json() as { items: Array<{ id: string }> };
  expect(documents.items).toHaveLength(1);
  const documentId = documents.items[0].id;
  await page.getByRole("link", { name: /Continue research/ }).click();
  await expect(page.getByLabel("Research paper editor")).toBeVisible();
  await expect(page.getByLabel("Research paper editor").getByRole("heading")).toHaveCount(8);
  await page.reload();
  await expect(page.getByLabel("Research paper editor").getByRole("heading")).toHaveCount(8);

  await page.goto(`${state.web_url}/workspace/saved-charts`);
  await page.getByRole("link", { name: "Explore charts" }).click();
  await expect(page).toHaveURL(`${state.web_url}/workspace/charts`);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.getByRole("link", { name: /^Network Activity/ }).click();
  await expect(page).toHaveURL(`${state.web_url}/workspace/data/network`);
  await expect(page.getByRole("heading", { name: "No network-level chart is registered yet" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.getByRole("link", { name: "Intents & Adoption", exact: true }).click();
  await expect(page).toHaveURL(`${state.web_url}/workspace/data/intents`);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expectNoSeriousViolations(page, "NI-080 workspace explorer");
  await page.getByRole("link", { name: "Open chart: Provider-reported Intents gross volume", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace\/data\/intents\/intents-volume/);
  await expect(page.locator("figure [role=img] svg")).toBeVisible();
  await page.getByRole("button", { name: "Custom range" }).click();
  const range = page.getByRole("dialog");
  await range.getByLabel("Start date").fill("2026-01-03");
  await range.getByLabel("End date").fill("2026-01-12");
  await range.getByRole("button", { name: "Apply range" }).click();
  await expect(page).toHaveURL(/\/workspace\/data\/intents\/intents-volume\?.*start=2026-01-03/);
  await expect(page.getByRole("region", { name: /exact data table/ })).toContainText("200.25");
  await page.getByRole("button", { name: "Save chart", exact: true }).click();
  await page.getByRole("link", { name: "Open saved chart" }).click();
  await expect(page).toHaveURL(/\/workspace\/saved-charts\//);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(page.getByRole("region", { name: /exact data table/ })).toContainText("200.25");


  const before = (await page.context().cookies()).find(cookie => cookie.name === "ni_session")?.value;
  const refresh = await page.request.post(`${state.web_url}/api/auth/refresh`, { headers: { origin: state.web_url } });
  expect(refresh.status()).toBe(200);
  expect((await page.context().cookies()).find(cookie => cookie.name === "ni_session")?.value).not.toBe(before);
  expect((await (await page.request.get(`${state.web_url}/api/auth/session`)).json()).subject).toBe(first.subject);

  const other = await browser.newContext();
  try {
    const secondPage = await other.newPage();
    const second = await enterDemo(secondPage);
    expect(second.subject).not.toBe(first.subject);
    const denied = await secondPage.request.get(`${state.web_url}/api/documents/${documentId}`);
    expect(denied.status()).toBe(404);
    const otherDocs = await (await secondPage.request.get(`${state.web_url}/api/documents`)).json();
    expect(otherDocs.items.map((item: { id: string }) => item.id)).not.toContain(documentId);
  } finally {
    await other.close();
  }

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(`${state.web_url}/login`);
  expect((await page.request.get(`${state.web_url}/api/documents`)).status()).toBe(401);
  const next = await enterDemo(page);
  expect(next.subject).not.toBe(first.subject);
  expect((await page.request.get(`${state.web_url}/api/documents/${documentId}`)).status()).toBe(404);
});
