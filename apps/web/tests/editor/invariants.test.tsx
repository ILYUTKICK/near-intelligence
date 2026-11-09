/**
 * NI-061 editor-boundary invariant regressions (synthetic fixtures, visibly
 * labeled). Focused complements to the existing editor suites — they do not
 * re-test the coordinator timing or the renderer internals:
 *
 * 1. A prose draft save must carry every COMMITTED block attr verbatim: the
 *    liveChart's pinned definition/dataset/selection and the dataTable's
 *    authored rows (including exact decimal strings) travel through the real
 *    serializer unchanged, and the un-interacted chart submits no inspection
 *    claim (the server keeps the loaded pins).
 * 2. The If-Match revision chain survives the real autosave: the save after
 *    an acknowledged autosave carries the revision the autosave response
 *    returned (ETag chain, never the stale original).
 * 3. Financial display strings stay strings: a 24-decimal cell renders in
 *    the workbench display path and is byte-identical in the save body JSON
 *    (no Number() coercion anywhere on the editor boundary).
 */
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadDocumentChart } from "@/features/editor/blocks/chart-api";
import { ResearchDocumentEditor } from "@/features/editor/workbench";
import type { CanonicalDocument } from "@/features/editor/canonical";

import { dataset, definition, metric, observation, series, view } from "../ui/renderer/fixtures";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/features/editor/blocks/chart-api", () => ({
  loadDocumentChart: vi.fn(),
}));

const DOC_ID = "22222222-2222-4222-8222-222222222222";
const VERSION_ID = "88888888-8888-4888-8888-888888888888";

const CHART_BLOCK_ID = "44444444-4444-4444-8444-444444444444";
const TABLE_BLOCK_ID = "55555555-5555-4555-8555-555555555555";
const DATASET_ID = "33333333-3333-4333-8333-333333333333";
const DEFINITION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

/** Exact 24-decimal string; any Number() detour would destroy the tail. */
const DECIMAL_CELL = "987654.321098765432109876543210";

const chartSelection = {
  start: "2026-06-01",
  end: "2026-06-04",
  frequency: "day" as const,
  filters: {},
};

const committedChartAttrs = {
  block_id: CHART_BLOCK_ID,
  chart_definition_version_id: DEFINITION_ID,
  mode: "live" as const,
  selection: chartSelection,
  observed_dataset_version_id: DATASET_ID,
  snapshot_id: null,
};

const committedTableAttrs = {
  block_id: TABLE_BLOCK_ID,
  columns: [
    { key: "day", label: "Day (fixture)", type: "date" as const },
    { key: "payouts", label: "Payouts NEAR (fixture)", type: "string" as const },
  ],
  rows: [
    ["2026-06-01", DECIMAL_CELL],
    ["2026-06-02", null],
  ],
};

const committedContext = {
  chart_definition_version_id: DEFINITION_ID,
  dataset_version_id: DATASET_ID,
  selection: chartSelection,
  context_hash: "a".repeat(64),
  renderer_version: "echarts-modular-svg@1",
  metric_definition_versions: [],
  resolved_at: "2026-11-09T00:00:00Z",
};

const chartDefinition = definition({
  id: DEFINITION_ID,
  filter_schema: { type: "object", properties: {}, additionalProperties: false },
});
const chartWindow = { start: "2026-06-01", end: "2026-06-04" };
const chartView = view(
  chartDefinition,
  [series(metric("NEAR", "Synthetic payouts (fixture)", "synthetic-payouts"), [
    observation("2026-06-01", DECIMAL_CELL),
  ], chartWindow)],
  {
    dataset: { ...dataset(chartWindow), id: DATASET_ID },
    selection: { ...chartSelection },
  },
);

const DOC: CanonicalDocument = {
  schema_version: 1,
  type: "doc",
  content: [
    {
      type: "heading",
      attrs: { block_id: "11111111-1111-4111-8111-111111111111", level: 1 },
      content: [{ type: "text", text: "Invariant fixture paper (fixture)" }],
    },
    {
      type: "paragraph",
      attrs: { block_id: "66666666-6666-4666-8666-666666666666" },
      content: [{ type: "text", text: "Committed prose (fixture)" }],
    },
    { type: "liveChart", attrs: committedChartAttrs },
    { type: "dataTable", attrs: committedTableAttrs },
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

function documentResponse(content: unknown, revision: number, resolvedContexts: unknown) {
  return {
    id: DOC_ID,
    title: "Editor invariant fixture",
    revision,
    schema_version: 1,
    current_version_id: VERSION_ID,
    created_at: "2026-11-01T09:00:00Z",
    updated_at: "2026-11-08T00:00:00Z",
    progress: { headings: 1, charts: 1, insights: 0 },
    content,
    resolved_contexts: resolvedContexts,
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
        resolved_contexts: { [CHART_BLOCK_ID]: committedContext },
      },
      document: {
        id: DOC_ID,
        title: "Editor invariant fixture",
        revision,
        schema_version: 1,
        current_version_id: VERSION_ID,
        created_at: "2026-11-01T09:00:00Z",
        updated_at: "2026-11-08T10:00:00Z",
        progress: { headings: 1, charts: 1, insights: 0 },
      },
    },
    201,
    { etag: `"${revision}"` },
  );
}

function mockApi(handlers: Handler[]): CapturedRequest[] {
  const requests: CapturedRequest[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    if (String(input) === "/api/auth/csrf") {
      return Promise.resolve(
        new Response(JSON.stringify({ token: "synthetic-csrf" }),
          { headers: { "content-type": "application/json" } }));
    }
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
    return Promise.resolve(jsonResponse(
      { error: { code: "UNHANDLED", message: `No handler for ${String(input)}`,
                 request_id: "req-fixture", retryable: false } }, 500));
  });
  vi.stubGlobal("fetch", fetchMock);
  return requests;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.mocked(loadDocumentChart).mockResolvedValue(chartView);
});

