/**
 * NI-015 public data explorer tests.
 *
 * Pattern: real (stubbed) fetch → Zod render-boundary validation → render,
 * with every request recorded so tests assert the exact query the pages
 * send. Covers: the five explorer categories and their registry-category
 * mapping; live per-category availability on the overview; category pages
 * serving real charts through GET /api/charts?category=… or honest
 * explanations (no placeholders, unavailable listed with reasons); the chart
 * detail under /data going through the SAME selection-url/catalog-api gates
 * as /charts (the identical-selection → identical-view-request invariant);
 * honest drop notes for unsupported URL parameters that are never forwarded;
 * URL round-trips (replace-state hrefs re-parse to the same selection); the
 * anonymous sign-in continuation restricted to internal /data paths; and
 * accessibility.
 *
 * ALL payloads in this file are synthetic and labeled "(fixture)" — no
 * production or research data.
 */
import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DataChartDetailPage from "@/app/(public)/data/[category]/[chartId]/page";
import DataCategoryPage from "@/app/(public)/data/[category]/page";
import DataExplorerPage from "@/app/(public)/data/page";
import ChartDetailPage from "@/app/(public)/charts/[chartId]/page";
import WorkspaceDataCategoryPage from "@/app/(workspace)/workspace/data/[category]/page";
import WorkspaceDataChartPage from "@/app/(workspace)/workspace/data/[category]/[chartId]/page";
import WorkspaceChartLibraryPage from "@/app/(workspace)/workspace/charts/page";
import {
  EXPLORER_CATEGORIES,
  explorerCategoryBySlug,
  explorerForRegistryCategory,
} from "@/features/charts/library/explorer-categories";
import { isInternalPath } from "@/features/charts/library/ChartAuthActions";
import { ChartDetailClient } from "@/features/charts/library/ChartDetailClient";
import {
  parseSelectionUrl,
  serializeSelectionQuery,
  shiftIsoDate,
  todayUtc,
} from "@/features/charts/library/selection-url";
import type { SerializedSelection } from "@/features/charts/library/selection-url";
import { CATALOG_CATEGORIES } from "@/features/charts/library/wording";
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

const METRIC_FEES_ID = "a2222222-2222-4222-8222-222222222222";
const DATASET_ID = "a3333333-3333-4333-8333-333333333333";
const DEFINITION_ID = "a4444444-4444-4444-8444-444444444444";

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
    content_sha256: "c".repeat(64),
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
  filters: Record<string, string[]> = {},
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
  selection: { start: string; end: string; filters?: Record<string, string[]> },
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
    context_hash: "d".repeat(64),
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

function catalogRouteFor(category: string, items: ChartDefinitionResponse[], nextCursor: string | null = null) {
  return (url: URL) =>
    url.pathname === "/api/charts" && url.searchParams.get("category") === category
      ? jsonResponse({ items, next_cursor: nextCursor })
      : undefined;
}

function sessionRoute(response: Response) {
  return (url: URL) => (url.pathname === "/api/auth/session" ? response : undefined);
}

