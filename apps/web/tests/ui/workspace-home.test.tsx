/** NI-024: isolated synthetic fixtures; no production data or user identities. */
import { axe } from "jest-axe";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkspaceHome } from "@/features/workspace/home/WorkspaceHome";
import type { Home } from "@/features/workspace/home/api";
import { AUTH_CHANGE } from "@/lib/auth/change";
import { metric, observation, series } from "./renderer/fixtures";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
const DOC = "11111111-1111-4111-8111-111111111111";
const CHART = "22222222-2222-4222-8222-222222222222";
const summary = { id: DOC, title: "Synthetic current research (fixture)", revision: 3,
  schema_version: 1, current_version_id: CHART, created_at: "2026-11-01T00:00:00Z",
  updated_at: "2026-11-08T00:00:00Z", progress: { headings: 1, charts: 2, insights: 0 } };
function homeFixture(): Home {
  return { recent_documents: [], recent_charts: [], recent_insights: [], indicators: [], counts: { documents: 0 } };
}
function setup(home: Home, handler?: (url: string, init: RequestInit) => Response | Promise<Response> | undefined) {
  const requests: Array<{ url: string; init: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input); requests.push({ url, init });
    const handled = handler?.(url, init);
    if (handled) return Promise.resolve(handled);
    if (url === "/api/auth/session") return Promise.resolve(Response.json({ subject: "synthetic-alice" }));
    if (url === "/api/auth/csrf") return Promise.resolve(Response.json({ token: "synthetic-csrf" }));
    if (url === "/api/home") return Promise.resolve(Response.json(home));
    throw new Error(`Unexpected test request: ${url}`);
  }));
  return requests;
}
afterEach(() => { vi.unstubAllGlobals(); push.mockReset(); });

