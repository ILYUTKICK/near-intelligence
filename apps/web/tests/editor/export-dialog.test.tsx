/**
 * NI-058 Export dialog tests (synthetic fixtures, visibly labeled): the
 * create -> poll -> download lifecycle with typed failed/expired states,
 * the workbench trigger gating, honest owner denial and accessibility of
 * the key states. Ownership enforcement itself is server-side; these tests
 * assert the client never sends an owner identifier and renders every
 * terminal state honestly.
 */
import { axe } from "jest-axe";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as download from "@/features/editor/persistence/download";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExportDialog } from "@/features/editor/exports/export-dialog";
import { ResearchDocumentEditor } from "@/features/editor/workbench";
import type { CanonicalDocument } from "@/features/editor/canonical";

const DOC_ID = "22222222-2222-4222-8222-222222222222";
const VERSION_ID = "99999999-9999-4999-8999-999999999999";
const JOB_ID = "77777777-7777-4777-8777-777777777777";
const EXPORT_PATH = `/api/documents/${DOC_ID}/exports`;

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// ProseMirror needs Range geometry in jsdom (same as the other editor suites).
const rangeRects = Object.getOwnPropertyDescriptor(Range.prototype, "getClientRects");
const rangeRect = Object.getOwnPropertyDescriptor(Range.prototype, "getBoundingClientRect");
beforeEach(() => {
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [new DOMRect(0, 0, 1, 1)] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect(0, 0, 1, 1) });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:fixture") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  if (rangeRects) Object.defineProperty(Range.prototype, "getClientRects", rangeRects);
  else Reflect.deleteProperty(Range.prototype, "getClientRects");
  if (rangeRect) Object.defineProperty(Range.prototype, "getBoundingClientRect", rangeRect);
  else Reflect.deleteProperty(Range.prototype, "getBoundingClientRect");
});

interface Route {
  match: (method: string, path: string) => boolean;
  respond: (init: RequestInit) => Response | Promise<Response>;
}

function mockFetch(routes: Route[]) {
  const calls: Array<{ method: string; path: string; init: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const isRequest = input instanceof Request;
    const url = new URL(isRequest ? input.url : String(input), window.location.origin);
    const method = (init.method ?? (isRequest ? input.method : "GET")).toUpperCase();
    // Real fetch applies init.headers OVER a Request's own headers
    // (privateFetch relies on that to add the CSRF token); the stub merges
    // the same way.
    const headers = new Headers(isRequest ? input.headers : undefined);
    for (const [name, value] of new Headers(init.headers ?? undefined).entries()) {
      headers.set(name, value);
    }
    const body = init.body ?? (isRequest && input.body ? await input.clone().text() : undefined);
    const requestInit: RequestInit = { method, headers, body };
    calls.push({ method, path: url.pathname, init: requestInit });
    for (const route of routes) {
      if (route.match(method, url.pathname)) {
        return await route.respond(requestInit);
      }
    }
    throw new Error(`Unexpected fixture request ${method} ${url.pathname}`);
  }));
  return calls;
}

function jobBody(status: string, extra: Record<string, unknown> = {}) {
  return {
    id: JOB_ID,
    document_id: DOC_ID,
    document_version_id: VERSION_ID,
    format: "markdown_zip",
    status,
    error_code: null,
    download_path: status === "succeeded" ? `${EXPORT_PATH}/${JOB_ID}/download` : null,
    expires_at: "2026-11-10T12:00:00Z",
    ...extra,
  };
}

const CSRF_ROUTE: Route = {
  // privateFetch checks the session CSRF token with a plain GET first.
  match: (_method, path) => path === "/api/auth/csrf",
  respond: () => Response.json({ token: "csrf-fixture" }),
};

const BUNDLE_ZIP = new Blob([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], { type: "application/zip" });

async function expectAccessible(dialog: HTMLElement) {
  const results = await axe(dialog);
  expect(results).toHaveNoViolations();
}

