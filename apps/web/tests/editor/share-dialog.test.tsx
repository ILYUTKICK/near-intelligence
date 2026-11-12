/**
 * NI-060 Share dialog tests (synthetic fixtures, visibly labeled): the
 * preview -> consent -> link-shown-once flow, the honest revocation list,
 * stale-preview gating and accessibility of the key states. Ownership
 * enforcement itself is server-side; these tests assert the client sends the
 * consent payload naming the revision and visible scope, never re-shows a
 * token after the create and never sends an owner identifier.
 */
import { axe } from "jest-axe";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchDocumentEditor } from "@/features/editor/workbench";
import { ShareDialog } from "@/features/editor/shares/share-dialog";
import type { CanonicalDocument } from "@/features/editor/canonical";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const DOC_ID = "33333333-3333-4333-8333-333333333333";
const VERSION_ID = "99999999-9999-4999-8999-999999999999";
const SHARE_ID = "88888888-8888-4888-8888-888888888888";
const SHARES_PATH = `/api/documents/${DOC_ID}/shares`;
const TOKEN = "share-token-fixture_0123456789abcdefghij";

// ProseMirror needs Range geometry in jsdom (same as the other editor suites).
const rangeRects = Object.getOwnPropertyDescriptor(Range.prototype, "getClientRects");
const rangeRect = Object.getOwnPropertyDescriptor(Range.prototype, "getBoundingClientRect");
beforeEach(() => {
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [new DOMRect(0, 0, 1, 1)] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect(0, 0, 1, 1) });
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

const CSRF_ROUTE: Route = {
  match: (_method, path) => path === "/api/auth/csrf",
  respond: () => Response.json({ token: "csrf-fixture" }),
};

function previewBody(revision = 7) {
  return {
    document_id: DOC_ID,
    revision,
    projection: {
      share_projection_version: 1,
      document: {
        title: "Fixture shared research (synthetic)",
        revision,
        schema_version: 1,
        content_sha256: "a".repeat(64),
        created_at: "2026-11-01T09:00:00Z",
        limitations: "Frozen read-only publication of one research revision (fixture).",
      },
      blocks: [
        { block_type: "paragraph", block_id: "11111111-1111-4111-8111-111111111111",
          runs: [{ type: "text", text: "Fixture intro paragraph", marks: [] }] },
      ],
      sources: [{ source_id: "SRC-FIXTURE", name: "Fixture source (synthetic)" }],
      model_runs: [],
      citations: [],
    },
    projection_sha256: "b".repeat(64),
    scope: { kind: "frozen_revision_allowlist", chart_blocks: 0, data_table_blocks: 0,
      insight_blocks: 0, source_references: 1 },
  };
}

function createdBody(extra: Record<string, unknown> = {}) {
  return {
    id: SHARE_ID,
    document_id: DOC_ID,
    document_version_id: VERSION_ID,
    revision: 7,
    status: "active",
    created_at: "2026-11-12T12:00:00Z",
    expires_at: "2026-11-19T12:00:00Z",
    share_token: TOKEN,
    share_path: `/share/${TOKEN}`,
    ...extra,
  };
}

function summaryBody(status: string) {
  return {
    id: SHARE_ID, document_id: DOC_ID, document_version_id: VERSION_ID,
    revision: 7, status, created_at: "2026-11-12T12:00:00Z",
    expires_at: status === "revoked" ? null : "2026-11-19T12:00:00Z",
    revoked_at: status === "revoked" ? "2026-11-12T13:00:00Z" : null,
  };
}

const BASE_ROUTES = (shares: unknown[] = []): Route[] => [
  CSRF_ROUTE,
  { match: (m, p) => m === "GET" && p === `${SHARES_PATH}/preview`,
    respond: () => Response.json(previewBody()) },
  { match: (m, p) => m === "GET" && p === SHARES_PATH,
    respond: () => Response.json({ items: shares }) },
];

async function expectAccessible(dialog: HTMLElement) {
  const results = await axe(dialog);
  expect(results).toHaveNoViolations();
}