describe("Workspace Home", () => {
  it("shows accessible first-use sections, then creates and opens a real acknowledged document in one action", async () => {
    const user = userEvent.setup();
    const requests = setup(homeFixture(), (url, init) => url === "/api/documents" && init.method === "POST"
      ? Response.json({ ...summary, content: {}, resolved_contexts: {} }, { status: 201 }) : undefined);
    const { container } = render(<WorkspaceHome />);
    await screen.findByRole("heading", { name: "Your research starts here" });
    expect(screen.getByText(/No documents yet/)).toBeVisible();
    expect(screen.getByText(/No saved charts yet/)).toBeVisible();
    expect(screen.getByText(/No insight notes/)).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
    await user.tab(); expect(screen.getByRole("button", { name: "Create document" })).toHaveFocus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(push).toHaveBeenCalledWith(`/workspace/research/${DOC}`));
    const request = requests.find((value) => value.url === "/api/documents")!;
    expect(JSON.parse(String(request.init.body))).toEqual({ title: "Untitled research" });
    expect(request.init.headers).toMatchObject({ "x-csrf-token": "synthetic-csrf", "idempotency-key": expect.any(String) });
    expect(request.init.cache).toBe("no-store");
    expect(JSON.stringify(requests)).not.toMatch(/user_id|owner_id|Authorization/);
  });

  it("resumes newest research in one action and derives checklist solely from its persisted counters", async () => {
    const home = homeFixture(); home.recent_documents = [summary]; home.counts.documents = 1;
    setup(home); render(<WorkspaceHome />);
    const continuation = await screen.findByRole("link", { name: /Continue research/ });
    expect(continuation).toHaveAttribute("href", `/workspace/research/${DOC}`);
    const user = userEvent.setup();
    await user.tab(); expect(screen.getByRole("button", { name: "Create document" })).toHaveFocus();
    await user.tab(); expect(continuation).toHaveFocus();
    const checklist = screen.getByRole("region", { name: "Research checklist" });
    expect(within(checklist).getByText("Add a chart — Complete")).toBeVisible();
    expect(within(checklist).getByText("Record an insight — To do")).toBeVisible();
    expect(document.body.textContent).not.toMatch(/confidence|conviction|\d+%/i);
  });

  it("keeps documents and owner navigation when one indicator is unavailable; retains exact decimals and pinned explorer context", async () => {
    const home = homeFixture(); home.recent_documents = [summary]; home.counts.documents = 1;
    const value = "123456789012345678901234.123456789012345678901234";
    const data = series(metric("NEAR", "Synthetic purchased quantity", "synthetic-metric"), [observation("2026-11-01", value)], { start: "2026-11-01", end: "2026-11-02" });
    data.points[0].quality.status = "stale";
    home.indicators = [{ chart_id: "observed-conversions", chart_version: 2, title: "Synthetic purchases", status: "available", series: data, reason: null },
      { chart_id: "gross-fees", chart_version: 1, title: "Synthetic fees", status: "unavailable", series: null, reason: "Synthetic source outage" }];
    home.recent_charts = [{ id: CHART, label: "Synthetic saved chart", mode: "live", chart_definition_version_id: DOC,
      selection: { start: "2026-11-01", end: "2026-11-02", frequency: "day", filters: {} }, snapshot_id: null,
      last_resolved_dataset_version_id: null, created_at: summary.created_at, updated_at: summary.updated_at }];
    home.recent_insights = [{ insight_id: CHART, document_id: DOC, document_title: summary.title, block_id: CHART,
      type: "observation", classification: "uncertain", modified_at: summary.updated_at, excerpt: "Synthetic saved note" }];
    setup(home); const { container } = render(<WorkspaceHome />);
    await screen.findByText(value);
    expect(screen.getByRole("link", { name: summary.title })).toBeVisible();
    expect(screen.getByText(/Synthetic source outage/)).toBeVisible();
    expect(screen.getByText(/Stale data/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Synthetic saved chart" })).toHaveAttribute("href", `/workspace/saved-charts/${CHART}`);
    expect(screen.getByText("Synthetic saved note")).toBeVisible();
    const link = screen.getByRole("link", { name: "Explore Synthetic purchases" });
    expect(link.getAttribute("href")).toContain(`dataset_version=${data.dataset.id}`);
    expect(link.getAttribute("href")).toContain("version=2&start=2026-11-01&end=2026-11-02");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("distinguishes loading, request failure and retry without fabricating rows", async () => {
    let resolveHome!: (response: Response) => void;
    let attempts = 0;
    setup(homeFixture(), (url) => url === "/api/home" ? (++attempts === 1
      ? new Promise<Response>((resolve) => { resolveHome = resolve; }) : Response.json(homeFixture())) : undefined);
    render(<WorkspaceHome />);
    await screen.findByRole("status", { name: "Loading your recent research" });
    await act(async () => resolveHome(Response.json({}, { status: 503 })));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your research could not be loaded");
    expect(screen.queryByRole("heading", { name: "Recent documents" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByRole("heading", { name: "Your research starts here" });
  });

  it("hides old-account content immediately on auth change", async () => {
    const home = homeFixture(); home.recent_documents = [summary]; home.counts.documents = 1;
    let subject = "synthetic-alice";
    setup(home, (url) => url === "/api/auth/session" ? Response.json({ subject })
      : url === "/api/home" && subject === "synthetic-bob" ? Response.json(homeFixture()) : undefined);
    render(<WorkspaceHome />); await screen.findByRole("link", { name: summary.title });
    subject = "synthetic-bob";
    act(() => { window.dispatchEvent(new Event(AUTH_CHANGE)); });
    expect(screen.queryByText(summary.title)).not.toBeInTheDocument();
    await screen.findByRole("heading", { name: "Your research starts here" });
    expect(screen.queryByText(summary.title)).not.toBeInTheDocument();
  });

  it("retains one creation intent on an uncertain failure and retry", async () => {
    let calls = 0;
    const requests = setup(homeFixture(), (url) => url === "/api/documents" ? (++calls === 1
      ? Promise.reject(new TypeError("Synthetic lost acknowledgement"))
      : Response.json({ ...summary, content: {}, resolved_contexts: {} }, { status: 201 })) : undefined);
    render(<WorkspaceHome />); const create = await screen.findByRole("button", { name: "Create document" });
    await userEvent.click(create); await screen.findByRole("alert");
    await userEvent.click(create); await waitFor(() => expect(push).toHaveBeenCalled());
    const writes = requests.filter((request) => request.url === "/api/documents");
    expect(writes).toHaveLength(2);
    expect(new Headers(writes[0].init.headers).get("idempotency-key")).toBe(new Headers(writes[1].init.headers).get("idempotency-key"));
  });

  it.each(["synthetic-alice", "synthetic-bob"])("defers late creation during focus checks and only resumes for the same subject (%s)", async (nextSubject) => {
    let check = false;
    let resolveSession!: (response: Response) => void;
    let resolveCreate!: (response: Response) => void;
    setup(homeFixture(), (url) => url === "/api/auth/session" && check
      ? new Promise<Response>((resolve) => { resolveSession = resolve; })
      : url === "/api/documents" ? new Promise<Response>((resolve) => { resolveCreate = resolve; }) : undefined);
    render(<WorkspaceHome />);
    await userEvent.click(await screen.findByRole("button", { name: "Create document" }));
    await waitFor(() => expect(resolveCreate).toBeDefined());
    check = true;
    act(() => { window.dispatchEvent(new Event("focus")); });
    expect(screen.queryByRole("button", { name: "Create document" })).not.toBeInTheDocument();
    await act(async () => resolveCreate(Response.json({ ...summary, content: {}, resolved_contexts: {} }, { status: 201 })));
    expect(push).not.toHaveBeenCalled();
    await act(async () => resolveSession(Response.json({ subject: nextSubject })));
    if (nextSubject === "synthetic-alice") await waitFor(() => expect(push).toHaveBeenCalledWith(`/workspace/research/${DOC}`));
    else {
      await screen.findByRole("button", { name: "Create document" });
      expect(push).not.toHaveBeenCalled();
    }
  });

  it("uses a fresh intent after an acknowledged creation if Home remains mounted", async () => {
    let calls = 0;
    const requests = setup(homeFixture(), (url) => url === "/api/documents"
      ? Response.json({ ...summary, id: ++calls === 1 ? DOC : CHART, content: {}, resolved_contexts: {} }, { status: 201 }) : undefined);
    render(<WorkspaceHome />); const create = await screen.findByRole("button", { name: "Create document" });
    await userEvent.click(create); await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
    await userEvent.click(create); await waitFor(() => expect(push).toHaveBeenCalledTimes(2));
    const writes = requests.filter((request) => request.url === "/api/documents");
    expect(new Headers(writes[0].init.headers).get("idempotency-key")).not.toBe(new Headers(writes[1].init.headers).get("idempotency-key"));
  });

  it("does not navigate when focus and creation acknowledgement arrive before effect flushing", async () => {
    let checking = false;
    let resolveCreate!: (response: Response) => void;
    setup(homeFixture(), (url) => url === "/api/auth/session" && checking ? new Promise<Response>(() => {})
      : url === "/api/documents" ? new Promise<Response>((resolve) => { resolveCreate = resolve; }) : undefined);
    render(<WorkspaceHome />);
    await userEvent.click(await screen.findByRole("button", { name: "Create document" }));
    await waitFor(() => expect(resolveCreate).toBeDefined());
    checking = true;
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      resolveCreate(Response.json({ ...summary, content: {}, resolved_contexts: {} }, { status: 201 }));
    });
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByRole("status", { name: "Checking your workspace session" })).toBeVisible();
  });
});
