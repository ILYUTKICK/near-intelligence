/**
 * NI-045 public-release duplication CTA tests: the affordance exists only
 * when the server actually serves a published release for the slug (a 404
 * availability read renders NOTHING — no faked availability), anonymous
 * visitors get the safe internal sign-in continuation, and signed-in users
 * duplicate through the documented contract (pinned publication_version,
 * client Idempotency-Key, no ownership or content claims).
 * Fixtures are synthetic and visibly labeled.
 */
import { axe } from "jest-axe";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DuplicateReleaseAction } from "@/features/public-research/DuplicateReleaseAction";

const routerPush = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush }),
}));

const SLUG = "synthetic-release";
const COPY_ID = "55555555-5555-4555-8555-555555555555";
const RELEASE = {
  id: "66666666-6666-4666-8666-666666666666",
  slug: SLUG,
  version: 2,
  title: "Synthetic public release (fixture)",
  content: {},
  evidence_manifest: [],
  content_sha256: "a".repeat(64),
  published_at: "2026-11-10T09:00:00Z",
};
const CREATED_DOCUMENT = {
  id: COPY_ID,
  title: "My private copy (fixture)",
  revision: 2,
  schema_version: 1,
  current_version_id: null,
  created_at: "2026-11-10T10:00:00Z",
  updated_at: "2026-11-10T10:00:00Z",
  progress: { headings: 0, charts: 0, insights: 0 },
  content: {},
  resolved_contexts: {},
};

function jsonResponse(body: unknown, status = 200): Response {
  return Response.json(body, { status, headers: { "cache-control": "no-store" } });
}

function mockApi(handlers: Array<(url: string, init: RequestInit) => Response | undefined>) {
  const requests: Array<{ url: string; init: RequestInit }> = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    if (url === "/api/auth/csrf") {
      return Promise.resolve(new Response(JSON.stringify({ token: "synthetic-csrf" }),
        { headers: { "content-type": "application/json" } }));
    }
    requests.push({ url, init });
    for (const handler of handlers) {
      const response = handler(url, init);
      if (response) return Promise.resolve(response);
    }
    return Promise.resolve(new Response(JSON.stringify({
      error: { code: "UNHANDLED", message: `No handler for ${url}`, request_id: "req-fixture",
               retryable: false, details: null } }), { status: 500 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return requests;
}

function sessionResponse(status: "anonymous" | "authenticated"): Response {
  return status === "anonymous"
    ? new Response(null, { status: 401 })
    : jsonResponse({ subject: "77777777-7777-4777-8777-777777777777", display_name: "Fixture" });
}

beforeEach(() => {
  routerPush.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function renderAction(): Promise<HTMLElement> {
  const { container } = render(<DuplicateReleaseAction slug={SLUG} nextPath="/research" />);
  return container;
}

describe("DuplicateReleaseAction — honest availability", () => {
  it("renders nothing when no release is published for the slug", async () => {
    const requests = mockApi([
      (url) => (url === `/api/publications/${SLUG}` ? new Response(null, { status: 404 }) : undefined),
    ]);
    const container = await renderAction();
    await waitFor(() => {
      expect(requests.some((request) => request.url === `/api/publications/${SLUG}`)).toBe(true);
    });
    // The honest absent state: no CTA, no faked availability, empty DOM.
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while the public API is unreachable (no fake state)", async () => {
    mockApi([
      (url) => (url === `/api/publications/${SLUG}`
        ? new Response(null, { status: 503 })
        : undefined),
    ]);
    const container = await renderAction();
    await waitFor(() => {
      expect(container).toBeEmptyDOMElement();
    });
  });
});

describe("DuplicateReleaseAction — sign-in continuation", () => {
  it("offers the internal sign-in continuation to an anonymous visitor", async () => {
    const requests = mockApi([
      (url) => {
        if (url === `/api/publications/${SLUG}`) return jsonResponse(RELEASE);
        if (url === "/api/auth/session") return sessionResponse("anonymous");
        return undefined;
      },
    ]);
    const container = await renderAction();

    const button = await screen.findByRole("button", { name: "Sign in to save a private copy" });
    expect(button).toBeDefined();
    // The internal `next` payload preserves the public research route only.
    expect(button.getAttribute("type")).toBe("button");
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();

    const user = userEvent.setup();
    await user.click(button);
    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith("/login?next=%2Fresearch");
    });
    expect(requests.every((request) => !request.url.includes("user_id"))).toBe(true);
  });
});

describe("DuplicateReleaseAction — signed-in duplicate dialog", () => {
  it("duplicates the pinned release with an Idempotency-Key and navigates to the copy", async () => {
    const requests = mockApi([
      (url, init) => {
        if (url === `/api/publications/${SLUG}`) return jsonResponse(RELEASE);
        if (url === "/api/auth/session") return sessionResponse("authenticated");
        if (url === `/api/publications/${SLUG}/duplicate` && init.method === "POST") {
          return jsonResponse(CREATED_DOCUMENT, 201);
        }
        return undefined;
      },
    ]);
    const container = await renderAction();

    const openButton = await screen.findByRole("button", { name: "Save a private copy" });
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();

    const user = userEvent.setup();
    await user.click(openButton);
    const dialog = await screen.findByRole("dialog", { name: /save a private copy/i });
    // The dialog pins the release version it READ and pre-fills the title.
    expect(dialog).toHaveTextContent(/version 2/);
    const title = within(dialog).getByLabelText("Title of your private copy");
    expect(title).toHaveValue("Synthetic public release (fixture)");

    await user.clear(title);
    await user.type(title, "My private copy (fixture)");
    await user.click(within(dialog).getByRole("button", { name: "Save private copy" }));

    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith(`/workspace/research/${COPY_ID}`);
    });
    const post = requests.find((request) => request.url === `/api/publications/${SLUG}/duplicate`
      && request.init.method === "POST");
    expect(post).toBeDefined();
    const headers = new Headers(post?.init.headers);
    expect(headers.get("idempotency-key")).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(JSON.parse(String(post?.init.body))).toEqual({
      publication_version: 2,
      title: "My private copy (fixture)",
    });
  });

  it("keeps the dialog open with the API error when the duplicate fails", async () => {
    mockApi([
      (url, init) => {
        if (url === `/api/publications/${SLUG}`) return jsonResponse(RELEASE);
        if (url === "/api/auth/session") return sessionResponse("authenticated");
        if (url === `/api/publications/${SLUG}/duplicate` && init.method === "POST") {
          return jsonResponse({
            error: { code: "REFERENCE_INVALID", message: "A public pin is unavailable",
                     request_id: "req-fixture", retryable: false, details: null },
          }, 422);
        }
        return undefined;
      },
    ]);
    await renderAction();

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Save a private copy" }));
    const dialog = await screen.findByRole("dialog", { name: /save a private copy/i });
    await user.click(within(dialog).getByRole("button", { name: "Save private copy" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("A public pin is unavailable");
    expect(routerPush).not.toHaveBeenCalled();
    expect(await axe(dialog, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("requires a title before submitting", async () => {
    mockApi([
      (url) => {
        if (url === `/api/publications/${SLUG}`) return jsonResponse(RELEASE);
        if (url === "/api/auth/session") return sessionResponse("authenticated");
        return undefined;
      },
    ]);
    await renderAction();

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Save a private copy" }));
    const dialog = await screen.findByRole("dialog", { name: /save a private copy/i });
    await user.clear(within(dialog).getByLabelText("Title of your private copy"));
    await user.click(within(dialog).getByRole("button", { name: "Save private copy" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Give the private copy a title before saving it.");
    expect(routerPush).not.toHaveBeenCalled();
  });
});
