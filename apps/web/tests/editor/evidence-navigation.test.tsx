/** NI-050 evidence navigation panel tests (synthetic fixtures, visibly labeled). */
import { axe } from "jest-axe";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { chartObservation } from "@/features/charts/renderer/observation-context";
import { loadDocumentChart } from "@/features/editor/blocks/chart-api";
import { AddInsightToResearch } from "@/features/editor/insights/public-insight";
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

const DOC_ID = "22222222-2222-4222-8222-222222222222";
const VERSION_ID = "33333333-3333-4333-8333-333333333333";
const HYPOTHESIS_A_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const HYPOTHESIS_B_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const INSIGHT_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const INSIGHT_BLOCK_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const CHART_BLOCK_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const RISK_BLOCK_ID = "f1111111-1111-4111-8111-111111111111";
const SUPPORTING_ID = "f2222222-2222-4222-8222-222222222222";
const CONTRADICTING_ID = "f3333333-3333-4333-8333-333333333333";
const CHART_EVIDENCE_ID = "f4444444-4444-4444-8444-444444444444";
const CITATION_EVIDENCE_ID = "f5555555-5555-4555-8555-555555555555";
const CITATION_ID = "f6666666-6666-4666-8666-666666666666";
const REVISION = 4;
const TIMESTAMP = "2026-11-09T12:00:00Z";

const metricDefinition = metric("USD", "Synthetic metric", "synthetic-usd");
const chartDefinition = definition({ metric_definition_ids: [metricDefinition.id] });
const chartView = view(chartDefinition, [
  series(metricDefinition, [observation("2026-11-01", "12.000000000000000001")]),
]);
const insightContext = chartObservation(chartView);

const hypothesisA = { type: "hypothesis", attrs: { block_id: "a1111111-1111-4111-8111-111111111111",
  hypothesis_id: HYPOTHESIS_A_ID, statement: "Loneliness hypothesis (fixture)", assessment: "untested",
  authored_at: TIMESTAMP, modified_at: TIMESTAMP } };
const hypothesisB = { type: "hypothesis", attrs: { block_id: "a2222222-2222-4222-8222-222222222222",
  hypothesis_id: HYPOTHESIS_B_ID, statement: "Adoption drives fee growth (fixture)", assessment: "mixed",
  authored_at: TIMESTAMP, modified_at: TIMESTAMP } };
const insight = { type: "insight", attrs: { block_id: INSIGHT_BLOCK_ID, insight_id: INSIGHT_ID,
  type: "observation", classification: "uncertain", context: insightContext,
  body: [{ type: "paragraph", content: [{ type: "text", text: "Synthetic pinned observation" }] }],
  authored_at: TIMESTAMP, modified_at: TIMESTAMP } };
const chartBlock = { type: "liveChart", attrs: { block_id: CHART_BLOCK_ID, mode: "live", snapshot_id: null,
  chart_definition_version_id: chartDefinition.id, observed_dataset_version_id: insightContext.dataset_version_id,
  selection: insightContext.selection } };
const risk = { type: "risk", attrs: { block_id: RISK_BLOCK_ID, title: "Attribution risk (fixture)",
  body: [{ type: "paragraph", content: [{ type: "text", text: "Synthetic risk body" }] }],
  related_hypothesis_id: HYPOTHESIS_B_ID } };
const supportingEvidence = { type: "evidence", attrs: { block_id: "a3333333-3333-4333-8333-333333333333",
  evidence_id: SUPPORTING_ID, hypothesis_id: HYPOTHESIS_B_ID, classification: "supporting",
  target_kind: "insight", target_id: INSIGHT_ID, explanation: "Synthetic supporting explanation" } };
const contradictingEvidence = { type: "evidence", attrs: { block_id: "a4444444-4444-4444-8444-444444444444",
  evidence_id: CONTRADICTING_ID, hypothesis_id: HYPOTHESIS_B_ID, classification: "contradicting",
  target_kind: "insight", target_id: INSIGHT_ID, explanation: "Synthetic contradicting explanation" } };
const chartEvidence = { type: "evidence", attrs: { block_id: "a5555555-5555-4555-8555-555555555555",
  evidence_id: CHART_EVIDENCE_ID, hypothesis_id: HYPOTHESIS_B_ID, classification: "uncertain",
  target_kind: "chart_block", target_id: CHART_BLOCK_ID, explanation: "Synthetic chart link explanation" } };

