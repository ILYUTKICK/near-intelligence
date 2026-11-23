/**
 * NI-063 — the complete research workflow end to end, against the REAL stack
 * (desktop 1440x900; desktop-only scope per the 8 November 2026 override).
 *
 * The Playwright global setup boots: a disposable loopback PostgreSQL 18, the
 * real FastAPI gateway behind the real production `next start` server, the
 * real NI-058 export worker, and one approved synthetic dataset staged through
 * the real NI-028 pipeline. The primary API is never mocked: every value the
 * assertions check was persisted in PostgreSQL and served through the real
 * delivery/documents/export routes.
 *
 * Honest auth boundary (the established harness pattern of this repository,
 * e.g. apps/api/tests/test_saved_charts_http.py): only the provider JWKS
 * transport is synthetic. Sign-in completes through a harness-only
 * `/_ni063/session` redirect that sets the real signed session cookie; ES256
 * verification, issuer/audience matching, principal bootstrap, CSRF and RLS
 * all execute normally. No real Supabase account is created or contacted.
 *
 * Journey (Testing strategy "Full E2E" row): anonymous claim trace
 * (landing → methodology → explore) → chart inspection with exact values →
 * sign-in continuation → save chart → create research with the pinned chart →
 * prose + hypothesis + insight + contrary evidence → reopen → source outage →
 * export on pinned data → ZIP/manifest/DB verification → second-user denial.
 */
import { expect, test, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

import { readState } from "./harness/state";
import { readZip } from "./harness/zip";

interface StackState {
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
  cluster_dir: string;
}

const state = readState() as StackState;

const DOCUMENT_TITLE = "Synthetic NI-063 claim trace";
const PARAGRAPH_ONE = "The inspected intents volume stays provider-reported and source-qualified; it is not token value.";
const OUTAGE_PARAGRAPH = "Recorded during the synthetic source outage: the pinned observation above is unchanged.";
const HYPOTHESIS_STATEMENT = "Does observed intents volume lead provider fee growth in this window?";
const INSIGHT_TEXT = "Volume rose across the pinned window while the source stayed single-provider; the claim only covers this window.";

/** State carried across the ordered journey (single worker, serial). */
const journey: {
  contextHash?: string;
  documentId?: string;
  documentVersionRow?: {
    id: string;
    revision: number;
    content_sha256: string;
    resolved_contexts: Record<string, { context_hash: string }>;
  };
  exportZipPath?: string;
  exportZipSha256?: string;
  exportJobId?: string;
  manifest?: {
    bundle_format_version: number;
    document: { document_id: string; version_id: string; revision: number; content_sha256: string; title: string };
    plan_sha256: string;
    files: Array<{ path: string; sha256: string; byte_size: number }>;
    charts: Array<{ block_id: string; svg: { path: string; sha256: string }; csv: { path: string; sha256: string } }>;
  };
} = {};

function sha256(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex");
}

/** Full pinned selection URL of the inspected chart (a validated selection). */
function chartSelectionUrl(): string {
  const filters = encodeURIComponent(JSON.stringify({ source: "SRC-LLAMA" }));
  return `${state.web_url}/data/intents/intents-volume?version=1`
    + `&start=${state.window.start}&end=${state.window.end}&filters=${filters}`;
}

async function setOutage(enabled: boolean, page: Page): Promise<void> {
  const response = await page.request.post(state.outage, { data: { enabled } });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ enabled });
}

async function expectRecordedDataset(page: Page) {
  // NI-096: provenance is announced nonvisually (sr-only), never a drawer.
  const provenance = page.getByText(`Dataset version: ${state.dataset_version_id}`);
  await expect(provenance).toBeAttached();
  await expect(provenance.locator("xpath=ancestor::*[contains(@class, 'sr-only')]").first()).toBeAttached();
}

async function inspectDocumentVersion(page: Page, documentId: string) {
  const response = await page.request.get(`${state.inspect_document}/${documentId}`);
  // The harness DB inspection must see the version row.
  expect(response.status()).toBe(200);
  return (await response.json()) as NonNullable<typeof journey.documentVersionRow>;
}

