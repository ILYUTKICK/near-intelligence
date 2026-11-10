/**
 * NI-062 workbench identity-guard coverage (the recorded NI-042 audit input:
 * "workbench.tsx retains loaded document/recovery content without
 * auth-change, focus or storage identity revalidation").
 *
 * Drives the REAL workbench against a stubbed same-origin fetch and proves
 * the identity boundary the persistence/session-owner guard enforces:
 *
 * - a verified cross-tab account switch (a DIFFERENT session subject) unmounts
 *   the editor, clears the local recovery draft and shows the honest
 *   session-changed boundary — Alice's content is never exposed to Bob;
 * - the same signal removes a stored sessionStorage draft before anything
 *   can restore it under the new principal;
 * - a verified session END (401) keeps the loaded content (the NI-040
 *   recovery contract: "sign in again, then retry the save") — the content
 *   still belongs to the SAME verified owner; the copy-as-new gate (covered
 *   in editor-save.test.tsx) plus the different-subject rule below close
 *   the exposure, and every submission path is dead while signed out;
 * - the same user re-verifying after re-authentication keeps the editor
 *   (the retry contract holds);
 * - an unverifiable session answer (outage/503) clears nothing — the guard
 *   never destroys work on a transport failure.
 *
 * All identities and documents are synthetic fixtures; ownership itself is
 * re-verified server-side on every request (NI-018/NI-019).
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AUTH_CHANGE, AUTH_CHANGE_STORAGE } from "@/lib/auth/change";
import { draftKey } from "@/features/editor/persistence/draft";
import { ResearchDocumentEditor } from "@/features/editor/workbench";
import type { CanonicalDocument } from "@/features/editor/canonical";

const routerPush = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush }),
}));

// ProseMirror scrolls a focused text selection. jsdom supplies no Range geometry.
const rangeRects = Object.getOwnPropertyDescriptor(Range.prototype, "getClientRects");
const rangeRect = Object.getOwnPropertyDescriptor(Range.prototype, "getBoundingClientRect");
beforeEach(() => {
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [new DOMRect(0, 0, 1, 1)] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect(0, 0, 1, 1) });
});
afterEach(() => {
  if (rangeRects) Object.defineProperty(Range.prototype, "getClientRects", rangeRects);
  else Reflect.deleteProperty(Range.prototype, "getClientRects");
  if (rangeRect) Object.defineProperty(Range.prototype, "getBoundingClientRect", rangeRect);
  else Reflect.deleteProperty(Range.prototype, "getBoundingClientRect");
});

const DOC_ID = "22222222-2222-4222-8222-222222222222";
const ALICE = "synthetic-alice-subject";
const BOB = "synthetic-bob-subject";

const DOC: CanonicalDocument = {
  schema_version: 1,
  type: "doc",
  content: [
    {
      type: "heading",
      attrs: { block_id: "11111111-1111-4111-8111-111111111111", level: 1 },
      content: [{ type: "text", text: "Guarded document (fixture)" }],
    },
  ],
};

function documentResponse(content: unknown) {
  return {
    id: DOC_ID,
    title: "Identity guard fixture",
    revision: 7,
    schema_version: 1,
    current_version_id: null,
    created_at: "2026-11-01T09:00:00Z",
    updated_at: "2026-11-08T00:00:00Z",
    progress: { headings: 1, charts: 0, insights: 0 },
    content,
    resolved_contexts: {},
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return Response.json(body, { status, headers: { "cache-control": "no-store" } });
}

/** Mutable session answer: tests flip it to simulate cross-tab identity moves. */
let sessionAnswer: Response | null = null;

function sessionReply(subject: string | null): void {
  sessionAnswer = subject === null
    ? jsonResponse({ error: "No valid session." }, 401)
    : jsonResponse({ status: "ok", subject, expiresAt: "2026-12-01T00:00:00Z" });
}

function mockApi() {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = input instanceof Request ? new URL(input.url).pathname : String(input);
    if (url === "/api/auth/session") {
      return Promise.resolve(sessionAnswer ?? jsonResponse({ error: "No valid session." }, 401));
    }
    if (url === `/api/documents/${DOC_ID}`) {
      return Promise.resolve(jsonResponse(documentResponse(DOC)));
    }
    return Promise.resolve(jsonResponse({ error: { code: "UNHANDLED", message: `No handler for ${url}`, request_id: "req-fixture", retryable: false, details: null } }, 500));
  }));
}