const paper = (content: unknown[]) => ({ schema_version: 1, type: "doc", content });

function serverEvidence(entry: { block_id: string; evidence_id: string; hypothesis_id: string;
  classification: string; target_kind: string; target_id: string; explanation: string }) {
  return { id: entry.evidence_id, document_id: DOC_ID, block_id: entry.block_id,
    hypothesis_id: entry.hypothesis_id, classification: entry.classification, target_kind: entry.target_kind,
    target_id: entry.target_id, explanation: entry.explanation, authored_at: TIMESTAMP, modified_at: TIMESTAMP };
}

/** Server-side projection list the panel reads (NI-049 GET surface). */
function evidenceList() {
  return [
    serverEvidence(supportingEvidence.attrs),
    serverEvidence(contradictingEvidence.attrs),
    serverEvidence(chartEvidence.attrs),
    serverEvidence({ block_id: "a6666666-6666-4666-8666-666666666666", evidence_id: CITATION_EVIDENCE_ID,
      hypothesis_id: HYPOTHESIS_B_ID, classification: "supporting", target_kind: "citation",
      target_id: CITATION_ID, explanation: "Synthetic public citation explanation" }),
  ];
}

function renderEditor(content: unknown[], options: { evidence?: () => unknown[]; failFirstEvidence?: boolean } = {}) {
  const { evidence = evidenceList, failFirstEvidence = false } = options;
  const requests: string[] = [];
  let evidenceRequests = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.origin);
    requests.push(url.pathname);
    if (url.pathname === "/api/auth/session") return Response.json({ subject: "synthetic-alice" });
    if (url.pathname === `/api/documents/${DOC_ID}`) {
      return Response.json({ id: DOC_ID, title: "Synthetic navigation research", revision: REVISION,
        schema_version: 1, current_version_id: VERSION_ID, created_at: TIMESTAMP, updated_at: TIMESTAMP,
        progress: { headings: 0, charts: 1, insights: 1 }, content: paper(content), resolved_contexts: {} });
    }
    if (url.pathname === `/api/documents/${DOC_ID}/evidence`) {
      evidenceRequests += 1;
      if (failFirstEvidence && evidenceRequests === 1) {
        return Response.json({ error: { code: "UNAVAILABLE", message: "Synthetic evidence outage",
          request_id: "fixture", retryable: true } }, { status: 500 });
      }
      return Response.json(evidence());
    }
    throw new Error(`Unexpected synthetic request ${url.pathname}`);
  }));
  const view = render(<ResearchDocumentEditor documentId={DOC_ID} />);
  return { view, requests, evidenceRequests: () => evidenceRequests };
}

async function renderReady(content: unknown[], options: { evidence?: () => unknown[] } = {}) {
  const handles = renderEditor(content, options);
  await screen.findByRole("textbox", { name: "Research paper editor" });
  const panel = await screen.findByTestId("evidence-navigation-panel");
  await waitFor(() => expect(within(panel).getAllByTestId("evidence-entry").length).toBeGreaterThan(0));
  return { ...handles, panel, unmount: handles.view.unmount };
}

const CONTENT = [hypothesisA, hypothesisB, insight, chartBlock, risk, supportingEvidence, contradictingEvidence, chartEvidence];

/** The document stays clean: no navigation in the panel may dirty the paper. */
function expectCleanDocument(expectedRevision: number = REVISION) {
  const status = screen.getByTestId("save-status");
  expect(status).toHaveTextContent(`Revision ${expectedRevision}`);
  expect(status).not.toHaveTextContent("Unsaved changes");
}

afterEach(() => { loader.mockReset(); });

