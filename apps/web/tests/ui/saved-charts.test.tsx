import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "jest-axe";
import { ChartAuthActions } from "@/features/charts/library/ChartAuthActions";
import { SaveChartButton } from "@/features/charts/saved/SaveChartButton";
import { SavedCharts } from "@/features/charts/saved/SavedCharts";
import { SavedChartDetail } from "@/features/charts/saved/SavedChartDetail";
import { AUTH_CHANGE } from "@/lib/auth/change";
import { definition, view } from "./renderer/fixtures";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/features/charts/renderer/ChartView", () => ({
  ChartView: (props: { actions?: React.ReactNode }) => <div>Shared chart renderer{props.actions ?? null}</div>,
}));
const id = "22222222-2222-4222-8222-222222222222";
const datasetId = "55555555-5555-4555-8555-555555555555";
const selection = { start: "2026-11-01", end: "2026-11-06", frequency: "day" as const, filters: { source: ["SRC-LLAMA"] } };
const saved = { id, label: "Synthetic saved chart", mode: "live" as const,
  chart_definition_version_id: id, selection, snapshot_id: null,
  last_resolved_dataset_version_id: id, created_at: "2026-11-06T12:00:00Z", updated_at: "2026-11-06T12:00:00Z" };
const input = { chart_definition_version_id: id, selection, dataset_version_id: id, mode: "live" as const };
function json(body: unknown, status = 200) { return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "content-type": "application/json" } }); }
afterEach(() => vi.unstubAllGlobals());

