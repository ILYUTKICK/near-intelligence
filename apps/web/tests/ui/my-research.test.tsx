/**
 * NI-023 My Research tests: the list renders only API-returned owner rows
 * (fixtures are synthetic and labeled), search/sort/pagination parameters go
 * to the server, create/rename/delete hit the documented contract
 * (Idempotency-Key, If-Match) and a stale revision (409) keeps the item with
 * an error and a refreshed list instead of silently overwriting or removing.
 * Owner isolation itself is server-side (NI-019): the client asserts it never
 * sends any user identifier and relies on the same-origin session.
 */
import { axe } from "jest-axe";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentList } from "@/features/documents/list/DocumentList";

const routerPush = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush }),
}));

const DOC_RECENT_ID = "22222222-2222-4222-8222-222222222222";
const DOC_OLDER_ID = "33333333-3333-4333-8333-333333333333";
const DOC_CREATED_ID = "44444444-4444-4444-8444-444444444444";

// Synthetic test fixtures, visibly labeled — production code never embeds
// sample documents (NI-023 acceptance: "no synthetic sample docs").
function summaryFixture(overrides: {
  id: string;
  title: string;
  updated_at: string;
  revision?: number;
  tags?: string[];
  favorite?: boolean;
}) {
  return {
    id: overrides.id,
    title: overrides.title,
    revision: overrides.revision ?? 1,
    schema_version: 1,
    current_version_id: null,
    created_at: "2026-11-01T09:00:00Z",
    updated_at: overrides.updated_at,
    progress: { headings: 0, charts: 0, insights: 0 },
    tags: overrides.tags ?? [],
    favorite: overrides.favorite ?? false,
  };
}

const RECENT_DOC = summaryFixture({
  id: DOC_RECENT_ID,
  title: "Zeta fee attribution notes (fixture)",
  updated_at: "2026-11-07T12:00:00Z",
  revision: 3,
});
const OLDER_DOC = summaryFixture({
  id: DOC_OLDER_ID,
  title: "Alpha supply questions (fixture)",
  updated_at: "2026-11-02T09:30:00Z",
  revision: 1,
});
const CREATED_DOC = {
  ...summaryFixture({
    id: DOC_CREATED_ID,
    title: "Brand new research (fixture)",
    updated_at: "2026-11-08T00:00:00Z",
    revision: 1,
  }),
  content: {},
  resolved_contexts: {},
};

interface CapturedRequest {
  url: string;
  init: RequestInit;
}

