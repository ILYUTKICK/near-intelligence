/** Synthetic chart and private document fixtures for NI-047. */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { ChartAuthActions } from "@/features/charts/library/ChartAuthActions";
import { chartObservation } from "@/features/charts/renderer/observation-context";
import { loadDocumentChart } from "@/features/editor/blocks/chart-api";
import { ResearchDocumentEditor } from "@/features/editor/workbench";
import { definition, metric, observation, series, view } from "../ui/renderer/fixtures";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/features/editor/blocks/chart-api", () => ({ loadDocumentChart: vi.fn() }));
vi.mock("@/features/charts/renderer/chart-factory", () => ({ defaultChartFactory: vi.fn(async () => ({
  setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn(),
})) }));

const id = "44444444-4444-4444-8444-444444444444";
const chartId = "55555555-5555-4555-8555-555555555555";
const versionId = "66666666-6666-4666-8666-666666666666";
const insightId = "77777777-7777-4777-8777-777777777777";
const insightBlockId = "88888888-8888-4888-8888-888888888888";
const hypothesisId = "99999999-9999-4999-8999-999999999999";
const time = "2026-11-08T12:00:00Z";
const metricDefinition = metric("USD", "Synthetic metric", "synthetic-usd");
const chart = view(definition({ metric_definition_ids: [metricDefinition.id] }), [
  series(metricDefinition, [observation("2026-11-01", "12.000000000000000001")]),
]);
const context = chartObservation(chart);
const chartBlock = { type: "liveChart", attrs: { block_id: chartId, mode: "live", observed_dataset_version_id: context.dataset_version_id,
  chart_definition_version_id: context.chart_definition_version_id, selection: context.selection } };
const hypothesis = { type: "hypothesis", attrs: { block_id: "22222222-2222-4222-8222-222222222222",
  hypothesis_id: hypothesisId, statement: "Synthetic hypothesis", assessment: "untested", authored_at: time, modified_at: time } };
const paper = (content: unknown[]) => ({ schema_version: 1, type: "doc", content });
const doc = { id, title: "Synthetic insight research", revision: 3, schema_version: 1, current_version_id: versionId,
  updated_at: time, created_at: time, progress: { headings: 0, charts: 1, insights: 0 } };
const researchPath = `/api/documents/${id}`;
const saved = (content: unknown[], revision = 4) => Response.json({
  document: { ...doc, revision },
  version: { id: versionId, document_id: id, revision, schema_version: 1, created_at: time, content_sha256: "a".repeat(64),
    content: paper(content), resolved_contexts: {} },
}, { status: 200 });

function fixture(content: unknown[], write: (request: Request) => Promise<Response>,
  current: () => { revision: number; content: unknown[] } = () => ({ revision: doc.revision, content })) {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(input instanceof Request ? input.url : String(input), location.origin).pathname;
    if (path === "/api/auth/session") return Response.json({ subject: "synthetic-alice" });
    if (path === "/api/auth/csrf") return Response.json({ token: "synthetic-csrf" });
    if (path === "/api/documents") return Response.json({ items: [doc], next_cursor: null });
    if (path === researchPath) {
      const currentDoc = current();
      return Response.json({ ...doc, revision: currentDoc.revision, content: paper(currentDoc.content), resolved_contexts: {} });
    }
    if (input instanceof Request && path.startsWith(`${researchPath}/insights`)) return write(input);
    throw new Error(`Unexpected synthetic request ${path}`);
  }));
}

afterEach(() => { vi.unstubAllGlobals(); vi.resetAllMocks(); sessionStorage.clear(); });

