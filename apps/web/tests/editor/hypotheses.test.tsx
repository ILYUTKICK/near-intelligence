/** Synthetic private research fixtures for NI-048. */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { components } from "@near-intelligence/shared-types";
import type { CanonicalBlock } from "@/features/editor/canonical";
import { ResearchDocumentEditor } from "@/features/editor/workbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const id = "11111111-1111-4111-8111-111111111111";
const blockId = "22222222-2222-4222-8222-222222222222";
const hypothesisId = "33333333-3333-4333-8333-333333333333";
const versionId = "44444444-4444-4444-8444-444444444444";
const time = "2026-11-09T10:00:00Z";
const path = `/api/documents/${id}`;
const paper = (content: CanonicalBlock[]) => ({ schema_version: 1, type: "doc", content });
const hypothesis: Extract<CanonicalBlock, { type: "hypothesis" }> = { type: "hypothesis", attrs: {
  block_id: blockId, hypothesis_id: hypothesisId, statement: "Synthetic original question", assessment: "untested", authored_at: time, modified_at: time,
} };
const evidence: CanonicalBlock = { type: "evidence", attrs: {
  block_id: "55555555-5555-4555-8555-555555555555", evidence_id: "66666666-6666-4666-8666-666666666666",
  hypothesis_id: hypothesisId, classification: "uncertain", target_kind: "citation", target_id: "77777777-7777-4777-8777-777777777777",
  explanation: "Synthetic evidence link",
} };
const risk: Extract<CanonicalBlock, { type: "risk" }> = { type: "risk", attrs: {
  block_id: "88888888-8888-4888-8888-888888888888", title: "Synthetic risk remains", related_hypothesis_id: hypothesisId,
  body: [{ type: "paragraph", content: [{ type: "text", text: "Synthetic risk rationale", marks: [] }] }],
} };

function fixture(initial: CanonicalBlock[], write: (request: Request, state: ReturnType<typeof stateFor>) => Promise<Response>) {
  const state = stateFor(initial);
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.origin);
    if (url.pathname === "/api/auth/session") return Response.json({ subject: "synthetic-alice" });
    if (url.pathname === "/api/auth/csrf") return Response.json({ token: "synthetic-csrf" });
    if (url.pathname === path) return Response.json(state.document());
    if (input instanceof Request && url.pathname.startsWith(`${path}/hypotheses`)) return write(new Request(input, init), state);
    throw new Error(`Unexpected synthetic request ${url.pathname}`);
  }));
}

function stateFor(initial: CanonicalBlock[]) {
  return {
    content: initial,
    revision: 1,
    document() {
      return { id, title: "Synthetic hypothesis research", revision: this.revision, schema_version: 1, current_version_id: versionId,
        updated_at: time, created_at: time, progress: { headings: 0, charts: 0, insights: 0 }, content: paper(this.content), resolved_contexts: {} };
    },
    saved(value: unknown, status = 200) {
      return Response.json({ document: this.document(), version: { id: versionId, document_id: id, revision: this.revision,
        schema_version: 1, created_at: time, content_sha256: "a".repeat(64), content: paper(this.content), resolved_contexts: {} }, value }, { status });
    },
  };
}

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