describe("ExportDialog lifecycle", () => {
  it("creates the job, polls and downloads the bundle exactly once", async () => {
    const calls = mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "POST" && p === EXPORT_PATH,
        respond: () => Response.json(jobBody("queued"), { status: 202 }) },
      { match: (m, p) => m === "GET" && p === `${EXPORT_PATH}/${JOB_ID}`,
        respond: () => Response.json(jobBody("succeeded")) },
      { match: (m, p) => m === "GET" && p === `${EXPORT_PATH}/${JOB_ID}/download`,
        respond: () => new Response(BUNDLE_ZIP, { headers: { "content-type": "application/zip" } }) },
    ]);
    const downloadSpy = vi.spyOn(download, "downloadBlob").mockImplementation(() => {});
    render(<ExportDialog open onOpenChange={() => {}} documentId={DOC_ID} versionId={VERSION_ID} />);

    // The dialog first asks for the format (default Markdown ZIP) and never
    // starts without the explicit choice.
    expect(screen.getByTestId("export-choosing")).toBeInTheDocument();
    expect(screen.queryByTestId("export-starting")).not.toBeInTheDocument();
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
    const markdownRadio = screen.getByTestId("export-format-markdown") as HTMLInputElement;
    expect(markdownRadio.checked).toBe(true);
    await userEvent.click(screen.getByTestId("export-start"));

    // First bounded poll after the interval; the finished job downloads
    // through the shared blob helper with a server-controlled filename.
    expect(await screen.findByTestId("export-ready", {}, { timeout: 4000 })).toBeInTheDocument();
    const create = calls.find((call) => call.method === "POST" && call.path === EXPORT_PATH);
    expect(create).toBeDefined();
    expect(JSON.parse(String(create?.init.body))).toEqual({
      document_version_id: VERSION_ID,
      format: "markdown_zip",
    });
    // A client Idempotency-Key rides the create (replay-safe), never an
    // owner identifier.
    const sent = new Headers(create?.init.headers);
    expect(sent.get("idempotency-key")).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    expect(sent.get("x-csrf-token")).toBe("csrf-fixture");
    expect(sent.get("authorization")).toBeNull();
    expect(downloadSpy).toHaveBeenCalledTimes(1);
    expect(downloadSpy.mock.calls[0]?.[1]).toBe(`near-export-${JOB_ID}.zip`);
    expect(calls.some((call) => call.method === "GET"
      && call.path === `${EXPORT_PATH}/${JOB_ID}`)).toBe(true);
    await expectAccessible(screen.getByRole("dialog"));
  });

  it("exports as PDF when chosen: the create carries format pdf and the download uses .pdf", async () => {
    const calls = mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "POST" && p === EXPORT_PATH,
        respond: () => Response.json(jobBody("queued", { format: "pdf" }), { status: 202 }) },
      { match: (m, p) => m === "GET" && p === `${EXPORT_PATH}/${JOB_ID}`,
        respond: () => Response.json(jobBody("succeeded", { format: "pdf" })) },
      { match: (m, p) => m === "GET" && p === `${EXPORT_PATH}/${JOB_ID}/download`,
        respond: () => new Response(new Blob([new Uint8Array([0x25, 0x50, 0x44, 0x46])],
          { type: "application/pdf" }), { headers: { "content-type": "application/pdf" } }) },
    ]);
    const downloadSpy = vi.spyOn(download, "downloadBlob").mockImplementation(() => {});
    render(<ExportDialog open onOpenChange={() => {}} documentId={DOC_ID} versionId={VERSION_ID} />);
    await userEvent.click(screen.getByTestId("export-format-pdf"));
    await userEvent.click(screen.getByTestId("export-start"));

    expect(await screen.findByTestId("export-ready", {}, { timeout: 4000 })).toBeInTheDocument();
    const create = calls.find((call) => call.method === "POST" && call.path === EXPORT_PATH);
    expect(JSON.parse(String(create?.init.body))).toEqual({
      document_version_id: VERSION_ID,
      format: "pdf",
    });
    expect(downloadSpy).toHaveBeenCalledTimes(1);
    expect(downloadSpy.mock.calls[0]?.[1]).toBe(`near-export-${JOB_ID}.pdf`);
    // The ready copy is format-honest (the PDF report, not the ZIP contents).
    expect(screen.getByTestId("export-ready")).toHaveTextContent(/PDF report was downloaded/);
    expect(screen.getByTestId("export-ready")).toHaveTextContent(/no live data/i);
  });

  it("keeps the chosen format across a retry and resets it on a fresh dialog session", async () => {
    const calls = mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "POST" && p === EXPORT_PATH,
        respond: () => Response.json(jobBody("failed", { format: "pdf",
          error_code: "chart_render_failed" }), { status: 202 }) },
    ]);
    const onOpenChange = vi.fn();
    const { rerender } = render(
      <ExportDialog open onOpenChange={onOpenChange} documentId={DOC_ID} versionId={VERSION_ID} />);
    await userEvent.click(screen.getByTestId("export-format-pdf"));
    await userEvent.click(screen.getByTestId("export-start"));
    await screen.findByTestId("export-failed", {}, { timeout: 4000 });

    // Retry keeps the per-session format choice (a NEW job, same format).
    await userEvent.click(screen.getByTestId("export-retry"));
    await waitFor(() => {
      const creates = calls.filter((call) => call.method === "POST" && call.path === EXPORT_PATH);
      expect(creates).toHaveLength(2);
    });
    const creates = calls.filter((call) => call.method === "POST" && call.path === EXPORT_PATH);
    for (const create of creates) {
      expect(JSON.parse(String(create.init.body)).format).toBe("pdf");
    }
    const keys = creates.map((call) => new Headers(call.init.headers).get("idempotency-key"));
    expect(keys[0]).toBeTruthy();
    expect(keys[0]).not.toBe(keys[1]);

    // Closing and reopening starts a fresh dialog session: the choice is
    // reset to the Markdown ZIP default (never persisted globally).
    await userEvent.click(screen.getByTestId("export-close"));
    expect(onOpenChange).toHaveBeenLastCalledWith(false);
    rerender(<ExportDialog open={false} onOpenChange={onOpenChange} documentId={DOC_ID} versionId={VERSION_ID} />);
    rerender(<ExportDialog open onOpenChange={onOpenChange} documentId={DOC_ID} versionId={VERSION_ID} />);
    const radio = await screen.findByTestId("export-format-markdown") as HTMLInputElement;
    expect(radio.checked).toBe(true);
    expect(screen.getByTestId("export-format-pdf")).not.toBeChecked();
  });

  it("resumes the same PDF request after an interrupted response and ignores a download after closing", async () => {
    let posts = 0;
    let finishDownload!: (response: Response) => void;
    const pendingDownload = new Promise<Response>(resolve => { finishDownload = resolve; });
    const downloadBlob = vi.spyOn(download, "downloadBlob").mockImplementation(() => {});
    const calls = mockFetch([
      CSRF_ROUTE,
      { match: (method, path) => method === "POST" && path === EXPORT_PATH,
        respond: () => ++posts === 1 ? new Response(null, { status: 503 })
          : Response.json(jobBody("succeeded", { format: "pdf" }), { status: 202 }) },
      { match: (method, path) => method === "GET" && path === `${EXPORT_PATH}/${JOB_ID}/download`,
        respond: () => pendingDownload },
    ]);
    const { unmount } = render(<ExportDialog open onOpenChange={() => {}} documentId={DOC_ID} versionId={VERSION_ID} />);
    await userEvent.click(screen.getByTestId("export-format-pdf"));
    await userEvent.click(screen.getByTestId("export-start"));
    await screen.findByTestId("export-error");
    await userEvent.click(screen.getByTestId("export-error-retry"));
    await waitFor(() => expect(calls.some(call => call.path.endsWith("/download"))).toBe(true));
    const requests = calls.filter(call => call.method === "POST");
    expect(requests).toHaveLength(2);
    expect(JSON.parse(String(requests[0].init.body))).toEqual({ document_version_id: VERSION_ID, format: "pdf" });
    expect(requests[1].init.body).toBe(requests[0].init.body);
    const key = new Headers(requests[0].init.headers).get("idempotency-key");
    expect(key).toBeTruthy();
    expect(new Headers(requests[1].init.headers).get("idempotency-key")).toBe(key);
    unmount();
    await act(async () => finishDownload(new Response("%PDF-1.4\n", { headers: { "content-type": "application/pdf" } })));
    expect(downloadBlob).not.toHaveBeenCalled();
  });

  it("shows the typed failed state and allows returning to the format choice", async () => {
    mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "POST" && p === EXPORT_PATH,
        respond: () => Response.json(jobBody("queued"), { status: 202 }) },
      { match: (m, p) => m === "GET" && p === `${EXPORT_PATH}/${JOB_ID}`,
        respond: () => Response.json(jobBody("failed", { error_code: "chart_render_failed" })) },
    ]);
    render(<ExportDialog open onOpenChange={() => {}} documentId={DOC_ID} versionId={VERSION_ID} />);
    await userEvent.click(screen.getByTestId("export-start"));
    const alert = await screen.findByTestId("export-failed", {}, { timeout: 4000 });
    expect(alert).toHaveTextContent(/failed on the server/);
    expect(alert).toHaveTextContent("chart_render_failed");
    expect(screen.queryByTestId("export-ready")).not.toBeInTheDocument();

    // The format choice is reachable again without closing the dialog.
    await userEvent.click(screen.getByTestId("export-failed-back"));
    expect(screen.getByTestId("export-choosing")).toBeInTheDocument();
    await expectAccessible(screen.getByRole("dialog"));
  });

  it("shows the honest expired state for a replayed expired job", async () => {
    mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "POST" && p === EXPORT_PATH,
        respond: () => Response.json(jobBody("expired"), { status: 202 }) },
    ]);
    render(<ExportDialog open onOpenChange={() => {}} documentId={DOC_ID} versionId={VERSION_ID} />);
    await userEvent.click(screen.getByTestId("export-start"));
    expect(await screen.findByTestId("export-expired")).toHaveTextContent(/has expired/);
  });

  it("surfaces the typed 410 when the bundle expires before the download", async () => {
    mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "POST" && p === EXPORT_PATH,
        respond: () => Response.json(jobBody("succeeded"), { status: 202 }) },
      {
        match: (m, p) => m === "GET" && p === `${EXPORT_PATH}/${JOB_ID}/download`,
        respond: () => Response.json(
          { error: { code: "EXPORT_EXPIRED", message: "The export artifact has expired",
                     request_id: "fixture", retryable: false } },
          { status: 410 }),
      },
    ]);
    render(<ExportDialog open onOpenChange={() => {}} documentId={DOC_ID} versionId={VERSION_ID} />);
    await userEvent.click(screen.getByTestId("export-start"));
    expect(await screen.findByTestId("export-expired")).toBeInTheDocument();
  });

  it("answers a foreign-document export with the honest denial text", async () => {
    mockFetch([
      CSRF_ROUTE,
      {
        match: (m, p) => m === "POST" && p === EXPORT_PATH,
        respond: () => Response.json(
          { error: { code: "NOT_FOUND", message: "Resource was not found",
                     request_id: "fixture", retryable: false } },
          { status: 404 }),
      },
    ]);
    render(<ExportDialog open onOpenChange={() => {}} documentId={DOC_ID} versionId={VERSION_ID} />);
    await userEvent.click(screen.getByTestId("export-start"));
    const alert = await screen.findByTestId("export-error");
    expect(alert).toHaveTextContent(/does not exist for your account/);
    await expectAccessible(screen.getByRole("dialog"));
  });

  it("maps the stale-revision 409 to the specific REVISION_NOT_ACKNOWLEDGED copy (NI-063 finding)", async () => {
    // NI-063 recorded: exporting right after in-session saves targets the
    // stale acknowledged revision and the API refuses with typed 409. The
    // regression pins that the dialog maps that code to the specific
    // guidance (never the generic transport fallback).
    mockFetch([
      CSRF_ROUTE,
      {
        match: (m, p) => m === "POST" && p === EXPORT_PATH,
        respond: () => Response.json(
          { error: { code: "REVISION_NOT_ACKNOWLEDGED", message: "The acknowledged revision is stale",
                     request_id: "fixture", retryable: false } },
          { status: 409 }),
      },
    ]);
    render(<ExportDialog open onOpenChange={() => {}} documentId={DOC_ID} versionId={VERSION_ID} />);
    await userEvent.click(screen.getByTestId("export-start"));
    const alert = await screen.findByTestId("export-error");
    expect(alert).toHaveTextContent(/no longer the document's current revision/);
    expect(alert).toHaveTextContent(/export the current revision/);
    await expectAccessible(screen.getByRole("dialog"));
  });
});