describe("Saved chart workflow", () => {
  it("retains a lost-response retry through same-account focus revalidation", async () => {
    const keys: string[] = [];
    let sessionChecks = 0;
    let releaseSession!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") {
        if (++sessionChecks === 2) return new Promise<Response>((resolve) => { releaseSession = resolve; });
        return json({ subject: "synthetic-alice" });
      }
      if (url === "/api/auth/csrf") return json({ token: "synthetic-csrf" });
      keys.push(new Headers(options.headers).get("idempotency-key")!);
      if (keys.length === 1) throw new Error("Response lost after commit");
      return json(saved, 201);
    }));
    const user = userEvent.setup();
    render(<ChartAuthActions chartTitle="Synthetic" nextPath="/charts/intents-volume" saveInput={input} />);
    await user.click(await screen.findByRole("button", { name: "Save chart" }));
    await screen.findByRole("alert");
    fireEvent(window, new Event("focus"));
    expect(screen.queryByRole("button", { name: "Save chart" })).toBeNull();
    releaseSession(json({ subject: "synthetic-alice" }));
    await user.click(await screen.findByRole("button", { name: "Save chart" }));
    await screen.findByRole("link", { name: "Open saved chart" });
    expect(keys).toHaveLength(2); expect(keys[1]).toBe(keys[0]);
    fireEvent(window, new Event("focus"));
    expect(await screen.findByRole("link", { name: "Open saved chart" })).toHaveAttribute("href", `/workspace/saved-charts/${id}`);
    expect(keys).toHaveLength(2);
  });

  it.each(["focus", AUTH_CHANGE])("discards the old account's save state on %s", async (event) => {
    let subject = "synthetic-alice";
    const keys: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return json({ subject });
      if (url === "/api/auth/csrf") return json({ token: "synthetic-csrf" });
      keys.push(new Headers(options.headers).get("idempotency-key")!);
      return json(saved, 201);
    }));
    const user = userEvent.setup();
    render(<ChartAuthActions chartTitle="Synthetic" nextPath="/charts/intents-volume" saveInput={input} />);
    await user.click(await screen.findByRole("button", { name: "Save chart" }));
    await screen.findByRole("link", { name: "Open saved chart" });
    subject = "synthetic-bob";
    fireEvent(window, new Event(event));
    expect(screen.queryByRole("link", { name: "Open saved chart" })).toBeNull();
    await user.click(await screen.findByRole("button", { name: "Save chart" }));
    await screen.findByRole("link", { name: "Open saved chart" });
    expect(keys[1]).not.toBe(keys[0]);
  });

  it("reuses the idempotency key after a lost response and preserves the inspected selection", async () => {
    const bodies: string[] = [], keys: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/csrf") return json({ token: "synthetic-csrf" });
      bodies.push(String(options.body)); keys.push(new Headers(options.headers).get("idempotency-key")!);
      if (bodies.length === 1) throw new Error("Lost response after commit");
      return json(saved, 201);
    }));
    const user = userEvent.setup();
    render(<SaveChartButton input={input} />);
    await user.click(screen.getByRole("button", { name: "Save chart" }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Save chart" }));
    expect(await screen.findByRole("link", { name: "Open saved chart" })).toHaveAttribute("href", `/workspace/saved-charts/${id}`);
    expect(keys[0]).toBe(keys[1]); expect(JSON.parse(bodies[0])).toEqual(input);
  });

  it("loads owned charts, renames and confirms removal with an accessible empty state", async () => {
    let items = [saved];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return json({ subject: "synthetic-alice" });
      if (url === "/api/auth/csrf") return json({ token: "synthetic-csrf" });
      if (options.method === "PATCH") { items = [{ ...saved, label: JSON.parse(String(options.body)).label }]; return json(items[0]); }
      if (options.method === "DELETE") { items = []; return json(null, 204); }
      return json({ items, next_cursor: null });
    }));
    const user = userEvent.setup();
    const { container } = render(<SavedCharts />);
    await screen.findByRole("link", { name: saved.label });
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
    await user.clear(screen.getByLabelText("Label")); await user.type(screen.getByLabelText("Label"), "Renamed");
    await user.click(screen.getByRole("button", { name: "Update label" }));
    await screen.findByRole("link", { name: "Renamed" });
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(items).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Confirm removal" }));
    await screen.findByText(/No saved charts match/);
    expect(items).toHaveLength(0);
  });

  it("discards an old owner's in-flight list immediately on account change", async () => {
    let release: (response: Response) => void = () => {};
    let count = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/session") return json({ subject: "synthetic-user" });
      if (++count === 1) return new Promise<Response>((resolve) => { release = resolve; });
      return json({ items: [], next_cursor: null });
    }));
    render(<SavedCharts />);
    await waitFor(() => expect(count).toBe(1));
    fireEvent(window, new Event(AUTH_CHANGE));
    await screen.findByText(/No saved charts match/);
    release(json({ items: [saved], next_cursor: null }));
    await waitFor(() => expect(screen.queryByText(saved.label)).not.toBeInTheDocument());
  });

  it("reopens a live saved context with the shared renderer and explicit change badge", async () => {
    const chartView = view(definition(), []);
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/session"
      ? json({ subject: "synthetic-alice" }) : json({ saved_chart: saved, view: chartView, dataset_changed: true })));
    render(<SavedChartDetail instanceId={id} />);
    await screen.findByText("Shared chart renderer");
    expect(screen.getByRole("status")).toHaveTextContent("Data changed");
    expect(screen.getByText(/latest approved dataset/)).toHaveTextContent(chartView.dataset.id);
  });

  it("freezes a live context from the saved detail and links to the snapshot list", async () => {
    const chartView = view(definition(), []);
    const frozen = {
      id: "77777777-7777-4777-8777-777777777777", chart_definition_version_id: chartView.definition.id,
      dataset_version_id: chartView.dataset.id, selection: saved.selection,
      calculation_context: { context_hash: "c".repeat(64), metric_definition_versions: [chartView.definition.id], renderer_version: "synthetic-renderer/1" },
      artifact_id: null, content_sha256: "d".repeat(64), created_at: "2026-11-06T12:00:00Z",
    };
    const bodies: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return json({ subject: "synthetic-alice" });
      if (url === "/api/auth/csrf") return json({ token: "synthetic-csrf" });
      if (url === "/api/snapshots") {
        bodies.push(String(options.body));
        return json(frozen, 201);
      }
      return json({ saved_chart: saved, view: chartView, dataset_changed: false });
    }));
    const user = userEvent.setup();
    render(<SavedChartDetail instanceId={id} />);
    await screen.findByText("Shared chart renderer");
    await user.click(screen.getByRole("button", { name: "Freeze snapshot" }));
    await screen.findByRole("status");
    expect(JSON.parse(bodies[0])).toEqual({ chart_definition_version_id: chartView.definition.id,
      dataset_version_id: chartView.dataset.id,
      selection: { start: saved.selection.start, end: saved.selection.end, frequency: "day", filters: saved.selection.filters } });
    expect(screen.getByRole("link", { name: "Open snapshots" })).toHaveAttribute("href", "/workspace/saved-charts/snapshots");
  });

  it("renders a snapshot context frozen with metadata and compare-to-live", async () => {
    const snapshotId = "77777777-7777-4777-8777-777777777777";
    const pinnedSaved = { ...saved, mode: "snapshot" as const, snapshot_id: snapshotId,
      last_resolved_dataset_version_id: datasetId };
    const snapshotRow = {
      id: snapshotId, chart_definition_version_id: saved.chart_definition_version_id,
      dataset_version_id: datasetId, selection: saved.selection,
      calculation_context: { context_hash: "c".repeat(64), metric_definition_versions: [saved.chart_definition_version_id], renderer_version: "synthetic-renderer/1" },
      artifact_id: null, content_sha256: "d".repeat(64), created_at: "2026-11-06T12:00:00Z",
    };
    const frozenView = view(definition(), [], { dataset: { ...view(definition(), []).dataset, id: datasetId } });
    const liveView = view(definition(), [], { dataset: { ...view(definition(), []).dataset, id: "88888888-8888-4888-8888-888888888888" } });
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return json({ subject: "synthetic-alice" });
      if (url === `/api/saved-charts/${id}`) return json({ saved_chart: pinnedSaved, view: frozenView, dataset_changed: false });
      if (url === `/api/snapshots/${snapshotId}`) return json({ snapshot: snapshotRow, view: frozenView });
      if (url === `/api/snapshots/${snapshotId}/compare-live`) {
        expect(new Headers(options.headers).get("x-csrf-token")).toBeNull();
        return json({ snapshot: snapshotRow, frozen_view: frozenView, live_view: liveView, dataset_changed: true });
      }
      throw new Error(`unexpected ${url}`);
    }));
    const user = userEvent.setup();
    render(<SavedChartDetail instanceId={id} />);
    await screen.findByText("Shared chart renderer");
    expect(screen.getByText(/Frozen snapshot view/)).toHaveTextContent(datasetId);
    expect(await screen.findByText(new RegExp("d".repeat(8)))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open snapshot" })).toHaveAttribute("href", `/workspace/saved-charts/snapshots/${snapshotId}`);
    expect(screen.queryByText("Data changed")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Compare to live" }));
    await screen.findByRole("heading", { name: "Compare to live" });
    expect(screen.getByText(/latest approved dataset differs/)).toBeInTheDocument();
    expect(screen.getAllByText(/Shared chart renderer/).length).toBeGreaterThanOrEqual(3);
  });
});
