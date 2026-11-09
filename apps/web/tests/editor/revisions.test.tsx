/** Synthetic private revision and chart fixtures. */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { ResearchRevisions } from "@/features/editor/revisions";
import * as download from "@/features/editor/persistence/download";
import { AUTH_CHANGE } from "@/lib/auth/change";
import { definition, metric, observation, series, view } from "../ui/renderer/fixtures";

vi.mock("@/features/charts/renderer/chart-factory", () => ({
  defaultChartFactory: vi.fn(async () => ({ setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn() })),
}));

const documentId = "22222222-2222-4222-8222-222222222222";
const versionId = "33333333-3333-4333-8333-333333333333";
const blockId = "44444444-4444-4444-8444-444444444444";
const documentPath = `/api/documents/${documentId}/versions`;
const chartPath = `${documentPath}/${versionId}/chart-blocks/${blockId}`;
const exactValue = "12.000000000000000001";
const chart = view(definition(), [series(metric("USD", "Synthetic metric", "synthetic"), [observation("2026-11-01", exactValue)])]);
const summary = { id: versionId, document_id: documentId, revision: 2, schema_version: 1,
  created_at: "2026-11-08T12:00:00Z", content_sha256: "c".repeat(64) };
const revision = { ...summary, resolved_contexts: {}, content: { schema_version: 1, type: "doc", content: [
  { type: "paragraph", attrs: { block_id: "55555555-5555-4555-8555-555555555555" }, content: [{ type: "text", text: "Synthetic saved prose" }] },
  { type: "liveChart", attrs: { block_id: blockId, chart_definition_version_id: chart.definition.id, mode: "live",
    observed_dataset_version_id: chart.dataset.id, selection: chart.selection, snapshot_id: null } },
] } };

function fixtureRequests(csvRequest = async () => new Response(`value\n${exactValue}\n`, { headers: { "content-type": "text/csv" } })) {
  const state = { allowed: true, chartAvailable: true };
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(input instanceof Request ? input.url : String(input), window.location.origin);
    urls.push(url.pathname + url.search);
    if (url.pathname === "/api/auth/session") return Response.json({ subject: state.allowed ? "fixture-alice" : "fixture-bob" });
    if (!state.allowed) return Response.json({}, { status: 404 });
    if (url.pathname === documentPath) return Response.json({ items: [summary], next_cursor: "older-fixture" });
    if (url.pathname === `${documentPath}/${versionId}`) return Response.json(revision);
    if (url.pathname === `${chartPath}/csv`) return csvRequest();
    if (url.pathname === `${chartPath}/view`) return state.chartAvailable ? Response.json(chart) : Response.json({
      error: { code: "RECONSTRUCTION_ERROR", message: "Synthetic missing artifact", request_id: "fixture", retryable: false },
    }, { status: 409 });
    throw new Error(`Unexpected fixture request ${url.pathname}`);
  }));
  return { state, urls };
}

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("links owner-scoped revisions and pagination from the history screen", async () => {
  fixtureRequests();
  render(<ResearchRevisions documentId={documentId} />);
  const base = `/workspace/research/${documentId}/versions`;
  expect(await screen.findByRole("link", { name: "Revision 2" })).toHaveAttribute("href", `${base}?version=${versionId}`);
  expect(screen.getByRole("link", { name: "Older revisions" })).toHaveAttribute("href", `${base}?cursor=older-fixture`);
});

it("renders the saved paper read-only and downloads exact CSV through the same revision", async () => {
  const { urls } = fixtureRequests();
  const save = vi.spyOn(download, "downloadBlob").mockImplementation(() => {});
  render(<ResearchRevisions documentId={documentId} versionId={versionId} />);
  expect(await screen.findByText(exactValue)).toBeInTheDocument();
  expect(screen.getByText("Synthetic saved prose").closest(".editor-paper")).toHaveAttribute("contenteditable", "false");
  expect(screen.queryByRole("button", { name: /refresh|edit properties|save now/i })).toBeNull();
  await userEvent.setup().click(screen.getByRole("button", { name: "Download saved CSV" }));
  await waitFor(() => expect(save).toHaveBeenCalledOnce());
  const [blob, filename] = save.mock.calls[0];
  expect(await blob.text()).toBe(`value\n${exactValue}\n`);
  expect(filename).toContain(versionId);
  expect(urls).toEqual(["/api/auth/session", `${documentPath}/${versionId}`, `${chartPath}/view`, `${chartPath}/csv`]);
});

it("keeps prose on a reconstruction error and clears the revision on account change", async () => {
  const { state, urls } = fixtureRequests();
  state.chartAvailable = false;
  render(<ResearchRevisions documentId={documentId} versionId={versionId} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Chart reconstruction failed");
  expect(screen.getByText("Synthetic saved prose")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Download saved CSV" })).toBeNull();
  state.allowed = false;
  fireEvent(window, new Event(AUTH_CHANGE));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("could not be found for your account"));
  expect(screen.queryByText("Synthetic saved prose")).toBeNull();
  expect(urls.filter(url => url === `${chartPath}/view`)).toHaveLength(1);
});

it("suppresses an in-flight CSV download when the account changes before delivery", async () => {
  let respond: (response: Response) => void = () => {};
  const pending = new Promise<Response>(resolve => { respond = resolve; });
  const { state, urls } = fixtureRequests(() => pending);
  const save = vi.spyOn(download, "downloadBlob").mockImplementation(() => {});
  render(<ResearchRevisions documentId={documentId} versionId={versionId} />);
  await userEvent.setup().click(await screen.findByRole("button", { name: "Download saved CSV" }));
  expect(urls).toContain(`${chartPath}/csv`);
  await act(async () => {
    state.allowed = false;
    fireEvent(window, new Event(AUTH_CHANGE));
    respond(new Response(`value\n${exactValue}\n`, { headers: { "content-type": "text/csv" } }));
  });
  expect(save).not.toHaveBeenCalled();
});
