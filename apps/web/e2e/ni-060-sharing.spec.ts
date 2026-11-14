/** NI-060 consent, frozen chart and revocation on the disposable NI-063 stack. */
import { expect, test } from "@playwright/test";

import { readState } from "./harness/state";

const state = readState() as {
  web_url: string;
  perf_document_id: string;
  session_alice: string;
  session_bob: string;
};

// A capability is only needed during the run. Keep it out of trace archives.
test.use({ trace: "off" });

test("shares one acknowledged revision by consent and revokes it for another user", async ({ page, browser }) => {
  const documentPath = `/workspace/research/${state.perf_document_id}`;
  await page.goto(`${state.session_alice}?next=${encodeURIComponent(documentPath)}`);
  const share = page.getByTestId("share-open");
  await share.click();
  const dialog = page.getByRole("dialog", { name: "Share this revision (read-only)" });
  await expect(dialog.getByTestId("share-create")).toBeDisabled();
  await dialog.getByText("Read the exact shared content", { exact: true }).click();
  const preview = dialog.getByTestId("share-viewer");
  await expect(preview.getByText(/NI-064 performance fixture paragraph 1/).first()).toBeVisible();
  await expect(preview.getByTestId("share-chart").first()).toContainText("Pinned version");
  await dialog.getByTestId("share-consent").check();
  await dialog.getByTestId("share-create").click();
  const secretLink = dialog.getByRole("textbox", { name: "Share link" });
  await expect(secretLink).toBeVisible();
  const viewerUrl = await secretLink.inputValue();
  // Check only shape/origin here so assertion failures cannot print the link.
  expect(new URL(viewerUrl).origin === state.web_url).toBe(true);
  expect(/^\/share\/[A-Za-z0-9_-]{43}$/.test(new URL(viewerUrl).pathname)).toBe(true);

  const reader = await browser.newContext();
  try {
    const viewer = await reader.newPage();
    await viewer.goto(`${state.session_bob}?next=${encodeURIComponent("/")}`);
    const response = await viewer.goto(viewerUrl);
    expect(response?.headers()["cache-control"]).toContain("no-store");
    expect(response?.headers()["referrer-policy"]).toBe("no-referrer");
    expect(response?.headers()["x-robots-tag"]).toContain("noindex");
    await expect(viewer.getByRole("link", { name: "Open workspace" })).toHaveCount(0);
    const paper = viewer.getByTestId("share-viewer");
    await expect(paper.getByRole("heading", { level: 1 })).toContainText("NI-064 performance fixture");
    await expect(paper.getByTestId("share-chart").first().getByRole("region", { name: /exact data table/ }))
      .toContainText("100");
    const privateDocument = await reader.request.get(`${state.web_url}/api/documents/${state.perf_document_id}`);
    expect(privateDocument.status()).toBe(404);

    await dialog.getByTestId("share-close").click();
    await expect(share).toBeFocused();
    await share.click();
    await expect(dialog.getByRole("textbox", { name: "Share link" })).toHaveCount(0);
    const active = dialog.getByRole("listitem").filter({
      has: page.getByText("Active", { exact: true }),
    }).first();
    await active.getByRole("button", { name: "Revoke" }).click();
    await active.getByRole("button", { name: "Confirm revoke" }).click();
    await expect(dialog.getByText("Revoked", { exact: true }).first()).toBeVisible();
    const denied = await viewer.reload();
    expect(denied?.headers()["cache-control"]).toContain("no-store");
    await expect(viewer.getByTestId("share-denied")).toBeVisible();
    await expect(paper).toHaveCount(0);
  } finally {
    await reader.close();
  }
});
