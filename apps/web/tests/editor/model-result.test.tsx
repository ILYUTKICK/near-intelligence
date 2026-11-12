/** NI-055 synthetic-only model-result regressions; no published research data. */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { loadPinnedRun } from "@/features/editor/blocks/model-run-api";
import { SlashMenu } from "@/features/editor/insert-menu";
import { ResearchDocumentEditor } from "@/features/editor/workbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const documentId = "44444444-4444-4444-8444-444444444444";
const versionId = "66666666-6666-4666-8666-666666666666";
const runId = "77777777-7777-4777-8777-777777777777";
const otherRunId = "88888888-8888-4888-8888-888888888888";
const datasetId = "99999999-9999-4999-8999-999999999999";
const blockId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const time = "2026-11-12T12:00:00Z";

const runDetail = {
  run_id: runId,
  model_id: "gross_fee_activity_v1",
  model_version: 1,
  gate_verdict: "READY_WITH_LIMITS",
  sample: { start: "2025-01-01", end_exclusive: "2025-02-01", nobs: 60 },
  tolerances: { coefficient_rtol: "0.00000001", coefficient_atol: "0.00000001" },
  code_commit: "a".repeat(40),
  manifest_url: `/api/model-runs/${runId}/manifest`,
  published_at: time,
  published_by: "Synthetic operator",
  specification: {},
  admission_reasons: [],
  design: {},
  estimation: {},
  coefficients: [{
    name: "fee_share_t-1", estimate: 0.123456789, std_error: 0.0123456789,
    t_stat: 9.9, p_value: 0.02, ci95_low: 0.1, ci95_high: 0.15,
  }],
  diagnostics: { stationarity: {} },
  interpretation: {},
  limitations: {
    prohibited_labels: ["Causal effect"],
    spec_limitation_notes: ["Synthetic limitation note"],
    gate_limit_codes: ["LIMIT-1"],
  },
  environment: {},
  reproduction: {},
  approval: { decision: "approve", reviewer: "Synthetic reviewer", review_reference: "synthetic-ref" },
};

const interpretation = [{ type: "paragraph", content: [{ type: "text", text: "Authored interpretation.", marks: [] }] }];
const modelBlock = { type: "modelResult", attrs: { block_id: blockId, model_run_id: runId, dataset_version_id: datasetId, interpretation } };
const paper = (content: unknown[]) => ({ schema_version: 1, type: "doc", content });
const doc = { id: documentId, title: "Synthetic model research", revision: 2, schema_version: 1,
  current_version_id: versionId, updated_at: time, created_at: time, progress: { headings: 0, charts: 0, insights: 0 } };
const researchPath = `/api/documents/${documentId}`;

function stubFetch(state: {
  document: () => { revision: number; content: unknown[] };
  savedVersionId?: string;
  version?: () => { revision: number; content: unknown[] };
  runs?: unknown;
  onInsert?: (request: Request) => Response;
  onSave?: (body: unknown) => Response;
  onExport?: (body: unknown) => Response;
}) {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : String(input), location.origin).pathname;
    if (path === "/api/auth/session") return Response.json({ subject: "synthetic-alice" });
    if (path === "/api/auth/csrf") return Response.json({ token: "synthetic-csrf" });
    if (path === "/api/model-runs") return Response.json({ items: [state.runs ?? runDetail], next_cursor: null });
    if (path === `/api/model-runs/${runId}`) return Response.json(state.runs ?? runDetail);
    if (path === researchPath) {
      const current = state.document();
      return Response.json({ ...doc, revision: current.revision, content: paper(current.content), resolved_contexts: {} });
    }
    if (path === researchPath && (init?.method ?? (input as Request).method) === "POST") throw new Error("unreachable");
    if (path === `${researchPath}/model-blocks`) {
      return state.onInsert?.({ headers: new Headers(init?.headers) } as Request) ?? new Response(null, { status: 500 });
    }
    if (path === `${researchPath}/versions`) {
      return state.onSave?.(JSON.parse(String(init?.body))) ?? new Response(null, { status: 500 });
    }
    const savedId = state.savedVersionId ?? versionId;
    if (path === `${researchPath}/versions/${savedId}`) {
      const saved = (state.version ?? state.document)();
      return Response.json({ id: savedId, document_id: documentId, revision: saved.revision, schema_version: 1,
        created_at: time, content_sha256: "a".repeat(64), content: paper(saved.content), resolved_contexts: {} });
    }
    if (path === `${researchPath}/exports` && state.onExport && input instanceof Request) {
      return state.onExport(await input.json());
    }
    throw new Error(`Unexpected synthetic request ${path}`);
  }));
}