const ANONYMOUS_SESSION = sessionRoute(
  jsonResponse({ error: { code: "UNAUTHORIZED", message: "No valid session.", request_id: "req-fixture", retryable: false, details: null } }, 401),
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

function viewRoute(chartId: string, definition: ChartDefinitionResponse) {
  return (url: URL) => {
    if (url.pathname !== `/api/charts/${chartId}/view`) {
      return undefined;
    }
    return jsonResponse(viewFixture(definition, {
      start: url.searchParams.get("start") ?? VIEW_WINDOW.start,
      end: url.searchParams.get("end") ?? VIEW_WINDOW.end,
      // the mock API echoes the server-canonical list form
      filters: Object.fromEntries(
        Object.entries(
          JSON.parse(url.searchParams.get("filters") ?? "{}") as Record<string, string | string[]>,
        ).map(([key, value]) => [key, Array.isArray(value) ? value : [value]])),
    }));
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

async function chartParameterNotice(): Promise<HTMLElement> {
  const message = await screen.findByText(
    "Some URL parameters were not used — the chart request carries only supported fields.",
  );
  const status = message.closest<HTMLElement>('[role="status"]');
  expect(status).not.toBeNull();
  return status!;
}

// -- explorer categories and the registry mapping ------------------------------ //

describe("explorer categories — the five /data categories and their mapping", () => {
  it("exposes exactly the five IA categories with the workspace labels in order", () => {
    expect(EXPLORER_CATEGORIES.map((category) => category.slug)).toEqual([
      "network",
      "intents",
      "revenue",
      "token-economics",
      "ecosystem",
    ]);
    expect(EXPLORER_CATEGORIES.map((category) => category.label)).toEqual([
      "Network Activity",
      "Intents & Adoption",
      "Revenue & Fees",
      "Token Economics",
      "Ecosystem",
    ]);
  });

  it("maps only closed registry categories and keeps the reverse direction total", () => {
    for (const category of EXPLORER_CATEGORIES) {
      for (const registryCategory of category.registryCategories) {
        expect(CATALOG_CATEGORIES).toContain(registryCategory);
      }
      expect(category.question.length).toBeGreaterThan(0);
      expect(category.scopeNote.length).toBeGreaterThan(0);
      expect(category.emptyExplanation.heading.length).toBeGreaterThan(0);
      expect(category.emptyExplanation.body.length).toBeGreaterThan(0);
    }
    // Every registry category resolves to exactly one explorer category —
    // or to none (model charts stay in the chart library/model section).
    expect(explorerForRegistryCategory("activity")?.slug).toBe("intents");
    expect(explorerForRegistryCategory("fees")?.slug).toBe("revenue");
    expect(explorerForRegistryCategory("treasury")?.slug).toBe("revenue");
    expect(explorerForRegistryCategory("supply")?.slug).toBe("token-economics");
    expect(explorerForRegistryCategory("model")).toBeNull();
  });

  it("states honestly that Network Activity and Ecosystem have no registered charts", () => {
    expect(explorerCategoryBySlug("network")?.registryCategories).toEqual([]);
    expect(explorerCategoryBySlug("ecosystem")?.registryCategories).toEqual([]);
    expect(explorerCategoryBySlug("ecosystem")?.emptyExplanation.heading).toBe(
      "Empty until source validation",
    );
    expect(explorerCategoryBySlug("unknown-slug")).toBeNull();
  });
});

// -- data explorer overview (/data) -------------------------------------------- //

describe("Data explorer overview — live availability or honest explanations", () => {
  const catalogItems = [
    definitionFixture({
      chart_id: "intents-volume",
      title: "Synthetic intents volume (fixture)",
      category: "activity",
    }),
    definitionFixture({
      chart_id: "protocol-revenue",
      title: "Synthetic protocol revenue (fixture)",
      category: "fees",
      data_status: "unavailable",
      unavailable_reason: "Revenue gate (fixture): no attributable ledger exists.",
    }),
    definitionFixture({
      chart_id: "model-diagnostics",
      title: "Synthetic model diagnostics (fixture)",
      category: "model",
      data_status: "unavailable",
      unavailable_reason: "Model gate (fixture): no published model artifact.",
      metric_definition_ids: [],
    }),
  ];

  async function renderOverview(searchParams: SearchValues = {}) {
    const ui = await DataExplorerPage({ searchParams: Promise.resolve(searchParams) });
    return render(ui);
  }

  it("derives per-category availability live from one bounded catalog request", async () => {
    const requests = installApiMock([
      (url) =>
        url.pathname === "/api/charts"
          ? jsonResponse({ items: catalogItems, next_cursor: null })
          : undefined,
    ]);
    await renderOverview();

    const catalogRequests = requestsTo(requests, "/api/charts");
    expect(catalogRequests).toHaveLength(1);
    expect([...catalogRequests[0].searchParams.keys()]).toEqual(["limit"]);
    expect(catalogRequests[0].searchParams.get("limit")).toBe("100");

    // Intents & Adoption: the activity chart counts as available.
    expect(screen.getByText(/1 available chart/)).toBeInTheDocument();
    // Revenue & Fees: nothing available, the gated chart stays honestly counted.
    expect(
      screen.getByText(
        /No available chart right now; 1 registered chart is unavailable and stays listed with the recorded reason/,
      ),
    ).toBeInTheDocument();
    // Token Economics: nothing mapped was returned — stated, never filled.
    expect(
      screen.getAllByText(/No chart is registered in the mapped registry categories yet/).length,
    ).toBeGreaterThan(0);
    // Network Activity and Ecosystem: the recorded honest explanations.
    expect(screen.getAllByText(/No network-level chart is registered yet/).length).toBe(1);
    expect(screen.getAllByText(/Empty until source validation/).length).toBe(1);
    // The model chart is outside the five categories and says where it lives.
    expect(screen.getByText(/not part of these five analytical categories/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "chart library" })).toHaveAttribute(
      "href",
      "/charts?category=model",
    );
    // Category cards link into the explorer.
    expect(screen.getByRole("link", { name: "Open category: Revenue & Fees" })).toHaveAttribute(
      "href",
      "/data/revenue",
    );
  });

  it("never forwards an arbitrary URL field and reports the drops", async () => {
    const requests = installApiMock([
      (url) =>
        url.pathname === "/api/charts"
          ? jsonResponse({ items: [], next_cursor: null })
          : undefined,
    ]);
    await renderOverview({ foo: "bar", sort: "asc" });

    const catalogRequests = requestsTo(requests, "/api/charts");
    expect(catalogRequests).toHaveLength(1);
    expect([...catalogRequests[0].searchParams.keys()]).toEqual(["limit"]);
    const status = screen.getByRole("status");
    expect(within(status).getByText("foo")).toBeInTheDocument();
    expect(within(status).getByText("sort")).toBeInTheDocument();
  });

  it("renders a catalog failure honestly and claims no availability", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/charts"
          ? apiError("DEPENDENCY_UNAVAILABLE", "The chart API is unavailable", true, 503)
          : undefined,
    ]);
    await renderOverview();

    const alert = screen.getByRole("alert");
    expect(within(alert).getByText(/catalog could not be loaded/)).toBeInTheDocument();
    expect(within(alert).getByText(/no availability is claimed/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: "Try again" })).toHaveAttribute("href", "/data");
    expect(screen.queryByText(/available chart/)).not.toBeInTheDocument();
  });

  it("fails honestly when the payload does not match the generated contract", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/charts"
          ? jsonResponse({ items: [{ chart_id: "broken" }], next_cursor: null })
          : undefined,
    ]);
    await renderOverview();
    expect(screen.getByRole("alert")).toHaveTextContent(/catalog could not be loaded/);
    expect(screen.queryByText("broken")).not.toBeInTheDocument();
  });

  it("passes axe on the overview", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/charts"
          ? jsonResponse({ items: catalogItems, next_cursor: null })
          : undefined,
    ]);
    const { container } = await renderOverview();
    expect(await axe(container, axeConfig)).toHaveNoViolations();
  });
});

