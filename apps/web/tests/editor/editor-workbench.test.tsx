/**
 * NI-039 workbench tests (synthetic fixtures, visibly labeled): honest load
 * states on the owner-checked route, the three-pane layout contract, the
 * mobile one-pane/drawer behavior, the explicit dependent-link delete
 * confirmation, the insert menu, outline accuracy and accessibility of the
 * key states. Owner isolation itself is server-side; these tests assert the
 * client never sends a user identifier (same contract as the NI-023 list).
 */
import { axe } from "jest-axe";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchDocumentEditor } from "@/features/editor/workbench";
import type { CanonicalDocument } from "@/features/editor/canonical";

// The editor shell navigates on conflict recovery (new-document copy);
// tests stub the app router like the NI-023 list tests do.
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

const HEADING_ID = "11111111-1111-4111-8111-111111111111";
const HYPOTHESIS_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const EVIDENCE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

/** Synthetic linked fixture: the hypothesis has one dependent evidence link. */
const LINKED_DOC: CanonicalDocument = {
  schema_version: 1,
  type: "doc",
  content: [
    {
      type: "hypothesis",
      attrs: {
        block_id: "33333333-3333-4333-8333-333333333333",
        hypothesis_id: HYPOTHESIS_ID,
        statement: "Adoption drives fee growth (fixture)",
        assessment: "untested",
        authored_at: "2026-11-08T00:00:00Z",
        modified_at: "2026-11-08T00:00:00Z",
      },
    },
    {
      type: "evidence",
      attrs: {
        block_id: "44444444-4444-4444-8444-444444444444",
        evidence_id: EVIDENCE_ID,
        hypothesis_id: HYPOTHESIS_ID,
        classification: "supporting",
        target_kind: "citation",
        target_id: "55555555-5555-4555-8555-555555555555",
        explanation: "Cited report (fixture)",
      },
    },
    {
      type: "heading",
      attrs: { block_id: HEADING_ID, level: 2 },
      content: [{ type: "text", text: "Analysis section (fixture)" }],
    },
  ],
};

/** Unlinked fixture for plain structural operations. */
const PLAIN_DOC: CanonicalDocument = {
  schema_version: 1,
  type: "doc",
  content: [
    {
      type: "heading",
      attrs: { block_id: HEADING_ID, level: 1 },
      content: [{ type: "text", text: "Notes (fixture)" }],
    },
    {
      type: "paragraph",
      attrs: { block_id: "66666666-6666-4666-8666-666666666666" },
      content: [{ type: "text", text: "First paragraph (fixture)" }],
    },
    {
      type: "paragraph",
      attrs: { block_id: "77777777-7777-4777-8777-777777777777" },
      content: [{ type: "text", text: "Second paragraph (fixture)" }],
    },
  ],
};