async function renderReady(handlers: Handler[] = []): Promise<CapturedRequest[]> {
  const requests = mockApi([
    ...handlers,
    (r) => (r.method === "GET" && r.url === `/api/documents/${DOC_ID}`
      ? jsonResponse(documentResponse(DOC, 7, { [CHART_BLOCK_ID]: committedContext }))
      : undefined),
  ]);
  render(<ResearchDocumentEditor documentId={DOC_ID} />);
  await screen.findByRole("textbox", { name: "Research paper editor" });
  return requests;
}

const saves = (requests: CapturedRequest[]) =>
  requests.filter((r) => r.method === "POST" && r.url.endsWith("/versions"));

/** A real editor content change through the NI-039 insert menu. */
async function insertDivider(): Promise<void> {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Insert block" }));
  const menu = await screen.findByRole("menu", { name: "Insert block" });
  await user.click(within(menu).getByRole("menuitem", { name: /Divider/ }));
  await waitFor(() => {
    expect(screen.getByTestId("save-status")).toHaveTextContent(/Unsaved changes/);
  });
}

describe("editor boundary invariants (NI-061)", () => {
  it("carries committed chart and table attrs verbatim through a prose draft save", async () => {
    const requests = await renderReady([
      (r) => (r.method === "POST" && r.url.endsWith("/versions") ? saveSuccess(8) : undefined),
    ]);

    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved .* · Revision 8/);
    });

    expect(saves(requests)).toHaveLength(1);
    const save = saves(requests)[0];
    expect(save.headers["if-match"]).toBe('"7"');
    const body = save.body as {
      schema_version: number;
      content: CanonicalDocument;
      observed_contexts: unknown[];
    };
    expect(body.schema_version).toBe(1);
    // the prose edit added the divider; the committed blocks are unchanged
    const chart = body.content.content.find((node) => node.type === "liveChart");
    const table = body.content.content.find((node) => node.type === "dataTable");
    expect(chart).toBeDefined();
    expect(chart?.attrs).toEqual(committedChartAttrs);
    expect(table).toBeDefined();
    expect(table?.attrs).toEqual(committedTableAttrs);
    // a prose-only save submits no inspection claim of its own: the loaded
    // pins stay on the server, the draft never mints a context
    expect(body.observed_contexts).toEqual([]);
  });

  it("keeps authored decimal cells exact through display and serialization", async () => {
    const requests = await renderReady([
      (r) => (r.method === "POST" && r.url.endsWith("/versions") ? saveSuccess(8) : undefined),
    ]);
    // the authored data table renders the raw string: no grouping, no float
    const block = await screen.findByLabelText("Data table block");
    const cell = within(block).getByRole("cell", { name: DECIMAL_CELL });
    expect(cell.textContent).toBe(DECIMAL_CELL);

    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved .* · Revision 8/);
    });
    const body = saves(requests)[0].body as { content: CanonicalDocument };
    const table = body.content.content.find((node) => node.type === "dataTable");
    const rows = (table?.attrs as { rows: Array<Array<string | null>> }).rows;
    // typed equality already fails on any float round trip: the exact
    // 30-significant-digit tail survives the editor round trip verbatim
    expect(rows).toEqual(committedTableAttrs.rows);
    // and the serialized body carries it as a JSON string, never a number
    expect(JSON.stringify(body)).toContain(`"${DECIMAL_CELL}"`);
    expect(JSON.stringify(body)).not.toContain("987654.32109876543211");
  });

  it("chains If-Match through a real autosave ack to the next save", async () => {
    const requests = await renderReady([
      (r) => (r.method === "POST" && r.url.endsWith("/versions") ? saveSuccess(8) : undefined),
    ]);
    await insertDivider();
    // the real autosave fires on its own (1s idle) with the loaded revision
    await waitFor(() => expect(saves(requests)).toHaveLength(1), { timeout: 3000 });
    expect(saves(requests)[0].headers["if-match"]).toBe('"7"');
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved .* · Revision 8/);
    });

    // the next edit's save must chain from the acknowledged revision 8
    const chainMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
      if (String(input) === "/api/auth/csrf") {
        return Promise.resolve(
          new Response(JSON.stringify({ token: "synthetic-csrf" }),
            { headers: { "content-type": "application/json" } }));
      }
      const headers = (init.headers ?? {}) as Record<string, string>;
      let body: unknown = null;
      if (typeof init.body === "string") {
        try {
          body = JSON.parse(init.body);
        } catch {
          body = init.body;
        }
      }
      const request: CapturedRequest = { method: init.method ?? "GET", url: String(input),
                                          headers, body };
      requests.push(request);
      if (request.method === "POST" && request.url.endsWith("/versions")) {
        return Promise.resolve(saveSuccess(9));
      }
      if (request.method === "GET" && request.url === `/api/documents/${DOC_ID}`) {
        return Promise.resolve(jsonResponse(documentResponse(DOC, 9,
          { [CHART_BLOCK_ID]: committedContext })));
      }
      return Promise.resolve(jsonResponse(
        { error: { code: "UNHANDLED", message: `No handler for ${String(input)}`,
                   request_id: "req-fixture", retryable: false } }, 500));
    });
    vi.stubGlobal("fetch", chainMock);

    await insertDivider();
    await userEvent.click(screen.getByTestId("save-now"));
    await waitFor(() => {
      expect(screen.getByTestId("save-status")).toHaveTextContent(/All changes saved .* · Revision 9/);
    });
    const chained = saves(requests).at(-1);
    expect(chained?.headers["if-match"]).toBe('"8"');
  });
});