it("captures the public inspection when opened and keeps its key and payload after an uncertain response", async () => {
  const requests: Array<{ key: string | null; body: unknown }> = [];
  fixture([hypothesis], async request => {
    expect(request.headers.get("x-csrf-token")).toBe("synthetic-csrf");
    expect(request.headers.get("if-match")).toBe('"3"');
    requests.push({ key: request.headers.get("idempotency-key"), body: await request.json() });
    if (requests.length === 1) throw new TypeError("Synthetic response loss");
    return saved([]);
  });
  const user = userEvent.setup();
  const input = { chart_definition_version_id: context.chart_definition_version_id, dataset_version_id: context.dataset_version_id,
    selection: context.selection, mode: "live" as const };
  const nextPath = "/charts/synthetic";
  const screenView = render(<ChartAuthActions nextPath={nextPath} chartTitle="Synthetic" saveInput={input} insightContext={context} />);
  await user.click(await screen.findByRole("button", { name: "Add Insight" }));
  await user.selectOptions(screen.getByLabelText("Destination"), await screen.findByRole("option", { name: doc.title }));
  await user.selectOptions(await screen.findByLabelText("Linked hypothesis"), hypothesisId);
  await user.type(screen.getByLabelText("Insight text"), "Synthetic note from the original inspection");
  const newer = { ...context, dataset_version_id: "11111111-1111-4111-8111-111111111111" };
  screenView.rerender(<ChartAuthActions nextPath={nextPath} chartTitle="Synthetic"
    saveInput={{ ...input, dataset_version_id: newer.dataset_version_id }} insightContext={newer} />);
  expect(screen.getByRole("dialog")).toHaveTextContent(context.dataset_version_id);
  await user.click(screen.getByRole("button", { name: "Confirm Add Insight" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic response loss");
  expect(screen.getByLabelText("Insight text")).toHaveValue("Synthetic note from the original inspection");
  await user.click(screen.getByRole("button", { name: "Retry confirmed insertion" }));
  expect(await screen.findByRole("link", { name: "Open research" })).toHaveAttribute("href", `/workspace/research/${id}`);
  expect(requests).toHaveLength(2);
  expect(requests[0].key).toBeTruthy();
  expect(requests[1]).toEqual(requests[0]);
  expect(requests[0].body).toMatchObject({ context, hypothesis_id: hypothesisId });
});

it("adds a chart insight at the saved anchor and adopts the acknowledged revision", async () => {
  const requests: unknown[] = [];
  vi.mocked(loadDocumentChart).mockResolvedValue(chart);
  fixture([chartBlock], async request => {
    const body = await request.json();
    requests.push(body);
    return saved([chartBlock, { type: "insight", attrs: {
      block_id: body.block_id, insight_id: insightId, type: body.type, classification: body.classification,
      body: body.body, context: body.context, authored_at: time, modified_at: time,
    } }]);
  });
  const user = userEvent.setup();
  sessionStorage.setItem(`near-intelligence.editor-draft.${id}`, JSON.stringify({ baseRevision: 3, capturedAt: time,
    body: { schema_version: 1, content: paper([chartBlock]), observed_contexts: [] } }));
  render(<ResearchDocumentEditor documentId={id} />);
  const add = await screen.findByRole("button", { name: "Add Insight" });
  expect(add).toBeDisabled();
  await user.click(await screen.findByTestId("draft-discard"));
  await waitFor(() => expect(add).toBeEnabled());
  await user.click(add);
  const dialog = await screen.findByRole("dialog");
  expect(dialog).toHaveTextContent(context.dataset_version_id);
  await user.selectOptions(within(dialog).getByLabelText("Insight type"), "risk");
  await user.type(within(dialog).getByLabelText("Insight text"), "Synthetic editor insight");
  await user.click(within(dialog).getByRole("button", { name: "Save insight" }));
  expect(await screen.findByText("Synthetic editor insight")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByTestId("editor-announcement")).toHaveTextContent("Insight saved"));
  expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved .*Revision 4/);
  expect(requests).toHaveLength(1);
  expect(requests[0]).toMatchObject({ after_block_id: chartId, type: "risk", context });
});

it("requires explicit evidence cleanup and keeps text on a stale revision", async () => {
  const insight = { type: "insight", attrs: { block_id: insightBlockId, insight_id: insightId, type: "observation", classification: "uncertain",
    context, body: [{ type: "paragraph", content: [{ type: "text", text: "Synthetic linked insight" }] }], authored_at: time, modified_at: time } };
  const evidence = { type: "evidence", attrs: { block_id: "33333333-3333-4333-8333-333333333333",
    evidence_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", hypothesis_id: hypothesisId, classification: "supporting",
    target_kind: "insight", target_id: insightId, explanation: "Synthetic evidence link" } };
  const removedHypothesisId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
  const removedHypothesis = { ...hypothesis, attrs: { ...hypothesis.attrs, block_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    hypothesis_id: removedHypothesisId, statement: "Synthetic hypothesis removed elsewhere" } };
  const requests: unknown[] = [];
  let revision = 3;
  let content = [hypothesis, removedHypothesis, insight, evidence];
  fixture([hypothesis, insight, evidence], async request => {
    const body = await request.json();
    requests.push(body);
    if (requests.length === 1) {
      revision = 4;
      content = [hypothesis, insight, evidence];
      return Response.json({ error: { code: "REVISION_CONFLICT", message: "Synthetic CAS conflict",
        request_id: "fixture", retryable: false } }, { status: 409 });
    }
    if (request.method === "PATCH") {
      expect(request.headers.get("if-match")).toBe('"4"');
      expect(body.hypothesis_id).toBeNull();
      revision = 5;
      content = [hypothesis, { ...insight, attrs: { ...insight.attrs, body: body.body } }, evidence];
      return saved(content, revision);
    }
    expect(request.headers.get("if-match")).toBe('"5"');
    return saved([hypothesis], 6);
  }, () => ({ revision, content }));
  const user = userEvent.setup();
  render(<ResearchDocumentEditor documentId={id} />);
  const edit = await screen.findByRole("button", { name: "Edit insight" });
  await waitFor(() => expect(edit).toBeEnabled());
  await user.click(edit);
  let dialog = await screen.findByRole("dialog");
  const text = within(dialog).getByLabelText("Insight text");
  await user.selectOptions(within(dialog).getByLabelText("Linked hypothesis"), removedHypothesisId);
  await user.clear(text);
  await user.type(text, "Synthetic draft kept after conflict");
  await user.click(within(dialog).getByRole("button", { name: "Save insight" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("research changed");
  expect(text).toHaveValue("Synthetic draft kept after conflict");
  expect(requests[0]).not.toHaveProperty("context");
  expect(within(dialog).getByRole("button", { name: "Save insight" })).toBeDisabled();
  await user.click(within(dialog).getByRole("button", { name: "Reload and review" }));
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Save insight" })).toBeEnabled());
  expect(text).toHaveValue("Synthetic draft kept after conflict");
  expect(within(dialog).getByText("The selected hypothesis was removed. Review the insight before saving.")).toBeInTheDocument();
  await user.click(within(dialog).getByRole("button", { name: "Save insight" }));
  expect(await screen.findByText("Synthetic draft kept after conflict")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Delete insight" }));
  dialog = await screen.findByRole("dialog");
  const remove = within(dialog).getByRole("button", { name: "Confirm deletion" });
  expect(remove).toBeDisabled();
  fireEvent.click(within(dialog).getByRole("checkbox", { name: /Also remove 1 linked evidence block/ }));
  await user.click(remove);
  await waitFor(() => expect(screen.queryByText("Synthetic draft kept after conflict")).toBeNull());
  expect(screen.queryByText("Synthetic evidence link")).toBeNull();
  expect(screen.getByText("Synthetic hypothesis")).toBeInTheDocument();
  expect(requests[2]).toEqual({ remove_evidence_links: true });
});