// -- data category pages (/data/[category]) ------------------------------------- //

describe("Data category page — real charts through the catalog category filter", () => {
  const activityChart = definitionFixture({
    chart_id: "intents-volume",
    title: "Synthetic intents volume (fixture)",
    category: "activity",
    visualization_type: "area",
  });
  const gatedFeesChart = definitionFixture({
    chart_id: "protocol-revenue",
    title: "Synthetic protocol revenue (fixture)",
    category: "fees",
    data_status: "unavailable",
    unavailable_reason: "Revenue gate (fixture): no attributable ledger exists.",
  });

  it("serves the mapped registry category and links into the explorer", async () => {
    const requests = installApiMock([
      catalogRouteFor("activity", [activityChart]),
    ]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "intents" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    const catalogRequests = requestsTo(requests, "/api/charts");
    expect(catalogRequests).toHaveLength(1);
    expect(catalogRequests[0].searchParams.get("category")).toBe("activity");
    expect([...catalogRequests[0].searchParams.keys()]).toEqual(["category"]);

    // The visible mapping line names the registry category.
    expect(screen.getByText(/Registry categories mapped here: Activity/)).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: "Open chart: Synthetic intents volume (fixture)" }),
    ).toHaveAttribute("href", "/data/intents/intents-volume");
  });

  it("lists unavailable charts with their reason and never hides them", async () => {
    installApiMock([
      catalogRouteFor("fees", [gatedFeesChart]),
      catalogRouteFor("treasury", []),
    ]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "revenue" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    expect(
      await screen.findByText("Unavailable — this is not zero"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Reason: Revenue gate \(fixture\)/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open chart: Synthetic protocol revenue (fixture)" }),
    ).toHaveAttribute("href", "/data/revenue/protocol-revenue");
  });

  it("issues one request per mapped registry category (revenue: fees and treasury)", async () => {
    const requests = installApiMock([
      catalogRouteFor("fees", [definitionFixture({ chart_id: "gross-fees" })]),
      catalogRouteFor("treasury", [definitionFixture({
        chart_id: "treasury-payouts",
        title: "Synthetic treasury payouts (fixture)",
        category: "treasury",
      })]),
    ]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "revenue" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    const categories = requestsTo(requests, "/api/charts")
      .map((url) => url.searchParams.get("category"))
      .sort();
    expect(categories).toEqual(["fees", "treasury"]);
    expect(
      await screen.findByRole("link", { name: "Open chart: Synthetic treasury payouts (fixture)" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open chart: Synthetic gross fees (fixture)" }),
    ).toBeInTheDocument();
  });

  it("answers Network Activity with the recorded explanation and makes no request", async () => {
    const requests = installApiMock([]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "network" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    expect(requestsTo(requests, "/api/charts")).toHaveLength(0);
    expect(
      await screen.findByText("No network-level chart is registered yet"),
    ).toBeInTheDocument();
    expect(screen.getByText(/This is not zero/)).toBeInTheDocument();
    expect(screen.getByText(/No registry category is mapped to this explorer category yet/))
      .toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse the chart library" })).toHaveAttribute(
      "href",
      "/charts",
    );
  });

  it("answers Ecosystem with the empty-until-source-validation explanation", async () => {
    const requests = installApiMock([]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "ecosystem" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    expect(requestsTo(requests, "/api/charts")).toHaveLength(0);
    expect(await screen.findByText("Empty until source validation")).toBeInTheDocument();
    expect(screen.getByText(/honestly empty rather than filled with placeholder entries/))
      .toBeInTheDocument();
  });

  it("states a mapped-but-empty category instead of showing placeholders", async () => {
    installApiMock([catalogRouteFor("supply", [])]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "token-economics" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    expect(await screen.findByText("No chart is registered for this category yet")).toBeInTheDocument();
    expect(screen.queryByText("Open chart")).not.toBeInTheDocument();
  });

  it("renders a catalog failure honestly with a retry that preserves the category", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/charts" && url.searchParams.get("category") === "fees"
          ? apiError("DEPENDENCY_UNAVAILABLE", "The chart API is unavailable", true, 503)
          : undefined,
    ]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "revenue" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/catalog could not be loaded/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: "Try again" })).toHaveAttribute(
      "href",
      "/data/revenue",
    );
  });

  it("drops unknown URL parameters with honest notes and forwards nothing", async () => {
    const requests = installApiMock([catalogRouteFor("activity", [])]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "intents" }),
      searchParams: Promise.resolve({ foo: "bar", start: "2026-01-01" }),
    });
    render(ui);

    const catalogRequests = requestsTo(requests, "/api/charts");
    expect(catalogRequests[0].searchParams.get("foo")).toBeNull();
    expect(catalogRequests[0].searchParams.get("start")).toBeNull();
    const status = await screen.findByRole("status");
    expect(within(status).getByText("foo")).toBeInTheDocument();
    expect(within(status).getByText("start")).toBeInTheDocument();
  });

  it("answers an unknown category slug with the 404 boundary", async () => {
    await expect(
      DataCategoryPage({
        params: Promise.resolve({ category: "politics" }),
        searchParams: Promise.resolve({}),
      }),
    ).rejects.toMatchObject({ digest: "NEXT_HTTP_ERROR_FALLBACK;404" });
  });

  it("passes axe on a loaded category", async () => {
    installApiMock([catalogRouteFor("activity", [activityChart])]);
    const ui = await DataCategoryPage({
      params: Promise.resolve({ category: "intents" }),
      searchParams: Promise.resolve({}),
    });
    const { container } = render(ui);
    await screen.findByRole("link", { name: "Open chart: Synthetic intents volume (fixture)" });
    expect(await axe(container, axeConfig)).toHaveNoViolations();
  });
});

