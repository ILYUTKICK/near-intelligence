/**
 * NI-040 editor save integration tests (synthetic fixtures, visibly labeled).
 * They drive the real workbench (owner-checked GET + Tiptap paper) against a
 * stubbed same-origin fetch and assert the acceptance criteria end to end:
 * the manual save contract (quoted If-Match, client Idempotency-Key, ETag/
 * revision update), autosave firing from real editor updates, truthful
 * statuses, the 409 recovery dialog (server state surfaced, explicit
 * overwrite/reload/download/new-copy — never a silent overwrite), the honest
 * offline queue (content retained, key-stable retry), typed errors keeping
 * content, the unload warning and the session draft recovery.
 *
 * Content changes are made through the REAL UI (the NI-039 insert menu):
 * jsdom cannot drive ProseMirror's text-input pipeline (no editing default
 * actions, no IME), while menu insertion dispatches genuine editor
 * transactions — exactly the signal the save scheduler consumes. The precise
 * 1s-idle/5s-max/coalescing semantics are covered by the coordinator unit
 * tests with injected timers (persistence-coordinator.test.ts).
 */
import { axe } from "jest-axe";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ResearchDocumentEditor } from "@/features/editor/workbench";
import type { CanonicalDocument } from "@/features/editor/canonical";

const routerPush = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush }),
}));

const DOC_ID = "22222222-2222-4222-8222-222222222222";
const NEW_DOC_ID = "99999999-9999-4999-8999-999999999999";
const VERSION_ID = "88888888-8888-4888-8888-888888888888";

/** The verified session subject the identity guard answers with (mutable). */
let sessionSubject = "synthetic-owner";

const DOC: CanonicalDocument = {
  schema_version: 1,
  type: "doc",
  content: [
    {
      type: "heading",
      attrs: { block_id: "11111111-1111-4111-8111-111111111111", level: 1 },
      content: [{ type: "text", text: "Notes (fixture)" }],
    },
    {
      type: "paragraph",
      attrs: { block_id: "66666666-6666-4666-8666-666666666666" },
      content: [{ type: "text", text: "First paragraph (fixture)" }],
    },
  ],
};

/** A server-side revision another session produced (the "second tab"). */
const SERVER_DOC_REV_9: CanonicalDocument = {
  schema_version: 1,
  type: "doc",
  content: [
    {
      type: "heading",
      attrs: { block_id: "11111111-1111-4111-8111-111111111111", level: 1 },
      content: [{ type: "text", text: "Notes (fixture)" }],
    },
    {
      type: "paragraph",
      attrs: { block_id: "66666666-6666-4666-8666-666666666666" },
      content: [{ type: "text", text: "Changed elsewhere (fixture)" }],
    },
  ],
};

interface CapturedRequest {
  method: string;
  url: string;
  headers: Record<string, string>;
  body: unknown;
}

type Handler = (request: CapturedRequest) => Response | Promise<Response> | undefined | null;

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return Response.json(body, { status, headers: { "cache-control": "no-store", ...headers } });
}

function errorResponse(
  status: number,
  code: string,
  message: string,
  details: Array<{ path: string; reason: string }> | null = null,
): Response {
  return jsonResponse({ error: { code, message, request_id: "req-fixture", retryable: false, details } }, status);
}

function documentResponse(content: unknown, overrides: Record<string, unknown> = {}) {
  return {
    id: DOC_ID,
    title: "Editor save fixture",
    revision: 7,
    schema_version: 1,
    current_version_id: null,
    created_at: "2026-11-01T09:00:00Z",
    updated_at: "2026-11-08T00:00:00Z",
    progress: { headings: 1, charts: 0, insights: 0 },
    content,
    resolved_contexts: {},
    ...overrides,
  };
}

function saveSuccess(revision: number): Response {
  return jsonResponse(
    {
      version: {
        id: VERSION_ID,
        document_id: DOC_ID,
        revision,
        schema_version: 1,
        content_sha256: "sha-fixture",
        created_at: "2026-11-08T10:00:00Z",
        content: DOC,
        resolved_contexts: {},
      },
      document: {
        id: DOC_ID,
        title: "Editor save fixture",
        revision,
        schema_version: 1,
        current_version_id: VERSION_ID,
        created_at: "2026-11-01T09:00:00Z",
        updated_at: "2026-11-08T10:00:00Z",
        progress: { headings: 1, charts: 0, insights: 0 },
      },
    },
    201,
    { etag: `"${revision}"` },
  );
}

