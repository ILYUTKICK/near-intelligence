import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "jest-axe";
import { SaveChartButton } from "@/features/charts/saved/SaveChartButton";
import { SavedCharts } from "@/features/charts/saved/SavedCharts";
import { SavedChartDetail } from "@/features/charts/saved/SavedChartDetail";
import { AUTH_CHANGE } from "@/lib/auth/change";
import { definition, view } from "./renderer/fixtures";

vi.mock("@/features/charts/renderer/ChartView", () => ({ ChartView: () => <div>Shared chart renderer</div> }));
const id = "22222222-2222-4222-8222-222222222222";
const selection = { start: "2026-11-01", end: "2026-11-06", frequency: "day" as const, filters: { source: "SRC-LLAMA" } };
const saved = { id, label: "Synthetic saved chart", mode: "live" as const,
  chart_definition_version_id: id, selection, snapshot_id: null,
  last_resolved_dataset_version_id: id, created_at: "2026-11-06T12:00:00Z", updated_at: "2026-11-06T12:00:00Z" };
const input = { chart_definition_version_id: id, selection, dataset_version_id: id, mode: "live" as const };
function json(body: unknown, status = 200) { return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "content-type": "application/json" } }); }
afterEach(() => vi.unstubAllGlobals());

describe("Saved chart workflow", () => {
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
});