function jsonResponse(body: unknown, status = 200): Response {
  return Response.json(body, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

function errorResponse(status: number, code: string, message: string, details?: unknown): Response {
  return jsonResponse(
    { error: { code, message, request_id: "req-fixture", retryable: false, details: details ?? null } },
    status,
  );
}

/**
 * Minimal method+URL router for the API surface used by the list. Records
 * every request so tests can assert exact headers, parameters and payloads.
 */
function mockApi(handlers: Array<(url: string, init: RequestInit) => Response | undefined>) {
  const requests: CapturedRequest[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    if (String(input) === "/api/auth/csrf") return Promise.resolve(new Response(JSON.stringify({ token: "synthetic-csrf" }), { headers: { "content-type": "application/json" } }));
    const url = String(input);
    requests.push({ url, init });
    for (const handler of handlers) {
      const response = handler(url, init);
      if (response) {
        return Promise.resolve(response);
      }
    }
    return Promise.resolve(errorResponse(500, "UNHANDLED", `No handler for ${url}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return requests;
}

function listPage(items: unknown[], nextCursor: string | null): Response {
  return jsonResponse({ items, next_cursor: nextCursor });
}

function isGetDocuments(url: string, init?: RequestInit): boolean {
  return (init?.method ?? "GET") === "GET" && new URL(url, "http://localhost").pathname === "/api/documents";
}

beforeEach(() => {
  routerPush.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function renderList() {
  const { container } = render(<DocumentList />);
  // Initial load resolves before interactions.
  await screen.findByRole("heading", { name: "My Research" });
  return { container };
}

describe("My Research list — ownership boundary", () => {
  it("renders exactly the API rows in API order and sends no user identifier", async () => {
    // The API returns updated_at-DESC order; note the titles deliberately
    // sort differently alphabetically, so any client-side re-sort would fail.
    const requests = mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([RECENT_DOC, OLDER_DOC], null) : undefined),
    ]);

    const { container } = await renderList();

    const list = screen.getByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Zeta fee attribution notes (fixture)");
    expect(items[1]).toHaveTextContent("Alpha supply questions (fixture)");

    // Every link points at the persisted document route via the document ID.
    const links = within(list).getAllByRole("link");
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      `/workspace/research/${DOC_RECENT_ID}`,
      `/workspace/research/${DOC_OLDER_ID}`,
    ]);

    // Owner isolation is enforced server-side: no request carries a user
    // identifier in the URL, query or headers — only the same-origin session.
    expect(requests.length).toBeGreaterThan(0);
    for (const request of requests) {
      expect(request.url.startsWith("/api/")).toBe(true);
      expect(request.url.toLowerCase()).not.toContain("user_id");
      expect(request.url.toLowerCase()).not.toContain("user-id");
      const headers = new Headers(request.init.headers);
      for (const headerName of headers.keys()) {
        expect(headerName.toLowerCase()).not.toBe("user_id");
        expect(headerName.toLowerCase()).not.toBe("authorization");
      }
      expect(JSON.stringify(request.init.body ?? "")).not.toContain("user_id");
    }

    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("keeps search, sort and pagination as server parameters", async () => {
    const pageTwo = summaryFixture({
      id: DOC_CREATED_ID,
      title: "Second page item (fixture)",
      updated_at: "2026-10-20T08:00:00Z",
    });
    const requests = mockApi([
      (url, init) => {
        if (!isGetDocuments(url, init)) {
          return undefined;
        }
        const requestUrl = new URL(url, "http://localhost");
        if (requestUrl.searchParams.get("cursor") === "MQ") {
          expect(requestUrl.searchParams.get("q")).toBe("alpha");
          return listPage([pageTwo], null);
        }
        // The sort itself is never a client parameter — the API owns the
        // updated_at DESC order; `q` narrows the same owner-scoped query.
        return listPage([OLDER_DOC], "MQ");
      },
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.type(screen.getByLabelText("Search by title"), "alpha");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await screen.findByText("Alpha supply questions (fixture)");
    const searchUrl = new URL(requests[requests.length - 1].url, "http://localhost");
    expect(searchUrl.pathname).toBe("/api/documents");
    expect(searchUrl.searchParams.get("q")).toBe("alpha");
    expect(searchUrl.searchParams.has("sort")).toBe(false);
    expect(searchUrl.searchParams.has("order")).toBe(false);

    await user.click(screen.getByRole("button", { name: "Show more documents" }));
    await screen.findByText("Second page item (fixture)");
    const moreUrl = new URL(requests[requests.length - 1].url, "http://localhost");
    expect(moreUrl.searchParams.get("cursor")).toBe("MQ");
    expect(moreUrl.searchParams.get("q")).toBe("alpha");
    // The loaded page stays appended in API order — no client re-sorting.
    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[1]).toHaveTextContent("Second page item (fixture)");

    // Clearing returns to the unfiltered list.
    await user.click(screen.getByRole("button", { name: "Clear" }));
    await screen.findByText("Alpha supply questions (fixture)");
    const clearedUrl = new URL(requests[requests.length - 1].url, "http://localhost");
    expect(clearedUrl.search).toBe("");
  });

  it("shows the honest first-use explanation for an empty workspace and no fake documents", async () => {
    const requests = mockApi([(url, init) => (isGetDocuments(url, init) ? listPage([], null) : undefined)]);

    const { container } = await renderList();

    expect(screen.getByRole("note", { name: "About research documents" })).toHaveTextContent(
      /private analysis notebook/i,
    );
    expect(screen.getByRole("button", { name: "Create your first document" })).toBeInTheDocument();
    // No synthetic sample documents may appear in production rendering: the
    // empty workspace renders the explanation only, never document rows.
    expect(screen.queryByRole("list")).toBeNull();
    expect(container.textContent).not.toMatch(/\(fixture\)/);

    // A search miss is a different, honest state.
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Search by title"), "nothing");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText(/No documents match your search/i)).toBeInTheDocument();
    const searchUrl = new URL(requests[requests.length - 1].url, "http://localhost");
    expect(searchUrl.searchParams.get("q")).toBe("nothing");

    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("surfaces load failures with a retry and keeps the session-expiry path honest", async () => {
    const requests = mockApi([
      (url, init) => (isGetDocuments(url, init) ? errorResponse(401, "UNAUTHENTICATED", "Missing or invalid session") : undefined),
    ]);

    const { container } = await renderList();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/session has expired/i);
    expect(screen.getByRole("link", { name: "Sign in again" })).toHaveAttribute("href", "/login");
    expect(requests).toHaveLength(1);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe("My Research actions — create, rename, delete", () => {
  it("creates with a client Idempotency-Key and navigates to the persisted document route", async () => {
    const requests = mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([RECENT_DOC], null) : undefined),
      (url, init) =>
        url === "/api/documents" && init.method === "POST"
          ? jsonResponse(CREATED_DOC, 201)
          : undefined,
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.click(screen.getByRole("button", { name: "New document" }));
    const dialog = await screen.findByRole("dialog", { name: /new research document/i });
    await user.type(within(dialog).getByLabelText("Title"), "Brand new research (fixture)");
    await user.click(within(dialog).getByRole("button", { name: "Create document" }));

    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith(`/workspace/research/${DOC_CREATED_ID}`);
    });
    const post = requests.find((request) => request.init.method === "POST");
    expect(post).toBeDefined();
    expect(post?.url).toBe("/api/documents");
    const headers = new Headers(post?.init.headers);
    const idempotencyKey = headers.get("idempotency-key");
    expect(idempotencyKey).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(JSON.parse(String(post?.init.body))).toEqual({ title: "Brand new research (fixture)" });
    expect(headers.get("content-type")).toContain("application/json");
  });

  it("sends the selected template_id (NI-045) and keeps the empty default template-free", async () => {
    const requests = mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([RECENT_DOC], null) : undefined),
      (url, init) =>
        url === "/api/documents" && init.method === "POST"
          ? jsonResponse(CREATED_DOC, 201)
          : undefined,
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.click(screen.getByRole("button", { name: "New document" }));
    const dialog = await screen.findByRole("dialog", { name: /new research document/i });
    // The empty document stays the default choice.
    expect(within(dialog).getByLabelText("Empty document")).toBeChecked();
    expect(within(dialog).getByLabelText("Investment research template")).not.toBeChecked();
    await user.type(within(dialog).getByLabelText("Title"), "Templated research (fixture)");
    await user.click(within(dialog).getByLabelText("Investment research template"));
    await user.click(within(dialog).getByRole("button", { name: "Create document" }));

    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith(`/workspace/research/${DOC_CREATED_ID}`);
    });
    const post = requests.find((request) => request.init.method === "POST");
    expect(JSON.parse(String(post?.init.body))).toEqual({
      title: "Templated research (fixture)",
      template_id: "investment-v1",
    });
  });

  it("retains the typed title and stays open when creation fails", async () => {
    mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([], null) : undefined),
      (_url, init) =>
        init.method === "POST"
          ? errorResponse(422, "VALIDATION_ERROR", "The request failed validation")
          : undefined,
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.click(screen.getByRole("button", { name: "New document" }));
    const dialog = await screen.findByRole("dialog", { name: /new research document/i });
    await user.type(within(dialog).getByLabelText("Title"), "Kept title (fixture)");
    await user.click(within(dialog).getByRole("button", { name: "Create document" }));

    const alert = await screen.findByRole("alert");
    // The typed server validation message is surfaced as-is; the dialog stays
    // open with the value retained for correction.
    expect(alert).toHaveTextContent("The request failed validation");
    expect(within(dialog).getByLabelText("Title")).toHaveValue("Kept title (fixture)");
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("renames through PATCH with the quoted If-Match revision", async () => {
    const renamedDoc = {
      ...RECENT_DOC,
      title: "Renamed fees note (fixture)",
      revision: 4,
      updated_at: "2026-11-08T00:30:00Z",
    };
    let listCalls = 0;
    const requests = mockApi([
      (url, init) => {
        if (!isGetDocuments(url, init)) {
          return undefined;
        }
        listCalls += 1;
        // The post-rename refresh returns the renamed summary — a revision
        // bumps updated_at, so the server order changes under the client.
        return listPage(listCalls === 1 ? [RECENT_DOC] : [renamedDoc], null);
      },
      (url, init) =>
        url === `/api/documents/${DOC_RECENT_ID}` && init.method === "PATCH"
          ? jsonResponse(renamedDoc)
          : undefined,
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.click(screen.getByRole("button", { name: "Rename" }));
    const dialog = await screen.findByRole("dialog", { name: /rename document/i });
    const input = within(dialog).getByLabelText("Title");
    expect(input).toHaveValue("Zeta fee attribution notes (fixture)");
    await user.clear(input);
    await user.type(input, "Renamed fees note (fixture)");
    await user.click(within(dialog).getByRole("button", { name: "Save new title" }));

    await screen.findByText("Renamed fees note (fixture)");
    expect(listCalls).toBe(2);
    const patch = requests.find((request) => request.init.method === "PATCH");
    expect(patch).toBeDefined();
    const headers = new Headers(patch?.init.headers);
    // 428 (missing If-Match) must be impossible: the client always sends the
    // quoted revision it got from the list summary.
    expect(headers.get("if-match")).toBe('"3"');
    expect(JSON.parse(String(patch?.init.body))).toEqual({ title: "Renamed fees note (fixture)" });
  });

  it("deletes through DELETE with If-Match and removes the row after confirmation", async () => {
    let deletedRequested = false;
    const requests = mockApi([
      (url, init) => {
        if (!isGetDocuments(url, init)) {
          return undefined;
        }
        // After the confirmed deletion the server no longer returns the row.
        return listPage(deletedRequested ? [OLDER_DOC] : [RECENT_DOC, OLDER_DOC], null);
      },
      (url, init) => {
        if (url === `/api/documents/${DOC_RECENT_ID}` && init.method === "DELETE") {
          deletedRequested = true;
          return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
        }
        return undefined;
      },
    ]);

    const user = userEvent.setup();
    await renderList();

    // Two rows are visible; open delete for the first (recent) one.
    const recentItem = screen.getByText("Zeta fee attribution notes (fixture)").closest("li");
    expect(recentItem).not.toBeNull();
    await user.click(within(recentItem as HTMLElement).getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: /delete document/i });
    expect(dialog).toHaveTextContent(/permanently removes the document/i);
    await user.click(within(dialog).getByRole("button", { name: "Delete permanently" }));

    await waitFor(() => {
      const list = screen.getByRole("list");
      expect(within(list).getAllByRole("listitem")).toHaveLength(1);
      expect(within(list).getAllByRole("listitem")[0]).toHaveTextContent(
        "Alpha supply questions (fixture)",
      );
    });
    const deleted = requests.find((request) => request.init.method === "DELETE");
    expect(deleted).toBeDefined();
    expect(new Headers(deleted?.init.headers).get("if-match")).toBe('"3"');
  });

  it("keeps the item with an error and refreshes the list when a revision conflict (409) arrives", async () => {
    const refreshedDoc = summaryFixture({
      id: DOC_RECENT_ID,
      title: "Zeta fee attribution notes (fixture)",
      updated_at: "2026-11-08T01:00:00Z",
      revision: 7,
    });
    let listCalls = 0;
    const requests = mockApi([
      (url, init) => {
        if (!isGetDocuments(url, init)) {
          return undefined;
        }
        listCalls += 1;
        // The refresh after the conflict must return the CURRENT revision so
        // the next attempt uses it, not the stale one.
        return listPage(listCalls === 1 ? [RECENT_DOC] : [refreshedDoc], null);
      },
      (url, init) =>
        url === `/api/documents/${DOC_RECENT_ID}` && init.method === "DELETE"
          ? errorResponse(
              409,
              "REVISION_CONFLICT",
              "Revision conflict: the document moved to revision 7",
              [{ path: "If-Match", reason: "current_revision:7" }],
            )
          : undefined,
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: /delete document/i });
    await user.click(within(dialog).getByRole("button", { name: "Delete permanently" }));

    // The item is retained — never silently removed — with an explicit error
    // and the refresh hint, and the list was re-fetched with fresh revisions.
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/changed elsewhere/i);
    expect(alert).toHaveTextContent(/try again/i);
    expect(screen.getByText("Zeta fee attribution notes (fixture)")).toBeInTheDocument();
    await waitFor(() => {
      expect(listCalls).toBe(2);
    });
    const deleted = requests.find((request) => request.init.method === "DELETE");
    expect(deleted).toBeDefined();
    expect(new Headers(deleted?.init.headers).get("if-match")).toBe('"3"');
  });

  it("keeps the rename dialog open with values retained on a transport failure", async () => {
    mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([OLDER_DOC], null) : undefined),
      (_url, init) => (init.method === "PATCH" ? Promise.reject(new TypeError("network down")) as unknown as Response : undefined),
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.click(screen.getByRole("button", { name: "Rename" }));
    const dialog = await screen.findByRole("dialog", { name: /rename document/i });
    const input = within(dialog).getByLabelText("Title");
    await user.clear(input);
    await user.type(input, "Offline edit (fixture)");
    await user.click(within(dialog).getByRole("button", { name: "Save new title" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not be renamed/i);
    expect(within(dialog).getByLabelText("Title")).toHaveValue("Offline edit (fixture)");
  });
});

describe("My Research organization — private tags and favorites (NI-072)", () => {
  const TAGGED_DOC = summaryFixture({
    id: DOC_RECENT_ID,
    title: "Zeta fee attribution notes (fixture)",
    updated_at: "2026-11-07T12:00:00Z",
    revision: 3,
    tags: ["fees", "defi"],
  });

  function organizationResponse(tags: string[], favorite: boolean): Response {
    return jsonResponse({
      document_id: DOC_RECENT_ID,
      tags,
      favorite,
      updated_at: "2026-11-08T02:00:00Z",
    });
  }

  it("applies the tag filter from a row chip and recovers by removing it", async () => {
    const requests = mockApi([
      (url, init) => {
        if (!isGetDocuments(url, init)) {
          return undefined;
        }
        const requestUrl = new URL(url, "http://localhost");
        if (requestUrl.searchParams.get("tag") === "fees") {
          return listPage([TAGGED_DOC], null);
        }
        return listPage([TAGGED_DOC, OLDER_DOC], null);
      },
    ]);

    const user = userEvent.setup();
    await renderList();

    // The row carries its private tags as filter chips.
    const list = screen.getByRole("list");
    expect(within(list).getAllByRole("button", { name: "fees" })).toHaveLength(1);
    await user.click(within(list).getByRole("button", { name: "fees" }));

    // The filter is a server parameter composed with nothing else.
    await waitFor(() => {
      const filtered = new URL(requests[requests.length - 1].url, "http://localhost");
      expect(filtered.searchParams.getAll("tag")).toEqual(["fees"]);
      expect(filtered.searchParams.has("favorite")).toBe(false);
    });
    await screen.findByRole("button", { name: "Remove tag filter fees" });
    expect(screen.getByRole("button", { name: "fees" })).toHaveAttribute("aria-pressed", "true");

    // Removing the filter recovers the unfiltered list (empty/deleted tag
    // filters are honest states, never errors).
    await user.click(screen.getByRole("button", { name: "Remove tag filter fees" }));
    await waitFor(() => {
      const cleared = new URL(requests[requests.length - 1].url, "http://localhost");
      expect(cleared.search).toBe("");
    });
    expect(within(screen.getByRole("list")).getAllByRole("listitem")).toHaveLength(2);
  });

  it("filters to favorites and shows the honest filtered empty state", async () => {
    const requests = mockApi([
      (url, init) => {
        if (!isGetDocuments(url, init)) {
          return undefined;
        }
        // Nothing in the synthetic workspace is favorited: the API returns
        // an empty page for favorite=true.
        const requestUrl = new URL(url, "http://localhost");
        return requestUrl.searchParams.get("favorite") === "true"
          ? listPage([], null)
          : listPage([OLDER_DOC], null);
      },
    ]);

    const user = userEvent.setup();
    const { container } = await renderList();

    const favoritesToggle = screen.getByRole("button", { name: "Favorites" });
    expect(favoritesToggle).toHaveAttribute("aria-pressed", "false");
    await user.click(favoritesToggle);

    await screen.findByText(/No documents match your filters/i);
    expect(screen.getByRole("button", { name: "Favorites" })).toHaveAttribute("aria-pressed", "true");
    const filtered = new URL(requests[requests.length - 1].url, "http://localhost");
    expect(filtered.searchParams.get("favorite")).toBe("true");
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();

    // Clearing filters returns the plain list with no query at all (the
    // toolbar and the empty state both offer the same recovery action).
    await user.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
    await screen.findByText("Alpha supply questions (fixture)");
    const cleared = new URL(requests[requests.length - 1].url, "http://localhost");
    expect(cleared.search).toBe("");
  });

  it("edits tags through the dialog and applies the server state to the row", async () => {
    const requests = mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([TAGGED_DOC], null) : undefined),
      (url, init) =>
        url === `/api/documents/${DOC_RECENT_ID}/organization` && init.method === "PATCH"
          ? organizationResponse(["fees", "supply"], false)
          : undefined,
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.click(screen.getByRole("button", { name: "Tags" }));
    const dialog = await screen.findByRole("dialog", { name: /edit tags/i });
    const input = within(dialog).getByLabelText("Tags");
    expect(input).toHaveValue("fees, defi");
    await user.clear(input);
    await user.type(input, "  Fees , Supply ");
    await user.click(within(dialog).getByRole("button", { name: "Save tags" }));

    // The raw comma-separated input is sent; normalization is the API's.
    const patch = requests.find((request) => request.init.method === "PATCH");
    expect(patch).toBeDefined();
    expect(new URL(patch?.url ?? "", "http://localhost").pathname)
      .toBe(`/api/documents/${DOC_RECENT_ID}/organization`);
    expect(JSON.parse(String(patch?.init.body))).toEqual({ tags: ["Fees", "Supply"] });
    const headers = new Headers(patch?.init.headers);
    // Metadata is not CAS-protected content: no If-Match is sent and no
    // revision is created.
    expect(headers.get("if-match")).toBeNull();

    // The server's stored state is applied to the row — new chips appear.
    await waitFor(() => {
      expect(within(screen.getByRole("list")).getByRole("button", { name: "supply" }))
        .toBeInTheDocument();
    });
    expect(within(screen.getByRole("list")).queryByRole("button", { name: "defi" })).toBeNull();
  });

  it("toggles the favorite flag optimistically and reverts with an error on failure", async () => {
    // Holder object: the reject function is captured from inside the fetch
    // mock so the test controls exactly when the PATCH fails.
    const patchGate: { reject: ((reason: unknown) => void) | null } = { reject: null };
    const requests = mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([TAGGED_DOC], null) : undefined),
      (url, init) => {
        if (url === `/api/documents/${DOC_RECENT_ID}/organization` && init.method === "PATCH") {
          return new Promise<Response>((_resolve, reject) => {
            patchGate.reject = reject;
          }) as unknown as Response;
        }
        return undefined;
      },
    ]);

    const user = userEvent.setup();
    await renderList();

    await user.click(screen.getByRole("button", { name: "Favorite" }));

    // Optimistic: the row flips while the PATCH is still in flight, and the
    // request carries exactly the metadata merge (no If-Match).
    const pendingButton = await screen.findByRole("button", { name: "Favorited" });
    expect(pendingButton).toHaveAttribute("aria-pressed", "true");
    const patch = requests.find((request) => request.init.method === "PATCH");
    expect(JSON.parse(String(patch?.init.body))).toEqual({ favorite: true });
    expect(new Headers(patch?.init.headers).get("if-match")).toBeNull();

    // The API refuses: the row reverts to the server's last known state and
    // an honest error is shown — nothing is silently retried or kept fake.
    patchGate.reject?.(new TypeError("network down"));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not be changed/i);
    const reverted = screen.getByRole("button", { name: "Favorite" });
    expect(reverted).toHaveAttribute("aria-pressed", "false");

    // A successful retry confirms the new state from the server's response.
    mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([TAGGED_DOC], null) : undefined),
      (url, init) =>
        url === `/api/documents/${DOC_RECENT_ID}/organization` && init.method === "PATCH"
          ? organizationResponse(TAGGED_DOC.tags, true)
          : undefined,
    ]);
    await user.click(screen.getByRole("button", { name: "Favorite" }));
    await screen.findByRole("button", { name: "Favorited" });
    expect(screen.getByRole("button", { name: "Favorited" })).toHaveAttribute("aria-pressed", "true");
  });

  it("moves keyboard focus between documents with arrow keys over the API order", async () => {
    mockApi([
      (url, init) => (isGetDocuments(url, init) ? listPage([RECENT_DOC, OLDER_DOC], null) : undefined),
    ]);

    const user = userEvent.setup();
    await renderList();

    // Only the document titles are row links; Enter opens the focused one
    // through the link's native semantics.
    const links = within(screen.getByRole("list")).getAllByRole("link");
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      `/workspace/research/${DOC_RECENT_ID}`,
      `/workspace/research/${DOC_OLDER_ID}`,
    ]);
    links[0].focus();
    await user.keyboard("{ArrowDown}");
    expect(links[1]).toHaveFocus();
    // ArrowDown on the last row stays put — no wraparound surprise.
    await user.keyboard("{ArrowDown}");
    expect(links[1]).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(links[0]).toHaveFocus();
    // Enter on the focused link is the browser's open action (native link);
    // the row's other controls stay in the plain tab order.
    expect(screen.getAllByRole("button", { name: "Rename" })).toHaveLength(2);
  });
});
