/** Synthetic saved research and catalog responses for NI-049. */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { chartObservation } from "@/features/charts/renderer/observation-context";
import { ResearchDocumentEditor } from "@/features/editor/workbench";
import { definition, metric, observation, series, view } from "../ui/renderer/fixtures";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const documentId = "11111111-1111-4111-8111-111111111111";
const versionId = "22222222-2222-4222-8222-222222222222";
const hypothesisId = "33333333-3333-4333-8333-333333333333";
const hypothesisBlockId = "44444444-4444-4444-8444-444444444444";
const insightId = "55555555-5555-4555-8555-555555555555";
const evidenceId = "66666666-6666-4666-8666-666666666666";
const modelId = "77777777-7777-4777-8777-777777777777";
const secondModel = "88888888-8888-4888-8888-888888888888";
const evidenceBlockId = "99999999-9999-4999-8999-999999999999";
const timestamp = "2026-11-09T12:00:00Z";
const path = `/api/documents/${documentId}`;
const metricDefinition = metric("USD", "Synthetic metric", "synthetic-usd");
const context = chartObservation(view(definition({ metric_definition_ids: [metricDefinition.id] }), [
  series(metricDefinition, [observation("2026-11-01", "12.000000000000000001")]),
]));

const hypothesis = { type: "hypothesis", attrs: { block_id: hypothesisBlockId, hypothesis_id: hypothesisId,
  statement: "Synthetic hypothesis", assessment: "untested", authored_at: timestamp, modified_at: timestamp } };
const insight = { type: "insight", attrs: { block_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", insight_id: insightId,
  body: [{ type: "paragraph", content: [{ type: "text", text: "Synthetic pinned observation" }] }], context,
  type: "observation", classification: "uncertain", authored_at: timestamp, modified_at: timestamp } };
const evidence = { type: "evidence", attrs: { block_id: evidenceBlockId, evidence_id: evidenceId, hypothesis_id: hypothesisId,
  classification: "supporting", target_kind: "insight", target_id: insightId, explanation: "Synthetic supporting link" } };

function fixture(
  write: (request: Request) => Promise<Response>,
  current: () => { revision: number; content: unknown[] } = () => ({ revision: 3, content: [hypothesis, insight, evidence] }),
  catalog?: (query: URLSearchParams) => Response,
) {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.origin);
    if (url.pathname === "/api/auth/session") return Response.json({ subject: "synthetic-alice" });
    if (url.pathname === "/api/auth/csrf") return Response.json({ token: "synthetic-csrf" });
    if (url.pathname === path) {
      const doc = current();
      return Response.json({ ...documentSummary(doc.revision), content: paper(doc.content), resolved_contexts: {} });
    }
    if (url.pathname === `${path}/evidence-targets` && catalog) return catalog(url.searchParams);
    if (input instanceof Request && url.pathname.startsWith(`${path}/evidence`)) return write(new Request(input, init));
    throw new Error(`Unexpected synthetic request ${url.pathname}`);
  }));
}

const paper = (content: unknown[]) => ({ schema_version: 1, type: "doc", content });
const documentSummary = (revision: number) => ({ id: documentId, title: "Synthetic evidence research", schema_version: 1, revision,
  current_version_id: versionId, updated_at: timestamp, created_at: timestamp, progress: { headings: 0, charts: 0, insights: 1 } });
function save(content: unknown[], revision: number, value: unknown, status = 200) {
  return Response.json({ document: documentSummary(revision), version: { id: versionId, document_id: documentId, revision, schema_version: 1,
    created_at: timestamp, content_sha256: "a".repeat(64), content: paper(content), resolved_contexts: {} }, value }, { status });
}

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

it("adds a contradictory link to a saved target without changing the authored assessment", async () => {
  const writes: unknown[] = [];
  fixture(async request => {
    expect(request.method).toBe("POST");
    expect(request.headers.get("if-match")).toBe('"3"');
    expect(request.headers.get("x-csrf-token")).toBe("synthetic-csrf");
    const body = await request.json();
    writes.push(body);
    const attrs = { block_id: body.block_id, evidence_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", hypothesis_id: body.hypothesis_id,
      classification: body.classification, target_kind: body.target_kind, target_id: body.target_id, explanation: body.explanation };
    return save([hypothesis, { type: "evidence", attrs }, insight, evidence], 4, attrs, 201);
  });
  const user = userEvent.setup();
  render(<ResearchDocumentEditor documentId={documentId} />);
  const add = await screen.findByRole("button", { name: "Add evidence" });
  await waitFor(() => expect(add).toBeEnabled());
  await user.click(add);
  const dialog = await screen.findByRole("dialog", { name: "Add evidence link" });
  expect(within(dialog).getByLabelText("Hypothesis")).toHaveValue(hypothesisId);
  const targets = within(dialog).getByLabelText("Evidence target");
  expect(within(targets).getAllByRole("option")).toHaveLength(2);
  await user.selectOptions(targets, insightId);
  await user.selectOptions(within(dialog).getByLabelText("Evidence classification"), "contradicting");
  await user.type(within(dialog).getByLabelText("Explanation"), "Synthetic contrary explanation");
  await user.click(within(dialog).getByRole("button", { name: "Save evidence link" }));
  await waitFor(() => expect(screen.getByLabelText("Hypothesis block")).toHaveTextContent("Supporting 1 · Contradicting 1 · Uncertain 0"));
  expect(screen.getByLabelText("Hypothesis block")).toHaveTextContent("Author assessment · Untested");
  expect(screen.getByText("Synthetic contrary explanation")).toBeInTheDocument();
  expect(writes).toEqual([{ after_block_id: hypothesisBlockId, block_id: expect.any(String), hypothesis_id: hypothesisId,
    classification: "contradicting", target_kind: "insight", target_id: insightId, explanation: "Synthetic contrary explanation" }]);
});

