/** NI-065 integrity findings panel tests (synthetic fixtures, visibly labeled). */
import { axe } from "jest-axe";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { loadDocumentChart } from "@/features/editor/blocks/chart-api";
import { ResearchDocumentEditor } from "@/features/editor/workbench";
import { shortId } from "@/features/editor/blocks/display";
import { definition, metric, observation, series, view } from "../ui/renderer/fixtures";

vi.mock("@/features/editor/blocks/chart-api", () => ({ loadDocumentChart: vi.fn() }));
vi.mock("@/features/charts/renderer/chart-factory", () => ({ defaultChartFactory: vi.fn(async () => ({
  setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn(),
})) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const loader = vi.mocked(loadDocumentChart);

// ProseMirror focus and the panel's scroll-into-view need geometry jsdom lacks.
beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(() => {});
  vi.spyOn(window, "scrollBy").mockImplementation(() => {});
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.resetAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
afterEach(() => { loader.mockReset(); });

const DOC_ID = "22222222-2222-4222-8222-222222222222";
const VERSION_ID = "33333333-3333-4333-8333-333333333333";
const PARA_BLOCK_ID = "a1111111-1111-4111-8111-111111111111";
const CHART_BLOCK_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const PINNED_DATASET_ID = "d1111111-1111-4111-8111-111111111111";
const NEWEST_DATASET_ID = "d2222222-2222-4222-8222-222222222222";
const DEFINITION_ID = "d3333333-3333-4333-8333-333333333333";
const CONTEXT_HASH = "a".repeat(64);
const REVISION = 4;
const TIMESTAMP = "2026-11-12T12:00:00Z";

const metricDefinition = metric("USD", "Synthetic metric", "synthetic-usd");
const chartDefinition = definition({ metric_definition_ids: [metricDefinition.id] });
const chartView = view(chartDefinition, [
  series(metricDefinition, [observation("2026-11-01", "12.000000000000000001")]),
]);

const paragraph = { type: "paragraph", attrs: { block_id: PARA_BLOCK_ID },
  content: [{ type: "text", text: "Synthetic integrity fixture paragraph" }] };
const chartBlock = { type: "liveChart", attrs: { block_id: CHART_BLOCK_ID, mode: "live", snapshot_id: null,
  chart_definition_version_id: chartDefinition.id, observed_dataset_version_id: PINNED_DATASET_ID,
  selection: { start: "2026-11-01", end: "2026-11-06", frequency: "day", filters: {} } } };
const paper = { schema_version: 1, type: "doc", content: [paragraph, chartBlock] };

const summary = { id: DOC_ID, title: "Synthetic integrity research", revision: REVISION,
  schema_version: 1, current_version_id: VERSION_ID, created_at: TIMESTAMP, updated_at: TIMESTAMP,
  progress: { headings: 0, charts: 1, insights: 0 } };

const staleFinding = {
  check_id: "stale_chart_context", severity: "advisory",
  message: "A newer approved dataset exists for this chart's required metrics. The saved "
    + "observation stays pinned; refreshing is an explicit action on the chart block, never an "
    + "automatic rewrite.",
  block_id: CHART_BLOCK_ID, dataset_version_id: PINNED_DATASET_ID,
  latest_dataset_version_id: NEWEST_DATASET_ID, chart_definition_version_id: DEFINITION_ID,
  context_hash: CONTEXT_HASH, jump: "block",
};
const missingContextFinding = {
  check_id: "missing_chart_context", severity: "warning",
  message: "The saved chart has no frozen context entry in this revision's resolved contexts. "
    + "This is a corruption signal: the chart cannot be reconstructed until it is explicitly "
    + "re-inspected and saved.",
  block_id: CHART_BLOCK_ID, chart_definition_version_id: DEFINITION_ID,
  dataset_version_id: PINNED_DATASET_ID, jump: "block",
};

const integrityResponse = (findings: unknown[], revision = REVISION) => ({
  document_id: DOC_ID, version_id: VERSION_ID, revision, is_acknowledged: true,
  findings,
  counts: Object.entries(
    Object.groupBy(findings as Array<{ check_id: string }>, (finding) => finding.check_id),
  ).map(([check_id, group]) => ({ check_id, count: group!.length })),
});

const saveSuccess = (revision: number, content: unknown) => Response.json({
  document: { ...summary, revision },
  version: { id: VERSION_ID, document_id: DOC_ID, revision, schema_version: 1,
    created_at: TIMESTAMP, content_sha256: "a".repeat(64), content,
    resolved_contexts: {} },
}, { status: 201, headers: { etag: `"${revision}"` } });

interface Options {
  integrity?: () => unknown[];
  revision?: number;
  failFirstIntegrity?: boolean;
}

function renderEditor(options: Options = {}) {
  const { integrity = () => [staleFinding], revision = REVISION, failFirstIntegrity = false } = options;
  const requests: string[] = [];
  let integrityRequests = 0;
  let currentRevision = revision;
  let savedOnce = false;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.origin);
    requests.push(url.pathname);
    if (url.pathname === "/api/auth/session") return Response.json({ subject: "synthetic-alice" });
    if (url.pathname === "/api/auth/csrf") return Response.json({ token: "synthetic-csrf" });
    if (url.pathname === `/api/documents/${DOC_ID}`) {
      return Response.json({ ...summary, revision: currentRevision, content: paper,
        resolved_contexts: {} });
    }
    if (url.pathname === `/api/documents/${DOC_ID}/integrity`) {
      integrityRequests += 1;
      if (failFirstIntegrity && integrityRequests === 1) {
        return Response.json({ error: { code: "UNAVAILABLE", message: "Synthetic integrity outage",
          request_id: "fixture", retryable: true } }, { status: 500 });
      }
      const checkedRevision = savedOnce ? currentRevision : revision;
      return Response.json(integrityResponse(integrity(), checkedRevision));
    }
    if (url.pathname === `/api/documents/${DOC_ID}/versions`
      && (input instanceof Request ? input.method : init.method) === "POST") {
      const rawBody = input instanceof Request ? await input.clone().text()
        : typeof init.body === "string" ? init.body : JSON.stringify(init.body ?? {});
      const body = JSON.parse(rawBody) as { content: unknown };
      currentRevision = REVISION + 1;
      savedOnce = true;
      return saveSuccess(currentRevision, body.content);
    }
    throw new Error(`Unexpected synthetic request ${url.pathname}`);
  }));
  const view = render(<ResearchDocumentEditor documentId={DOC_ID} />);
  return { view, requests, integrityRequests: () => integrityRequests };
}

