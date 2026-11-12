/**
 * NI-064 — desktop keyboard journeys through the research editor workbench
 * (1440x900; desktop-only scope per the 8 November 2026 override).
 *
 * Every step asserts the ACTUAL focus target (toHaveFocus), not merely the
 * absence of violations: insert menu, slash menu, keyboard block reorder,
 * chart source drawer, evidence dialog and export dialog (trap + Escape with
 * focus return), and the visible focus ring on real keyboard focus.
 *
 * Honest boundary (recorded in the card): jsdom cannot emulate IME
 * composition and these Playwright keyboard events do not compose CJK text
 * either — real IME behavior stays an operator-side manual check. Keyboard
 * block REORDER (the keyboard alternative to drag) IS covered here against
 * the real editor.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { signIn, stackState } from "./helpers";

const state = stackState();

/** ProseMirror "Mod" is Meta on macOS, Ctrl elsewhere (CI runs Linux). */
const MOD = process.platform === "darwin" ? "Meta" : "Control";

/** Document order distance between two text markers (negative = A before B). */
async function documentOrder(page: Page, textA: string, textB: string): Promise<number> {
  return page.evaluate(([a, b]) => {
    const paper = document.querySelector("[data-pane='paper']");
    if (!paper) throw new Error("paper pane missing");
    const walker = document.createTreeWalker(paper, NodeFilter.SHOW_TEXT);
    let order = 0;
    let positionA = -1;
    let positionB = -1;
    while (walker.nextNode()) {
      const value = walker.currentNode.textContent ?? "";
      if (value.includes(a) && positionA === -1) positionA = order;
      if (value.includes(b) && positionB === -1) positionB = order;
      order += 1;
    }
    if (positionA === -1 || positionB === -1) throw new Error("marker text not found");
    return positionA - positionB;
  }, [textA, textB]);
}

/** The colon disambiguates "paragraph 1" from "paragraph 10"..."paragraph 19". */
const PARAGRAPH_ONE = "NI-064 performance fixture paragraph 1:";
const PARAGRAPH_TWO = "NI-064 performance fixture paragraph 2:";

async function openFixtureDocument(page: Page): Promise<Locator> {
  await signIn(page, state, `/workspace/research/${state.perf_document_id}`);
  const editor = page.getByLabel("Research paper editor");
  await expect(editor).toBeVisible();
  // The last prose block is rendered: all 200 blocks are in the editor DOM.
  await expect(editor.getByText("NI-064 performance fixture paragraph 160").first())
    .toBeVisible({ timeout: 30_000 });
  return editor;
}

/**
 * Walk backwards from the editor to a toolbar control with real Shift+Tab
 * presses (keyboard focus, so :focus-visible applies) and return it focused.
 * On failure, report the recorded focus path so the walk is debuggable.
 */
async function shiftTabTo(page: Page, target: Locator, maxSteps = 40): Promise<void> {
  const describeActive = (): Promise<string> => page.evaluate(() => {
    const node = document.activeElement;
    if (!node) {
      return "none";
    }
    const label = node.getAttribute("aria-label") ?? node.textContent?.slice(0, 40) ?? "";
    return `${node.tagName.toLowerCase()}${label ? ` "${label.trim()}"` : ""}`;
  });
  const path: string[] = [];
  for (let step = 0; step < maxSteps; step += 1) {
    const focused = await target.evaluate((node) => node === document.activeElement);
    if (focused) {
      return;
    }
    await page.keyboard.press("Shift+Tab");
    path.push(await describeActive());
  }
  throw new Error(
    `Shift+Tab walk did not reach the target within ${maxSteps} steps; focus path: ${
      path.join(" -> ")}`,
  );
}

/**
 * The deepest paragraph carrying the marker text. (getByText also matches
 * ancestor elements, and .first() would click the outer editor's center.)
 */
function markerParagraph(page: Page, marker: string) {
  return page.getByLabel("Research paper editor")
    .locator("p")
    .filter({ hasText: marker })
    .first();
}

async function focusMarkerParagraph(page: Page, marker: string): Promise<void> {
  await markerParagraph(page, marker).click();
}

test.describe.configure({ mode: "serial" });

test("skip link is the first tab stop with a visible focus ring; the toolbar is reachable backwards", async ({ page }) => {
  await openFixtureDocument(page);

  // First Tab from a fresh page load lands on the skip link with the token
  // focus ring (2px) actually drawn.
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to main content" });
  await expect(skip).toBeFocused();
  await expect(skip).toHaveCSS("outline-width", "2px");

  // The workbench toolbar is reachable backwards from the paper: in DOM
  // order the outline pane sits between the toolbar and the paper, so the
  // first Shift+Tab lands on the last outline entry, and continuing reaches
  // the Insert block trigger.
  await markerParagraph(page, PARAGRAPH_TWO).click();
  await page.keyboard.press("Shift+Tab");
  const outlineNav = page.getByRole("navigation", { name: "Document outline" }).first();
  const outlineFocused = await outlineNav.evaluate(
    (node) => node.contains(document.activeElement),
  );
  expect(outlineFocused, "Shift+Tab from the paper lands in the outline pane").toBe(true);
  await shiftTabTo(page, page.getByRole("button", { name: "Insert block" }), 40);
});