function mockApi(handlers: Handler[]): CapturedRequest[] {
  const requests: CapturedRequest[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    if (String(input) === "/api/auth/csrf") return Promise.resolve(new Response(JSON.stringify({ token: "synthetic-csrf" }), { headers: { "content-type": "application/json" } }));
    // NI-062: the workbench identity guard verifies the session on mount.
    // Early-return (uncaptured) so request-count assertions stay about the
    // document API; the mutable subject lets the cross-principal test flip
    // the verified answer between actions.
    if (String(input) === "/api/auth/session") return Promise.resolve(Response.json({ status: "ok", subject: sessionSubject, expiresAt: "2026-12-01T00:00:00Z" }, { headers: { "cache-control": "no-store" } }));
    const headers = (init.headers ?? {}) as Record<string, string>;
    let body: unknown = null;
    if (typeof init.body === "string") {
      try {
        body = JSON.parse(init.body);
      } catch {
        body = init.body;
      }
    }
    const request: CapturedRequest = { method: init.method ?? "GET", url: String(input), headers, body };
    requests.push(request);
    for (const handler of handlers) {
      const response = handler(request);
      if (response) {
        return Promise.resolve(response);
      }
    }
    return Promise.resolve(errorResponse(500, "UNHANDLED", `No handler for ${String(input)}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return requests;
}

afterEach(() => {
  vi.unstubAllGlobals();
  // The recovery draft lives in sessionStorage; tests must not leak one.
  sessionStorage.clear();
  vi.restoreAllMocks();
  sessionSubject = "synthetic-owner";
});

async function renderReady(handlers: Handler[]): Promise<CapturedRequest[]> {
  const requests = mockApi([
    ...handlers,
    // Default owner-checked GET (NI-023 client) for the fixture document —
    // custom handlers may override it by coming first.
    (r) =>
      r.method === "GET" && r.url === `/api/documents/${DOC_ID}` ? jsonResponse(documentResponse(DOC)) : undefined,
  ]);
  render(<ResearchDocumentEditor documentId={DOC_ID} />);
  await screen.findByRole("textbox", { name: "Research paper editor" });
  return requests;
}

const saves = (requests: CapturedRequest[]) => requests.filter((r) => r.url.endsWith("/versions"));

/**
 * Makes a REAL editor content change through the NI-039 insert menu. The
 * status check is optional: during an in-flight save ("Saving…") or a typed
 * auth error the coordinator keeps that status — coalescing the edit is the
 * honest behavior, not an immediate dirty flip.
 */
async function insertDivider(expectDirty = true): Promise<void> {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Insert block" }));
  const menu = await screen.findByRole("menu", { name: "Insert block" });
  await user.click(within(menu).getByRole("menuitem", { name: /Divider/ }));
  await waitFor(() => {
    expect(screen.queryByRole("menu", { name: "Insert block" })).not.toBeInTheDocument();
  });
  await waitFor(() => {
    expect(screen.getByTestId("editor-announcement")).toHaveTextContent(/inserted/i);
  });
  if (expectDirty) {
    // The transaction marked the document unsaved — the status is truthful.
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/Unsaved changes/);
    });
  }
}

describe("manual save", () => {
  it("posts the canonical document with quoted If-Match and an Idempotency-Key, then updates the revision", async () => {
    const requests = await renderReady([(r) => (r.method === "POST" && r.url.endsWith("/versions") ? saveSuccess(8) : undefined)]);
    await insertDivider();

    await userEvent.click(screen.getByTestId("save-now"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved at 10:00:00 UTC · Revision 8/);
    });

    const save = saves(requests)[0];
    expect(save).toBeDefined();
    expect(save.method).toBe("POST");
    expect(save.url).toBe(`/api/documents/${DOC_ID}/versions`);
    // Exactly the quoted current revision (bare numbers would be a 428).
    expect(save.headers["if-match"]).toBe('"7"');
    // Client-generated UUID key (retry-safe per the API contract).
    expect(save.headers["idempotency-key"]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    const body = save.body as { schema_version: number; content: CanonicalDocument; observed_contexts: unknown[] };
    expect(body.schema_version).toBe(1);
    expect(body.observed_contexts).toEqual([]);
    expect(JSON.stringify(body.content)).toContain('"divider"');
    // The header reflects the acknowledged revision; the Save control rests.
    expect(screen.getByText(/· Revision 8 · Schema version 1/)).toBeInTheDocument();
    expect(screen.getByTestId("save-now")).toBeDisabled();
  });

  it("claims Mod+S for the document save", async () => {
    const requests = await renderReady([(r) => (r.method === "POST" && r.url.endsWith("/versions") ? saveSuccess(8) : undefined)]);
    await insertDivider();
    const event = new KeyboardEvent("keydown", { key: "s", metaKey: true, cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    await waitFor(() => {
      expect(saves(requests)).toHaveLength(1);
    });
  });
});

describe("autosave", () => {
  it("fires from a real editor update without any user action", async () => {
    const requests = await renderReady([(r) => (r.method === "POST" && r.url.endsWith("/versions") ? saveSuccess(8) : undefined)]);
    await insertDivider();
    // The 1s-idle schedule is asserted precisely in the coordinator unit
    // tests; here the wiring must deliver the request on its own.
    await waitFor(
      () => {
        expect(saves(requests)).toHaveLength(1);
      },
      { timeout: 3000 },
    );
    expect(saves(requests)[0].headers["if-match"]).toBe('"7"');
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved at 10:00:00 UTC · Revision 8/);
    });
  });

  it("changes made while a save runs stay dirty and save afterwards", async () => {
    const released: Array<(response: Response) => void> = [];
    const requests = await renderReady([
      (r) => {
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          return new Promise<Response>((resolve) => {
            released.push(resolve);
          });
        }
        return undefined;
      },
    ]);
    await insertDivider();
    // The debounced autosave is in flight.
    await waitFor(
      () => {
        expect(saves(requests)).toHaveLength(1);
      },
      { timeout: 3000 },
    );
    // The user keeps editing while the request runs — coalesced, so the
    // truthful status stays "Saving…".
    await insertDivider(false);
    released[0]?.(saveSuccess(8));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/Unsaved changes/);
    });
    // The coalesced follow-up carries the newer content with a fresh key.
    await waitFor(
      () => {
        expect(saves(requests)).toHaveLength(2);
      },
      { timeout: 3000 },
    );
    expect(saves(requests)[1].headers["if-match"]).toBe('"8"');
    expect(saves(requests)[1].headers["idempotency-key"]).not.toBe(saves(requests)[0].headers["idempotency-key"]);
    expect(saves(requests)[1].body).toBeDefined();
    released[1]?.(saveSuccess(9));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved at 10:00:00 UTC · Revision 9/);
    });
  });
});

describe("409 conflict recovery (no silent last-write-wins)", () => {
  async function conflicted(): Promise<CapturedRequest[]> {
    const requests = await renderReady([
      (r) => {
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          return errorResponse(409, "REVISION_CONFLICT", "Document revision moved", [
            { path: "If-Match", reason: "current_revision:9" },
          ]);
        }
        return undefined;
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    await waitFor(() => {
      expect(saves(requests)).toHaveLength(1);
    });
    return requests;
  }

  it("surfaces the server state and offers explicit options without overwriting", async () => {
    const requests = await conflicted();
    const dialog = screen.getByTestId("conflict-dialog");
    expect(within(dialog).getByText(/changed in another session/i)).toBeInTheDocument();
    // The typed 409 detail is the server truth shown to the user.
    expect(within(dialog).getByText(/revision 9/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Your editor holds revision 7/)).toBeInTheDocument();
    // No silent retry/overwrite: autosave stays stopped.
    await new Promise((resolve) => setTimeout(resolve, 1300));
    expect(saves(requests)).toHaveLength(1);
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("overwrites only after the explicit confirmation, CAS against the reported revision", async () => {
    const requests = await renderReady([
      (r) => {
        if (r.method !== "POST" || !r.url.endsWith("/versions")) {
          return undefined;
        }
        if (r.headers["if-match"] === '"7"') {
          return errorResponse(409, "REVISION_CONFLICT", "Document revision moved", [
            { path: "If-Match", reason: "current_revision:9" },
          ]);
        }
        return saveSuccess(10);
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    await screen.findByTestId("conflict-dialog");
    // The explicit dialog button is the only path to an overwrite.
    await userEvent.click(within(screen.getByTestId("conflict-dialog")).getByTestId("conflict-overwrite"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved at 10:00:00 UTC · Revision 10/);
    });
    expect(saves(requests)).toHaveLength(2);
    expect(saves(requests)[1].headers["if-match"]).toBe('"9"');
    expect(saves(requests)[1].headers["idempotency-key"]).not.toBe(saves(requests)[0].headers["idempotency-key"]);
    expect(screen.queryByTestId("conflict-dialog")).not.toBeInTheDocument();
  });

  it("reloads the server version only on request and adopts it as the clean state", async () => {
    const requests = await renderReady([
      (r) => {
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          return errorResponse(409, "REVISION_CONFLICT", "Document revision moved", [
            { path: "If-Match", reason: "current_revision:9" },
          ]);
        }
        if (r.method === "GET" && r.url === `/api/documents/${DOC_ID}`) {
          return jsonResponse(documentResponse(SERVER_DOC_REV_9, { revision: 9 }));
        }
        return undefined;
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    const dialog = await screen.findByTestId("conflict-dialog");
    await userEvent.click(within(dialog).getByTestId("conflict-reload"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/No unsaved changes · Revision 9/);
    });
    // The editor now renders the SERVER content; local edits were discarded
    // exactly as the button said.
    expect(screen.getByRole("textbox", { name: "Research paper editor" })).toHaveTextContent(
      "Changed elsewhere (fixture)",
    );
    expect(saves(requests)).toHaveLength(1);
    expect(screen.queryByTestId("conflict-dialog")).not.toBeInTheDocument();
  });

  it("downloads the local copy without needing the API", async () => {
    await conflicted();
    const createObjectURL = vi.fn((blob: Blob) => {
      void blob;
      return "blob:fixture";
    });
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL }));
    await userEvent.click(within(screen.getByTestId("conflict-dialog")).getByTestId("conflict-download"));
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = createObjectURL.mock.calls[0][0];
    expect(await blob.text()).toContain('"divider"');
  });

  it("saves the local content as a new document and navigates to it", async () => {
    const requests = await renderReady([
      (r) => {
        if (r.method === "POST" && r.url === "/api/documents") {
          return jsonResponse(documentResponse(DOC, { id: NEW_DOC_ID, revision: 1 }), 201);
        }
        if (r.method === "POST" && r.url === `/api/documents/${NEW_DOC_ID}/versions`) {
          return saveSuccess(2);
        }
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          return errorResponse(409, "REVISION_CONFLICT", "Document revision moved", [
            { path: "If-Match", reason: "current_revision:9" },
          ]);
        }
        return undefined;
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    const dialog = await screen.findByTestId("conflict-dialog");
    await userEvent.click(within(dialog).getByTestId("conflict-new-copy"));
    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith(`/workspace/research/${NEW_DOC_ID}`);
    });
    const creates = requests.filter((r) => r.url === "/api/documents");
    expect(creates).toHaveLength(1);
    expect(creates[0].headers["idempotency-key"]).toMatch(/^[0-9a-f-]{36}$/i);
    const copySave = requests.find((r) => r.url === `/api/documents/${NEW_DOC_ID}/versions`);
    expect(copySave).toBeDefined();
    expect(copySave?.headers["if-match"]).toBe('"1"');
  });

  it("refuses to carry the local content into another principal's new document (NI-062)", async () => {
    const requests = await renderReady([
      (r) => {
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          return errorResponse(409, "REVISION_CONFLICT", "Document revision moved", [
            { path: "If-Match", reason: "current_revision:9" },
          ]);
        }
        return undefined;
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    const dialog = await screen.findByTestId("conflict-dialog");
    // Between the conflict and the click, another principal signs in on
    // another tab: the fresh re-verification at click time returns Bob.
    sessionSubject = "synthetic-bob";
    await userEvent.click(within(dialog).getByTestId("conflict-new-copy"));
    // NO document is created — Alice's content can never be written into
    // Bob's new document. The verified different subject also clears the
    // workbench, so the end state is the honest session boundary (the
    // dialog's transient refusal may already be unmounted with it).
    await screen.findByText(/session has ended or changed/i);
    expect(requests.filter((r) => r.method === "POST" && r.url === "/api/documents")).toHaveLength(0);
    await waitFor(() => {
      expect(screen.queryByRole("textbox")).toBeNull();
    });
    sessionSubject = "synthetic-owner";
  });

  it("keeps editing (dismiss) and reopens through the review button", async () => {
    await conflicted();
    await userEvent.click(within(screen.getByTestId("conflict-dialog")).getByTestId("conflict-keep-editing"));
    expect(screen.queryByTestId("conflict-dialog")).not.toBeInTheDocument();
    // The paused state stays visible and honest in the status line.
    expect(screen.getByTestId("save-status")).toHaveTextContent(
      /Saving is paused — this document changed in another session/,
    );
    await userEvent.click(screen.getByTestId("review-conflict"));
    expect(screen.getByTestId("conflict-dialog")).toBeInTheDocument();
  });
});

describe("honest offline queue", () => {
  it("holds the content, never fakes success, and retries with the SAME idempotency key", async () => {
    let failFirst = true;
    const requests = await renderReady([
      (r) => {
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          if (failFirst) {
            failFirst = false;
            throw new TypeError("network offline");
          }
          return saveSuccess(8);
        }
        return undefined;
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/Offline — saving is paused/);
    });
    // Content is retained in the editor while queued.
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Divider/);
    expect(screen.getByTestId("save-now")).toBeEnabled();

    await userEvent.click(screen.getByTestId("retry-queued"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved at 10:00:00 UTC · Revision 8/);
    });
    const attempts = saves(requests);
    expect(attempts).toHaveLength(2);
    // Key-stable retry: a committed save replays instead of duplicating.
    expect(attempts[1].headers["idempotency-key"]).toBe(attempts[0].headers["idempotency-key"]);
    expect(attempts[1].headers["if-match"]).toBe('"7"');
  });

  it("retries automatically when the browser reports the connection back", async () => {
    let failNext = true;
    const requests = await renderReady([
      (r) => {
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          if (failNext) {
            failNext = false;
            throw new TypeError("network offline");
          }
          return saveSuccess(8);
        }
        return undefined;
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/Offline — saving is paused/);
    });
    window.dispatchEvent(new Event("online"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved at 10:00:00 UTC · Revision 8/);
    });
    const attempts = saves(requests);
    expect(attempts).toHaveLength(2);
    expect(attempts[1].headers["idempotency-key"]).toBe(attempts[0].headers["idempotency-key"]);
  });
});

describe("typed failures keep the content", () => {
  it("surfaces an expired session, keeps the edits and retries after sign-in", async () => {
    let authed = false;
    const requests = await renderReady([
      (r) => {
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          return authed ? saveSuccess(8) : errorResponse(401, "AUTHENTICATION_REQUIRED", "Authentication is required");
        }
        return undefined;
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/session has expired/i);
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Divider/);
    // Editing does not fix auth: no autosave request fires while expired,
    // and the typed error stays surfaced.
    await insertDivider(false);
    await new Promise((resolve) => setTimeout(resolve, 1300));
    expect(saves(requests)).toHaveLength(1);

    authed = true;
    await userEvent.click(screen.getByTestId("retry-save"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved at 10:00:00 UTC · Revision 8/);
    });
    expect(JSON.stringify(saves(requests)[1].body)).toContain('"divider"');
  });

  it("surfaces the server's typed message for validation failures and keeps the content", async () => {
    const requests = await renderReady([
      (r) =>
        r.method === "POST" && r.url.endsWith("/versions")
          ? errorResponse(422, "REFERENCE_INVALID", "The evidence target does not exist for this owner")
          : undefined,
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/The evidence target does not exist for this owner/);
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Divider/);
    expect(screen.getByTestId("retry-save")).toBeInTheDocument();
    expect(saves(requests)).toHaveLength(1);
  });

  it("surfaces the size limit and offers a local download", async () => {
    await renderReady([
      (r) =>
        r.method === "POST" && r.url.endsWith("/versions")
          ? errorResponse(413, "PAYLOAD_TOO_LARGE", "Request is too large")
          : undefined,
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/size limit/i);
    expect(screen.getByTestId("retry-save")).toBeInTheDocument();
    expect(screen.getByTestId("download-copy")).toBeInTheDocument();
  });
});

describe("unload warning", () => {
  it("warns before unloading while content is unacknowledged, not when clean", async () => {
    await renderReady([(r) => (r.method === "POST" && r.url.endsWith("/versions") ? saveSuccess(8) : undefined)]);
    const unload = () => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    };
    expect(unload()).toBe(false);
    await insertDivider();
    expect(unload()).toBe(true);
    await userEvent.click(screen.getByTestId("save-now"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved/);
    });
    expect(unload()).toBe(false);
  });
});

describe("session draft recovery", () => {
  const draftKey = `near-intelligence.editor-draft.${DOC_ID}`;

  it("offers to restore a draft captured before an offline save attempt", async () => {
    let failFirst = true;
    await renderReady([
      (r) => {
        if (r.method === "POST" && r.url.endsWith("/versions")) {
          if (failFirst) {
            failFirst = false;
            throw new TypeError("network offline");
          }
          return saveSuccess(8);
        }
        return undefined;
      },
    ]);
    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    await screen.findByTestId("retry-queued");
    // The failed attempt captured a draft before going offline. Simulate the
    // tab reload: unmount, keep sessionStorage, render a fresh editor.
    cleanup();
    expect(JSON.parse(sessionStorage.getItem(draftKey) ?? "{}").body).toBeDefined();
    await renderReady([(r) => (r.method === "POST" && r.url.endsWith("/versions") ? saveSuccess(8) : undefined)]);
    const banner = await screen.findByTestId("draft-recovery");
    expect(within(banner).getByText(/draft with unsaved changes/i)).toBeInTheDocument();
    await userEvent.click(within(banner).getByTestId("draft-restore"));
    expect(screen.getByRole("separator")).toBeInTheDocument();
    expect(screen.getByTestId("save-status")).toHaveTextContent(/Unsaved changes/);
    // The restored content saves through the normal autosave path.
    await waitFor(
      () => {
        expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved/);
      },
      { timeout: 3000 },
    );
  });

  it("discarding the draft is explicit and clears the offer", async () => {
    sessionStorage.setItem(
      draftKey,
      JSON.stringify({
        baseRevision: 7,
        capturedAt: "2026-11-08T09:00:00Z",
        body: { schema_version: 1, content: DOC, observed_contexts: [] },
      }),
    );
    await renderReady([]);
    const banner = await screen.findByTestId("draft-recovery");
    expect(within(banner).getByTestId("draft-discard")).toBeInTheDocument();
    await userEvent.click(within(banner).getByTestId("draft-discard"));
    expect(screen.queryByTestId("draft-recovery")).not.toBeInTheDocument();
    expect(sessionStorage.getItem(draftKey)).toBeNull();
  });

  it("an invalid draft cannot be restored and says why", async () => {
    sessionStorage.setItem(
      draftKey,
      JSON.stringify({
        baseRevision: 7,
        capturedAt: "2026-11-08T09:00:00Z",
        // A divider without a block_id fails the canonical validation.
        body: {
          schema_version: 1,
          content: { schema_version: 1, type: "doc", content: [{ type: "divider", attrs: {} }] },
          observed_contexts: [],
        },
      }),
    );
    await renderReady([]);
    const banner = await screen.findByTestId("draft-recovery");
    expect(within(banner).getByText(/cannot be restored/i)).toBeInTheDocument();
    expect(within(banner).getByText(/must_be_uuid/i)).toBeInTheDocument();
    expect(within(banner).queryByTestId("draft-restore")).not.toBeInTheDocument();
  });
});