// --------------------------------------------------------------------------- //
// Workbench trigger
// --------------------------------------------------------------------------- //

const PLAIN_DOC: CanonicalDocument = {
  schema_version: 1,
  type: "doc",
  content: [
    {
      type: "heading",
      attrs: { block_id: "11111111-1111-4111-8111-111111111111", level: 1 },
      content: [{ type: "text", text: "Notes (fixture)" }],
    },
  ],
};

function documentResponse(content: unknown, overrides: Record<string, unknown> = {}) {
  return {
    id: DOC_ID,
    title: "Editor workbench fixture",
    revision: 7,
    schema_version: 1,
    current_version_id: VERSION_ID,
    created_at: "2026-11-01T09:00:00Z",
    updated_at: "2026-11-08T00:00:00Z",
    progress: { headings: 1, charts: 0, insights: 0 },
    content,
    resolved_contexts: {},
    ...overrides,
  };
}

describe("Export trigger in the workbench", () => {
  it("is disabled without an acknowledged revision", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(input instanceof Request ? input.url : String(input), window.location.origin);
      if (url.pathname === `/api/documents/${DOC_ID}`) {
        return Response.json(documentResponse(PLAIN_DOC, { current_version_id: null }));
      }
      throw new Error(`Unexpected fixture request ${url.pathname}`);
    }));
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    const button = await screen.findByTestId("export-open");
    expect(button).toBeDisabled();
  });

  it("opens the export dialog from the header and closes while processing", async () => {
    const calls = mockFetch([
      { match: (method, path) => path === `/api/documents/${DOC_ID}`,
        respond: () => Response.json(documentResponse(PLAIN_DOC)) },
      CSRF_ROUTE,
      { match: (method, path) => method === "POST" && path === EXPORT_PATH,
        respond: () => Response.json(jobBody("queued"), { status: 202 }) },
      { match: (method, path) => method === "GET" && path === `${EXPORT_PATH}/${JOB_ID}`,
        respond: () => Response.json(jobBody("running")) },
    ]);
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    await screen.findByRole("textbox", { name: "Research paper editor" });
    await userEvent.click(screen.getByTestId("export-open"));
    const dialog = await screen.findByTestId("export-dialog");
    expect(dialog).toHaveAttribute("role", "dialog");
    // The dialog first asks for the format; starting it posts the default
    // Markdown ZIP choice.
    await userEvent.click(screen.getByTestId("export-start"));
    expect(await screen.findByTestId("export-processing")).toBeInTheDocument();
    const create = calls.find((call) => call.method === "POST" && call.path === EXPORT_PATH);
    expect(create).toBeDefined();
    // Closing is possible while processing; the queued job keeps running
    // server-side (the dialog says so).
    await userEvent.click(screen.getByTestId("export-close"));
    await waitFor(() => {
      expect(screen.queryByTestId("export-dialog")).not.toBeInTheDocument();
    });
  });
});