it("lists per-hypothesis evidence with classification counts, counterarguments and explicit empty states", async () => {
  const { requests } = await renderReady(CONTENT);
  expect(requests).toContain(`/api/documents/${DOC_ID}/evidence`);
  const panel = screen.getByTestId("evidence-navigation-panel");
  const groupA = within(panel).getByRole("article", { name: "Evidence for hypothesis: Loneliness hypothesis (fixture)" });
  expect(within(groupA).getByTestId("evidence-counts")).toHaveTextContent(
    "No linked evidence yet — Supporting 0 · Contradicting 0 · Uncertain 0");
  expect(within(groupA).getByText("Use “Add evidence” on the hypothesis card to link the first target.")).toBeInTheDocument();
  expect(within(groupA).getByText("No contradicting evidence is linked to this hypothesis.")).toBeInTheDocument();
  expect(within(groupA).getByText("No risk blocks reference this hypothesis.")).toBeInTheDocument();

  const groupB = within(panel).getByRole("article", { name: "Evidence for hypothesis: Adoption drives fee growth (fixture)" });
  expect(within(groupB).getByTestId("evidence-counts")).toHaveTextContent(
    "Supporting 2 · Contradicting 1 · Uncertain 1");
  expect(within(groupB).getByText("Synthetic supporting explanation")).toBeInTheDocument();
  expect(within(groupB).getByText("Synthetic contradicting explanation")).toBeInTheDocument();
  expect(within(groupB).getByText("Synthetic chart link explanation")).toBeInTheDocument();
  expect(within(groupB).getByText("Synthetic public citation explanation")).toBeInTheDocument();
  // The contradicting entry is surfaced as the counterargument of the hypothesis.
  expect(within(groupB).getByText(/1 contradicting entry above records the authors/)).toBeInTheDocument();
  expect(within(groupB).getByRole("button", { name: "Show risk Attribution risk (fixture) in the paper" })).toBeInTheDocument();
  // The author assessment stays separate from the evidence counts.
  expect(within(groupB).getByText("Author assessment · Mixed")).toBeInTheDocument();
  // The classification wording stays editorial; rendering the panel never rewrites the paper.
  expectCleanDocument();
  // Axe is scoped to the panel subtree: the workbench-wide axe contract is
  // asserted by the existing editor-workbench/editor-save suites, and a
  // whole-body scan here measurably slowed the parallel suite.
  expect(await axe(panel, { rules: { region: { enabled: false } } })).toHaveNoViolations();
});

it("navigates from a contradicting entry to the target insight, keeps its pinned context and restores focus on return", async () => {
  const user = userEvent.setup();
  await renderReady(CONTENT);
  const entry = screen.getByRole("button", { name: "Show contradicting evidence in the paper (Insight in this research)" });
  // Keyboard activation: the entries are real buttons (Enter/Space work; the
  // visible focus ring comes from the shared focus-visible outline token).
  entry.focus();
  expect(entry).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(screen.getByTestId("editor-announcement")).toHaveTextContent("Showing the insight in the paper");
  // The selection moved to the insight block; the properties pane follows it.
  const properties = screen.getByLabelText("Block properties");
  expect(within(properties).getAllByText("Insight").length).toBeGreaterThan(0);
  // Navigation is read-only: the pinned context of the insight is untouched and
  // the document stays clean (no autosave, no attribute rewrite).
  const insightCard = screen.getByLabelText("Insight block");
  expect(insightCard).toHaveTextContent("2026-11-01 – 2026-11-06 (UTC, half-open)");
  expect(insightCard).toHaveTextContent(shortId(insightContext.dataset_version_id));
  expect(insightCard).toHaveTextContent("Synthetic pinned observation");
  expectCleanDocument();
  // Back returns keyboard focus to the originating evidence entry.
  await user.click(screen.getByTestId("evidence-return"));
  expect(entry).toHaveFocus();
  expect(screen.queryByTestId("evidence-return")).toBeNull();
  expectCleanDocument();
});