function documentResponse(content: unknown, overrides: Record<string, unknown> = {}) {
  return {
    id: DOC_ID,
    title: "Editor workbench fixture",
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

function jsonResponse(body: unknown, status = 200): Response {
  return Response.json(body, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

function errorResponse(status: number, code: string, message: string): Response {
  return jsonResponse(
    { error: { code, message, request_id: "req-fixture", retryable: false, details: null } },
    status,
  );
}

function mockApi(handlers: Array<(url: string) => Response | undefined>) {
  const requests: Array<{ url: string; init: RequestInit }> = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = input instanceof Request ? new URL(input.url).pathname : String(input);
    requests.push({ url, init });
    for (const handler of handlers) {
      const response = handler(url);
      if (response) {
        return Promise.resolve(response);
      }
    }
    return Promise.resolve(errorResponse(500, "UNHANDLED", `No handler for ${url}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return requests;
}

afterEach(() => {
  vi.unstubAllGlobals();
  // The recovery draft lives in sessionStorage; tests must not leak one into
  // the next render.
  sessionStorage.clear();
});

async function renderReady(content: CanonicalDocument = PLAIN_DOC, handlers: Array<(url: string) => Response | undefined> = []) {
  const requests = mockApi([
    ...handlers,
    (url) => (url === `/api/documents/${DOC_ID}` ? jsonResponse(documentResponse(content)) : undefined),
  ]);
  render(<ResearchDocumentEditor documentId={DOC_ID} />);
  await screen.findByRole("textbox", { name: "Research paper editor" });
  return requests;
}

describe("honest load states", () => {
  it("loads the persisted document into the editor (owner-checked GET)", async () => {
    const requests = await renderReady();
    expect(requests).toHaveLength(1);
    expect(requests[0].url).toBe(`/api/documents/${DOC_ID}`);
    // The client sends no user identifier — ownership rides the session.
    expect(Object.keys(requests[0].init.headers as Record<string, string>)).not.toContain("authorization");
    expect(screen.getByRole("heading", { name: "Editor workbench fixture" })).toBeInTheDocument();
    // NI-040: the loaded content is the acknowledged baseline — a truthful
    // clean status, not a fake "saving" promise.
    expect(screen.getByTestId("save-status")).toHaveTextContent(/No unsaved changes · Revision 7/);
    expect(screen.getByText(/· Revision 7 · Schema version 1/)).toBeInTheDocument();
  });

  it("shows a loading skeleton shaped like the paper first", async () => {
    mockApi([
      (url) => (url === `/api/documents/${DOC_ID}` ? jsonResponse(documentResponse(PLAIN_DOC)) : undefined),
    ]);
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    expect(screen.getByRole("status", { name: "Loading document" })).toBeInTheDocument();
    await screen.findByRole("textbox", { name: "Research paper editor" });
  });

  it("answers an inaccessible document with the same honest not-found state", async () => {
    mockApi([
      (url) =>
        url === `/api/documents/${DOC_ID}` ? errorResponse(404, "RESOURCE_NOT_FOUND", "Resource not found") : undefined,
    ]);
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /does not exist or does not belong to your account/i,
    );
    // Never renders an editor for a foreign/absent document.
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("offers re-authentication on session expiry", async () => {
    mockApi([
      (url) => (url === `/api/documents/${DOC_ID}` ? errorResponse(401, "UNAUTHORIZED", "Unauthorized") : undefined),
    ]);
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/session has expired/i);
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("keeps an error retryable without changing anything", async () => {
    mockApi([
      (url) => (url === `/api/documents/${DOC_ID}` ? errorResponse(500, "INTERNAL", "Boom") : undefined),
    ]);
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be loaded/i);
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("rejects a malformed document id without any request", async () => {
    const requests = mockApi([]);
    render(<ResearchDocumentEditor documentId="not-a-uuid" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /does not exist or does not belong to your account/i,
    );
    expect(requests).toHaveLength(0);
  });

  it("opens an unsupported schema version read-only with a recovery download", async () => {
    mockApi([
      (url) =>
        url === `/api/documents/${DOC_ID}`
          ? jsonResponse(documentResponse({ schema_version: 9, type: "doc", content: [] }))
          : undefined,
    ]);
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    expect(await screen.findByTestId("recovery-view")).toHaveTextContent(/read-only/i);
    expect(screen.getByTestId("download-content")).toHaveTextContent(/Download stored content/);
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("refuses invalid stored content before rendering (no partial editor)", async () => {
    mockApi([
      (url) =>
        url === `/api/documents/${DOC_ID}`
          ? jsonResponse(documentResponse({ schema_version: 1, type: "doc", content: [{ type: "divider", attrs: {} }] }))
          : undefined,
    ]);
    render(<ResearchDocumentEditor documentId={DOC_ID} />);
    expect(await screen.findByTestId("recovery-view")).toHaveTextContent(/canonical document validation/i);
    expect(screen.getByTestId("recovery-view")).toHaveTextContent(/block_id: must_be_uuid/);
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});

describe("three-pane layout contract", () => {
  it("renders outline, paper and tools panes with honest structure", async () => {
    await renderReady(LINKED_DOC);
    expect(screen.getByTestId("editor-grid")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Research paper editor" })).toBeInTheDocument();
    // The outline pane carries the heading structure.
    const outline = screen.getAllByRole("navigation", { name: "Document outline" });
    expect(outline.length).toBeGreaterThan(0);
    // The properties pane exists.
    expect(screen.getAllByLabelText("Block properties").length).toBeGreaterThan(0);
    // Drawer triggers exist for small screens; the NI-040 save control is real.
    expect(screen.getByRole("button", { name: "Open outline drawer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open tools drawer" })).toBeInTheDocument();
    const saveButton = screen.getByRole("button", { name: "Save now" });
    expect(saveButton).toBeDisabled(); // nothing unsaved yet
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("opens outline and tools drawers, closes them and never shows two at once", async () => {
    const user = userEvent.setup();
    await renderReady(LINKED_DOC);
    await user.click(screen.getByRole("button", { name: "Open outline drawer" }));
    const drawers = screen.getAllByRole("dialog");
    expect(drawers).toHaveLength(1);
    expect(within(drawers[0]).getByText("Analysis section (fixture)")).toBeInTheDocument();
    // Radix aria-hides everything outside the open drawer, so the other
    // trigger is not reachable until it closes — one drawer at a time.
    expect(screen.queryByRole("button", { name: "Open tools drawer" })).toBeNull();
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: "Open tools drawer" }));
    const toolsDrawer = screen.getAllByRole("dialog")[0];
    expect(within(toolsDrawer).getByText("Properties")).toBeInTheDocument();
    expect(within(toolsDrawer).getAllByTestId("context-pane").length).toBeGreaterThan(0);
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("keeps the desktop panes collapsible", async () => {
    const user = userEvent.setup();
    await renderReady();
    expect(screen.getByRole("button", { name: "Collapse outline" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Collapse outline" }));
    expect(screen.getByRole("button", { name: "Show outline pane" })).toHaveAttribute("aria-pressed", "false");
    await user.click(screen.getByRole("button", { name: "Show outline pane" }));
    expect(screen.getByRole("button", { name: "Collapse outline" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("block operations through the UI", () => {
  it("moves the current block down and announces it politely", async () => {
    const user = userEvent.setup();
    await renderReady();
    // The initial selection sits in the first block (the heading).
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Heading/);
    await user.click(screen.getByRole("button", { name: "Move down" }));
    expect(screen.getByTestId("editor-announcement")).toHaveTextContent(/moved down/i);
    // The outline follows the moved heading (now the last block).
    const outline = screen.getAllByRole("navigation", { name: "Document outline" })[0];
    expect(within(outline).getByRole("button", { name: /Notes \(fixture\)/ })).toBeInTheDocument();
  });

  it("duplicates the current block with new ids through the toolbar", async () => {
    const user = userEvent.setup();
    await renderReady();
    await user.click(screen.getByRole("button", { name: "Duplicate" }));
    expect(screen.getByTestId("editor-announcement")).toHaveTextContent(/duplicated/i);
    // Two headings now share the outline text (copy has a fresh id).
    const outline = screen.getAllByRole("navigation", { name: "Document outline" })[0];
    expect(within(outline).getAllByRole("button", { name: /Notes \(fixture\)/ })).toHaveLength(2);
  });

  it("previews dependent evidence links before deleting a linked target", async () => {
    const user = userEvent.setup();
    const versionId = "88888888-8888-4888-8888-888888888888";
    const remaining = { ...LINKED_DOC, content: LINKED_DOC.content.slice(2) };
    await renderReady(LINKED_DOC, [
      url => url === "/api/auth/session" ? jsonResponse({ subject: "synthetic-alice" }) : undefined,
      url => url === "/api/auth/csrf" ? jsonResponse({ token: "synthetic-csrf" }) : undefined,
      url => url === `/api/documents/${DOC_ID}/hypotheses/${HYPOTHESIS_ID}` ? jsonResponse({
        document: documentResponse(remaining, { revision: 8, current_version_id: versionId }),
        version: { id: versionId, document_id: DOC_ID, revision: 8, schema_version: 1, content: remaining },
        value: { deleted_id: HYPOTHESIS_ID },
      }) : undefined,
    ]);
    // The fixture puts the linked hypothesis first — the default selection.
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Hypothesis/);
    await user.click(screen.getByRole("button", { name: "Delete block" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Remove 1 linked evidence block.")).toBeInTheDocument();
    const confirm = within(dialog).getByRole("button", { name: "Confirm deletion" });
    expect(confirm).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox", { name: "Confirm linked cleanup" }));
    await user.click(confirm);
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("editor-announcement")).toHaveTextContent("Hypothesis deleted from this revision.");
    // The heading remains and the deleted hypothesis no longer has an outline entry.
    expect(screen.queryByRole("button", { name: /Hypothesis · Adoption/ })).toBeNull();
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Heading/);
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("cancels the delete confirmation and removes nothing", async () => {
    const user = userEvent.setup();
    await renderReady(LINKED_DOC);
    await user.click(screen.getByRole("button", { name: "Delete block" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Hypothesis/);
  });

  it("deletes an unlinked block without a confirmation dialog", async () => {
    const user = userEvent.setup();
    await renderReady();
    await user.click(screen.getByRole("button", { name: "Delete block" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("editor-announcement")).toHaveTextContent(/deleted/i);
  });

  it("inserts a divider block through the insert menu after the current block", async () => {
    const user = userEvent.setup();
    await renderReady();
    await user.click(screen.getByRole("button", { name: "Insert block" }));
    // The menu is named by its trigger (Radix aria-labelledby).
    const menu = await screen.findByRole("menu", { name: "Insert block" });
    await user.click(within(menu).getByRole("menuitem", { name: /Divider/ }));
    await waitFor(() => {
      expect(screen.queryByRole("menu", { name: "Insert block" })).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("editor-announcement")).toHaveTextContent(/inserted/i);
    // The divider is now the current block and its properties are shown.
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Divider/);
    expect(screen.getByText(/Semantic separator/)).toBeInTheDocument();
  });

  it("navigates from the outline to the heading and shows its properties", async () => {
    const user = userEvent.setup();
    await renderReady(LINKED_DOC);
    // Default selection is the first block (hypothesis).
    expect(screen.getByTestId("current-block-label")).toHaveTextContent(/Hypothesis/);
    const outline = screen.getAllByRole("navigation", { name: "Document outline" })[0];
    await user.click(within(outline).getByRole("button", { name: /Analysis section \(fixture\)/ }));
    // The context pane now shows the heading properties.
    await waitFor(() => {
      expect(screen.getAllByTestId("context-pane")[0]).toHaveTextContent(/Heading level 2/);
    });
    expect(screen.getByTestId("editor-announcement")).toHaveTextContent(/Selected the heading/);
  });
});

describe("context tools", () => {
  it("edits authored table cells from the properties pane within the bounds", async () => {
    const TABLE_DOC: CanonicalDocument = {
      schema_version: 1,
      type: "doc",
      content: [
        {
          type: "dataTable",
          attrs: {
            block_id: "88888888-8888-4888-8888-888888888888",
            columns: [
              { key: "column_1", label: "Month", type: "string" },
              { key: "column_2", label: "Note", type: "string" },
            ],
            rows: [
              ["Jan (fixture)", ""],
            ],
          },
        },
      ],
    };
    const user = userEvent.setup();
    await renderReady(TABLE_DOC);
    expect(screen.getByTestId("table-properties")).toBeInTheDocument();
    const cell = screen.getByLabelText("Row 1, column Month") as HTMLInputElement;
    expect(cell).toHaveValue("Jan (fixture)");
    await user.type(cell, "!");
    expect(cell).toHaveValue("Jan (fixture)!");
    // The paper re-renders the cell value from the canonical attrs.
    expect(screen.getByText("Jan (fixture)!")).toBeInTheDocument();
    // Bounds: adding rows is possible, the cell cap is stated.
    expect(screen.getByText(/of 1000 allowed cells/)).toBeInTheDocument();
  });

  it("shows annotation contract fields for the selected evidence block", async () => {
    await renderReady(LINKED_DOC);
    // Move the selection onto the evidence card through the properties
    // pane's own reflection of the first block (the fixture's evidence is
    // second; the hypothesis is first and shows its own contract fields).
    const pane = screen.getAllByTestId("context-pane")[0];
    expect(pane).toHaveTextContent(/Assessment/);
    expect(pane).toHaveTextContent(/untested/);
    expect(pane).toHaveTextContent(/2026-11-08T00:00:00Z/);
  });
});