async function renderReady(options: Options = {}) {
  const handles = renderEditor(options);
  await screen.findByRole("textbox", { name: "Research paper editor" });
  const panel = await screen.findByTestId("integrity-panel");
  // The acknowledged-revision line appears once the report resolved (findings
  // list or explicit empty state).
  await waitFor(() => expect(within(panel).getByTestId("integrity-revision")).toBeInTheDocument());
  return { ...handles, panel, unmount: handles.view.unmount };
}

/** The document stays clean: no panel interaction may dirty the paper. */
function expectCleanDocument(expectedRevision: number = REVISION) {
  const status = screen.getByTestId("save-status");
  expect(status).toHaveTextContent(`Revision ${expectedRevision}`);
  expect(status).not.toHaveTextContent("Unsaved changes");
}

it("renders advisory findings with exact references and jumps to the source block", async () => {
  loader.mockResolvedValue(chartView);
  const user = userEvent.setup();
  const { requests } = await renderReady();
  expect(requests).toContain(`/api/documents/${DOC_ID}/integrity`);
  const panel = screen.getByTestId("integrity-panel");
  await within(panel).findByTestId("integrity-findings");
  // Advisory vocabulary with no truth score; exact refs visible in text
  // (no hover-only information).
  expect(within(panel).getByText("Advisory · Newer approved data exists")).toBeInTheDocument();
  expect(within(panel).getByText(/newer approved dataset exists for this chart/i)).toBeInTheDocument();
  expect(within(panel).getByText(
    new RegExp(`Block ${shortId(CHART_BLOCK_ID)} · Definition ${shortId(DEFINITION_ID)} · `
      + `Dataset ${shortId(PINNED_DATASET_ID)} · Newest approved dataset ${shortId(NEWEST_DATASET_ID)}`
      + ` · Context hash ${shortId(CONTEXT_HASH)}`),
  )).toBeInTheDocument();
  // The refresh stays the chart block's own explicit action.
  expect(within(panel).getByText(/this panel never changes the pin/i)).toBeInTheDocument();
  expectCleanDocument();

  // Jump-to-source: selection moves to the chart block; the properties pane
  // follows it; the pinned context is untouched.
  const jump = within(panel).getByRole("button", {
    name: `Show block ${shortId(CHART_BLOCK_ID)} in the paper` });
  jump.focus();
  expect(jump).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(screen.getByTestId("editor-announcement"))
    .toHaveTextContent("Showing the block with the “Newer approved data exists” finding in the paper");
  const properties = screen.getByLabelText("Block properties");
  expect(within(properties).getAllByText("Live chart").length).toBeGreaterThan(0);
  expectCleanDocument();

  // Axe is scoped to the panel subtree (workbench-wide contract asserted by
  // the existing workbench/save suites).
  expect(await axe(panel, { rules: { region: { enabled: false } } })).toHaveNoViolations();
});