afterEach(() => { vi.unstubAllGlobals(); vi.resetAllMocks(); sessionStorage.clear(); });

describe("insert/slash menu item", () => {
  it("offers Model result on the shared slash surface and reports the choice", async () => {
    const user = userEvent.setup();
    const onInsert = vi.fn();
    render(<SlashMenu onInsert={onInsert} onClose={vi.fn()} coordinates={{ left: 0, top: 0 }} boundaryWidth={300} />);
    const list = screen.getByRole("listbox", { name: "Block types" });
    const item = within(list).getByRole("option", { name: /Model result/ });
    expect(item).toHaveTextContent("Published model run + your interpretation");
    await user.click(item);
    expect(onInsert).toHaveBeenCalledWith({ type: "modelResult", headingLevel: undefined });
  });
});

describe("pinned run reader", () => {
  it("accepts only the exact pinned identity and fails honestly otherwise", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : String(input), location.origin).pathname;
      expect(path).toBe(`/api/model-runs/${runId}`);
      return Response.json(runDetail);
    }));
    const run = await loadPinnedRun(runId);
    expect(run.run_id).toBe(runId);
    expect(run.coefficients[0].estimate).toBe(0.123456789);
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ ...runDetail, run_id: otherRunId })));
    await expect(loadPinnedRun(runId)).rejects.toThrow("does not match the pinned identity");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 404 })));
    await expect(loadPinnedRun(runId)).rejects.toThrow("could not be loaded");
  });
});

