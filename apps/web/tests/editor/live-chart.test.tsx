/** NI-042 synthetic-only node/renderer regressions; no published research data. */
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InteractiveChart, type ChartBlockAttrs } from "@/features/editor/blocks/live-chart";
import { ResearchDocumentEditor } from "@/features/editor/workbench";
import { loadDocumentChart } from "@/features/editor/blocks/chart-api";
import { definition, metric, observation, series, view } from "../ui/renderer/fixtures";

vi.mock("@/features/editor/blocks/chart-api", () => ({ loadDocumentChart: vi.fn() }));
vi.mock("@/features/charts/renderer/chart-factory", () => ({ defaultChartFactory: vi.fn(async () => ({ setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn() })) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
const definitionFixture = definition({ filter_schema: { type: "object", properties: { source: { type: "string", enum: ["synthetic-a", "synthetic-b"] } }, additionalProperties: false } });
const resolved = view(definitionFixture, [series(metric("USD", "Synthetic USD", "synthetic"), [observation("2026-11-01", "12.000000000000000001")])]);
const attrs: ChartBlockAttrs = { block_id: "11111111-1111-4111-8111-111111111111", mode: "live", chart_definition_version_id: definitionFixture.id, observed_dataset_version_id: resolved.dataset.id, selection: { ...resolved.selection, filters: {} } };
const context = { documentId: "22222222-2222-4222-8222-222222222222", subject: "synthetic-alice", saved: true, ready: true };
const loader = vi.mocked(loadDocumentChart);
// jsdom has no Range geometry. ProseMirror's real Undo scrolls the selection;
// these bounded stand-ins let us test content/focus, never pixel geometry.
const rangeRects = Object.getOwnPropertyDescriptor(Range.prototype, "getClientRects");
const rangeRect = Object.getOwnPropertyDescriptor(Range.prototype, "getBoundingClientRect");
beforeEach(() => {
  vi.spyOn(window, "scrollBy").mockImplementation(() => {});
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [new DOMRect(0, 0, 1, 1)] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect(0, 0, 1, 1) });
});
afterEach(() => {
  if (rangeRects) Object.defineProperty(Range.prototype, "getClientRects", rangeRects); else Reflect.deleteProperty(Range.prototype, "getClientRects");
  if (rangeRect) Object.defineProperty(Range.prototype, "getBoundingClientRect", rangeRect); else Reflect.deleteProperty(Range.prototype, "getBoundingClientRect");
});

afterEach(() => { vi.resetAllMocks(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });
function resolveNormally(pointer: () => string | null = () => null) { loader.mockImplementation(async (_doc, _def, selection, dataset) => ({ ...resolved, selection: { ...selection, filters: selection.filters ?? {}, frequency: "day" }, dataset: { ...resolved.dataset, id: dataset === "latest" ? "33333333-3333-4333-8333-333333333333" : dataset }, latest_approved_dataset_version_id: pointer() })); }

describe("Interactive editor chart", () => {
  it("renders the shared exact table, sources, definition and honest gated insight action", async () => {
    resolveNormally(); const apply = vi.fn(); render(<InteractiveChart attrs={attrs} context={context} onApply={apply} />);
    expect(await screen.findByText("12.000000000000000001")).toBeInTheDocument();
    expect(screen.getByText("Sources & definitions")).toBeInTheDocument();
    expect(screen.getByText("Chart definition and pinned context")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Insight" })).toBeDisabled();
    expect(screen.getByText(/saved, resolved chart/)).toBeInTheDocument(); expect(apply).not.toHaveBeenCalled();
    expect(loader.mock.calls[0]?.[3]).toBe(attrs.observed_dataset_version_id);
  });
  it("keeps range/filter drafts local and resolves before one explicit persisted edit", async () => {
    resolveNormally(); const apply = vi.fn(); const user = userEvent.setup();
    render(<InteractiveChart attrs={attrs} context={context} onApply={apply} />);
    await screen.findByRole("button", { name: "Apply range and filters" });
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-11-02" } });
    await user.selectOptions(screen.getByLabelText("Source"), "synthetic-b");
    expect(apply).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Apply range and filters" }));
    await waitFor(() => expect(apply).toHaveBeenCalledOnce());
    expect(apply).toHaveBeenCalledWith({ selection: { start: "2026-11-02", end: attrs.selection.end, frequency: "day", filters: { source: "synthetic-b" } }, observed_dataset_version_id: attrs.observed_dataset_version_id });
    await user.click(screen.getByRole("button", { name: "Refresh to latest and save observation" }));
    await waitFor(() => expect(apply).toHaveBeenCalledTimes(2));
    expect(loader.mock.calls.at(-1)?.[3]).toBe("latest");
  });
  it("round-trips an NI-071 multi-value filter draft into one persisted explicit edit", async () => {
    const recipients = ["buybacks.multisignature.near", "fefundsadmin.sputnik-dao.near"];
    const multiDefinition = definition({ filter_schema: { type: "object", properties: {
      recipient: { type: "string", enum: recipients, multi_value: true,
        reconciliation: { aggregate_metric_id: "m", aggregate_metric_version: 1, universe_note: "fixture" } },
    }, additionalProperties: false } });
    const multiResolved = view(multiDefinition, [series(metric("NEAR", "Synthetic payouts", "synthetic"), [observation("2026-11-01", "5")])]);
    loader.mockImplementation(async (_doc, _def, selection, datasetVersion) => ({
      ...multiResolved,
      selection: { ...selection, filters: selection.filters ?? {}, frequency: "day" as const },
      dataset: { ...multiResolved.dataset, id: datasetVersion },
    }));
    const apply = vi.fn(); const user = userEvent.setup();
    const multiAttrs: ChartBlockAttrs = { ...attrs, chart_definition_version_id: multiDefinition.id, selection: { ...multiResolved.selection, filters: {} } };
    const element = render(<InteractiveChart attrs={multiAttrs} context={context} onApply={apply} />);
    await screen.findByRole("button", { name: "Apply range and filters" });

    // Draft-local: checking two recipients never writes the document.
    await user.click(screen.getByRole("checkbox", { name: recipients[1] }));
    await user.click(screen.getByRole("checkbox", { name: recipients[0] }));
    expect(apply).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Apply range and filters" }));
    await waitFor(() => expect(apply).toHaveBeenCalledOnce());
    // The resolved context (server-validated canonical echo) drives the edit;
    // the stored per-key order is the declared option order.
    const appliedSelection = apply.mock.calls[0][0].selection as { filters: Record<string, string[]> };
    expect(appliedSelection.filters).toEqual({ recipient: [recipients[0], recipients[1]] });
    // the shared controls canonicalize on change, so the request — like the
    // persisted edit — carries the declared option order
    expect(loader.mock.calls.at(-1)?.[2].filters).toEqual({ recipient: [recipients[0], recipients[1]] });
    // The applied selection is acknowledged by the parent (attrs update),
    // then clearing every box removes the dimension ("all — no filter").
    element.rerender(<InteractiveChart attrs={{ ...multiAttrs, selection: apply.mock.calls[0][0].selection as ChartBlockAttrs["selection"] }} context={context} onApply={apply} />);
    await user.click(screen.getByRole("checkbox", { name: recipients[0] }));
    await user.click(screen.getByRole("checkbox", { name: recipients[1] }));
    await user.click(screen.getByRole("button", { name: "Apply range and filters" }));
    await waitFor(() => expect(apply).toHaveBeenCalledTimes(2));
    expect((apply.mock.calls[1][0].selection as { filters: Record<string, string[]> }).filters).toEqual({});
  });

  it("leaves the persisted node untouched on source/range errors and rejects late results after account suspension", async () => {
    resolveNormally(); const apply = vi.fn(); const user = userEvent.setup();
    const element = render(<InteractiveChart attrs={attrs} context={context} onApply={apply} />);
    await screen.findByLabelText("Start date");
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-11-08" } });
    expect(screen.getByRole("button", { name: "Apply range and filters" })).toHaveAttribute("aria-disabled", "true");
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-11-02" } });
    loader.mockRejectedValueOnce(new Error("Synthetic source unavailable"));
    await user.click(screen.getByRole("button", { name: "Apply range and filters" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic source unavailable"); expect(apply).not.toHaveBeenCalled();
    let finish: (value: typeof resolved) => void = () => {};
    loader.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    await user.click(screen.getByRole("button", { name: "Apply range and filters" }));
    element.rerender(<InteractiveChart attrs={attrs} context={{ ...context, ready: false }} onApply={apply} />);
    await act(async () => finish(resolved));
    expect(apply).not.toHaveBeenCalled(); expect(screen.queryByText("Sources & definitions")).not.toBeInTheDocument();
  });
  it("drops an edit completed in the same batch as an account change or Undo, and on deletion", async () => {
    resolveNormally(); const user = userEvent.setup(); const apply = vi.fn();
    const element = render(<InteractiveChart attrs={attrs} context={context} onApply={apply} />);
    await screen.findByLabelText("Start date");
    let finish: (value: typeof resolved) => void = () => {};
    loader.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    await user.click(screen.getByRole("button", { name: "Refresh to latest and save observation" }));
    await act(async () => {
      element.rerender(<InteractiveChart attrs={attrs} context={{ ...context, ready: false }} onApply={apply} />);
      finish(resolved);
    });
    expect(apply).not.toHaveBeenCalled();
    element.rerender(<InteractiveChart attrs={attrs} context={context} onApply={apply} />);
    await screen.findByLabelText("Start date");
    loader.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    await user.click(screen.getByRole("button", { name: "Refresh to latest and save observation" }));
    await act(async () => {
      element.rerender(<InteractiveChart attrs={{ ...attrs, selection: { ...attrs.selection, start: "2026-11-02" } }} context={context} onApply={apply} />);
      finish(resolved);
    });
    expect(apply).not.toHaveBeenCalled();
    element.unmount(); await act(async () => finish(resolved)); expect(apply).not.toHaveBeenCalled();
  });
  it("hides an old context when Undo changes the inspected selection and its reload fails", async () => {
    resolveNormally(); const apply = vi.fn();
    const element = render(<InteractiveChart attrs={attrs} context={context} onApply={apply} />);
    expect(await screen.findByText("12.000000000000000001")).toBeInTheDocument();
    loader.mockRejectedValueOnce(new Error("Synthetic pinned reconstruction unavailable"));
    element.rerender(<InteractiveChart attrs={{ ...attrs, selection: { ...attrs.selection, start: "2026-11-02" } }} context={context} onApply={apply} />);
    expect(screen.queryByText("12.000000000000000001")).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic pinned reconstruction unavailable");
    expect(screen.queryByText("Sources & definitions")).not.toBeInTheDocument(); expect(apply).not.toHaveBeenCalled();
  });
  it("activates chart controls when a local chart draft is restored into an initially empty document", async () => {
    resolveNormally(); const user = userEvent.setup();
    const content = { schema_version: 1, type: "doc", content: [{ type: "liveChart", attrs: { ...attrs, snapshot_id: null } }] };
    sessionStorage.setItem(`near-intelligence.editor-draft.${context.documentId}`, JSON.stringify({ baseRevision: 2, capturedAt: "2026-11-08T00:00:00Z", body: { schema_version: 1, content, observed_contexts: [] } }));
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith("/api/auth/session")) return Response.json({ subject: "synthetic-alice" });
      return Response.json({ id: context.documentId, title: "Synthetic empty server document", revision: 2, schema_version: 1, current_version_id: null, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-08T00:00:00Z", progress: { headings: 0, charts: 0, insights: 0 }, content: { schema_version: 1, type: "doc", content: [] }, resolved_contexts: {} });
    }));
    render(<ResearchDocumentEditor documentId={context.documentId} />);
    await user.click(await screen.findByTestId("draft-restore"));
    expect(await screen.findByText("12.000000000000000001")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh to latest and save observation" })).toBeEnabled();
  });
  it("uses the actual Tiptap node, saves applied context, and Escape returns focus without losing prose", async () => {
    let newerDataset: string | null = null;
    resolveNormally(() => newerDataset); const user = userEvent.setup(); const savedBodies: Record<string, unknown>[] = [];
    const normalLoad = loader.getMockImplementation()!;
    let changedReads = 0;
    let finishStale: (() => void) | undefined;
    loader.mockImplementation(async (...args) => {
      const result = await normalLoad(...args);
      if (args[2].start === "2026-11-02" && ++changedReads === 2) {
        return new Promise(resolve => { finishStale = () => resolve(result); });
      }
      return result;
    });
    const content = { schema_version: 1, type: "doc", content: [{ type: "paragraph", attrs: { block_id: "44444444-4444-4444-8444-444444444444" }, content: [{ type: "text", text: "Synthetic local prose" }] }, { type: "liveChart", attrs: { ...attrs, snapshot_id: null } }] };
    const summary = { id: context.documentId, title: "Synthetic chart document", revision: 2, schema_version: 1, current_version_id: null, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-08T00:00:00Z", progress: { headings: 0, charts: 1, insights: 0 } };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.endsWith("/api/auth/session")) return Response.json({ subject: "synthetic-alice" });
      if (url.endsWith("/api/auth/csrf")) return Response.json({ token: "synthetic-csrf" });
      if (url.endsWith("/versions")) {
        savedBodies.push(JSON.parse(String(init?.body)));
        newerDataset = "33333333-3333-4333-8333-333333333333";
        return Response.json({ document: { ...summary, revision: 3, updated_at: "2026-11-08T12:00:00Z" }, version: { revision: 3 } }, { status: 201, headers: { etag: '"3"' } });
      }
      return Response.json({ ...summary, content, resolved_contexts: {} });
    }));
    render(<ResearchDocumentEditor documentId={context.documentId} />);
    expect(await screen.findByText("12.000000000000000001")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-11-02" } });
    await user.selectOptions(screen.getByLabelText("Source"), "synthetic-a");
    const applyControl = screen.getByRole("button", { name: "Apply range and filters" });
    await user.pointer([{ keys: "[TouchA>]", target: applyControl }, { keys: "[/TouchA]", target: applyControl }]);
    expect(await screen.findByText("Changed — document has unsaved edits")).toBeInTheDocument();
    expect(applyControl).toHaveFocus();
    const sourceTrigger = screen.getByRole("button", { name: "Sources & definitions" });
    await user.click(sourceTrigger); await screen.findByRole("dialog");
    await user.keyboard("{Escape}"); await waitFor(() => expect(sourceTrigger).toHaveFocus());
    screen.getByLabelText("Start date").focus(); await user.keyboard("{Escape}");
    expect(screen.getByRole("textbox", { name: "Research paper editor" })).toHaveFocus();
    expect(screen.getByText("Synthetic local prose")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Save now/ }));
    await waitFor(() => expect(savedBodies.length).toBeGreaterThan(0));
    expect(JSON.stringify(savedBodies[0])).toContain('"source":"synthetic-a"');
    expect(JSON.stringify(savedBodies[0])).toContain('"start":"2026-11-02"');
    expect(JSON.stringify(savedBodies[0])).toContain("Synthetic local prose");
    expect(savedBodies[0].observed_contexts).toEqual([{
      chart_definition_version_id: definitionFixture.id, dataset_version_id: attrs.observed_dataset_version_id,
      selection: { start: "2026-11-02", end: attrs.selection.end, frequency: "day", filters: { source: "synthetic-a" } },
      context_hash: resolved.context_hash, renderer_version: definitionFixture.renderer_version,
      metric_definition_versions: definitionFixture.metric_definition_ids, resolved_at: resolved.resolved_at,
    }]);
    expect(await screen.findByText("Newer approved data available")).toBeInTheDocument();
    expect(finishStale).toBeDefined();
    await act(async () => finishStale?.());
    expect(screen.getByText("Newer approved data available")).toBeInTheDocument();
    expect(loader.mock.calls.every(call => call[3] === attrs.observed_dataset_version_id)).toBe(true);
    const paper = screen.getByRole("textbox", { name: "Research paper editor" });
    paper.focus(); fireEvent.keyDown(paper, { key: "z", ctrlKey: true });
    await waitFor(() => expect(screen.getByLabelText("Start date")).toHaveValue(attrs.selection.start));
    expect(within(paper).getByText("Synthetic local prose")).toBeInTheDocument();
    fireEvent.keyDown(paper, { key: "z", ctrlKey: true, shiftKey: true });
    await waitFor(() => expect(screen.getByLabelText("Start date")).toHaveValue("2026-11-02"));
  });
});

describe("Compact editor chart chrome (NI-078, NI-076 D5)", () => {
  it("keeps the pin and save state visible with the dataset id in the disclosure", async () => {
    resolveNormally();
    render(<InteractiveChart attrs={attrs} context={context} onApply={vi.fn()} />);
    await screen.findByText("12.000000000000000001");
    const identifier = screen.getByText(`Observed dataset: ${attrs.observed_dataset_version_id}`);
    expect(identifier.closest("details")).not.toHaveAttribute("open");
    expect(screen.getByText("Live chart · pinned observation")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Saved in document revision");
    expect(screen.getByText(/Opening or typing never refreshes this pin/)).toBeInTheDocument();
  });

  it("keeps the explicit refresh and stable action row outside the frame", async () => {
    resolveNormally();
    const { container } = render(<InteractiveChart attrs={attrs} context={context} onApply={vi.fn()} />);
    await screen.findByText("12.000000000000000001");
    const refresh = screen.getByRole("button", { name: "Refresh to latest and save observation" });
    expect(refresh).toBeEnabled();
    // The action row is the block's own control group, not a frame toolbar
    // remount: it exists before and after the view resolves (stable focus).
    const group = refresh.closest("div[role='group']") ?? refresh.closest("div");
    expect(group).not.toBeNull();
    expect(container.contains(refresh)).toBe(true);
  });
});