// -- data chart detail (/data/[category]/[chartId]) ------------------------------ //

describe("Data chart detail — the same gates as /charts", () => {
  const definition = definitionFixture();

  function detailRoutes(session = ANONYMOUS_SESSION) {
    return [
      chartRoute("gross-fees", definition),
      metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      viewRoute("gross-fees", definition),
      session,
    ];
  }

  it("resolves an identical selection to the identical view request as /charts", async () => {
    // The identical selection URL rendered through the NI-034 chart detail…
    const chartsRequests = installApiMock(detailRoutes());
    const chartsUi = await ChartDetailPage({
      params: Promise.resolve({ chartId: "gross-fees" }),
      searchParams: Promise.resolve({
        version: "1",
        start: VIEW_WINDOW.start,
        end: VIEW_WINDOW.end,
        filters: '{"source":"SRC-LLAMA"}',
      }),
    });
    render(chartsUi);
    await screen.findByRole("region", { name: /exact data table/ });

    // …and through the public data explorer must produce the exact same view
    // request — the shared selection gate, not a parallel implementation.
    const dataRequests = installApiMock(detailRoutes());
    const dataUi = await DataChartDetailPage({
      params: Promise.resolve({ category: "revenue", chartId: "gross-fees" }),
      searchParams: Promise.resolve({
        version: "1",
        start: VIEW_WINDOW.start,
        end: VIEW_WINDOW.end,
        filters: '{"source":"SRC-LLAMA"}',
      }),
    });
    render(dataUi);
    await screen.findAllByRole("region", { name: /exact data table/ });

    const chartsQuery = requestsTo(chartsRequests, "/api/charts/gross-fees/view")[0].search;
    const dataQuery = requestsTo(dataRequests, "/api/charts/gross-fees/view")[0].search;
    expect(dataQuery).toBe(chartsQuery);
    // And the request is the fully pinned selection, filters included.
    expect(dataQuery).toContain("definition_version=1");
    expect(dataQuery).toContain(`start=${VIEW_WINDOW.start}`);
    expect(dataQuery).toContain(`end=${VIEW_WINDOW.end}`);
    expect(decodeURIComponent(dataQuery)).toContain('{"source":"SRC-LLAMA"}');
  });

  it("never forwards an arbitrary URL field and reports the drops", async () => {
    const requests = installApiMock(detailRoutes());
    const ui = await DataChartDetailPage({
      params: Promise.resolve({ category: "revenue", chartId: "gross-fees" }),
      searchParams: Promise.resolve({
        version: "1",
        start: VIEW_WINDOW.start,
        end: VIEW_WINDOW.end,
        foo: "bar",
        admin: "true",
      }),
    });
    render(ui);

    const viewRequests = requestsTo(requests, "/api/charts/gross-fees/view");
    expect([...viewRequests[0].searchParams.keys()]).toEqual(["definition_version", "start", "end"]);
    const status = await chartParameterNotice();
    expect(within(status).getByText("foo")).toBeInTheDocument();
    expect(within(status).getByText("admin")).toBeInTheDocument();
  });

  it("falls back honestly when the URL range exceeds the version's bound", async () => {
    const requests = installApiMock(detailRoutes());
    const ui = await DataChartDetailPage({
      params: Promise.resolve({ category: "revenue", chartId: "gross-fees" }),
      searchParams: Promise.resolve({ version: "1", start: "2025-10-01", end: "2026-11-06" }),
    });
    render(ui);

    const viewRequests = requestsTo(requests, "/api/charts/gross-fees/view");
    // The fallback is the version's default preset anchored to today (UTC) —
    // exactly what the /charts detail resolves for the same URL.
    const expectedEnd = todayUtc();
    const expectedStart = shiftIsoDate(expectedEnd, -90);
    expect(viewRequests[0].searchParams.get("start")).toBe(expectedStart);
    expect(viewRequests[0].searchParams.get("end")).toBe(expectedEnd);
    expect(viewRequests[0].searchParams.get("definition_version")).toBe("1");
    const status = await chartParameterNotice();
    expect(within(status).getAllByText(/at most 366/).length).toBe(2);
  });

  it("renders an unavailable chart with its reason and never requests a view", async () => {
    const gated = definitionFixture({
      chart_id: "protocol-revenue",
      title: "Synthetic protocol revenue (fixture)",
      data_status: "unavailable",
      unavailable_reason: "Revenue gate (fixture): no attributable ledger exists.",
      metric_definition_ids: [],
    });
    const requests = installApiMock([
      chartRoute("protocol-revenue", gated),
      ANONYMOUS_SESSION,
    ]);
    const ui = await DataChartDetailPage({
      params: Promise.resolve({ category: "revenue", chartId: "protocol-revenue" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    expect(await screen.findByText(/Unavailable — this is not zero/)).toBeInTheDocument();
    expect(screen.getAllByText(/Revenue gate \(fixture\)/).length).toBeGreaterThan(0);
    expect(requestsTo(requests, "/api/charts/protocol-revenue/view")).toHaveLength(0);
    expect(screen.queryByText("Definition, dataset and quality")).not.toBeInTheDocument();
  });

  it("answers a chart outside the category mapping with the 404 boundary", async () => {
    // gross-fees is registry category fees → Revenue & Fees, not Intents.
    installApiMock(detailRoutes());
    await expect(
      DataChartDetailPage({
        params: Promise.resolve({ category: "intents", chartId: "gross-fees" }),
        searchParams: Promise.resolve({}),
      }),
    ).rejects.toMatchObject({ digest: "NEXT_HTTP_ERROR_FALLBACK;404" });

    // Model-category charts are not reachable through any explorer category —
    // the definition exists, so the mismatch itself is what 404s.
    const modelChart = definitionFixture({
      chart_id: "model-diagnostics",
      title: "Synthetic model diagnostics (fixture)",
      category: "model",
      data_status: "unavailable",
      unavailable_reason: "Model gate (fixture): no published model artifact.",
      metric_definition_ids: [],
    });
    installApiMock([chartRoute("model-diagnostics", modelChart), ANONYMOUS_SESSION]);
    await expect(
      DataChartDetailPage({
        params: Promise.resolve({ category: "revenue", chartId: "model-diagnostics" }),
        searchParams: Promise.resolve({}),
      }),
    ).rejects.toMatchObject({ digest: "NEXT_HTTP_ERROR_FALLBACK;404" });
  });

  it("answers an unknown category slug or unknown chart with the 404 boundary", async () => {
    await expect(
      DataChartDetailPage({
        params: Promise.resolve({ category: "politics", chartId: "gross-fees" }),
        searchParams: Promise.resolve({}),
      }),
    ).rejects.toMatchObject({ digest: "NEXT_HTTP_ERROR_FALLBACK;404" });

    installApiMock([
      (url) =>
        url.pathname === "/api/charts/gross-fees"
          ? apiError("NOT_FOUND", "Resource was not found", false, 404)
          : undefined,
    ]);
    await expect(
      DataChartDetailPage({
        params: Promise.resolve({ category: "revenue", chartId: "gross-fees" }),
        searchParams: Promise.resolve({}),
      }),
    ).rejects.toMatchObject({ digest: "NEXT_HTTP_ERROR_FALLBACK;404" });
  });

  it("recovers from a server-rejected selection with a reset to this route", async () => {
    installApiMock([
      chartRoute("gross-fees", definition),
      metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      (url) =>
        url.pathname === "/api/charts/gross-fees/view"
          ? apiError("FILTER_UNSUPPORTED", "Filters or range are not supported", false, 422)
          : undefined,
      ANONYMOUS_SESSION,
    ]);
    const ui = await DataChartDetailPage({
      params: Promise.resolve({ category: "revenue", chartId: "gross-fees" }),
      searchParams: Promise.resolve({
        version: "1",
        start: VIEW_WINDOW.start,
        end: VIEW_WINDOW.end,
      }),
    });
    render(ui);

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/rejected this selection as unsupported/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: "Reset to the default selection" }))
      .toHaveAttribute("href", "/data/revenue/gross-fees?version=1");
  });

  it("links back to the explorer category after a resolved view", async () => {
    installApiMock(detailRoutes());
    const ui = await DataChartDetailPage({
      params: Promise.resolve({ category: "revenue", chartId: "gross-fees" }),
      searchParams: Promise.resolve({
        version: "1",
        start: VIEW_WINDOW.start,
        end: VIEW_WINDOW.end,
      }),
    });
    render(ui);

    await screen.findByRole("region", { name: /exact data table/ });
    expect(screen.getByRole("link", { name: "More charts in Revenue & Fees" })).toHaveAttribute(
      "href",
      "/data/revenue",
    );
    // Breadcrumbs: Data → category → chart.
    const breadcrumb = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(breadcrumb).getByRole("link", { name: "Data" })).toHaveAttribute("href", "/data");
    expect(within(breadcrumb).getByRole("link", { name: "Revenue & Fees" })).toHaveAttribute(
      "href",
      "/data/revenue",
    );
  });

  it("passes axe on the resolved data chart detail", async () => {
    installApiMock(detailRoutes());
    const ui = await DataChartDetailPage({
      params: Promise.resolve({ category: "revenue", chartId: "gross-fees" }),
      searchParams: Promise.resolve({
        version: "1",
        start: VIEW_WINDOW.start,
        end: VIEW_WINDOW.end,
      }),
    });
    const { container } = render(ui);
    await screen.findByRole("region", { name: /exact data table/ });
    expect(await axe(container, axeConfig)).toHaveNoViolations();
  });
});