it("renders corruption warnings distinctly and honestly", async () => {
  await renderReady({ integrity: () => [missingContextFinding] });
  const panel = screen.getByTestId("integrity-panel");
  await within(panel).findByTestId("integrity-findings");
  expect(within(panel).getByText("Warning — inspect before editing · Missing frozen chart context"))
    .toBeInTheDocument();
  expect(within(panel).getByText(/corruption signal/i)).toBeInTheDocument();
  expectCleanDocument();
});

it("shows the explicit empty state for a clean revision", async () => {
  await renderReady({ integrity: () => [] });
  const panel = screen.getByTestId("integrity-panel");
  await within(panel).findByTestId("integrity-empty");
  expect(within(panel).getByTestId("integrity-empty"))
    .toHaveTextContent("No integrity findings on this revision.");
  expect(within(panel).getByTestId("integrity-revision"))
    .toHaveTextContent("Checked saved revision 4.");
  expect(within(panel).queryAllByTestId("integrity-findings")).toHaveLength(0);
});

it("keeps findings readable after a failed check and an explicit retry", async () => {
  const user = userEvent.setup();
  const { integrityRequests } = renderEditor({ failFirstIntegrity: true });
  await screen.findByRole("textbox", { name: "Research paper editor" });
  const panel = await screen.findByTestId("integrity-panel");
  expect(await within(panel).findByRole("alert"))
    .toHaveTextContent("Integrity findings could not be loaded. Nothing was changed — try again.");
  await user.click(within(panel).getByRole("button", { name: "Retry integrity check" }));
  await waitFor(() => expect(within(panel).getAllByTestId("integrity-findings").length).toBe(1));
  expect(integrityRequests()).toBe(2);
});

it("reruns the check when the acknowledged revision changes after a save", async () => {
  loader.mockResolvedValue(chartView);
  const user = userEvent.setup();
  const { requests, integrityRequests } = await renderReady({ integrity: () => [staleFinding] });
  expect(integrityRequests()).toBe(1);
  // The author edits and saves: the acknowledged revision advances and the
  // panel reruns against the new revision without any manual action.
  await user.click(screen.getByRole("button", { name: "Insert block" }));
  const menu = await screen.findByRole("menu", { name: "Insert block" });
  await user.click(within(menu).getByRole("menuitem", { name: /Divider/ }));
  await waitFor(() => expect(screen.getByTestId("save-status")).toHaveTextContent(/Unsaved changes/));
  await userEvent.click(screen.getByTestId("save-now"));
  await waitFor(() => expect(screen.getByTestId("save-status")).toHaveTextContent(/Revision 5/));
  await waitFor(() => expect(integrityRequests()).toBe(2));
  const panel = screen.getByTestId("integrity-panel");
  await waitFor(() => expect(within(panel).getByTestId("integrity-revision"))
    .toHaveTextContent("Checked saved revision 5."));
  expect(requests.filter((path) => path === `/api/documents/${DOC_ID}/integrity`).length).toBe(2);
  expectCleanDocument(5);
});

it("shows the honest unsaved-edits notice while the paper has local changes", async () => {
  loader.mockResolvedValue(chartView);
  const user = userEvent.setup();
  await renderReady();
  const panel = screen.getByTestId("integrity-panel");
  await within(panel).findByTestId("integrity-revision");
  await waitFor(() => expect(within(panel).getByTestId("integrity-revision"))
    .toHaveTextContent(/Checked saved revision 4\./));
  await user.click(screen.getByRole("button", { name: "Insert block" }));
  const menu = await screen.findByRole("menu", { name: "Insert block" });
  await user.click(within(menu).getByRole("menuitem", { name: /Divider/ }));
  await waitFor(() => expect(screen.getByTestId("save-status")).toHaveTextContent(/Unsaved changes/));
  // The status line states that unsaved edits are not checked yet.
  expect(within(panel).getByTestId("integrity-revision"))
    .toHaveTextContent(/the paper has unsaved edits, so findings appear after the next save\./);
});

afterEach(cleanup);