it("navigates to a pinned chart, keeps its observation intact, and Escape returns focus to the entry", async () => {
  loader.mockResolvedValue(chartView);
  const user = userEvent.setup();
  await renderReady(CONTENT);
  expect(await screen.findByText("12.000000000000000001")).toBeInTheDocument();
  expect(screen.getByText("Chart definition and pinned context")).toBeInTheDocument();
  const entry = screen.getByRole("button", { name: "Show uncertain evidence in the paper (Chart in this research)" });
  await user.click(entry);
  expect(screen.getByTestId("editor-announcement")).toHaveTextContent("Showing the chart in the paper");
  const properties = screen.getByLabelText("Block properties");
  expect(within(properties).getAllByText("Live chart").length).toBeGreaterThan(0);
  // The chart's saved observation is unchanged by the navigation.
  expect(within(properties).getByText(insightContext.dataset_version_id)).toBeVisible();
  expect(screen.getByText(/Opening or typing never refreshes this pin/)).toBeInTheDocument();
  expectCleanDocument();
  const back = screen.getByTestId("evidence-return");
  back.focus();
  const paper = screen.getByRole("textbox", { name: "Research paper editor" });
  const originalFocus = paper.focus.bind(paper);
  paper.focus = (...args: FocusOptions[]) => {
    console.error("NI050-TEST paper.focus called", new Error("stack").stack?.split("\n").slice(1, 6).join(" | "));
    return originalFocus(...args);
  };
  console.error("NI050-TEST active", document.activeElement?.textContent?.slice(0, 30));
  await user.keyboard("{Escape}");
  console.error("NI050-TEST after escape", document.activeElement?.textContent?.slice(0, 30));
  expect(entry).toHaveFocus();
  expect(screen.queryByTestId("evidence-return")).toBeNull();
});

it("reports public citation targets honestly without pretending they are paper blocks", async () => {
  const user = userEvent.setup();
  await renderReady(CONTENT);
  const entry = screen.getByRole("button", { name: "Show supporting evidence in the paper (Public citation)" });
  await user.click(entry);
  expect(screen.getByTestId("editor-announcement")).toHaveTextContent("outside the paper");
  // No in-paper navigation happened: no back affordance appears and the
  // properties pane still shows the initial paragraph selection.
  expect(screen.queryByTestId("evidence-return")).toBeNull();
  expect(within(screen.getByLabelText("Block properties")).queryAllByText("Live chart")).toHaveLength(0);
  expect(screen.getByText("Public artifact — inspected outside this paper; its id stays pinned on the link."))
    .toBeInTheDocument();
});

it("keeps the linked graph readable after a failed load and an explicit retry", async () => {
  const user = userEvent.setup();
  const { evidenceRequests } = renderEditor(CONTENT, { failFirstEvidence: true });
  await screen.findByRole("textbox", { name: "Research paper editor" });
  const panel = await screen.findByTestId("evidence-navigation-panel");
  expect(await within(panel).findByRole("alert"))
    .toHaveTextContent("Linked evidence could not be loaded. Nothing was changed — try again.");
  await user.click(within(panel).getByRole("button", { name: "Retry evidence list" }));
  await waitFor(() => expect(within(panel).getAllByTestId("evidence-entry").length).toBe(4));
  expect(evidenceRequests()).toBe(2);
});

it("rebuilds the same linked graph when the document is reopened", async () => {
  const first = await renderReady(CONTENT);
  first.unmount();
  const second = await renderReady(CONTENT);
  const panel = screen.getByTestId("evidence-navigation-panel");
  const groupB = within(panel).getByRole("article", { name: "Evidence for hypothesis: Adoption drives fee growth (fixture)" });
  expect(within(groupB).getByTestId("evidence-counts")).toHaveTextContent("Supporting 2 · Contradicting 1 · Uncertain 1");
  expect(within(groupB).getByRole("button", { name: "Show contradicting evidence in the paper (Insight in this research)" }))
    .toBeInTheDocument();
  expect(second.requests).toContain(`/api/documents/${DOC_ID}/evidence`);
});

it("shows an honest empty state for research without hypotheses", async () => {
  renderEditor([{ type: "paragraph", attrs: { block_id: "a7777777-7777-4777-8777-777777777777" },
    content: [{ type: "text", text: "Plain fixture paragraph" }] }], { evidence: () => [] });
  await screen.findByRole("textbox", { name: "Research paper editor" });
  const panel = await screen.findByTestId("evidence-navigation-panel");
  expect(within(panel).getByText(/No hypotheses in this research yet/)).toBeInTheDocument();
  expect(within(panel).queryAllByTestId("evidence-entry")).toHaveLength(0);
});