// -- URL round-trips and safe continuation under /data --------------------------- //

describe("Data chart detail island — selection URLs and continuation stay /data-internal", () => {
  const definition = definitionFixture();
  const viewPayload = viewFixture(definition, VIEW_WINDOW);
  const baseSelection: SerializedSelection = {
    version: 1,
    start: VIEW_WINDOW.start,
    end: VIEW_WINDOW.end,
    datasetVersion: "latest",
    filters: {},
  };

  it("writes range changes back to the /data URL and the URL re-parses to the same selection", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <ChartDetailClient
        chartId="gross-fees"
        definition={definition}
        view={viewPayload}
        selection={baseSelection}
        dropped={[]}
        basePath="/data/revenue"
      />,
    );
    await screen.findByRole("region", { name: /exact data table/ });

    await user.click(
      within(screen.getByRole("group", { name: "Time range" })).getByRole("button", { name: "Last 30 days" }),
    );
    expect(routerReplace).toHaveBeenCalledTimes(1);
    const [href] = routerReplace.mock.calls[0];
    expect(href).toBe(`/data/revenue/gross-fees?version=1&start=2026-10-07&end=${VIEW_WINDOW.end}`);

    // Back/forward navigation replays the URL through the same gate and gets
    // the same selection (INFORMATION_ARCHITECTURE.md replace-state contract).
    const reparsed = parseSelectionUrl(new URLSearchParams(String(href).split("?")[1]), definition);
    expect(reparsed.range).toEqual({ start: "2026-10-07", end: VIEW_WINDOW.end });
    expect(reparsed.filters).toEqual({});
    expect(reparsed.dropped).toEqual([]);
    unmount();
  });

  it("carries validated filters through the /data URL round-trip", async () => {
    const user = userEvent.setup();
    const selection: SerializedSelection = { ...baseSelection, filters: { source: "SRC-LLAMA" } };
    const { unmount } = render(
      <ChartDetailClient
        chartId="gross-fees"
        definition={definition}
        view={viewFixture(definition, VIEW_WINDOW)}
        selection={selection}
        dropped={[]}
        basePath="/data/revenue"
      />,
    );
    await screen.findByRole("region", { name: /exact data table/ });

    const select = screen.getByLabelText("Source");
    await user.selectOptions(select, "SRC-DASHBOARD");
    const [href] = routerReplace.mock.calls[routerReplace.mock.calls.length - 1];
    expect(href).toBe(
      `/data/revenue/gross-fees?version=1&start=${VIEW_WINDOW.start}&end=${VIEW_WINDOW.end}`
      + `&filters=${encodeURIComponent('{"source":"SRC-DASHBOARD"}')}`,
    );
    const reparsed = parseSelectionUrl(new URLSearchParams(String(href).split("?")[1]), definition);
    expect(reparsed.filters).toEqual({ source: "SRC-DASHBOARD" });
    expect(reparsed.range).toEqual({ start: VIEW_WINDOW.start, end: VIEW_WINDOW.end });
    expect(reparsed.dropped).toEqual([]);
    // Re-serializing the reparsed selection reproduces the same canonical
    // URL query (deterministic sorted filter keys).
    expect(serializeSelectionQuery({
      version: reparsed.version ?? definition.version,
      start: reparsed.range?.start ?? "",
      end: reparsed.range?.end ?? "",
      datasetVersion: reparsed.datasetVersion ?? "latest",
      filters: reparsed.filters,
    })).toBe(String(href).split("?")[1]);
    unmount();
  });

  it("offers anonymous users a sign-in continuation preserving the /data selection", async () => {
    const user = userEvent.setup();
    installApiMock([ANONYMOUS_SESSION]);
    render(
      <ChartDetailClient
        chartId="gross-fees"
        definition={definition}
        view={viewPayload}
        selection={baseSelection}
        dropped={[]}
        basePath="/data/revenue"
      />,
    );

    const saveButton = await screen.findByRole("button", { name: "Sign in to save this chart" });
    await user.click(saveButton);
    expect(routerPush).toHaveBeenCalledTimes(1);
    const [href] = routerPush.mock.calls[0];
    expect(href.startsWith("/login?next=")).toBe(true);
    const next = decodeURIComponent(String(href).split("next=")[1]);
    expect(next).toBe(
      `/data/revenue/gross-fees?${serializeSelectionQuery({ ...baseSelection, datasetVersion: "a3333333-3333-4333-8333-333333333333" })}`,
    );
    const continuation = screen.getByText(/^Signing in to continue — this chart/);
    expect(continuation).toHaveAttribute("role", "status");
    expect(continuation).toHaveTextContent(/selection are preserved in the sign-in link/);
  });

  it("accepts only internal /data paths as continuation targets", () => {
    const base = "/data/revenue/";
    expect(isInternalPath("/data/revenue/gross-fees?version=1", base)).toBe(true);
    expect(isInternalPath("//evil.example/data/revenue", base)).toBe(false);
    expect(isInternalPath("https://evil.example/data/revenue", base)).toBe(false);
    expect(isInternalPath("/data/revenue\\evil", base)).toBe(false);
    expect(isInternalPath("/charts/gross-fees", base)).toBe(false);
    expect(isInternalPath("/data/intents/intents-volume", base)).toBe(false);
  });
});