it("adds a hypothesis to empty research, retains the retry key, and reopens the authored assessment", async () => {
  const calls: Array<{ key: string | null; body: components["schemas"]["HypothesisCreateRequest"] }> = [];
  fixture([], async (request, state) => {
    expect(request.headers.get("x-csrf-token")).toBe("synthetic-csrf");
    expect(request.headers.get("if-match")).toBe('"1"');
    const body = await request.json() as components["schemas"]["HypothesisCreateRequest"];
    calls.push({ key: request.headers.get("idempotency-key"), body });
    if (calls.length === 1) throw new TypeError("Synthetic response loss");
    const added = { ...hypothesis, attrs: { ...hypothesis.attrs, ...body } };
    state.content = [added];
    state.revision = 2;
    return state.saved({ ...body, id: hypothesisId, document_id: id, authored_at: time, modified_at: time }, 201);
  });
  const user = userEvent.setup();
  const view = render(<ResearchDocumentEditor documentId={id} />);
  const add = await screen.findByRole("button", { name: "Add hypothesis" });
  await waitFor(() => expect(add).toBeEnabled());
  await user.click(add);
  const dialog = await screen.findByRole("dialog", { name: "Add hypothesis" });
  const select = await within(dialog).findByLabelText("Author assessment");
  expect(select).toHaveValue("untested");
  expect(within(select).getAllByRole("option").map(option => option.textContent)).toEqual([
    "Untested", "Supported", "Mixed", "Weakened", "Insufficient data",
  ]);
  await user.selectOptions(select, "insufficient_data");
  await user.type(within(dialog).getByLabelText("Hypothesis statement"), "Synthetic unconfirmed question");
  await user.click(within(dialog).getByRole("button", { name: "Save hypothesis" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("Synthetic response loss");
  await user.click(within(dialog).getByRole("button", { name: "Retry same change" }));
  expect(await screen.findByLabelText("Hypothesis block")).toHaveTextContent("Author assessment · Insufficient data");
  expect(screen.getByLabelText("Hypothesis block")).toHaveTextContent("0 linked evidence blocks");
  expect(calls).toHaveLength(2);
  expect(calls[0].key).toBeTruthy();
  expect(calls[0].body).not.toHaveProperty("after_block_id");
  expect(calls[1]).toEqual(calls[0]);
  view.unmount();
  render(<ResearchDocumentEditor documentId={id} />);
  expect(await screen.findByLabelText("Hypothesis block")).toHaveTextContent("Synthetic unconfirmed question");
  const entry = await screen.findByRole("button", { name: "Hypothesis · Synthetic unconfirmed question" });
  expect(entry).toHaveAttribute("data-hypothesis-id", hypothesisId);
  expect(entry).toHaveAttribute("aria-current", "true");
});

it("keeps a stale edit and its linked evidence, then requires cleanup and retains the risk text", async () => {
  const calls: Array<{ method: string; body: unknown }> = [];
  fixture([hypothesis, evidence, risk], async (request, state) => {
    const body = await request.json();
    calls.push({ method: request.method, body });
    if (calls.length === 1) {
      state.revision = 2;
      return Response.json({ error: { code: "REVISION_CONFLICT", message: "Synthetic newer revision", request_id: "fixture", retryable: false } }, { status: 409 });
    }
    if (request.method === "PATCH") {
      expect(request.headers.get("if-match")).toBe('"2"');
      const edited = { ...hypothesis, attrs: { ...hypothesis.attrs, ...body } };
      state.revision = 3;
      state.content = [edited, evidence, risk];
      return state.saved({ ...body, block_id: blockId, id: hypothesisId, document_id: id, authored_at: time, modified_at: time });
    }
    expect(request.headers.get("if-match")).toBe('"3"');
    const { related_hypothesis_id: related, ...riskAttrs } = risk.attrs;
    expect(related).toBe(hypothesisId);
    state.content = [{ ...risk, attrs: riskAttrs }];
    state.revision = 4;
    return state.saved({ deleted_id: hypothesisId });
  });
  const user = userEvent.setup();
  render(<ResearchDocumentEditor documentId={id} />);
  const edit = await screen.findByRole("button", { name: "Edit hypothesis" });
  await waitFor(() => expect(edit).toBeEnabled());
  await user.click(edit);
  const dialog = await screen.findByRole("dialog", { name: "Edit hypothesis" });
  const statement = within(dialog).getByLabelText("Hypothesis statement");
  await user.clear(statement);
  await user.type(statement, "Synthetic revised question");
  await user.selectOptions(within(dialog).getByLabelText("Author assessment"), "mixed");
  const save = within(dialog).getByRole("button", { name: "Save hypothesis" });
  await user.click(save);
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("research changed");
  expect(save).toBeDisabled();
  await user.click(within(dialog).getByRole("button", { name: "Reload and review" }));
  await waitFor(() => expect(save).toBeEnabled());
  expect(statement).toHaveValue("Synthetic revised question");
  await user.click(save);
  await waitFor(() => expect(screen.getByLabelText("Hypothesis block")).toHaveTextContent("Author assessment · Mixed"));
  expect(screen.getByLabelText("Hypothesis block")).toHaveTextContent("1 linked evidence block");
  expect(screen.getByRole("button", { name: "Hypothesis · Synthetic revised question" })).toHaveAttribute("data-hypothesis-id", hypothesisId);
  await user.click(screen.getByRole("button", { name: "Delete block" }));
  const deletion = await screen.findByRole("dialog", { name: "Delete hypothesis" });
  expect(within(deletion).getByText("Remove 1 linked evidence block.")).toBeInTheDocument();
  expect(within(deletion).getByText(/Clear the hypothesis link on 1 insight or risk block/)).toBeInTheDocument();
  const confirm = within(deletion).getByRole("button", { name: "Confirm deletion" });
  expect(confirm).toBeDisabled();
  await user.click(within(deletion).getByRole("checkbox", { name: "Confirm linked cleanup" }));
  await user.click(confirm);
  await waitFor(() => expect(screen.queryByLabelText("Hypothesis block")).toBeNull());
  expect(screen.queryByText("Synthetic evidence link")).toBeNull();
  const riskCard = screen.getByLabelText("Risk block");
  expect(within(riskCard).getByRole("textbox", { name: "Risk title" })).toHaveValue("Synthetic risk remains");
  expect(riskCard).toHaveTextContent("Synthetic risk rationale");
  expect(riskCard).toHaveTextContent("No related hypothesis");
  expect(calls).toEqual([
    { method: "PATCH", body: { statement: "Synthetic revised question", assessment: "mixed" } },
    { method: "PATCH", body: { statement: "Synthetic revised question", assessment: "mixed" } },
    { method: "DELETE", body: { remove_evidence_links: true } },
  ]);
});