describe("model result block", () => {
  it("renders the recorded summary with limits before coefficients and verbatim values", async () => {
    stubFetch({ document: () => ({ revision: doc.revision, content: [modelBlock] }) });
    render(<ResearchDocumentEditor documentId={documentId} />);
    const card = await screen.findByRole("group", { name: "Model result block" });
    await waitFor(() => expect(card.textContent).toContain("gross_fee_activity_v1 · v1"));
    // Limits precede any coefficient (the NI-054 ordering contract).
    const text = card.textContent ?? "";
    expect(text.indexOf("Prohibited labels")).toBeLessThan(text.indexOf("fee_share_t-1"));
    expect(text.indexOf("Causal effect")).toBeLessThan(text.indexOf("fee_share_t-1"));
    // Recorded floats verbatim — no rounding, no locale formatting.
    expect(within(card).getByText("0.123456789")).toBeInTheDocument();
    expect(within(card).getByText("0.0123456789")).toBeInTheDocument();
    expect(within(card).getByText("0.02")).toBeInTheDocument();
    expect(within(card).getByText("[0.1, 0.15]")).toBeInTheDocument();
    expect(within(card).getByText("Synthetic limitation note")).toBeInTheDocument();
    expect(within(card).getByText(/Gate limit codes: LIMIT-1/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "published run page" })).toHaveAttribute("href", `/models/${runId}`);
    expect(within(card).getByLabelText("Interpretation of the pinned model result")).toHaveValue("Authored interpretation.");
  });

  it("rejects a run response that does not match the pinned identity and keeps the ids", async () => {
    stubFetch({ document: () => ({ revision: doc.revision, content: [modelBlock] }), runs: { ...runDetail, run_id: otherRunId } });
    render(<ResearchDocumentEditor documentId={documentId} />);
    const card = await screen.findByRole("group", { name: "Model result block" });
    expect(await within(card).findByRole("alert")).toHaveTextContent("does not match the pinned identity");
    expect(within(card).queryByText("fee_share_t-1")).not.toBeInTheDocument();
    expect(within(card).getAllByText(/^77777777/).length).toBeGreaterThan(0);
  });

  it("keeps the pinned ids unchanged while the interpretation prose is edited and saved", async () => {
    const savedBodies: unknown[] = [];
    let savedProse = "";
    stubFetch({
      document: () => ({ revision: doc.revision, content: [modelBlock] }),
      onSave: (body) => {
        savedBodies.push(body);
        const block = (body as { content: { content: Array<{ type: string; attrs: Record<string, unknown> }> } }).content.content
          .find((node) => node.type === "modelResult");
        savedProse = JSON.stringify(block?.attrs.interpretation);
        return Response.json({
          document: { ...doc, revision: doc.revision + 1, updated_at: "2026-11-12T13:00:00Z" },
          version: { id: versionId, document_id: documentId, revision: doc.revision + 1, schema_version: 1,
            created_at: time, content_sha256: "a".repeat(64), content: paper([modelBlock]), resolved_contexts: {} },
        }, { status: 201, headers: { etag: `"${doc.revision + 1}"` } });
      },
    });
    const user = userEvent.setup();
    render(<ResearchDocumentEditor documentId={documentId} />);
    const card = await screen.findByRole("group", { name: "Model result block" });
    const textarea = within(card).getByLabelText("Interpretation of the pinned model result");
    await user.clear(textarea);
    await user.type(textarea, "Edited prose; the pinned run stays.");
    await user.click(screen.getByRole("button", { name: /^Save now/ }));
    await waitFor(() => expect(savedBodies.length).toBeGreaterThan(0));
    const block = (savedBodies[0] as { content: { content: Array<{ type: string; attrs: Record<string, unknown> }> } }).content.content
      .find((node) => node.type === "modelResult");
    expect(block?.attrs.model_run_id).toBe(runId);
    expect(block?.attrs.dataset_version_id).toBe(datasetId);
    expect(block?.attrs.block_id).toBe(blockId);
    expect(savedProse).toContain("Edited prose; the pinned run stays.");
    // No coefficient-like attr can enter the saved content.
    expect(JSON.stringify(savedBodies[0])).not.toContain("coefficients");
  });

  it("returns keyboard focus to the selected block on Escape without losing prose", async () => {
    stubFetch({ document: () => ({ revision: doc.revision, content: [modelBlock] }) });
    const user = userEvent.setup();
    render(<ResearchDocumentEditor documentId={documentId} />);
    const card = await screen.findByRole("group", { name: "Model result block" });
    const textarea = within(card).getByLabelText("Interpretation of the pinned model result");
    textarea.focus();
    expect(textarea).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Research paper editor" })).toHaveFocus());
    expect(within(card).getByLabelText("Interpretation of the pinned model result")).toHaveValue("Authored interpretation.");
  });

  it("inserts a pinned model result through the Add Model chooser and reopens it", async () => {
    const insertedVersionId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
    const onExport = vi.fn<(body: unknown) => Response>(() => Response.json({ id: blockId, document_id: documentId,
      document_version_id: insertedVersionId, format: "markdown_zip", status: "queued" }, { status: 202 }));
    const inserts: Array<{ ifMatch: string | null; key: string | null }> = [];
    let inserted = false;
    const insertedPaper = [modelBlock];
    stubFetch({
      document: () => ({ revision: inserted ? 3 : doc.revision, content: inserted ? insertedPaper : [] }),
      savedVersionId: insertedVersionId,
      onExport,
      onInsert: (request) => {
        inserts.push({ ifMatch: request.headers.get("if-match"), key: request.headers.get("idempotency-key") });
        inserted = true;
        return Response.json({ document: { ...doc, revision: 3, current_version_id: insertedVersionId, updated_at: "2026-11-12T14:00:00Z" },
          value: { block_id: blockId } }, { status: 201, headers: { etag: '"3"' } });
      },
    });
    const user = userEvent.setup();
    render(<ResearchDocumentEditor documentId={documentId} />);
    const paperEditor = await screen.findByRole("textbox", { name: "Research paper editor" });
    await user.click(screen.getByRole("button", { name: "Insert block" }));
    await user.click(screen.getByRole("menuitem", { name: /Model result/ }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByRole("option", { name: new RegExp(runId) });
    await user.selectOptions(within(dialog).getByLabelText("Published run"), runId);
    await user.type(within(dialog).getByLabelText("Approved dataset version (UUID)"), datasetId);
    await user.type(within(dialog).getByLabelText("Interpretation of the pinned model result"), "Chosen interpretation");
    // The confirm stays gated until every pin and the prose are present.
    const confirm = within(dialog).getByRole("button", { name: "Confirm Add Model" });
    const datasetInput = within(dialog).getByLabelText("Approved dataset version (UUID)");
    await user.clear(datasetInput);
    expect(confirm).toBeDisabled();
    await user.type(datasetInput, datasetId);
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    expect(await screen.findByText("Model result added with its pinned run and dataset.")).toBeInTheDocument();
    expect(inserts).toHaveLength(1);
    expect(inserts[0].ifMatch).toBe('"2"');
    expect(inserts[0].key).toMatch(/^[a-f0-9-]{36}$/);
    const card = screen.getByRole("group", { name: "Model result block" });
    expect(within(card).getByText("Authored interpretation.")).toBeInTheDocument();
    expect(within(card).getAllByText(/gross_fee_activity_v1/).length).toBeGreaterThan(0);
    // The context pane shows the pinned identities of the selected block.
    expect(screen.getByTestId("context-pane")).toHaveTextContent(datasetId.slice(0, 8));
    await waitFor(() => expect(paperEditor).toHaveFocus());
    await user.click(screen.getByTestId("export-open"));
    expect(onExport).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Start export" }));
    await waitFor(() => expect(onExport).toHaveBeenCalledWith({ document_version_id: insertedVersionId, format: "markdown_zip" }));
    await user.click(screen.getByTestId("export-close"));
  });

  it("reloads after a stale revision and retries a lost confirmation using the exact saved revision", async () => {
    const external = { type: "paragraph", attrs: { block_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" },
      content: [{ type: "text", text: "An edit from another tab.", marks: [] }] };
    const attempts: Array<{ revision: string | null; key: string | null }> = [];
    let current = { revision: 2, content: [] as unknown[] };
    stubFetch({
      document: () => current,
      version: () => ({ revision: 4, content: [external, modelBlock] }),
      onInsert: ({ headers }) => {
        attempts.push({ revision: headers.get("if-match"), key: headers.get("idempotency-key") });
        if (attempts.length === 1) {
          current = { revision: 3, content: [external] };
          return Response.json({ error: { code: "REVISION_CONFLICT", message: "Synthetic stale revision",
            request_id: "synthetic", retryable: false, details: [] } }, { status: 409 });
        }
        if (attempts.length === 2) {
          current = { revision: 5, content: [modelBlock] };
          throw new Error("Synthetic connection loss");
        }
        return Response.json({ document: { ...doc, revision: 4 }, value: { block_id: blockId } }, { status: 201 });
      },
    });
    const user = userEvent.setup();
    render(<ResearchDocumentEditor documentId={documentId} />);
    await screen.findByRole("textbox", { name: "Research paper editor" });
    await user.click(screen.getByRole("button", { name: "Insert block" }));
    await user.click(screen.getByRole("menuitem", { name: /Model result/ }));
    const dialog = within(await screen.findByRole("dialog"));
    await user.selectOptions(await dialog.findByLabelText("Published run"), runId);
    await user.type(dialog.getByLabelText("Approved dataset version (UUID)"), datasetId);
    const prose = dialog.getByLabelText("Interpretation of the pinned model result");
    await user.type(prose, "Authored interpretation.");
    await user.click(dialog.getByRole("button", { name: "Confirm Add Model" }));
    await user.click(await dialog.findByRole("button", { name: "Reload and review" }));
    await dialog.findByText(/The current revision is loaded/);
    expect(prose).toHaveValue("Authored interpretation.");
    await user.click(dialog.getByRole("button", { name: "Confirm Add Model" }));
    await dialog.findByText("Synthetic connection loss");
    await user.click(dialog.getByRole("button", { name: "Retry confirmed insertion" }));
    await screen.findByText("Model result added with its pinned run and dataset.");
    expect(attempts.map(({ revision }) => revision)).toEqual(['"2"', '"3"', '"3"']);
    expect(attempts[1].key).toBe(attempts[2].key);
    expect(screen.getByText("An edit from another tab.")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Model result block" })).toBeInTheDocument();
  });

  it("shows an honest typed failure when the chosen run is not published (zero side effects)", async () => {
    stubFetch({
      document: () => ({ revision: doc.revision, content: [] }),
      onInsert: () => Response.json({ error: { code: "REFERENCE_INVALID", message: "Referenced model run does not exist or is not a published immutable artifact",
        request_id: "synthetic", retryable: false, details: [{ path: "model_run_id", reason: "dangling_model_run_reference" }] } }, { status: 422 }),
    });
    const user = userEvent.setup();
    render(<ResearchDocumentEditor documentId={documentId} />);
    await screen.findByRole("textbox", { name: "Research paper editor" });
    await user.click(screen.getByRole("button", { name: "Insert block" }));
    await user.click(screen.getByRole("menuitem", { name: /Model result/ }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(await within(dialog).findByLabelText("Published run"), runId);
    await user.type(within(dialog).getByLabelText("Approved dataset version (UUID)"), datasetId);
    await user.type(within(dialog).getByLabelText("Interpretation of the pinned model result"), "Never stored");
    await user.click(within(dialog).getByRole("button", { name: "Confirm Add Model" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("not a published immutable artifact");
    // The dialog stays open with the draft intact; nothing was inserted.
    expect(within(dialog).getByLabelText("Interpretation of the pinned model result")).toHaveValue("Never stored");
    expect(screen.queryByRole("group", { name: "Model result block" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Research paper editor" })).toHaveFocus());
  });
});