describe("NI-080 workspace explorer context", () => {
  it("keeps Network Activity's honest empty state and library action in the cabinet", async () => {
    const requests = installApiMock([]);
    render(await WorkspaceDataCategoryPage({ params: Promise.resolve({ category: "network" }), searchParams: Promise.resolve({}) }));
    expect(screen.getByRole("heading", { name: "No network-level chart is registered yet" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Browse the chart library" })).toHaveAttribute("href", "/workspace/charts");
    expect(requestsTo(requests, "/api/charts")).toHaveLength(0);
  });

  it("links Intents charts into the workspace detail rather than the public layout", async () => {
    const chart = definitionFixture({ chart_id: "intents-volume", category: "activity" });
    installApiMock([catalogRouteFor("activity", [chart])]);
    render(await WorkspaceDataCategoryPage({ params: Promise.resolve({ category: "intents" }), searchParams: Promise.resolve({}) }));
    expect(screen.getByRole("link", { name: `Open chart: ${chart.title}` })).toHaveAttribute("href", "/workspace/data/intents/intents-volume");
  });

  it("keeps catalog search, category tabs and chart links inside workspace", async () => {
    const chart = definitionFixture();
    installApiMock([(url) => url.pathname === "/api/charts" ? jsonResponse({ items: [chart], next_cursor: null }) : undefined]);
    render(await WorkspaceChartLibraryPage({ searchParams: Promise.resolve({ q: "fees" }) }));
    expect(screen.getByRole("search")).toHaveAttribute("action", "/workspace/charts");
    expect(screen.getByRole("link", { name: `Open chart: ${chart.title}` })).toHaveAttribute("href", "/workspace/charts/gross-fees");
    expect(screen.getByRole("link", { name: "All charts" }).getAttribute("href")).toBe("/workspace/charts?q=fees");
  });

  it("uses the same pinned query while detail backlinks stay inside workspace", async () => {
    const chart = definitionFixture();
    const requests = installApiMock([
      chartRoute("gross-fees", chart), metricRoute(metricFixture(METRIC_FEES_ID, "provider_gross_fees_usd", "USD")),
      viewRoute("gross-fees", chart), ANONYMOUS_SESSION,
    ]);
    render(await WorkspaceDataChartPage({ params: Promise.resolve({ category: "revenue", chartId: "gross-fees" }),
      searchParams: Promise.resolve({ version: "1", start: VIEW_WINDOW.start, end: VIEW_WINDOW.end, filters: '{"source":"SRC-LLAMA"}' }) }));
    await screen.findByRole("region", { name: /exact data table/ });
    expect(screen.getByRole("link", { name: "More charts in Revenue & Fees" })).toHaveAttribute("href", "/workspace/data/revenue");
    const query = requestsTo(requests, "/api/charts/gross-fees/view")[0];
    expect(query.searchParams.get("start")).toBe(VIEW_WINDOW.start);
    expect(query.searchParams.get("end")).toBe(VIEW_WINDOW.end);
    expect(query.searchParams.get("filters")).toBe('{"source":"SRC-LLAMA"}');
  });
});


it("NI-080 featured chart resolves its default range against the same old approved coverage", async () => {
  const definition = definitionFixture({ chart_id: "observed-conversions", category: "activity" });
  const requests = installApiMock([
    catalogRouteFor("activity", [definition]),
    (url) => {
      if (url.pathname !== "/api/charts/observed-conversions/view") return undefined;
      const view = viewFixture(definition, { start: url.searchParams.get("start")!, end: url.searchParams.get("end")! });
      view.dataset = datasetFixture({ start: "2026-01-01", end: "2026-01-15" });
      for (const series of view.series) series.dataset = view.dataset;
      return jsonResponse(view);
    },
  ]);
  render(await WorkspaceDataCategoryPage({ params: Promise.resolve({ category: "intents" }), searchParams: Promise.resolve({}) }));
  const views = requestsTo(requests, "/api/charts/observed-conversions/view");
  expect(views).toHaveLength(2);
  expect(views[1].searchParams.get("end")).toBe("2026-01-15");
  expect(views[1].searchParams.get("dataset_version")).toBe(DATASET_ID);
  const link = screen.getByRole("link", { name: /Inspect range and data/ });
  expect(link.getAttribute("href")).toContain("/workspace/data/intents/observed-conversions?");
  expect(link.getAttribute("href")).toContain("end=2026-01-15");
  expect(link.getAttribute("href")).toContain(`dataset_version=${DATASET_ID}`);
});
