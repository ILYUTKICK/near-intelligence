import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "jest-axe";
import { FreezeSnapshotButton } from "@/features/charts/snapshots/FreezeSnapshotButton";
import { Snapshots } from "@/features/charts/snapshots/Snapshots";
import { SnapshotDetail } from "@/features/charts/snapshots/SnapshotDetail";
import { definition, view } from "./renderer/fixtures";

vi.mock("@/features/charts/renderer/ChartView", () => ({ ChartView: (props: { view?: { dataset: { id: string } } }) => <div>Shared chart renderer {props.view?.dataset.id ?? ""}</div> }));

const snapshotId = "33333333-3333-4333-8333-333333333333";
const definitionId = "44444444-4444-4444-8444-444444444444";
const datasetId = "55555555-5555-4555-8555-555555555555";
const liveDatasetId = "66666666-6666-4666-8666-666666666666";
const selection = { start: "2026-11-01", end: "2026-11-06", frequency: "day" as const, filters: { source: "SRC-LLAMA" } };
const snapshot = {
  id: snapshotId, chart_definition_version_id: definitionId, dataset_version_id: datasetId,
  selection,
  calculation_context: { context_hash: "c".repeat(64), metric_definition_versions: [definitionId], renderer_version: "synthetic-renderer/1" },
  artifact_id: null, content_sha256: "d".repeat(64), created_at: "2026-11-06T12:00:00Z",
};
const frozenView = view(definition(), [], { dataset: { ...view(definition(), []).dataset, id: datasetId } });
const liveView = view(definition(), [], { dataset: { ...view(definition(), []).dataset, id: liveDatasetId } });
const detail = { snapshot, view: frozenView };
const freezeInput = { chart_definition_version_id: definitionId, dataset_version_id: datasetId, selection };
function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }); }
function csrfFetch(respond: (url: string, options: RequestInit) => Promise<Response>) {
  return vi.fn(async (url: string, options: RequestInit = {}) => {
    if (url === "/api/auth/session") return json({ subject: "synthetic-alice" });
    if (url === "/api/auth/csrf") return json({ token: "synthetic-csrf" });
    return respond(url, options);
  });
}
afterEach(() => vi.unstubAllGlobals());