it("pages published targets and preserves an explicit retarget after a stale revision", async () => {
  let revision = 3;
  let content: unknown[] = [hypothesis, insight, evidence];
  const writes: Array<{ method: string; body: unknown }> = [];
  fixture(async request => {
    if (request.method === "DELETE") {
      expect(await request.text()).toBe("");
      expect(request.headers.get("if-match")).toBe('"5"');
      writes.push({ method: request.method, body: null });
      return save([hypothesis, insight], 6, { deleted_id: evidenceId });
    }
    const body = await request.json();
    writes.push({ method: request.method, body });
    if (writes.length === 1) {
      revision = 4;
      return Response.json({ error: { code: "REVISION_CONFLICT", message: "Synthetic newer revision", request_id: "fixture", retryable: false } }, { status: 409 });
    }
    expect(request.headers.get("if-match")).toBe('"4"');
    const edited = { ...evidence, attrs: { ...evidence.attrs, ...body } };
    content = [hypothesis, insight, edited];
    revision = 5;
    return save(content, revision, edited.attrs);
  }, () => ({ revision, content }), query => {
    expect(query.get("target_kind")).toBe("model_run");
    return query.get("cursor") === "next-synthetic-page"
      ? Response.json({ items: [{ id: secondModel, label: "Synthetic second public run" }], next_cursor: null })
      : Response.json({ items: [{ id: modelId, label: "Synthetic first public run" }], next_cursor: "next-synthetic-page" });
  });
  const user = userEvent.setup();
  render(<ResearchDocumentEditor documentId={documentId} />);
  const edit = await screen.findByRole("button", { name: "Edit evidence link" });
  await waitFor(() => expect(edit).toBeEnabled());
  await user.click(edit);
  const dialog = await screen.findByRole("dialog", { name: "Edit evidence link" });
  await user.selectOptions(within(dialog).getByLabelText("Target type"), "model_run");
  await user.click(await within(dialog).findByRole("button", { name: "Load more targets" }));
  const option = await within(dialog).findByRole("option", { name: "Synthetic second public run" });
  await user.selectOptions(within(dialog).getByLabelText("Evidence target"), option);
  const submit = within(dialog).getByRole("button", { name: "Save evidence link" });
  await user.click(submit);
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("research changed");
  await user.click(within(dialog).getByRole("button", { name: "Reload and review" }));
  await waitFor(() => expect(submit).toBeEnabled());
  expect(within(dialog).getByLabelText("Evidence target")).toHaveValue(secondModel);
  expect(within(dialog).getByLabelText("Explanation")).toHaveValue("Synthetic supporting link");
  await user.click(submit);
  await waitFor(() => expect(screen.getByLabelText("Evidence block")).toHaveTextContent("Supporting · Published model run"));
  await user.click(screen.getByRole("button", { name: "Delete evidence link" }));
  const deletion = await screen.findByRole("dialog", { name: "Delete evidence link" });
  await user.click(within(deletion).getByRole("button", { name: "Confirm deletion" }));
  await waitFor(() => expect(screen.queryByLabelText("Evidence block")).toBeNull());
  expect(writes[1]).toEqual(writes[0]);
  expect(writes[0]).toMatchObject({ method: "PATCH", body: { target_kind: "model_run", target_id: secondModel } });
  expect(writes[2]).toEqual({ method: "DELETE", body: null });
  expect(screen.getByLabelText("Hypothesis block")).toHaveTextContent("0 linked evidence blocks");
});

it("requires explicit reselection when the same private target has a new pin", async () => {
  let revision = 3;
  let currentInsight = insight;
  fixture(async () => {
    revision = 4;
    currentInsight = { ...insight, attrs: { ...insight.attrs, context: { ...context,
      dataset_version_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc" } } };
    return Response.json({ error: { code: "REVISION_CONFLICT", message: "Synthetic changed pin", request_id: "fixture", retryable: false } }, { status: 409 });
  }, () => ({ revision, content: [hypothesis, currentInsight, evidence] }));
  const user = userEvent.setup();
  render(<ResearchDocumentEditor documentId={documentId} />);
  const edit = await screen.findByRole("button", { name: "Edit evidence link" });
  await waitFor(() => expect(edit).toBeEnabled());
  await user.click(edit);
  const dialog = await screen.findByRole("dialog", { name: "Edit evidence link" });
  const explanation = within(dialog).getByLabelText("Explanation");
  await user.clear(explanation);
  await user.type(explanation, "Synthetic retained explanation");
  const submit = within(dialog).getByRole("button", { name: "Save evidence link" });
  await user.click(submit);
  await user.click(await within(dialog).findByRole("button", { name: "Reload and review" }));
  expect(await within(dialog).findByText(/A selection changed or was removed/)).toBeInTheDocument();
  const target = within(dialog).getByLabelText("Evidence target");
  expect(target).toHaveValue("");
  expect(explanation).toHaveValue("Synthetic retained explanation");
  expect(submit).toBeDisabled();
  await user.selectOptions(target, insightId);
  expect(submit).toBeEnabled();
});