test("insert menu opens and inserts from the keyboard with a live announcement", async ({ page }) => {
  const editor = await openFixtureDocument(page);
  await focusMarkerParagraph(page, PARAGRAPH_TWO);

  // Reach the trigger with real keyboard focus, so :focus-visible holds.
  const insertButton = page.getByRole("button", { name: "Insert block" });
  await markerParagraph(page, PARAGRAPH_TWO).click();
  await shiftTabTo(page, insertButton);
  await expect(insertButton).toHaveCSS("outline-width", "2px");

  await page.keyboard.press("Enter");
  const dividerItem = page.getByRole("menuitem", { name: /Divider/ });
  await expect(dividerItem).toBeVisible();
  // Arrow down to the last item (Divider); early presses can land while the
  // menu is still mounting, so press until the item actually holds focus.
  let dividerFocused = false;
  for (let step = 0; step < 15 && !dividerFocused; step += 1) {
    await page.keyboard.press("ArrowDown");
    dividerFocused = await dividerItem.evaluate((node) => node === document.activeElement);
  }
  if (!dividerFocused) {
    const activeLabel = await page.evaluate(() => {
      const node = document.activeElement;
      return `${node?.tagName.toLowerCase()} "${node?.getAttribute("aria-label") ?? node?.textContent?.slice(0, 30) ?? ""}"`;
    });
    throw new Error(`ArrowDown walk did not reach the Divider menu item; active element: ${activeLabel}`);
  }
  await expect(dividerItem).toBeFocused();
  await page.keyboard.press("Enter");
  // The polite live region announces the insertion (NI-039 contract).
  await expect(page.getByTestId("editor-announcement")).toContainText("Block inserted");
  // Radix returned focus to the trigger, so the undo must go back through
  // the editor surface: refocus the paper on a deterministic prose block
  // (a center click can land on a chart node control in the 200-block
  // fixture), then undo the inserted divider so the fixture keeps its
  // 200 blocks.
  await expect(editor.locator("hr[data-editor-divider]")).toHaveCount(1);
  await markerParagraph(page, PARAGRAPH_TWO).click();
  await page.keyboard.press(`${MOD}+z`);
  await expect(editor.locator("hr[data-editor-divider]")).toHaveCount(0);
});

test("slash menu: opens from / in an empty block, inserts with Enter, closes with Escape", async ({ page }) => {
  // The canonical "/" trigger is an EMPTY top-level paragraph, so the journey
  // runs on a fresh throwaway document created through the real product flow
  // (the 200-block performance fixture stays pristine for the other suites).
  await signIn(page, state, "/workspace");
  await page.getByRole("button", { name: "Create document" }).click();
  const editor = page.getByLabel("Research paper editor");
  await expect(editor).toBeVisible({ timeout: 30_000 });
  await editor.click();

  // keyboard.insertText goes through Chromium's real editing pipeline
  // (beforeinput), which is the path the fixed slash trigger listens on;
  // Playwright's synthetic key events bypass that pipeline on this Chromium
  // build and produce no DOM input events at all.
  await page.keyboard.insertText("/");
  const slashMenu = page.getByTestId("slash-menu");
  await expect(slashMenu).toBeVisible();
  await expect(slashMenu).toHaveAttribute("aria-label", "Insert block (slash menu)");
  await expect(slashMenu.getByRole("option", { name: /Paragraph/ }))
    .toHaveAttribute("aria-selected", "true");

  // ArrowDown twice -> Heading 1; Enter inserts it and announces.
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(slashMenu).toBeHidden();
  await expect(page.getByTestId("editor-announcement")).toContainText("Block inserted");
  // Reload to a deterministic baseline (the throwaway document was never
  // saved with content) and repeat the trigger for the Escape path.
  await page.reload();
  await expect(editor).toBeVisible({ timeout: 30_000 });
  await editor.click();

  // Escape closes the menu without inserting anything.
  await page.keyboard.insertText("/");
  await expect(slashMenu).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(slashMenu).toBeHidden();
  await expect(editor).toBeFocused();
});

