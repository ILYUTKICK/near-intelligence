/**
 * NI-034 chart library and detail navigation tests.
 *
 * Pattern: real (stubbed) fetch → Zod render-boundary validation → render,
 * with every request recorded so tests assert the exact query the pages
 * send. Covers: search/category/cursor reflecting the catalog request;
 * honest drop notes for URL parameters that are never forwarded ("no
 * arbitrary URL fetch fields"); range/filter validation against the
 * definition version's bounded ranges and closed filter schema with honest
 * fallback; version/dataset pinning surviving navigation (URL round-trip);
 * stale/unavailable/404/503/422 states with actionable recovery; the
 * definitions/quality panel; the anonymous sign-in continuation payload
 * (internal /charts path only); accessibility.
 *
 * ALL payloads in this file are synthetic and labeled "(fixture)" — no
 * production or research data.
 */
import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChartDetailPage from "@/app/(public)/charts/[chartId]/page";
import ChartLibraryPage from "@/app/(public)/charts/page";
import {
  chartDetailHref,
  defaultRangeFor,
  isIsoCalendarDate,
  parseSelectionUrl,
  serializeSelectionQuery,
  shiftIsoDate,
  todayUtc,
  windowDays,
} from "@/features/charts/library/selection-url";
import type { SerializedSelection } from "@/features/charts/library/selection-url";
import { isInternalChartPath } from "@/features/charts/library/ChartAuthActions";
import { CatalogSearch } from "@/features/charts/library/CatalogSearch";
import { ChartDetailClient } from "@/features/charts/library/ChartDetailClient";
import type {
  ChartDefinitionResponse,
  ChartViewResponse,
  MetricResponse,
  SeriesResponse,
} from "@/features/charts/renderer/view-types";
import { RENDERER_VERSION } from "@/features/charts/renderer/view-types";
import { observation } from "./renderer/fixtures";

// The web server env contract is loaded lazily on first page render; set the
// documented variables before any render so loadServerEnv resolves them.
process.env.APP_ENV = "test";
process.env.APP_ORIGIN = "http://localhost:3000";
process.env.API_INTERNAL_URL = "http://api.test:8000";

const routerPush = vi.hoisted(() => vi.fn());
const routerReplace = vi.hoisted(() => vi.fn());

/** Mirrors Next.js' notFound(): throws the 404 fallback error with its digest. */
function notFoundMock(): never {
  const error = new Error("NEXT_HTTP_ERROR_FALLBACK;404") as Error & { digest?: string };
  error.digest = "NEXT_HTTP_ERROR_FALLBACK;404";
  throw error;
}

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, replace: routerReplace, refresh: vi.fn() }),
  notFound: notFoundMock,
}));

// -- synthetic fixtures (visibly labeled) ------------------------------------ //

const METRIC_FEES_ID = "22222222-2222-4222-8222-222222222222";
const DATASET_ID = "33333333-3333-4333-8333-333333333333";
const DEFINITION_ID = "44444444-4444-4444-8444-444444444444";
const PINNED_DATASET_ID = "55555555-5555-4555-8555-555555555555";

const SOURCE_FILTER_SCHEMA = {
  type: "object",
  properties: { source: { type: "string", enum: ["SRC-LLAMA", "SRC-DASHBOARD"] } },
  additionalProperties: false,
};

function metricFixture(
  id: string,
  metricId: string,
  unit: string,
  availability: MetricResponse["availability"] = "P",
): MetricResponse {
  return {
    id,
    metric_id: metricId,
    version: 1,
    title: `Synthetic ${metricId} (fixture)`,
    definition: "Synthetic metric definition (fixture).",
    formula: `${metricId}_daily_sum (fixture)`,
    unit,
    frequency: "daily",
    source_id: "SRC-FIXTURE",
    economic_scope: "Synthetic scope (fixture).",
    availability,
    limitations: ["Synthetic fixture limitation — never published data."],
  };
}

function definitionFixture(
  overrides: Partial<ChartDefinitionResponse> = {},
): ChartDefinitionResponse {
  return {
    id: DEFINITION_ID,
    chart_id: "gross-fees",
    version: 1,
    title: "Synthetic gross fees (fixture)",
    description: "Synthetic chart description (fixture).",
    category: "fees",
    metric_definition_ids: [METRIC_FEES_ID],
    visualization_type: "bar",
    units: { required_primary: "USD" },
    filter_schema: SOURCE_FILTER_SCHEMA,
    available_ranges: { presets_days: [7, 30, 90], max_days: 366 },
    renderer_version: RENDERER_VERSION,
    update_frequency: "daily",
    data_status: "available",
    unavailable_reason: null,
    source_lineage: {
      sources: ["SRC-FIXTURE"],
      note: "Synthetic lineage note (fixture).",
    },
    ...overrides,
  };
}

function datasetFixture(window: { start: string; end: string }) {
  return {
    id: DATASET_ID,
    dataset_key: "synthetic-fixture-dataset",
    version: 1,
    status: "approved" as const,
    start: window.start,
    end: window.end,
    source_as_of: "2026-11-06T00:00:00Z",
    retrieved_at: "2026-11-06T06:00:00Z",
    pipeline_version: "synthetic-pipeline@1 (fixture)",
    content_sha256: "a".repeat(64),
    quality: {
      status: "ok" as const,
      bound_kind: null,
      reasons: [],
      coverage: { observed: 5, expected: 5 },
      freshness_target_seconds: 86_400,
    },
    manifest_url: null,
    supersedes_id: null,
  };
}

function seriesFixture(
  metric: MetricResponse,
  window: { start: string; end: string },
  filters: Record<string, string> = {},
): SeriesResponse {
  return {
    metric,
    dataset: datasetFixture(window),
    selection: { start: window.start, end: window.end, frequency: "day", filters },
    points: [
      observation(window.start, "1000"),
      observation(shiftIsoDate(window.start, 1), null),
      observation(shiftIsoDate(window.start, 2), "3000"),
    ],
    sources: [{
      id: "SRC-FIXTURE",
      name: "Synthetic fixture source (test fixture)",
      docs_url: "https://docs.example.test/fixture",
      verified_at: null,
      license_status: "verified" as const,
      access_status: "documented" as const,
      lineage: ["fixture step: synthetic"],
      expected_update_frequency: null,
      last_success_at: null,
    }],
  };
}