function storedDraft(): string {
  return JSON.stringify({
    baseRevision: 7,
    capturedAt: "2026-11-10T10:00:00.000Z",
    body: { schema_version: 1, content: DOC, observed_contexts: [] },
  });
}

async function renderEditor() {
  mockApi();
  render(<ResearchDocumentEditor documentId={DOC_ID} />);
  await screen.findByRole("textbox", { name: "Research paper editor" });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  sessionAnswer = null;
});

describe("verified identity changes clear the workbench", () => {
  it("unmounts the editor when a different subject verifies (account switch)", async () => {
    sessionReply(ALICE);
    await renderEditor();
    expect(screen.getByRole("heading", { name: "Identity guard fixture" })).toBeInTheDocument();

    // Bob signs in on another tab: the auth-change signal + verified session.
    sessionReply(BOB);
    window.dispatchEvent(new Event(AUTH_CHANGE));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent(/session has ended or changed/i);
    // Alice's content is gone from the DOM (not merely hidden).
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Identity guard fixture" })).toBeNull();
  });

  it("clears the stored recovery draft with the editor", async () => {
    sessionReply(ALICE);
    sessionStorage.setItem(draftKey(DOC_ID), storedDraft());
    await renderEditor();
    // The interrupted-session draft is offered (NI-040 recovery surface).
    expect(screen.getByTestId("draft-recovery")).toBeInTheDocument();

    sessionReply(BOB);
    window.dispatchEvent(new Event(AUTH_CHANGE));
    // The draft panel itself carries role="alert", so target the boundary
    // copy instead of any alert role.
    await screen.findByText(/session has ended or changed/i);
    expect(screen.queryByTestId("draft-recovery")).toBeNull();
    await waitFor(() => {
      expect(sessionStorage.getItem(draftKey(DOC_ID))).toBeNull();
    });
  });

  it("re-checks on the cross-tab storage signal without any same-tab event", async () => {
    sessionReply(ALICE);
    await renderEditor();
    sessionReply(BOB);
    // The login tab wrote the opaque storage signal; no AUTH_CHANGE event.
    window.dispatchEvent(new StorageEvent("storage", { key: AUTH_CHANGE_STORAGE }));
    await screen.findByRole("alert");
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});

describe("session end and re-authentication keep the same owner's content", () => {
  it("keeps the editor on a verified 401 and clears only when another principal verifies", async () => {
    sessionReply(ALICE);
    await renderEditor();
    // Session ended (logout/expiry): the honest answer is "no session".
    sessionReply(null);
    window.dispatchEvent(new Event(AUTH_CHANGE));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toBeInTheDocument();
    });
    // The loaded content stays (NI-040 recovery contract) — nobody new has
    // verified, and every submission path is dead while signed out.
    expect(screen.getByRole("textbox", { name: "Research paper editor" })).toBeInTheDocument();

    // Bob verifies: NOW the cross-principal rule clears everything.
    sessionReply(BOB);
    window.dispatchEvent(new Event(AUTH_CHANGE));
    await screen.findByRole("alert");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("keeps the editor when the same user re-verifies after re-authentication", async () => {
    sessionReply(ALICE);
    await renderEditor();
    sessionReply(null);
    window.dispatchEvent(new Event(AUTH_CHANGE));
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Research paper editor" })).toBeInTheDocument();
    });
    // Alice signs back in: the subject matches the owner again — no clear.
    sessionReply(ALICE);
    window.dispatchEvent(new Event(AUTH_CHANGE));
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Research paper editor" })).toBeInTheDocument();
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("never clears on an unverifiable answer (outage)", async () => {
    sessionReply(ALICE);
    await renderEditor();
    // Provider outage: the session endpoint answers 503 (cookie kept).
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse({ error: "Server configuration error." }, 503))));
    window.dispatchEvent(new Event(AUTH_CHANGE));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.getByRole("textbox", { name: "Research paper editor" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

// The copy-as-new identity gate needs the full 409 machinery (coordinator
// conflict state + dialog); it is driven through the REAL workbench this
// suite renders by tests/editor/editor-save.test.tsx ("refuses to carry the
// local content into another principal's new document"), which flips the
// verified subject at click time and asserts no document is created and the
// editor clears.