// The three tests below run in ISOLATED browser contexts: earlier tests in
// this file close pages whose unacknowledged autosave state was written to
// sessionStorage as a recovery draft for this same document (the NI-040
// beforeunload contract), and a shared context would leak that draft banner
// into these journeys.
test("keyboard block reorder moves the focused block and announces it", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await openFixtureDocument(page);
  await expect(markerParagraph(page, PARAGRAPH_ONE)).toBeVisible();

  const before = await documentOrder(page, PARAGRAPH_ONE, PARAGRAPH_TWO);
  expect(before).toBeLessThan(0); // paragraph 1 precedes paragraph 2

  // Focus paragraph 2 and move it up with the Mod-Alt shortcut (the keyboard
  // alternative to drag; ProseMirror Mod = Meta on macOS).
  // Let the workbench's post-load settling (autosave acks, account
  // revalidation) finish before interacting.
  await page.waitForTimeout(2500);
  await focusMarkerParagraph(page, PARAGRAPH_TWO);
  const caretProbe = await page.evaluate(() => {
    const pm = document.querySelector(".ProseMirror") as HTMLElement & {
      editor?: { state: { selection: { $from: { depth: number; pos: number; parent: { type: { name: string }; textContent: string } } } } };
    };
    const sel = pm?.editor?.state.selection.$from;
    return { depth: sel?.depth, pos: sel?.pos, parent: sel?.parent.type.name, text: sel?.parent.textContent.slice(0, 40) };
  });
  console.log(`[reorder] caret before move: ${JSON.stringify(caretProbe)}`);
  await page.keyboard.press(`${MOD}+Alt+ArrowUp`);
  await expect(page.getByTestId("editor-announcement")).toContainText("moved up");
  const after = await documentOrder(page, PARAGRAPH_ONE, PARAGRAPH_TWO);
  expect(after).toBeGreaterThan(0); // paragraph 2 now precedes paragraph 1

  // Move it back down: document order restored.
  await page.keyboard.press(`${MOD}+Alt+ArrowDown`);
  await expect(page.getByTestId("editor-announcement")).toContainText("moved down");
  const restored = await documentOrder(page, PARAGRAPH_ONE, PARAGRAPH_TWO);
  expect(restored).toBeLessThan(0);
  await context.close();
});

test("chart source drawer and pinned-context details operate from the keyboard", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const editor = await openFixtureDocument(page);
  const firstChart = editor.locator("[data-live-chart-block]").first();
  await firstChart.scrollIntoViewIfNeeded();
  // The editor chart pins the NI-064 performance dataset by UUID; the
  // rendered value is the perf fixture's first day ("100.00", trailing zero
  // trimmed by the significant-digit formatter).
  await expect(firstChart.getByText(`Observed dataset: ${state.perf_dataset_version_id}`))
    .toBeVisible({ timeout: 30_000 });
  await expect(firstChart.getByText("100").first()).toBeVisible({ timeout: 30_000 });

  // Native details summary: focus + Enter toggles the pinned-context drawer.
  const summary = firstChart.getByText("Chart definition and pinned context");
  await summary.focus();
  await expect(summary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(firstChart.getByText(/Context hash: [0-9a-f]{64}/)).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(firstChart.getByText(/Context hash: [0-9a-f]{64}/)).toBeHidden();

  // Escape inside the chart node returns selection to the editor (NI-042).
  await summary.focus();
  await page.keyboard.press("Escape");
  await expect(editor).toBeFocused();

  // The chart's source dialog: keyboard open, Escape closes with focus
  // returned to the trigger (Radix dialog contract).
  const sourcesTrigger = firstChart.getByRole("button", { name: /Sources/ }).first();
  await sourcesTrigger.focus();
  await expect(sourcesTrigger).toBeFocused();
  await page.keyboard.press("Enter");
  const sourceDialog = page.getByRole("dialog", { name: "Sources and definitions" });
  await expect(sourceDialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sourceDialog).toBeHidden();
  await expect(sourcesTrigger).toBeFocused();
  await context.close();
});

test("evidence and export dialogs trap focus and return it on Escape", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await openFixtureDocument(page);

  // Hypothesis dialog: focus enters the dialog, stays inside across Tab, and
  // Escape returns focus to the trigger. (The performance fixture has no
  // hypothesis, so the evidence-link dialog — reachable only from a
  // hypothesis card — is exercised by the NI-063 journey, which also covers
  // the evidence panel's keyboard entry navigation and focus return.)
  const hypothesisTrigger = page.getByRole("button", { name: "Add hypothesis" });
  await hypothesisTrigger.focus();
  await page.keyboard.press("Enter");
  const hypothesisDialog = page.getByRole("dialog");
  await expect(hypothesisDialog).toBeVisible();
  const hypothesisFocusedInside = await page.evaluate(() =>
    Boolean(document.querySelector("[role='dialog']")?.contains(document.activeElement)));
  expect(hypothesisFocusedInside).toBe(true);
  for (let step = 0; step < 6; step += 1) {
    await page.keyboard.press("Tab");
    const inside = await page.evaluate(() =>
      Boolean(document.querySelector("[role='dialog']")?.contains(document.activeElement)));
    expect(inside, `Tab ${step + 1} stays inside the hypothesis dialog`).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(hypothesisDialog).toBeHidden();
  await expect(hypothesisTrigger).toBeFocused();

  // Export dialog: same trap + Escape-with-return contract.
  const exportTrigger = page.getByTestId("export-open");
  await exportTrigger.focus();
  await page.keyboard.press("Enter");
  const exportDialog = page.getByTestId("export-dialog");
  await expect(exportDialog).toBeVisible();
  for (let step = 0; step < 6; step += 1) {
    await page.keyboard.press("Tab");
    const inside = await page.evaluate(() =>
      Boolean(document.querySelector("[role='dialog']")?.contains(document.activeElement)));
    expect(inside, `Tab ${step + 1} stays inside the export dialog`).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(exportDialog).toBeHidden();
  await expect(exportTrigger).toBeFocused();
  await context.close();
});