it("completes the J4 chain: explorer Add Insight after destination selection, then evidence navigation", async () => {
  const user = userEvent.setup();
  const posts: Array<{ headers: Record<string, string | null>; body: Record<string, unknown> }> = [];
  const summary = { id: DOC_ID, title: "Synthetic navigation research", revision: REVISION, schema_version: 1,
    current_version_id: VERSION_ID, created_at: TIMESTAMP, updated_at: TIMESTAMP, progress: { headings: 0, charts: 1, insights: 0 } };
  const saved = (nextContent: unknown[], nextRevision: number) => Response.json({
    document: { ...summary, revision: nextRevision },
    version: { id: VERSION_ID, document_id: DOC_ID, revision: nextRevision, schema_version: 1, created_at: TIMESTAMP,
      content_sha256: "a".repeat(64), content: paper(nextContent), resolved_contexts: {} },
    value: insight.attrs,
  });
  let content: unknown[] = [hypothesisA, hypothesisB, risk];
  let revision = REVISION;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.origin);
    if (url.pathname === "/api/auth/session") return Response.json({ subject: "synthetic-alice" });
    if (url.pathname === "/api/auth/csrf") return Response.json({ token: "synthetic-csrf" });
    if (url.pathname === "/api/documents") return Response.json({ items: [summary], next_cursor: null });
    if (url.pathname === `/api/documents/${DOC_ID}/insights` && input instanceof Request) {
      const request = new Request(input, init);
      posts.push({ headers: { "if-match": request.headers.get("if-match"), csrf: request.headers.get("x-csrf-token") },
        body: await request.json() });
      // The server allocates the stable insight id the evidence links target.
      const created = { ...insight, attrs: { ...insight.attrs,
        body: [{ type: "paragraph", content: [{ type: "text", text: "Synthetic explorer insight" }] }] } };
      content = [hypothesisA, hypothesisB, risk, chartBlock, created, supportingEvidence, contradictingEvidence];
      revision = 5;
      return saved(content, revision);
    }
    if (url.pathname === `/api/documents/${DOC_ID}`) {
      return Response.json({ ...summary, revision, content: paper(content), resolved_contexts: {} });
    }
    if (url.pathname === `/api/documents/${DOC_ID}/evidence`) return Response.json(evidenceList());
    throw new Error(`Unexpected synthetic request ${url.pathname}`);
  }));

  // Phase 1 — the explorer context: Add Insight opens, the destination is
  // selected inside it (AddChartToResearch precedent), and the created
  // insight freezes the inspected context through the shared insights API.
  render(<AddInsightToResearch context={insightContext} suspended={false} />);
  await user.click(await screen.findByRole("button", { name: "Add Insight" }));
  await user.type(await screen.findByLabelText("Insight text"), "Synthetic explorer insight");
  await user.selectOptions(screen.getByLabelText("Destination"),
    await screen.findByRole("option", { name: "Synthetic navigation research" }));
  await user.selectOptions(await screen.findByLabelText("Linked hypothesis"), HYPOTHESIS_B_ID);
  await user.click(screen.getByRole("button", { name: "Confirm Add Insight" }));
  expect(await screen.findByRole("link", { name: "Open research" })).toHaveAttribute("href", `/workspace/research/${DOC_ID}`);
  expect(posts).toHaveLength(1);
  expect(posts[0].headers["if-match"]).toBe(`"${REVISION}"`);
  expect(posts[0].headers.csrf).toBe("synthetic-csrf");
  expect(posts[0].body).toMatchObject({ context: insightContext, hypothesis_id: HYPOTHESIS_B_ID,
    type: "observation", classification: "uncertain" });

  // Phase 2 — reopen the research: the linked graph navigates like any other.
  cleanup();
  render(<ResearchDocumentEditor documentId={DOC_ID} />);
  await screen.findByRole("textbox", { name: "Research paper editor" });
  const panel = await screen.findByTestId("evidence-navigation-panel");
  await waitFor(() => expect(within(panel).getAllByTestId("evidence-entry").length).toBeGreaterThan(0));
  const entry = within(panel).getByRole("button", { name: "Show contradicting evidence in the paper (Insight in this research)" });
  await user.click(entry);
  expect(screen.getByTestId("editor-announcement")).toHaveTextContent("Showing the insight in the paper");
  const insightCard = screen.getByLabelText("Insight block");
  expect(insightCard).toHaveTextContent("Synthetic explorer insight");
  expect(insightCard).toHaveTextContent("2026-11-01 – 2026-11-06 (UTC, half-open)");
  expect(insightCard).toHaveTextContent(shortId(insightContext.dataset_version_id));
  expectCleanDocument(5);
});