describe("ShareDialog consent flow", () => {
  it("previews the exact publication scope and creates only after explicit consent", async () => {
    let created = false;
    const calls = mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "GET" && p === `${SHARES_PATH}/preview`,
        respond: () => Response.json(previewBody()) },
      { match: (m, p) => m === "GET" && p === SHARES_PATH,
        respond: () => Response.json({ items: created ? [summaryBody("active")] : [] }) },
      { match: (m, p) => m === "POST" && p === SHARES_PATH,
        respond: () => { created = true; return Response.json(createdBody(), { status: 201 }); } },
    ]);
    render(<ShareDialog open onOpenChange={() => {}} documentId={DOC_ID} revision={7} />);

    // The preview names what is visible and what is not, before any consent.
    expect(await screen.findByTestId("share-preview-visible")).toHaveTextContent("Fixture shared research");
    expect(screen.getByTestId("share-preview-visible")).toHaveTextContent("revision 7");
    expect(screen.getByTestId("share-preview-hidden")).toHaveTextContent(/Your identity/);
    // The create control is disabled until the consent checkbox is ticked.
    expect(screen.getByTestId("share-create")).toBeDisabled();
    await userEvent.click(screen.getByTestId("share-consent"));
    await userEvent.click(screen.getByTestId("share-create"));

    const createdPanel = await screen.findByTestId("share-created");
    expect(createdPanel).toHaveTextContent(/only this once/);
    const link = screen.getByTestId("share-link") as HTMLInputElement;
    expect(link.value).toBe(`http://localhost:3000/share/${TOKEN}`);
    // The consent payload names the revision, the scope and the preview hash,
    // and rides a client Idempotency-Key; no owner identifier is sent.
    const post = calls.find((call) => call.method === "POST" && call.path === SHARES_PATH);
    expect(post).toBeDefined();
    expect(JSON.parse(String(post?.init.body))).toEqual({
      acknowledged_revision: 7,
      preview_sha256: "b".repeat(64),
      visible_scope: { kind: "frozen_revision_allowlist", chart_blocks: 0,
        data_table_blocks: 0, insight_blocks: 0, source_references: 1 },
      expires_at: expect.any(String),
    });
    expect(new Headers(post?.init.headers).get("idempotency-key")).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    expect(new Headers(post?.init.headers).get("authorization")).toBeNull();
    // The list refreshes with the created share (status Active, no token).
    expect(await screen.findByTestId("share-status")).toHaveTextContent("Active");
    expect(screen.getByTestId("share-list").textContent).not.toContain(TOKEN);
    await expectAccessible(screen.getByRole("dialog"));
  });

  it("shows the token exactly once: a reopened dialog never re-displays it", async () => {
    let created = false;
    const calls = mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "GET" && p === `${SHARES_PATH}/preview`,
        respond: () => Response.json(previewBody()) },
      { match: (m, p) => m === "GET" && p === SHARES_PATH,
        respond: () => Response.json({ items: created ? [summaryBody("active")] : [] }) },
      { match: (m, p) => m === "POST" && p === SHARES_PATH,
        respond: () => { created = true; return Response.json(createdBody(), { status: 201 }); } },
    ]);
    const onOpenChange = vi.fn();
    const { rerender } = render(<ShareDialog open onOpenChange={onOpenChange} documentId={DOC_ID} revision={7} />);
    await userEvent.click(await screen.findByTestId("share-consent"));
    await userEvent.click(screen.getByTestId("share-create"));
    expect(await screen.findByTestId("share-created")).toBeInTheDocument();

    // Close: the dialog unmounts its state; the consent never survives.
    await userEvent.click(screen.getByTestId("share-close"));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    rerender(<ShareDialog open={false} onOpenChange={onOpenChange} documentId={DOC_ID} revision={7} />);
    rerender(<ShareDialog open onOpenChange={onOpenChange} documentId={DOC_ID} revision={7} />);
    // The reopened dialog shows the list (the share exists) but NO token.
    expect(await screen.findByTestId("share-list")).toBeInTheDocument();
    expect(screen.queryByTestId("share-created")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(`http://localhost:3000/share/${TOKEN}`)).not.toBeInTheDocument();
    expect(screen.getByTestId("share-create")).toBeDisabled();
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(1);
  });

  it("copies the link to the clipboard with an honest failure fallback", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("permission denied"));
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    mockFetch([
      ...BASE_ROUTES(),
      { match: (m, p) => m === "POST" && p === SHARES_PATH,
        respond: () => Response.json(createdBody(), { status: 201 }) },
    ]);
    render(<ShareDialog open onOpenChange={() => {}} documentId={DOC_ID} revision={7} />);
    await userEvent.click(await screen.findByTestId("share-consent"));
    await userEvent.click(screen.getByTestId("share-create"));
    await screen.findByTestId("share-created");
    await userEvent.click(screen.getByTestId("share-copy"));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(`http://localhost:3000/share/${TOKEN}`));
    // Permission denied: the link STAYS visible for a manual copy.
    expect(screen.getByTestId("share-link")).toBeInTheDocument();
  });

  it("revokes with an explicit confirmation and shows the honest revoked state", async () => {
    let revoked = false;
    mockFetch([
      CSRF_ROUTE,
      { match: (m, p) => m === "GET" && p === `${SHARES_PATH}/preview`,
        respond: () => Response.json(previewBody()) },
      { match: (m, p) => m === "GET" && p === SHARES_PATH,
        respond: () => Response.json({ items: [summaryBody(revoked ? "revoked" : "active")] }) },
      { match: (m, p) => m === "DELETE" && p === `${SHARES_PATH}/${SHARE_ID}`,
        respond: () => { revoked = true; return new Response(null, { status: 204 }); } },
    ]);
    render(<ShareDialog open onOpenChange={() => {}} documentId={DOC_ID} revision={7} />);
    expect(await screen.findByTestId("share-status")).toHaveTextContent("Active");
    await userEvent.click(screen.getByTestId("share-revoke"));
    // The revoke needs the explicit confirm step.
    expect(screen.getByTestId("share-revoke-confirm")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("share-revoke-confirm"));
    expect(await screen.findByTestId("share-status")).toHaveTextContent("Revoked");
  });

  it("gates creation on a fresh preview when the editor moved ahead", async () => {
    // The dialog is told the editor holds revision 8; the preview is of 7.
    mockFetch(BASE_ROUTES());
    render(<ShareDialog open onOpenChange={() => {}} documentId={DOC_ID} revision={8} />);
    expect(await screen.findByTestId("share-preview-stale")).toHaveTextContent(/revision 8/);
    await userEvent.click(screen.getByTestId("share-consent"));
    expect(screen.getByTestId("share-create")).toBeDisabled();
  });

  it("maps the stale-preview 409 to the review-again guidance", async () => {
    mockFetch([
      ...BASE_ROUTES(),
      { match: (m, p) => m === "POST" && p === SHARES_PATH,
        respond: () => Response.json(
          { error: { code: "PREVIEW_MISMATCH", message: "The consented preview does not match",
                     request_id: "fixture", retryable: false } },
          { status: 409 }),
      },
    ]);
    render(<ShareDialog open onOpenChange={() => {}} documentId={DOC_ID} revision={7} />);
    await userEvent.click(await screen.findByTestId("share-consent"));
    await userEvent.click(screen.getByTestId("share-create"));
    const alert = await screen.findByTestId("share-error");
    expect(alert).toHaveTextContent(/changed since the preview/);
    expect(alert).toHaveTextContent(/Review the fresh preview/);
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
    id: DOC_ID, title: "Editor workbench fixture", revision: 7, schema_version: 1,
    current_version_id: VERSION_ID, created_at: "2026-11-01T09:00:00Z",
    updated_at: "2026-11-08T00:00:00Z",
    progress: { headings: 1, charts: 0, insights: 0 },
    content, resolved_contexts: {},
    ...overrides,
  };
}

describe("Share trigger in the workbench", () => {
  it("is disabled without an acknowledged revision", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(input instanceof Request ? input.url : String(input), window.location.origin);
      if (url.pathname === `/api/documents/${DOC_ID}`) {
        return Response.json(documentResponse(PLAIN_DOC, { current_version_id: null }));
      }
      throw new Error(`Unexpected fixture request ${url.pathname}`);
    }));
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    const button = await screen.findByTestId("share-open");
    expect(button).toBeDisabled();
  });

  it("opens the share dialog from the header of a clean editor", async () => {
    mockFetch([
      { match: (method, path) => method === "GET" && path === `/api/documents/${DOC_ID}`,
        respond: () => Response.json(documentResponse(PLAIN_DOC)) },
      ...BASE_ROUTES(),
    ]);
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    await screen.findByRole("textbox", { name: "Research paper editor" });
    await userEvent.click(screen.getByTestId("share-open"));
    expect(await screen.findByTestId("share-dialog")).toHaveAttribute("role", "dialog");
  });
});