/** Autosave may persist an intermediate typing revision; capture the acknowledged one. */
async function waitForSavedRevision(page: Page, minimumRevision: number): Promise<number> {
  let acknowledged = 0;
  await expect.poll(async () => {
    const status = await page.getByTestId("save-status").textContent();
    const match = /^(?:All changes saved|No unsaved changes).*Revision (\d+)/.exec(status ?? "");
    acknowledged = match ? Number(match[1]) : 0;
    return acknowledged;
  }, { timeout: 30_000 }).toBeGreaterThanOrEqual(minimumRevision);
  return acknowledged;
}

/** Insert one paragraph after the current block and type into it. */
async function addParagraph(page: Page, text: string): Promise<void> {
  await page.getByRole("button", { name: "Insert block" }).click();
  await page.getByRole("menuitem", { name: "Paragraph" }).click();
  const editor = page.getByLabel("Research paper editor");
  const paragraph = editor.locator("p").last();
  await paragraph.click();
  await page.keyboard.type(text);
  await expect(editor).toContainText(text);
}

test.describe.configure({ mode: "serial" });

test("complete research journey: anonymous trace, sign-in, save chart, document, evidence, outage, export", async ({ page }) => {
  test.setTimeout(600_000);

  // -- 1. Anonymous visitors see only public artifacts ------------------- //
  const homeApi = await page.request.get(`${state.web_url}/api/home`);
  // Anonymous /api/home must not leak private aggregates.
  expect(homeApi.status()).toBe(401);
  const documentsApi = await page.request.get(`${state.web_url}/api/documents`);
  // Anonymous /api/documents must be denied.
  expect(documentsApi.status()).toBe(401);

  await page.goto(`${state.web_url}/`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  // NI-086 overview copy: the anonymous paths into the public thesis and
  // methodology keep their relative hrefs under the new link names.
  const thesisLink = page.getByRole("link", { name: "full research" });
  await expect(thesisLink).toBeVisible();
  expect(await thesisLink.getAttribute("href")).toMatch(/^\//);
  const methodologyLink = page.getByRole("link", { name: "Our methodology" });
  await expect(methodologyLink).toBeVisible();

  await page.goto(`${state.web_url}/methodology`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("#definitions")).toBeAttached();

  // -- 2. Claim trace through the public explorer ------------------------ //
  await page.goto(`${state.web_url}/data`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.getByRole("link", { name: /Intents/ }).first().click();
  await expect(page).toHaveURL(/\/data\/intents$/);

  await page.getByRole("link", { name: /Provider-reported Intents gross volume/ }).first().click();
  await expect(page).toHaveURL(/\/data\/intents\/intents-volume/);
  await expect(page.getByRole("heading", { level: 1, name: "Provider-reported Intents gross volume" }))
    .toBeVisible();
  // NI-096: the anonymous surface exposes exactly ONE private-action
  // continuation — the context-preserving Add to research.
  await expect(page.getByRole("button", { name: "+ Add to research" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in to save this chart" })).toHaveCount(0);

  // NI-080/NI-092: an implicit default is clamped to the approved coverage and
  // preselects the first approved filter value. Explicit dates remain
  // authoritative even when they have no observations.
  await expect(page.getByRole("group", { name: "Time range" })).toBeVisible();
  // The inspected selection may end before dataset coverage. Read the
  // independent delivery metadata instead of treating state.window as the
  // complete dataset's half-open period.
  const coverageResponse = await page.request.get(`${state.api_url}/api/datasets/${state.dataset_version_id}`);
  expect(coverageResponse.ok()).toBe(true);
  const coverage = await coverageResponse.json() as { start: string; end: string };
  expect(coverage.start).toBe("2026-01-01");
  expect(coverage.end).toBe("2026-01-15");
  await expect(page.getByText(`Default period: ${coverage.start} to ${coverage.end} UTC (end excluded), within the latest approved dataset.`, { exact: true })).toBeVisible();
  await expect(page.getByText(state.pin_value)).toBeVisible();
  await page.goto(`${state.web_url}/data/intents/intents-volume?version=1&start=2026-11-01&end=2026-11-04`);
  await expect(page).toHaveURL(/start=2026-11-01&end=2026-11-04/);
  await expect(page.getByText(state.pin_value)).toHaveCount(0);
  await expect(page.getByText(/Nothing was observed for this selection/)).toBeVisible();

  // The pinned full-selection claim: exact persisted values, exact dataset.
  await page.goto(chartSelectionUrl());
  await expect(page.getByText(state.pin_value).first()).toBeVisible();
  // The dataset identity is the exact persisted approved dataset (browser -> DB).
  await expectRecordedDataset(page);

  // Keyboard range control: focus the 7-day preset and activate it with Enter;
  // the preset anchors to the pinned selection end, not the wall clock.
  const sevenDays = page.getByRole("group", { name: "Time range" })
    .getByRole("button", { name: "Last 7 days" });
  await sevenDays.focus();
  await expect(sevenDays).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(sevenDays).toHaveAttribute("aria-pressed", "true");
  const anchoredStart = "2026-01-07"; // Last 7 days anchored to the pinned end (UTC [start, end))
  await expect.poll(() => page.url(), { timeout: 15_000 })
    .toContain(`start=${anchoredStart}&end=${state.window.end}`);

  // -- 3. Sign-in continuation preserves the inspected selection --------- //
  const continueButton = page.getByRole("button", { name: "+ Add to research" });
  await continueButton.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/login\?next=/);
  const loginUrl = new URL(page.url());
  const nextPath = decodeURIComponent(loginUrl.searchParams.get("next") ?? "");
  expect(nextPath.startsWith("/data/intents/intents-volume")).toBe(true);
  expect(nextPath).toContain(`start=${anchoredStart}`); // the keyboard selection survives

  // Harness-only synthetic session (real signed cookie, ES256 verified by the
  // gateway chain); it redirects to the preserved internal target.
  await page.goto(`${state.session_alice}?next=${encodeURIComponent(nextPath)}`);
  await expect.poll(() => page.url()).toContain("/data/intents/intents-volume");
  await expect.poll(() => page.url()).toContain(`start=${anchoredStart}`);
  await expect.poll(() => page.url()).toContain(`dataset_version=${state.dataset_version_id}`);
  await expect(page.getByRole("button", { name: "Add to research", exact: true })).toBeVisible();

  // -- 4. Add the chart to an owned research document --------------------- //
  // NI-096: the Save chart action was removed from the detail UI; the owned
  // persistence flow is Add to research with the pinned context.
  await page.getByRole("button", { name: "Add to research", exact: true }).click();
  const saveDialog = page.getByRole("dialog");
  await expect(saveDialog.getByText(/Inspected dataset: /)).toBeVisible();
  await saveDialog.getByRole("button", { name: "Confirm Add Chart" }).click();
  await expect(saveDialog).toBeHidden();
  await page.goto(`${state.web_url}/workspace`);
  const savedResearch = page.getByRole("link", { name: /Continue research/ }).first();
  await expect(savedResearch).toBeVisible();
  await savedResearch.click();
  await expect(page).toHaveURL(/\/workspace\/research\//);
  // The added chart is a live view over the inspected 7-day selection
  // (UTC [start, end)); the first day carries the persisted exact value.
  await expect(page.getByText(state.day_values[anchoredStart]).first()).toBeVisible();

  // -- 5. Add to research: destination picker -> new document ------------- //
  await page.goto(chartSelectionUrl());
  await page.getByRole("button", { name: "Add to research" }).click();
  const destinationDialog = page.getByRole("dialog");
  await expect(destinationDialog).toContainText("Add chart to your research");
  await expect(destinationDialog).toContainText(`Inspected dataset: ${state.dataset_version_id}`);
  await destinationDialog.getByLabel("Destination").selectOption({ label: "Create new research" });
  await destinationDialog.getByLabel("New research title").fill(DOCUMENT_TITLE);
  await destinationDialog.getByRole("button", { name: "Confirm Add Chart" }).click();
  // The acknowledged status and the link render outside the dialog subtree.
  await expect(page.getByText("One chart added with its inspected context."))
    .toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: "Open research" }).click();
  await expect(page).toHaveURL(/\/workspace\/research\/[0-9a-f-]{36}$/);
  journey.documentId = page.url().split("/").pop();

  // -- 6. The document holds the pinned chart ---------------------------- //
  const editor = page.getByLabel("Research paper editor");
  await expect(editor).toBeVisible();
  await expect(page.getByText("Opening or typing never refreshes this pin")).toBeVisible();
  await expect(page.getByText(state.pin_value).first()).toBeVisible();
  await waitForSavedRevision(page, 2);
  // NI-065: a real saved uncited chart yields an actionable advisory. The
  // keyboard jump changes selection only, then adding an insight fixes it.
  const integrity = page.getByTestId("integrity-panel").filter({ visible: true });
  await expect(integrity.getByTestId("integrity-revision")).toHaveText("Checked saved revision 2.");
  await expect(integrity.getByText("Advisory · Uncited pinned chart")).toBeVisible();
  const integrityJump = integrity.getByRole("button", { name: /Show block .* in the paper/ });
  await integrityJump.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("editor-announcement")).toContainText("Uncited pinned chart");
  await waitForSavedRevision(page, 2);
  // Capture the pinned context hash from the chart node's own inspection.
  await page.getByText("Chart definition and pinned context").click();
  await expect(page.getByText(`Observed dataset: ${state.dataset_version_id}`)).toBeVisible();
  const contextLine = page.getByText(/^Context hash: [0-9a-f]{64}$/);
  await expect(contextLine).toBeVisible();
  journey.contextHash = ((await contextLine.textContent()) ?? "").replace("Context hash: ", "");

  // -- 7. Prose via the insert menu; capture its saved revision --------- //
  await addParagraph(page, PARAGRAPH_ONE);
  const proseRevision = await waitForSavedRevision(page, 3);

  // -- 8. Hypothesis ------------------------------------------------------ //
  await page.getByRole("button", { name: "Add hypothesis" }).click();
  const hypothesisDialog = page.getByRole("dialog");
  await expect(hypothesisDialog).toContainText("Add hypothesis");
  await hypothesisDialog.getByLabel("Hypothesis statement").fill(HYPOTHESIS_STATEMENT);
  await hypothesisDialog.getByRole("button", { name: "Save hypothesis" }).click();
  await expect(page.getByText(HYPOTHESIS_STATEMENT).first()).toBeVisible();
  const hypothesisRevision = await waitForSavedRevision(page, proseRevision + 1);

  // -- 9. Insight pinned to the chart's inspected context ----------------- //
  await page.getByRole("button", { name: "Add Insight" }).click();
  const insightDialog = page.getByRole("dialog");
  await expect(insightDialog.getByLabel("Insight text")).toBeVisible();
  await insightDialog.getByLabel("Insight text").fill(INSIGHT_TEXT);
  await insightDialog.getByRole("button", { name: "Save insight" }).click();
  await expect(page.getByText(INSIGHT_TEXT).first()).toBeVisible();
  const insightRevision = await waitForSavedRevision(page, hypothesisRevision + 1);
  await expect(integrity.getByTestId("integrity-revision")).toHaveText(`Checked saved revision ${insightRevision}.`);
  await expect(integrity.getByTestId("integrity-empty")).toHaveText("No integrity findings on this revision.");
  await expect(integrity.getByTestId("integrity-findings")).toHaveCount(0);

  // -- 10. Contrary evidence against the hypothesis ----------------------- //
  await page.getByRole("button", { name: "Add evidence" }).click();
  const evidenceDialog = page.getByRole("dialog");
  await expect(evidenceDialog).toContainText("Link a saved target to a hypothesis");
  await evidenceDialog.getByLabel("Evidence classification").selectOption({ label: "Contradicting" });
  await evidenceDialog.getByLabel("Target type").selectOption({ label: "Insight in this research" });
  const targetSelect = evidenceDialog.getByLabel("Evidence target");
  // Option 0 is the "Choose a target" placeholder; option 1 is the insight
  // (its label starts with the authored insight text).
  await targetSelect.selectOption({ index: 1 });
  const chosenTarget = await targetSelect.locator("option:checked").textContent();
  expect(chosenTarget?.startsWith(INSIGHT_TEXT.slice(0, 40))).toBe(true);
  await evidenceDialog.getByLabel("Explanation").fill(INSIGHT_TEXT);
  await evidenceDialog.getByRole("button", { name: "Save evidence link" }).click();
  const linkedRevision = await waitForSavedRevision(page, insightRevision + 1);

  // -- 11. Reopen: the saved context matches ------------------------------ //
  await page.reload();
  await expect(page.getByLabel("Research paper editor")).toBeVisible();
  await waitForSavedRevision(page, linkedRevision);
  await expect(page.getByText(HYPOTHESIS_STATEMENT).first()).toBeVisible();
  await expect(page.getByText(INSIGHT_TEXT).first()).toBeVisible();
  // The pinned-context details is collapsed after a fresh load; open it again.
  await page.getByText("Chart definition and pinned context").click();
  await expect(page.getByText(`Observed dataset: ${state.dataset_version_id}`)).toBeVisible();
  await expect(page.getByText(`Context hash: ${journey.contextHash}`).first()).toBeVisible();
  const counts = page.getByTestId("evidence-counts");
  await expect(counts).toContainText("Supporting 0 · Contradicting 1 · Uncertain 0");
  await page.screenshot({ path: test.info().outputPath("comic-lab-editor.png") });

  // Keyboard navigation through the evidence panel: Enter opens the linked
  // insight, the back control (Enter) returns focus to the originating entry.
  const contradictingEntry = page.getByTestId("evidence-entry").first();
  await contradictingEntry.focus();
  await page.keyboard.press("Enter");
  const backButton = page.getByTestId("evidence-return");
  await backButton.focus();
  await page.keyboard.press("Enter");
  await expect(contradictingEntry).toBeFocused();

  // The DB revision row: exact version, content hash and the pinned context.
  journey.documentVersionRow = await inspectDocumentVersion(page, journey.documentId!);
  expect(journey.documentVersionRow.revision).toBe(linkedRevision);
  expect(journey.documentVersionRow.content_sha256).toMatch(/^[0-9a-f]{64}$/);
  const persistedContext = Object.values(journey.documentVersionRow.resolved_contexts)[0];
  expect(persistedContext.context_hash).toBe(journey.contextHash);

  // -- 12. Source outage: explicit failure, prose keeps saving ------------ //
  await setOutage(true, page);

  // The public explorer fails honestly and never fabricates values.
  await page.goto(chartSelectionUrl());
  await expect(page.getByRole("heading", { name: "Data unavailable", exact: true })).toBeVisible();
  await expect(page.getByText("No approved dataset is available for this chart yet.", { exact: true })).toBeVisible();
  await expect(page.getByText(state.pin_value)).toHaveCount(0);

  // The editor's pinned chart still resolves its observed dataset (explicit
  // UUID, no latest lookup) while the frame stays honestly historical.
  await page.goto(`${state.web_url}/workspace/research/${journey.documentId}`);
  await expect(page.getByText(state.pin_value).first()).toBeVisible();
  await page.getByText("Chart definition and pinned context").click();
  await expect(page.getByText(`Observed dataset: ${state.dataset_version_id}`)).toBeVisible();

  // Refresh-to-latest fails honestly; the last good values remain.
  await page.getByRole("button", { name: "Refresh to latest and save observation" }).click();
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page.getByText(state.pin_value).first()).toBeVisible();

  // Prose persistence survives the outage.
  await addParagraph(page, OUTAGE_PARAGRAPH);
  const exportRevision = await waitForSavedRevision(page, linkedRevision + 1);

  // The export target is the revision acknowledged by autosave.
  await expect(page.getByLabel("Research paper editor")).toBeVisible();
  await waitForSavedRevision(page, exportRevision);
  // Refresh the DB row: export must pin the exact acknowledged revision.
  journey.documentVersionRow = await inspectDocumentVersion(page, journey.documentId!);
  expect(journey.documentVersionRow.revision).toBe(exportRevision);

  // -- 13. Export the pinned revision (outage still on) ------------------- //
  page.on("response", (response) => {
    if (response.url().includes("/exports")) {
      console.log(`[ni063-spec] export response: ${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  const downloadPromise = page.waitForEvent("download", { timeout: 120_000 });
  await page.getByTestId("export-open").click();
  const exportDialog = page.getByTestId("export-dialog");
  await expect(exportDialog).toBeVisible();
  // NI-059: the dialog first asks for the bundle format and starts the job
  // only on the explicit Start action (Markdown ZIP is the preselected
  // default; the PDF path is the same job lifecycle).
  await expect(exportDialog.getByTestId("export-choosing")).toBeVisible();
  await exportDialog.getByTestId("export-start").click();
  const download = await downloadPromise;
  const exportDir = path.join(os.tmpdir(), `ni063-e2e-export-${Date.now()}`);
  mkdirSync(exportDir, { recursive: true });
  journey.exportZipPath = path.join(exportDir, "near-export.zip");
  await download.saveAs(journey.exportZipPath);
  await expect(exportDialog.getByTestId("export-ready")).toBeVisible();
  const zipBytes = readFileSync(journey.exportZipPath);
  journey.exportZipSha256 = sha256(zipBytes);

  const files = readZip(zipBytes);
  const manifestBytes = files.get("manifest.json")?.data;
  expect(manifestBytes).toBeDefined();
  const manifest = JSON.parse(manifestBytes!.toString("utf-8")) as NonNullable<typeof journey["manifest"]>;
  journey.manifest = manifest;
  journey.exportJobId = download.suggestedFilename()
    .replace(/^near-export-/, "").replace(/\.zip$/, "");

  // Manifest pins the exact revision the DB holds.
  expect(manifest.bundle_format_version).toBe(1);
  expect(manifest.document.document_id).toBe(journey.documentId);
  expect(manifest.document.revision).toBe(exportRevision);
  expect(manifest.document.version_id).toBe(journey.documentVersionRow!.id);
  expect(manifest.document.content_sha256).toBe(journey.documentVersionRow!.content_sha256);
  expect(manifest.document.title).toBe(DOCUMENT_TITLE);
  expect(manifest.plan_sha256).toMatch(/^[0-9a-f]{64}$/);

  // Every manifest file entry matches the actual bytes (hash + size), and
  // every bundle member is manifest-recorded (manifest.json excepted: a
  // manifest cannot record its own hash).
  const manifestPaths = new Set<string>(["manifest.json"]);
  for (const entry of manifest.files) {
    const member = files.get(entry.path);
    expect(member !== undefined, `bundle member ${entry.path}`).toBe(true);
    expect(sha256(member!.data)).toBe(entry.sha256);
    expect(member!.data.length).toBe(entry.byte_size);
    manifestPaths.add(entry.path);
  }
  for (const name of files.keys()) {
    expect(manifestPaths.has(name), `unexpected unmanifested member ${name}`).toBe(true);
  }
  // Chart asset records: SVG + CSV for the single chart block, present + hashed.
  expect(manifest.charts).toHaveLength(1);
  for (const record of manifest.charts) {
    expect(sha256(files.get(record.svg.path)!.data)).toBe(record.svg.sha256);
    expect(sha256(files.get(record.csv.path)!.data)).toBe(record.csv.sha256);
    expect(record.svg.path).toMatch(/^assets\/chart-[0-9a-f-]{36}\.svg$/);
    expect(record.csv.path).toMatch(/^assets\/chart-[0-9a-f-]{36}\.csv$/);
  }

  // research.md: title, content, pinned values and resolved relative links.
  const research = files.get("research.md")!.data.toString("utf-8");
  expect(research).toContain(DOCUMENT_TITLE);
  expect(research).toContain(PARAGRAPH_ONE);
  expect(research).toContain(OUTAGE_PARAGRAPH);
  expect(research).toContain(HYPOTHESIS_STATEMENT);
  expect(research).toContain(INSIGHT_TEXT);
  // The pinned chart values live in the CSV asset; research.md embeds it.
  expect(research).toContain("assets/chart-");
  const internalLinks = [...research.matchAll(/\]\(([^)]+)\)/g)]
    .map((match) => match[1])
    .filter((link) => !link.startsWith("http://") && !link.startsWith("https://"));
  expect(internalLinks.length).toBeGreaterThan(0);
  for (const link of internalLinks) {
    expect(files.has(link), `research.md link ${link} resolves inside the bundle`).toBe(true);
  }
  // The chart CSV carries the exact decimal strings (no rounding, no zero-fill).
  const csv = files.get(manifest.charts[0].csv.path)!.data.toString("utf-8");
  expect(csv).toContain(state.pin_value);
  expect(csv).toContain("Provider-reported Intents gross volume (source-qualified)");

  // A second download of the same job is byte-identical in this environment.
  const againPromise = page.waitForEvent("download", { timeout: 60_000 });
  await exportDialog.getByTestId("export-download-again").click();
  const secondDownload = await againPromise;
  const secondPath = path.join(exportDir, "near-export-again.zip");
  await secondDownload.saveAs(secondPath);
  expect(sha256(readFileSync(secondPath))).toBe(journey.exportZipSha256);

  // The DB row still pins the exported revision (late edits never change it).
  const afterExport = await inspectDocumentVersion(page, journey.documentId!);
  expect(afterExport.revision).toBe(manifest.document.revision);
  expect(afterExport.content_sha256).toBe(manifest.document.content_sha256);

  await page.getByTestId("export-close").click();

  // -- 14. The outage ends and the explorer recovers ---------------------- //
  await setOutage(false, page);
  await page.goto(chartSelectionUrl());
  await expect(page.getByText(state.pin_value).first()).toBeVisible();

  // Keep the downloaded bundle path for the run record.
  writeFileSync(path.join(exportDir, "verified-manifest.json"),
    JSON.stringify(manifest, null, 2));
});

test("a second user cannot reach the private research or its export", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${state.session_bob}?next=${encodeURIComponent("/workspace")}`);
  await expect(page).toHaveURL(/\/workspace$/);

  // Bob's home never lists Alice's document.
  await expect(page.getByText(DOCUMENT_TITLE)).toHaveCount(0);

  // The document URL is one generic 404 for a non-owner (no existence leak).
  await page.goto(`${state.web_url}/workspace/research/${journey.documentId}`);
  await expect(page.getByText(DOCUMENT_TITLE)).toHaveCount(0);

  // Bob cannot download the export bundle either.
  const denied = await context.request.get(
    `${state.web_url}/api/documents/${journey.documentId}/exports/${journey.exportJobId}/download`);
  expect(denied.status()).toBe(404);
  const deniedBody = await denied.body();
  expect(deniedBody.subarray(0, 2).toString()).not.toBe("PK");
  await context.close();
});

test("the public explorer shows approved data again once the outage ends", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await setOutage(false, page);
  await page.goto(chartSelectionUrl());
  await expect(page.getByText(state.pin_value).first()).toBeVisible();
  await expectRecordedDataset(page);
  await context.close();
});

test("a signed-in reader can copy a pinned publication and edit only the private copy", async ({ page, browser }) => {
  const publicationUrl = `${state.web_url}/api/publications/near-thesis-2026-11?version=1`;
  const published = await page.request.get(publicationUrl);
  expect(published.status()).toBe(200);
  const publicContent = await published.json();
  await page.goto(`${state.web_url}/research`);
  await page.getByRole("button", { name: "Sign in to save a private copy" }).click();
  await expect(page).toHaveURL(/\/login\?next=%2Fresearch$/);
  await page.goto(`${state.session_alice}?next=${encodeURIComponent("/research")}`);
  await page.getByRole("button", { name: "Save a private copy" }).click();
  const dialog = page.getByRole("dialog", { name: "Save a private copy of this research" });
  await expect(dialog).toContainText("version 1");
  await dialog.getByLabel("Title of your private copy").fill("Synthetic NI-045 private copy");
  await dialog.getByRole("button", { name: "Save private copy" }).click();
  await expect(page).toHaveURL(/\/workspace\/research\/[0-9a-f-]{36}$/);
  const copyPath = new URL(page.url()).pathname;
  const copyId = copyPath.split("/").pop();
  const editor = page.getByLabel("Research paper editor");
  await expect(editor).toContainText("Synthetic publication heading");
  await expect(editor).toContainText("near-thesis-2026-11");
  const edit = "Synthetic private edit";
  await addParagraph(page, edit);
  await waitForSavedRevision(page, 3);
  await page.reload();
  await expect(editor).toContainText(edit);

  const afterEdit = await page.request.get(publicationUrl);
  expect(afterEdit.headers().etag).toBe(published.headers().etag);
  expect(await afterEdit.json()).toEqual(publicContent);
  const bob = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  try {
    const bobPage = await bob.newPage();
    await bobPage.goto(`${state.session_bob}?next=${encodeURIComponent("/workspace")}`);
    const denied = await bob.request.get(`${state.web_url}/api/documents/${copyId}`);
    expect(denied.status()).toBe(404);
  } finally {
    await bob.close();
  }
});