function viewFixture(
  definition: ChartDefinitionResponse,
  selection: { start: string; end: string; filters?: Record<string, string> },
): ChartViewResponse {
  const series = seriesFixture(
    metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD"),
    selection,
    selection.filters ?? {},
  );
  return {
    definition,
    selection: series.selection,
    dataset: series.dataset,
    series: [series],
    resolved_at: "2026-11-06T12:00:00Z",
    context_hash: "b".repeat(64),
    quality: {
      status: "ok",
      bound_kind: null,
      reasons: [],
      coverage: { observed: 5, expected: 5 },
      freshness_target_seconds: 86_400,
    },
  };
}

const VIEW_WINDOW = { start: "2026-11-01", end: "2026-11-06" };

// -- fetch mock infrastructure ------------------------------------------------ //

interface RecordedRequest {
  url: URL;
  init: RequestInit;
}

function jsonResponse(body: unknown, status = 200): Response {
  return Response.json(body, { status });
}

function apiError(code: string, message: string, retryable = false, status = 500): Response {
  return jsonResponse(
    { error: { code, message, request_id: "req-fixture", retryable, details: null } },
    status,
  );
}

function installApiMock(routes: Array<(url: URL) => Response | undefined>): RecordedRequest[] {
  const requests: RecordedRequest[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    // openapi-fetch passes a Request object; extract its URL for matching.
    const url = input instanceof Request ? new URL(input.url) : new URL(String(input), "http://localhost");
    requests.push({ url, init });
    for (const handler of routes) {
      const response = handler(url);
      if (response) {
        return Promise.resolve(response);
      }
    }
    return Promise.resolve(apiError("UNHANDLED", `no mock route for ${url.pathname}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return requests;
}

function requestsTo(requests: RecordedRequest[], pathname: string): URL[] {
  return requests.filter((request) => request.url.pathname === pathname).map((r) => r.url);
}

function sessionRoute(response: Response) {
  return (url: URL) => (url.pathname === "/api/auth/session" ? response : undefined);
}

const ANONYMOUS_SESSION = sessionRoute(
  jsonResponse({ error: { code: "UNAUTHORIZED", message: "No valid session.", request_id: "req-fixture", retryable: false, details: null } }, 401),
);
const AUTHENTICATED_SESSION = sessionRoute(
  jsonResponse({ status: "ok", subject: "fixture-user", expiresAt: "2026-11-09T00:00:00Z" }),
);

function chartRoute(chartId: string, definition: ChartDefinitionResponse, status = 200) {
  return (url: URL) =>
    url.pathname === `/api/charts/${chartId}`
      ? jsonResponse(definition, status)
      : undefined;
}

function metricRoute(metric: MetricResponse) {
  return (url: URL) =>
    url.pathname === `/api/metrics/${metric.id}` ? jsonResponse(metric) : undefined;
}

function viewRoute(
  chartId: string,
  respond: (url: URL) => Response,
) {
  return (url: URL) =>
    url.pathname === `/api/charts/${chartId}/view` ? respond(url) : undefined;
}

/** The pinned selection used across detail-page tests. */
function pinnedSelection(overrides: Partial<SerializedSelection> = {}): SerializedSelection {
  return {
    version: 1,
    start: VIEW_WINDOW.start,
    end: VIEW_WINDOW.end,
    datasetVersion: "latest",
    filters: {},
    ...overrides,
  };
}

type SearchValues = Record<string, string | string[] | undefined>;

beforeEach(() => {
  routerPush.mockReset();
  routerReplace.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const axeConfig = { rules: { region: { enabled: false } } };

// -- selection-url (pure validation) ------------------------------------------ //

describe("selection-url — the single gate between URL and fetch", () => {
  const definition = definitionFixture();

  it("parses a fully pinned selection: version, range, dataset version and filters", () => {
    const parsed = parseSelectionUrl(
      new URLSearchParams(
        `version=1&start=${VIEW_WINDOW.start}&end=${VIEW_WINDOW.end}&dataset_version=${PINNED_DATASET_ID}&filters=${encodeURIComponent('{"source":"SRC-LLAMA"}')}`,
      ),
      definition,
    );
    expect(parsed.version).toBe(1);
    expect(parsed.datasetVersion).toBe(PINNED_DATASET_ID);
    expect(parsed.range).toEqual(VIEW_WINDOW);
    expect(parsed.filters).toEqual({ source: "SRC-LLAMA" });
    expect(parsed.dropped).toEqual([]);
  });

  it("drops every unapproved URL parameter with an honest reason", () => {
    const parsed = parseSelectionUrl(
      new URLSearchParams("version=1&start=2026-11-01&end=2026-11-06&foo=bar&api_key=secret"),
      definition,
    );
    expect(parsed.dropped.map((item) => item.param).sort()).toEqual(["api_key", "foo"]);
    expect(parsed.dropped.every((item) => item.reason.includes("not sent to the chart API"))).toBe(true);
  });

  it("reports conflicting duplicate values instead of picking one silently", () => {
    const parsed = parseSelectionUrl(
      new URLSearchParams("version=1&start=2026-11-01&start=2026-11-02&end=2026-11-06"),
      definition,
    );
    expect(parsed.range).toBeNull();
    expect(parsed.dropped.some((item) => item.param === "start" && item.reason.includes("conflicting"))).toBe(true);
  });

  it("validates the range against the version's bounded max and names the fallback preset", () => {
    const parsed = parseSelectionUrl(
      new URLSearchParams("start=2025-10-01&end=2026-11-06"), // 401 days > 366
      definition,
    );
    expect(parsed.range).toBeNull();
    expect(parsed.dropped.filter((item) => item.param === "start")).toHaveLength(1);
    expect(parsed.dropped[0].reason).toContain("at most 366");
    expect(parsed.dropped[0].reason).toContain("90 days");
  });

  it("rejects malformed dates and empty windows", () => {
    for (const query of [
      "start=2026-02-30&end=2026-11-06",
      "start=nonsense&end=2026-11-06",
      `start=${VIEW_WINDOW.end}&end=${VIEW_WINDOW.start}`,
      `start=${VIEW_WINDOW.start}&end=${VIEW_WINDOW.start}`,
    ]) {
      const parsed = parseSelectionUrl(new URLSearchParams(query), definition);
      expect(parsed.range).toBeNull();
      expect(parsed.dropped.length).toBeGreaterThan(0);
    }
  });

  it("accepts only approved filter keys and values from the closed schema", () => {
    const parsed = parseSelectionUrl(
      new URLSearchParams(
        `filters=${encodeURIComponent('{"source":"SRC-LLAMA","wallet":"x"}')}`,
      ),
      definition,
    );
    expect(parsed.filters).toEqual({ source: "SRC-LLAMA" });
    expect(parsed.dropped.map((item) => item.param)).toEqual(["filters.wallet"]);
    expect(parsed.dropped[0].reason).toContain("not supported by this chart version");

    const unlistedValue = parseSelectionUrl(
      new URLSearchParams(`filters=${encodeURIComponent('{"source":"SRC-NOPE"}')}`),
      definition,
    );
    expect(unlistedValue.filters).toEqual({});
    expect(unlistedValue.dropped[0].reason).toContain("not an approved option");
  });

  it("drops any filter on a chart version with an empty filter domain", () => {
    const unfiltered = definitionFixture({ filter_schema: { type: "object", properties: {}, additionalProperties: false } });
    const parsed = parseSelectionUrl(
      new URLSearchParams(`filters=${encodeURIComponent('{"source":"SRC-LLAMA"}')}`),
      unfiltered,
    );
    expect(parsed.filters).toEqual({});
    expect(parsed.dropped[0].reason).toContain("registers no filters");
  });

  it("drops invalid JSON and non-object filter documents", () => {
    for (const raw of ["{not json", '["source"]', "42"]) {
      const parsed = parseSelectionUrl(
        new URLSearchParams(`filters=${encodeURIComponent(raw)}`),
        definition,
      );
      expect(parsed.filters).toEqual({});
      expect(parsed.dropped[0].param).toBe("filters");
    }
  });

  it("drops malformed version and dataset_version values", () => {
    const parsed = parseSelectionUrl(
      new URLSearchParams("version=0&dataset_version=not-a-uuid"),
      definition,
    );
    expect(parsed.version).toBeNull();
    expect(parsed.datasetVersion).toBeNull();
    expect(parsed.dropped.map((item) => item.param).sort()).toEqual(["dataset_version", "version"]);
  });

  it("round-trips through serialization so version/range/filters survive navigation", () => {
    const selection = pinnedSelection({
      filters: { source: "SRC-DASHBOARD" },
      datasetVersion: PINNED_DATASET_ID,
    });
    const query = serializeSelectionQuery(selection);
    expect(query).toBe(
      `version=1&start=${VIEW_WINDOW.start}&end=${VIEW_WINDOW.end}`
      + `&dataset_version=${PINNED_DATASET_ID}&filters=${encodeURIComponent('{"source":"SRC-DASHBOARD"}')}`,
    );
    const reparsed = parseSelectionUrl(new URLSearchParams(query), definition);
    expect(reparsed.version).toBe(1);
    expect(reparsed.range).toEqual(VIEW_WINDOW);
    expect(reparsed.datasetVersion).toBe(PINNED_DATASET_ID);
    expect(reparsed.filters).toEqual({ source: "SRC-DASHBOARD" });
    expect(reparsed.dropped).toEqual([]);
    // The internal continuation URL stays an internal path.
    expect(chartDetailHref("gross-fees", selection)).toBe(`/charts/gross-fees?${query}`);
    expect(chartDetailHref("gross-fees", selection).startsWith("/charts/")).toBe(true);
  });

  it("serializes sorted filter keys deterministically", () => {
    const query = serializeSelectionQuery(
      pinnedSelection({ filters: { source: "SRC-LLAMA", price_basis: "end_of_day" } }),
    );
    expect(query).toContain(encodeURIComponent('{"price_basis":"end_of_day","source":"SRC-LLAMA"}'));
  });

  it("anchors the default range to the provided end with the largest preset", () => {
    expect(defaultRangeFor(definition, "2026-11-05")).toEqual({ start: "2026-08-07", end: "2026-11-05" });
    expect(windowDays("2026-08-07", "2026-11-05")).toBe(90);
    expect(isIsoCalendarDate("2026-11-05")).toBe(true);
    expect(isIsoCalendarDate("2026-02-30")).toBe(false);
    expect(shiftIsoDate("2026-11-01", 5)).toBe("2026-11-06");
  });

  it("guards the internal continuation path against open-redirect payloads", () => {
    expect(isInternalChartPath("/charts/gross-fees?version=1")).toBe(true);
    expect(isInternalChartPath("//evil.example/charts")).toBe(false);
    expect(isInternalChartPath("https://evil.example/charts")).toBe(false);
    expect(isInternalChartPath("/charts\\evil")).toBe(false);
    expect(isInternalChartPath("/workspace/documents")).toBe(false);
  });
});

// -- chart library page (/charts) --------------------------------------------- //

describe("Chart library page — the catalog request reflects the URL", () => {
  const items = [
    definitionFixture({
      chart_id: "intents-volume",
      title: "Synthetic intents volume (fixture)",
      category: "activity",
      visualization_type: "area",
    }),
    definitionFixture({
      chart_id: "model-diagnostics",
      title: "Synthetic model diagnostics (fixture)",
      category: "model",
      data_status: "unavailable",
      unavailable_reason: "Model gate (fixture): no published model artifact exists yet.",
      metric_definition_ids: [],
    }),
  ];

  function catalogResponse(nextCursor: string | null) {
    return jsonResponse({ items, next_cursor: nextCursor });
  }

  async function renderLibrary(searchParams: SearchValues) {
    const ui = await ChartLibraryPage({ searchParams: Promise.resolve(searchParams) });
    return render(ui);
  }

  it("sends exactly the validated q/category/cursor parameters to the catalog API", async () => {
    const requests = installApiMock([
      (url) => (url.pathname === "/api/charts" ? catalogResponse(null) : undefined),
    ]);
    await renderLibrary({ q: " fees ", category: "fees", cursor: "MTA" });

    const catalogRequests = requestsTo(requests, "/api/charts");
    expect(catalogRequests).toHaveLength(1);
    expect([...catalogRequests[0].searchParams.keys()]).toEqual(["q", "category", "cursor"]);
    expect(catalogRequests[0].searchParams.get("q")).toBe("fees");
    expect(catalogRequests[0].searchParams.get("category")).toBe("fees");
    expect(catalogRequests[0].searchParams.get("cursor")).toBe("MTA");
    expect(await screen.findByRole("link", { name: "Open chart: Synthetic intents volume (fixture)" })).toHaveAttribute(
      "href",
      "/charts/intents-volume",
    );
  });

  it("sends no request field for unapproved URL parameters and says so", async () => {
    const requests = installApiMock([
      (url) => (url.pathname === "/api/charts" ? catalogResponse(null) : undefined),
    ]);
    await renderLibrary({ foo: "bar", category: "politics", sort: "asc" });

    const catalogRequests = requestsTo(requests, "/api/charts");
    expect(catalogRequests).toHaveLength(1);
    expect([...catalogRequests[0].searchParams.keys()]).toEqual([]);
    const status = screen.getByRole("status");
    expect(within(status).getByText("foo")).toBeInTheDocument();
    expect(within(status).getByText("category")).toBeInTheDocument();
    expect(within(status).getByText(/category must be one of/)).toBeInTheDocument();
  });

  it("drops an unrecognized pagination cursor and shows the first page", async () => {
    const requests = installApiMock([
      (url) => (url.pathname === "/api/charts" ? catalogResponse(null) : undefined),
    ]);
    await renderLibrary({ cursor: "###bad###" });
    expect(requestsTo(requests, "/api/charts")[0].searchParams.get("cursor")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("pagination cursor was not recognized");
  });

  it("renders every catalog card with its honest data status, unavailable included", async () => {
    installApiMock([(url) => (url.pathname === "/api/charts" ? catalogResponse("MTA") : undefined)]);
    await renderLibrary({});

    expect(await screen.findByRole("heading", { name: "Synthetic intents volume (fixture)" })).toBeInTheDocument();
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByText("Unavailable — this is not zero")).toBeInTheDocument();
    expect(screen.getByText(/Reason: Model gate \(fixture\)/)).toBeInTheDocument();
    expect(screen.getAllByText(/Units: USD/).length).toBe(2);
    const next = screen.getByRole("link", { name: "Next page" });
    expect(new URL(next.getAttribute("href") ?? "", "http://localhost").searchParams.get("cursor")).toBe("MTA");
  });

  it("shows an honest empty state instead of placeholder charts", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/charts"
          ? jsonResponse({ items: [], next_cursor: null })
          : undefined,
    ]);
    await renderLibrary({ q: "nothing matches" });
    expect(await screen.findByText("Nothing to show")).toBeInTheDocument();
    expect(screen.getByText(/No registered chart matches this search/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Clear search and filters" })).toHaveAttribute("href", "/charts");
  });

  it("renders a catalog failure honestly with a retry that preserves the query", async () => {
    installApiMock([(url) => (url.pathname === "/api/charts" ? apiError("DEPENDENCY_UNAVAILABLE", "The chart API is unavailable", true, 503) : undefined)]);
    await renderLibrary({ category: "fees" });

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/catalog could not be loaded/)).toBeInTheDocument();
    expect(within(alert).getByText(/unavailable right now/)).toBeInTheDocument();
    const retry = within(alert).getByRole("link", { name: "Try again" });
    expect(new URL(retry.getAttribute("href") ?? "", "http://localhost").searchParams.get("category")).toBe("fees");
  });

  it("fails honestly when the payload does not match the generated contract", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/charts"
          ? jsonResponse({ items: [{ chart_id: "broken" }], next_cursor: null })
          : undefined,
    ]);
    await renderLibrary({});
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/catalog could not be loaded/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Open chart/ })).not.toBeInTheDocument();
    expect(screen.queryByText("broken")).not.toBeInTheDocument();
  });

  it("passes axe on the loaded catalog", async () => {
    installApiMock([(url) => (url.pathname === "/api/charts" ? catalogResponse(null) : undefined)]);
    const { container } = await renderLibrary({});
    await screen.findByRole("heading", { name: "Synthetic intents volume (fixture)" });
    expect(await axe(container, axeConfig)).toHaveNoViolations();
  });

  it("search submits push the query into the URL and keep the active category", async () => {
    const user = userEvent.setup();
    render(<CatalogSearch initialQuery="fees" category="fees" />);
    const input = screen.getByLabelText("Search charts");
    await user.clear(input);
    await user.type(input, "supply");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(routerPush).toHaveBeenCalledWith("/charts?q=supply&category=fees");
  });

  it("search without a query clears the query parameter entirely", async () => {
    const user = userEvent.setup();
    render(<CatalogSearch initialQuery="fees" category={null} />);
    await user.clear(screen.getByLabelText("Search charts"));
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(routerPush).toHaveBeenCalledWith("/charts");
  });
});

// -- chart detail page (/charts/{chartId}) ------------------------------------- //

describe("Chart detail page — validated selection URLs", () => {
  const definition = definitionFixture();
  const viewPayload = viewFixture(definition, VIEW_WINDOW);

  function detailRoutes(extraRoutes: Array<(url: URL) => Response | undefined> = [], session = ANONYMOUS_SESSION) {
    return [
      chartRoute("gross-fees", definition),
      metricRoute(
        metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD"),
      ),
      viewRoute("gross-fees", (url) => {
        const requestStart = url.searchParams.get("start");
        const requestEnd = url.searchParams.get("end");
        return jsonResponse(
          viewPayload.series[0].selection.start === requestStart && viewPayload.series[0].selection.end === requestEnd
            ? viewPayload
            : viewFixture(definition, {
                start: requestStart ?? VIEW_WINDOW.start,
                end: requestEnd ?? VIEW_WINDOW.end,
              }),
        );
      }),
      session,
      ...extraRoutes,
    ];
  }

  async function renderDetail(searchParams: SearchValues, chartId = "gross-fees") {
    const ui = await ChartDetailPage({
      params: Promise.resolve({ chartId }),
      searchParams: Promise.resolve(searchParams),
    });
    return render(ui);
  }

  it("pins version and range from the URL into the view request and renders the chart", async () => {
    const requests = installApiMock(detailRoutes());
    await renderDetail({ version: "1", start: VIEW_WINDOW.start, end: VIEW_WINDOW.end });

    const viewRequests = requestsTo(requests, "/api/charts/gross-fees/view");
    expect(viewRequests).toHaveLength(1);
    expect([...viewRequests[0].searchParams.keys()]).toEqual(["definition_version", "start", "end"]);
    expect(viewRequests[0].searchParams.get("definition_version")).toBe("1");
    expect(viewRequests[0].searchParams.get("start")).toBe(VIEW_WINDOW.start);
    expect(viewRequests[0].searchParams.get("end")).toBe(VIEW_WINDOW.end);

    // The renderer resolved the pinned view: accessible table and frame.
    expect(await screen.findByRole("region", { name: /exact data table/ })).toBeInTheDocument();
    expect(screen.getByText(/Definition version v1 \(pinned in the URL\)/)).toBeInTheDocument();
    expect(screen.getByText("Live — latest approved data")).toBeInTheDocument();
    // Session checked for the continuation actions; anonymous buttons render.
    expect(await screen.findByRole("button", { name: "Sign in to save this chart" })).toBeInTheDocument();
  });

  it("never forwards an arbitrary URL field to the view request and reports the drops", async () => {
    const requests = installApiMock(detailRoutes());
    await renderDetail({
      version: "1",
      start: VIEW_WINDOW.start,
      end: VIEW_WINDOW.end,
      foo: "bar",
      admin: "true",
    });

    const viewRequests = requestsTo(requests, "/api/charts/gross-fees/view");
    expect([...viewRequests[0].searchParams.keys()]).toEqual(["definition_version", "start", "end"]);
    const status = await screen.findByRole("status");
    expect(within(status).getByText("foo")).toBeInTheDocument();
    expect(within(status).getByText("admin")).toBeInTheDocument();
    expect(within(status).getAllByText(/unsupported URL parameter/).length).toBe(2);
  });

  it("falls back honestly when the URL range exceeds the version's bound", async () => {
    const requests = installApiMock(detailRoutes());
    await renderDetail({ version: "1", start: "2025-10-01", end: "2026-11-06" });

    const viewRequests = requestsTo(requests, "/api/charts/gross-fees/view");
    // The fallback is the version's default preset anchored to today (UTC).
    const expectedEnd = todayUtc();
    const expectedStart = shiftIsoDate(expectedEnd, -90);
    expect(viewRequests[0].searchParams.get("start")).toBe(expectedStart);
    expect(viewRequests[0].searchParams.get("end")).toBe(expectedEnd);
    expect(viewRequests[0].searchParams.get("definition_version")).toBe("1");

    const status = await screen.findByRole("status");
    // start and end both carry the fallback note.
    expect(within(status).getAllByText(/at most 366/).length).toBe(2);
    expect(within(status).getAllByText(/90 days/).length).toBe(2);
  });

  it("forwards only schema-approved filters and drops the rest with reasons", async () => {
    const requests = installApiMock(detailRoutes());
    await renderDetail({
      version: "1",
      start: VIEW_WINDOW.start,
      end: VIEW_WINDOW.end,
      filters: '{"source":"SRC-LLAMA","wallet":"x"}',
    });

    const viewRequests = requestsTo(requests, "/api/charts/gross-fees/view");
    expect(viewRequests[0].searchParams.get("filters")).toBe('{"source":"SRC-LLAMA"}');
    const status = await screen.findByRole("status");
    expect(within(status).getByText("filters.wallet")).toBeInTheDocument();
    expect(within(status).getByText(/not supported by this chart version/)).toBeInTheDocument();
  });

  it("states honestly when a chart version registers no filters and drops URL filters", async () => {
    const unfilteredDefinition = definitionFixture({
      filter_schema: { type: "object", properties: {}, additionalProperties: false },
    });
    installApiMock([
      chartRoute("gross-fees", unfilteredDefinition),
      metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      viewRoute("gross-fees", () => jsonResponse(viewFixture(unfilteredDefinition, VIEW_WINDOW))),
      ANONYMOUS_SESSION,
    ]);
    await renderDetail({
      version: "1",
      start: VIEW_WINDOW.start,
      end: VIEW_WINDOW.end,
      filters: '{"source":"SRC-LLAMA"}',
    });

    expect(await screen.findByText(/No filters are registered for this chart version/)).toBeInTheDocument();
    const status = screen.getByRole("status");
    expect(within(status).getByText(/registers no filters/)).toBeInTheDocument();
  });

  it("pins a historical dataset version and renders the historical mode", async () => {
    const requests = installApiMock([
      chartRoute("gross-fees", definition),
      metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      viewRoute("gross-fees", () => jsonResponse(viewFixture(definition, VIEW_WINDOW))),
      (url) => {
        if (url.pathname === `/api/datasets/${PINNED_DATASET_ID}`) {
          return jsonResponse(datasetFixture({ start: "2026-08-07", end: "2026-11-05" }));
        }
        return undefined;
      },
      ANONYMOUS_SESSION,
    ]);
    await renderDetail({
      version: "1",
      start: VIEW_WINDOW.start,
      end: VIEW_WINDOW.end,
      dataset_version: PINNED_DATASET_ID,
    });

    const viewRequests = requestsTo(requests, "/api/charts/gross-fees/view");
    expect(viewRequests[0].searchParams.get("dataset_version")).toBe(PINNED_DATASET_ID);
    await screen.findByText("Historical — pinned version");
  });

  it("anchors a missing range to the pinned dataset's coverage end, never wall-clock", async () => {
    const requests = installApiMock([
      chartRoute("gross-fees", definition),
      metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      viewRoute("gross-fees", (url) => {
        const requestStart = url.searchParams.get("start");
        const requestEnd = url.searchParams.get("end");
        return jsonResponse(
          viewFixture(definition, { start: requestStart ?? VIEW_WINDOW.start, end: requestEnd ?? VIEW_WINDOW.end }),
        );
      }),
      (url) =>
        url.pathname === `/api/datasets/${PINNED_DATASET_ID}`
          ? jsonResponse(datasetFixture({ start: "2026-08-07", end: "2026-11-05" }))
          : undefined,
      ANONYMOUS_SESSION,
    ]);
    await renderDetail({ version: "1", dataset_version: PINNED_DATASET_ID });
    const viewRequests = requestsTo(requests, "/api/charts/gross-fees/view");
    expect(viewRequests[0].searchParams.get("start")).toBe("2026-08-07");
    expect(viewRequests[0].searchParams.get("end")).toBe("2026-11-05");
    expect(viewRequests[0].searchParams.get("dataset_version")).toBe(PINNED_DATASET_ID);
    expect(await screen.findByText(/coverage end \(2026-11-05 UTC\)/)).toBeInTheDocument();
    expect(screen.getByText("Historical — pinned version")).toBeInTheDocument();
  });

  it("renders an unavailable chart with its reason and never requests a view", async () => {
    const gated = definitionFixture({
      chart_id: "model-diagnostics",
      title: "Synthetic model diagnostics (fixture)",
      category: "model",
      data_status: "unavailable",
      unavailable_reason: "Model gate (fixture): no published model artifact exists yet.",
      metric_definition_ids: [],
    });
    const requests = installApiMock([
      chartRoute("model-diagnostics", gated),
      ANONYMOUS_SESSION,
    ]);
    await renderDetail({}, "model-diagnostics");

    expect(await screen.findByText(/Unavailable — this is not zero/)).toBeInTheDocument();
    // The gate reason is rendered by both the renderer's unavailable state
    // and the definitions panel.
    expect(screen.getAllByText(/Model gate \(fixture\)/).length).toBeGreaterThan(0);
    expect(requestsTo(requests, "/api/charts/model-diagnostics/view")).toHaveLength(0);
    // Definitions stay fully visible for an unavailable chart.
    expect(screen.getByText("Definition, dataset and quality")).toBeInTheDocument();
    expect(screen.getByText(/Unavailable — Model gate \(fixture\)/)).toBeInTheDocument();
    expect(screen.getByText(/No dataset is pinned for this chart right now/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sign in to save this chart" })).not.toBeInTheDocument();
  });

  it("renders a data-not-ready resolution honestly with retry and methodology actions", async () => {
    installApiMock([
      chartRoute("gross-fees", definition),
      metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      viewRoute("gross-fees", () =>
        apiError("DATA_NOT_READY", "no approved dataset exists for latest", true, 503)),
      ANONYMOUS_SESSION,
    ]);
    await renderDetail({ version: "1", start: VIEW_WINDOW.start, end: VIEW_WINDOW.end });

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/No approved dataset is ready/)).toBeInTheDocument();
    expect(within(alert).getByText(/this is not zero/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: "Try again" })).toHaveAttribute(
      "href",
      "/charts/gross-fees?version=1",
    );
    expect(within(alert).getByRole("link", { name: "How this data is collected" })).toHaveAttribute(
      "href",
      "/methodology#collection",
    );
    // No fake loading state next to the failure.
    expect(screen.queryByText("Loading chart data")).not.toBeInTheDocument();
  });

  it("recovers from a server-rejected selection with a reset action", async () => {
    installApiMock([
      chartRoute("gross-fees", definition),
      metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      viewRoute("gross-fees", () =>
        apiError("FILTER_UNSUPPORTED", "Filters or range are not supported by this version", false, 422)),
      ANONYMOUS_SESSION,
    ]);
    await renderDetail({ version: "1", start: VIEW_WINDOW.start, end: VIEW_WINDOW.end });

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/rejected this selection as unsupported/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: "Reset to the default selection" })).toHaveAttribute(
      "href",
      "/charts/gross-fees?version=1",
    );
  });

  it("answers an unknown chart or version with the 404 boundary", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/charts/gross-fees"
          ? apiError("NOT_FOUND", "Resource was not found", false, 404)
          : undefined,
    ]);
    await expect(
      ChartDetailPage({
        params: Promise.resolve({ chartId: "gross-fees" }),
        searchParams: Promise.resolve({}),
      }),
    ).rejects.toMatchObject({ digest: "NEXT_HTTP_ERROR_FALLBACK;404" });
  });

  it("shows the definitions/quality panel with metric availability in words", async () => {
    installApiMock(detailRoutes());
    await renderDetail({ version: "1", start: VIEW_WINDOW.start, end: VIEW_WINDOW.end });

    await screen.findByRole("region", { name: /exact data table/ });
    const panel = screen.getByRole("region", { name: /Definition, dataset and quality/ });
    expect(within(panel).getByText("Chart definition")).toBeInTheDocument();
    expect(within(panel).getAllByText("v1 (immutable)").length).toBeGreaterThan(0);
    expect(within(panel).getByText(DEFINITION_ID)).toBeInTheDocument();
    expect(within(panel).getByText(/presets 7, 30, 90 days; at most 366 days per view/)).toBeInTheDocument();
    // Availability code P rendered in words, never as a bare letter.
    expect(within(panel).getByText("Provider-reported")).toBeInTheDocument();
    expect(
      within(panel).getByText(/Saved provider-reported data; source-qualified and revisable/),
    ).toBeInTheDocument();
    expect(within(panel).getByText(/provider_gross_fees_usd_daily_sum \(fixture\)/)).toBeInTheDocument();
    expect(within(panel).getByText("Synthetic fixture limitation — never published data.")).toBeInTheDocument();
    // Resolved dataset provenance (the dd mixes span and text children, so
    // the match runs on the whole textContent — the renderer-test pattern).
    expect(
      within(panel).getByText((_, element) => element?.textContent === "synthetic-fixture-dataset v1 (approved)"),
    ).toBeInTheDocument();
    expect(within(panel).getByText("5 of 5 expected periods")).toBeInTheDocument();
    expect(within(panel).getAllByText("2026-11-06T00:00:00Z").length).toBeGreaterThan(0);
    expect(within(panel).getByText("a".repeat(64))).toBeInTheDocument();
    // Methodology anchors.
    expect(within(panel).getByRole("link", { name: "metric definitions" })).toHaveAttribute(
      "href",
      "/methodology#definitions",
    );
    expect(within(panel).getByRole("link", { name: "collection and cleaning" })).toHaveAttribute(
      "href",
      "/methodology#collection",
    );
  });

  it("renders a metric that failed to resolve as unavailable, not guessed", async () => {
    installApiMock([
      chartRoute("gross-fees", definition),
      (url) =>
        url.pathname === `/api/metrics/${METRIC_FEES_ID}`
          ? apiError("NOT_FOUND", "Resource was not found", false, 404)
          : undefined,
      viewRoute("gross-fees", () => jsonResponse(viewFixture(definition, VIEW_WINDOW))),
      ANONYMOUS_SESSION,
    ]);
    await renderDetail({ version: "1", start: VIEW_WINDOW.start, end: VIEW_WINDOW.end });
    const panel = await screen.findByRole("region", { name: /Definition, dataset and quality/ });
    expect(within(panel).getByText(/availability is not guessed/)).toBeInTheDocument();
    expect(within(panel).getByText(METRIC_FEES_ID)).toBeInTheDocument();
  });

  it("passes axe on the resolved chart page", async () => {
    installApiMock(detailRoutes());
    const { container } = await renderDetail({ version: "1", start: VIEW_WINDOW.start, end: VIEW_WINDOW.end });
    await screen.findByRole("region", { name: /exact data table/ });
    expect(await axe(container, axeConfig)).toHaveNoViolations();
  });
});

// -- URL-syncing detail island and continuation -------------------------------- //

describe("ChartDetailClient — selection survives navigation through the URL", () => {
  const definition = definitionFixture();
  const viewPayload = viewFixture(definition, VIEW_WINDOW);
  const baseSelection = pinnedSelection();

  function renderClient(selection = baseSelection) {
    return render(
      <ChartDetailClient
        chartId="gross-fees"
        definition={definition}
        view={viewPayload}
        selection={selection}
        dropped={[]}
      />,
    );
  }

  it("writes preset range changes back to the URL with the pinned version and filters", async () => {
    const user = userEvent.setup();
    const { unmount } = renderClient(pinnedSelection({ filters: { source: "SRC-LLAMA" } }));
    await screen.findByRole("region", { name: /exact data table/ });

    await user.click(within(screen.getByRole("group", { name: "Time range" })).getByRole("button", { name: "Last 30 days" }));
    expect(routerReplace).toHaveBeenCalledTimes(1);
    const [href] = routerReplace.mock.calls[0];
    expect(href).toBe(
      `/charts/gross-fees?version=1&start=2026-10-07&end=${VIEW_WINDOW.end}`
      + `&filters=${encodeURIComponent('{"source":"SRC-LLAMA"}')}`,
    );
    unmount();
  });

  it("applies a custom range only when it satisfies the version bound", async () => {
    const user = userEvent.setup();
    const { unmount } = renderClient();
    await screen.findByRole("region", { name: /exact data table/ });
    await user.click(screen.getByRole("button", { name: "Custom range" }));

    const startInput = screen.getByLabelText("Start date");
    const endInput = screen.getByLabelText("End date");
    await user.clear(startInput);
    await user.type(startInput, "2026-10-07");
    await user.clear(endInput);
    await user.type(endInput, VIEW_WINDOW.end);
    await user.click(screen.getByRole("button", { name: "Apply range" }));
    expect(routerReplace).toHaveBeenCalledWith(
      `/charts/gross-fees?version=1&start=2026-10-07&end=${VIEW_WINDOW.end}`,
      { scroll: false },
    );
    unmount();
  });

  it("rejects an unsupported custom range with an inline reason, never silently clamping", async () => {
    const user = userEvent.setup();
    const { unmount } = renderClient();
    await screen.findByRole("region", { name: /exact data table/ });
    await user.click(screen.getByRole("button", { name: "Custom range" }));

    const startInput = screen.getByLabelText("Start date");
    const endInput = screen.getByLabelText("End date");
    await user.clear(startInput);
    await user.type(startInput, "2025-10-01");
    await user.clear(endInput);
    await user.type(endInput, VIEW_WINDOW.end);
    await user.click(screen.getByRole("button", { name: "Apply range" }));
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/at most 366 days per view/);
    expect(alert).toHaveTextContent(/401/);
    expect(routerReplace).not.toHaveBeenCalled();
    unmount();
  });

  it("updates a filter through the closed schema and clears it back to all", async () => {
    const user = userEvent.setup();
    const { unmount } = renderClient();
    await screen.findByRole("region", { name: /exact data table/ });

    const select = screen.getByLabelText("Source");
    await user.selectOptions(select, "SRC-DASHBOARD");
    expect(routerReplace).toHaveBeenCalledWith(
      `/charts/gross-fees?version=1&start=${VIEW_WINDOW.start}&end=${VIEW_WINDOW.end}`
      + `&filters=${encodeURIComponent('{"source":"SRC-DASHBOARD"}')}`,
      { scroll: false },
    );

    await user.selectOptions(select, "");
    expect(routerReplace).toHaveBeenLastCalledWith(
      `/charts/gross-fees?version=1&start=${VIEW_WINDOW.start}&end=${VIEW_WINDOW.end}`,
      { scroll: false },
    );
    unmount();
  });
});

describe("ChartAuthActions — anonymous private-action continuation", () => {
  const definition = definitionFixture();

  function renderActions(selection = pinnedSelection()) {
    return render(
      <ChartDetailClient
        chartId="gross-fees"
        definition={definition}
        view={viewFixture(definition, VIEW_WINDOW)}
        selection={selection}
        dropped={[]}
      />,
    );
  }

  it("offers anonymous users a sign-in continuation preserving the selection", async () => {
    const user = userEvent.setup();
    installApiMock([ANONYMOUS_SESSION]);
    renderActions();

    const saveButton = await screen.findByRole("button", { name: "Sign in to save this chart" });
    expect(screen.getByRole("button", { name: "Sign in to add it to research" })).toBeInTheDocument();
    expect(screen.getByText(/Saving and adding to research need your account/)).toBeInTheDocument();

    await user.click(saveButton);
    expect(routerPush).toHaveBeenCalledTimes(1);
    const [href] = routerPush.mock.calls[0];
    expect(href.startsWith("/login?next=")).toBe(true);
    const next = new URL(href, "http://localhost").searchParams.get("next") ?? "";
    expect(next.startsWith("/charts/gross-fees?")).toBe(true);
    expect(new URL(next, "http://localhost").searchParams.get("version")).toBe("1");
    expect(new URL(next, "http://localhost").searchParams.get("start")).toBe(VIEW_WINDOW.start);
    expect(new URL(next, "http://localhost").searchParams.get("end")).toBe(VIEW_WINDOW.end);
    // The pending UI announces the continuation honestly.
    expect(screen.getByRole("status")).toHaveTextContent(/selection are preserved in the sign-in link/);
  });

  it("offers saved-chart persistence to a signed-in visitor", async () => {
    installApiMock([AUTHENTICATED_SESSION]);
    renderActions();
    await screen.findByRole("button", { name: "Save chart" });
    expect(screen.queryByRole("button", { name: "Sign in to save this chart" })).not.toBeInTheDocument();
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("stays honest when the session state cannot be checked", async () => {
    installApiMock([
      sessionRoute(apiError("DEPENDENCY_UNAVAILABLE", "Server configuration error.", false, 503)),
    ]);
    renderActions();
    await screen.findByText(/sign-in state could not be checked/);
    expect(screen.queryByRole("button", { name: "Sign in to save this chart" })).not.toBeInTheDocument();
  });
});

// -- NI-078 D3: compact detail presentation ------------------------------------ //

describe("Chart detail compact presentation (NI-076 D3)", () => {
  const definition = definitionFixture();
  const viewPayload = viewFixture(definition, VIEW_WINDOW);

  async function renderCompactDetail() {
    const requests = installApiMock([
      chartRoute("gross-fees", definition),
      metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      viewRoute("gross-fees", () => jsonResponse(viewPayload)),
      ANONYMOUS_SESSION,
    ]);
    const ui = await ChartDetailPage({
      params: Promise.resolve({ chartId: "gross-fees" }),
      searchParams: Promise.resolve({ version: "1", start: VIEW_WINDOW.start, end: VIEW_WINDOW.end }),
    });
    return { requests, ...render(ui) };
  }

  it("renders one title: the page h1, with no repeated title inside the frame", async () => {
    renderCompactDetail();
    await screen.findByRole("region", { name: /exact data table/ });
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(definition.title);
    // The frame no longer repeats the chart title in its figcaption.
    const figure = document.querySelector("figure");
    expect(figure).not.toBeNull();
    expect(within(figure as HTMLElement).queryByText(definition.title, { exact: true })).toBeNull();
  });

  it("keeps visible metadata short and moves the description into Sources", async () => {
    renderCompactDetail();
    await screen.findByRole("region", { name: /exact data table/ });
    expect(screen.getByText(/Definition version v1 \(pinned in the URL\)/)).toBeInTheDocument();
    // The long description is not rendered as page prose; it stays available
    // through the Sources & definitions drawer.
    expect(screen.queryByText(definition.description)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sources & definitions" })).toBeInTheDocument();
  });

  it("places the selection and action controls inside the frame toolbar above the plot", async () => {
    const { unmount } = await renderCompactDetail();
    await screen.findByRole("region", { name: /exact data table/ });
    const figure = document.querySelector("figure") as HTMLElement;
    // Filters, custom range, refresh and the private-action continuations
    // share the frame toolbar row with the range presets and sources.
    expect(within(figure).getByRole("group", { name: "Chart filters" })).toBeInTheDocument();
    expect(within(figure).getByRole("button", { name: "Custom range" })).toBeInTheDocument();
    expect(within(figure).getByRole("button", { name: "Refresh to latest" })).toBeInTheDocument();
    expect(within(figure).getByRole("button", { name: "Sign in to save this chart" })).toBeInTheDocument();
    expect(within(figure).getByRole("group", { name: "Time range" })).toBeInTheDocument();
    // The plot region renders inside the same frame, below the toolbar.
    expect(within(figure).getByRole("img")).toBeInTheDocument();
    unmount();
  });

  it("keeps exact values visible without hover under the compact header", async () => {
    await renderCompactDetail();
    // The compact header removes only the repeated title; the hover-free
    // exact-value contract holds on the detail page (no disclosure here).
    const table = await screen.findByRole("region", { name: /exact data table/ });
    expect(table).toBeInTheDocument();
    expect(screen.queryByText("Exact values and summary")).toBeNull();
  });
});