describe("Snapshot freeze control", () => {
  it("freezes the inspected evidence, reusing the idempotency key after a lost response", async () => {
    const keys: string[] = [];
    const fetcher = csrfFetch((url, options) => {
      if (url === "/api/snapshots") {
        keys.push(new Headers(options.headers).get("idempotency-key")!);
        if (keys.length === 1) throw new Error("Response lost after commit");
        return json(snapshot, 201);
      }
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetcher);
    const user = userEvent.setup();
    const { container } = render(<FreezeSnapshotButton input={freezeInput} />);
    await user.click(screen.getByRole("button", { name: "Freeze snapshot" }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Freeze snapshot" }));
    await screen.findByRole("status");
    expect(JSON.parse(String(fetcher.mock.calls.at(-1)?.[1]?.body))).toEqual(freezeInput);
    expect(keys).toHaveLength(2); expect(keys[1]).toBe(keys[0]);
    expect(screen.getByRole("link", { name: "Open snapshots" })).toHaveAttribute("href", "/workspace/saved-charts/snapshots");
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
  it("surfaces a failed freeze honestly", async () => {
    vi.stubGlobal("fetch", csrfFetch(async (url) => {
      if (url === "/api/snapshots") return json({ error: { code: "VALIDATION_ERROR", message: "Filters are not supported by this version", request_id: "synthetic", retryable: false, details: [] } }, 422);
      throw new Error(`unexpected ${url}`);
    }));
    const user = userEvent.setup();
    render(<FreezeSnapshotButton input={freezeInput} />);
    await user.click(screen.getByRole("button", { name: "Freeze snapshot" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Filters are not supported");
  });
});

describe("Snapshot list", () => {
  it("shows loading, an accessible empty state and owner-scoped metadata", async () => {
    let items: unknown[] = [snapshot];
    const fetcher = csrfFetch(async (url, options) => {
      if (options.method === "DELETE") { items = []; return new Response(null, { status: 204 }); }
      if (url.startsWith("/api/snapshots/")) return json(detail);
      return json({ items, next_cursor: null });
    });
    vi.stubGlobal("fetch", fetcher);
    const user = userEvent.setup();
    const { container } = render(<Snapshots />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading snapshots");
    await screen.findByText(/Frozen chart snapshot/);
    expect(screen.getByText(new RegExp(datasetId))).toBeInTheDocument();
    expect(screen.getByText(new RegExp("d".repeat(8)))).toBeInTheDocument();
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Remove" }));
    await user.click(screen.getByRole("button", { name: "Confirm removal" }));
    await screen.findByText(/No snapshots yet/);
    expect(items).toHaveLength(0);
  });
  it("reports a referenced snapshot instead of deleting it (409)", async () => {
    const fetcher = csrfFetch(async (url, options) => {
      if (options.method === "DELETE") return json({ error: { code: "REFERENCE_IN_USE", message: "referenced", request_id: "synthetic", retryable: false, details: [] } }, 409);
      if (url.startsWith("/api/snapshots/")) return json(detail);
      return json({ items: [snapshot], next_cursor: null });
    });
    vi.stubGlobal("fetch", fetcher);
    const user = userEvent.setup();
    render(<Snapshots />);
    await screen.findByText(/Frozen chart snapshot/);
    await user.click(screen.getByRole("button", { name: "Remove" }));
    await user.click(screen.getByRole("button", { name: "Confirm removal" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("referenced by a saved chart and cannot be deleted");
  });
  it("offers retry on a load failure", async () => {
    const fetcher = csrfFetch(async () => { throw new Error("down"); });
    vi.stubGlobal("fetch", fetcher);
    render(<Snapshots />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("down");
    expect(alert).toHaveTextContent("Try again");
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });
});

describe("Snapshot detail", () => {
  it("renders the frozen view with storage metadata and explicit compare-to-live", async () => {
    const fetcher = csrfFetch(async (url) => {
      if (url === `/api/snapshots/${snapshotId}/compare-live`) {
        return json({ snapshot, frozen_view: frozenView, live_view: liveView, dataset_changed: true });
      }
      if (url === `/api/snapshots/${snapshotId}`) return json(detail);
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetcher);
    const user = userEvent.setup();
    render(<SnapshotDetail snapshotId={snapshotId} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading snapshot");
    await screen.findByText("Shared chart renderer " + datasetId);
    expect(screen.getByText(new RegExp("d".repeat(8)))).toBeInTheDocument();
    expect(screen.getByText(new RegExp("c".repeat(8)))).toBeInTheDocument();
    expect(screen.getByText(/pinned dataset/)).toHaveTextContent(datasetId);
    await user.click(screen.getByRole("button", { name: "Compare to live" }));
    await screen.findByRole("heading", { name: "Compare to live" });
    expect(screen.getByText(/latest approved dataset differs/)).toBeInTheDocument();
    expect(screen.getByText("Shared chart renderer " + liveDatasetId)).toBeInTheDocument();
    expect(screen.getAllByText("Shared chart renderer " + datasetId).length).toBe(2);
  });
  it("explains an identical pin and keeps the comparison read-only", async () => {
    const fetcher = csrfFetch(async (url) => {
      if (url === `/api/snapshots/${snapshotId}/compare-live`) {
        return json({ snapshot, frozen_view: frozenView, live_view: frozenView, dataset_changed: false });
      }
      if (url === `/api/snapshots/${snapshotId}`) return json(detail);
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetcher);
    const user = userEvent.setup();
    render(<SnapshotDetail snapshotId={snapshotId} />);
    await screen.findByText("Shared chart renderer " + datasetId);
    await user.click(screen.getByRole("button", { name: "Compare to live" }));
    expect(await screen.findByText(/same one this snapshot pins/)).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });
  it("surfaces a failed comparison and a failed removal", async () => {
    const conflict = { error: { code: "REFERENCE_IN_USE", message: "referenced", request_id: "synthetic", retryable: false, details: [] } };
    const fetcher = csrfFetch(async (url, options) => {
      if (options.method === "DELETE") return json(conflict, 409);
      if (url === `/api/snapshots/${snapshotId}/compare-live`) return new Response(null, { status: 503 });
      if (url === `/api/snapshots/${snapshotId}`) return json(detail);
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetcher);
    const user = userEvent.setup();
    render(<SnapshotDetail snapshotId={snapshotId} />);
    await screen.findByText("Shared chart renderer " + datasetId);
    await user.click(screen.getByRole("button", { name: "Compare to live" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The snapshot could not be managed");
    await user.click(screen.getByRole("button", { name: "Remove snapshot" }));
    expect((await screen.findAllByRole("alert")).at(-1)).toHaveTextContent("referenced by a saved chart");
  });
});
