/**
 * NI-054 role-A completion: public model catalog (/models) and run detail
 * (/models/{run_id}) tests.
 *
 * Pattern: real (stubbed) fetch → Zod render-boundary validation → render,
 * with every request recorded so tests assert the exact call the pages make.
 * Covers the handoff contract: honest "no published model yet" empty state
 * (never a placeholder result); limits-before-coefficients ordering
 * (mechanical fee-volume warning + prohibited labels render before any
 * coefficient, structural DOM-order assertions); exact recorded floats
 * rendered verbatim without rounding; every gate limit code visible; the
 * manifest download link with the offline verify pointer; the mechanical
 * `question` template framing; honest ready:false readiness; the generic
 * 404 boundary without existence leak; the GET-only access-trigger
 * invariant (behavioral and structural); accessibility.
 *
 * ALL payloads in this file are synthetic and labeled "(fixture)" — no
 * production or research data, no fitted statistics.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ModelsPage from "@/app/(public)/models/page";
import ModelRunPage from "@/app/(public)/models/[runId]/page";
import ModelNotFound from "@/app/(public)/models/not-found";
import { ModelSpecificationPanel } from "@/features/models/ModelSpecificationPanel";
import type {
  ModelDefinition,
  ModelReadiness,
  ModelRunDetail,
  ModelRunSummary,
} from "@/features/models/models-schema";

// The web server env contract is loaded lazily on first page render; set the
// documented variables before any render so loadServerEnv resolves them.
process.env.APP_ENV = "test";
process.env.APP_ORIGIN = "http://localhost:3000";
process.env.API_INTERNAL_URL = "http://api.test:8000";

/** Mirrors Next.js' notFound(): throws the 404 fallback error with its digest. */
function notFoundMock(): never {
  const error = new Error("NEXT_HTTP_ERROR_FALLBACK;404") as Error & { digest?: string };
  error.digest = "NEXT_HTTP_ERROR_FALLBACK;404";
  throw error;
}

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  notFound: notFoundMock,
}));

// -- synthetic fixtures (visibly labeled) ------------------------------------ //

const RUN_ID = "77777777-7777-4777-8777-777777777777";
const DEFINITION_RECORD_ID = "88888888-8888-4888-8888-888888888888";
const MODEL_ID = "gross_fee_activity_v1";
const CODE_COMMIT = "a".repeat(40);

/** All values below are invented for the tests; none is a fitted result. */
const COEFFICIENTS = [
  {
    name: "const",
    estimate: 0.012345678901234,
    std_error: 0.000123456789012345,
    t_stat: 12.3456789012345,
    p_value: 1.25e-12,
    ci95_low: -0.024689135678901234,
    ci95_high: 0.04938024689135678,
  },
  {
    name: "dlog_provider_intents_volume_usd",
    estimate: 0.987654321098765,
    std_error: 0.0123456789012345,
    t_stat: 80.00000000000001,
    p_value: 2.5e-80,
    ci95_low: 0.9634567890123456,
    ci95_high: 1.0118518531851844,
  },
];

const LIMITATIONS = {
  prohibited_labels: [
    "protocol revenue (fixture)",
    "a causal effect (fixture)",
    "a demand elasticity (fixture)",
  ],
  spec_limitation_notes: [
    "Mechanical construction warning (fixture): the regressor is constructed mechanically from the reported fee and volume series, so the fitted slope is expected to be close to the fee accrual ratio and is not independent evidence.",
    "Short sample (fixture): the window cannot establish a long-term stable mechanism.",
    "No causal claim (fixture): the specification declares association only.",
  ],
  gate_limit_codes: [
    "LIMIT_MECHANICAL_CONSTRUCTION",
    "LIMIT_SHORT_SAMPLE",
    "LIMIT_SINGLE_PROVIDER_LINEAGE",
    "OQ02_JUDGING_RISK",
  ],
};

const ADMISSION_REASONS = [
  {
    code: "SPEC_PROXY_ADMITTED",
    severity: "informational" as const,
    detail: "Fixture detail: the named proxy specification is admitted with limits.",
  },
  {
    code: "LIMIT_SHORT_SAMPLE",
    severity: "limit" as const,
    detail: "Fixture detail: the sample window is below the long-run threshold.",
  },
];

const INTERPRETATION = {
  template_id: "bounded_association_v1",
  rendering_policy: "Fixture rendering policy: fixed template sentences over recorded numbers only.",
  sentences: [
    "Fixture sentence: the fitted slope is a short-run association, not a causal effect.",
    "Fixture sentence: the estimate uses 90 observations between recorded dates.",
  ],
  authoring_note: "Fixture authoring note: an authored interpretation is added at publication.",
  mechanical_construction_warning: LIMITATIONS.spec_limitation_notes[0],
};

function summaryFixture(overrides: Partial<ModelRunSummary> = {}): ModelRunSummary {
  return {
    run_id: RUN_ID,
    model_id: MODEL_ID,
    model_version: 1,
    gate_verdict: "READY_WITH_LIMITS",
    sample: { start: "2026-08-06", end_exclusive: "2026-11-04", nobs: 90 },
    // The recorded tolerances travel as decimal strings per the API contract
    // (^[0-9]+(\.[0-9]+)?$): rtol 1e-8, atol 1e-10.
    tolerances: { coefficient_rtol: "0.00000001", coefficient_atol: "0.0000000001" },
    code_commit: CODE_COMMIT,
    manifest_url: `/api/model-runs/${RUN_ID}/manifest`,
    published_at: "2026-11-08T00:00:00Z",
    published_by: "fixture-operator",
    ...overrides,
  };
}

function detailFixture(overrides: Partial<ModelRunDetail> = {}): ModelRunDetail {
  return {
    ...summaryFixture(),
    specification: {
      spec_id: MODEL_ID,
      declared_target: "dlog_provider_gross_fees_usd (fixture)",
      dependent_variable: { metric_id: "provider_gross_fees_usd (fixture)" },
      explanatory_variables: [{ metric_id: "provider_intents_volume_usd (fixture)" }],
      frequency: "day",
      family: "gaussian (fixture)",
      baseline: "difference_log (fixture)",
    },
    admission_reasons: ADMISSION_REASONS,
    design: { declared_columns: ["const", "dlog_provider_intents_volume_usd"], rows: 90 },
    estimation: {
      method: "OLS with Newey-West HAC (fixture)",
      maxlags: 7,
      r_squared: 0.42,
      adj_r_squared: 0.41,
      covariance: { type: "HAC", kernel: "bartlett", maxlags: 7, use_t: true, use_correction: true },
    },
    coefficients: COEFFICIENTS,
    diagnostics: {
      stationarity: [{ test: "adf (fixture)", status: "computed" }],
      residual: { ljung_box: { lags: [3, 7] } },
    },
    interpretation: INTERPRETATION,
    limitations: LIMITATIONS,
    environment: { python: "3.13 (fixture)", blas: "fixture-blas" },
    reproduction: { coefficient_rtol: "1e-8", coefficient_atol: "1e-10" },
    approval: {
      decision: "approve" as const,
      reviewer: "Fixture reviewer (test)",
      review_reference: "fixture-review-reference-1",
      reviewed_at: "2026-11-08T00:00:00Z",
      notes: null,
    },
    ...overrides,
  };
}

const DEFINITION: ModelDefinition = {
  id: DEFINITION_RECORD_ID,
  model_id: MODEL_ID,
  version: 1,
  question:
    "Association of the declared target dlog_provider_gross_fees_usd (fixture) with provider_intents_volume_usd (fixture) (day frequency, family gaussian (fixture), baseline difference_log (fixture)); the specification declares association only, never causality.",
  specification: { spec_id: MODEL_ID, declared_target: "dlog_provider_gross_fees_usd (fixture)" },
  required_metric_ids: ["provider_gross_fees_usd", "provider_intents_volume_usd"],
  readiness_rules: { min_observations: 60, observations_per_parameter: 10 },
  limitations: LIMITATIONS,
  latest_published_run_id: RUN_ID,
};

const READINESS_READY: ModelReadiness = {
  model_id: MODEL_ID,
  ready: true,
  verdict: "READY_WITH_LIMITS",
  reasons: ADMISSION_REASONS,
  overall_verdict: "READY_WITH_LIMITS (fixture)",
  selected_specification: MODEL_ID,
  recorded_in_run_id: RUN_ID,
};

const READINESS_NOT_READY: ModelReadiness = {
  model_id: "true_revenue_daily_v1",
  ready: false,
  verdict: "NOT_READY",
  reasons: [
    {
      code: "OQ01_REVENUE_SERIES_UNRESOLVED",
      severity: "rejecting",
      detail: "Fixture detail: no attributable protocol revenue series is established.",
    },
  ],
  overall_verdict: "NOT_READY (fixture)",
  selected_specification: null,
  recorded_in_run_id: RUN_ID,
};

// -- fetch mock infrastructure ------------------------------------------------ //

interface RecordedRequest {
  url: URL;
  method: string;
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
    // openapi-fetch passes a Request object; extract its URL and method.
    const request = input instanceof Request ? input : new Request(new URL(String(input), process.env.APP_ORIGIN), init);
    const url = new URL(request.url);
    requests.push({ url, method: request.method });
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

/** Matches the run detail route for any run identity (manifest route excluded). */
function runDetailRoute(respond: (url: URL) => Response) {
  return (url: URL) =>
    url.pathname.startsWith("/api/model-runs/") && !url.pathname.endsWith("/manifest")
      ? respond(url)
      : undefined;
}

function definitionRoute(response: Response) {
  return (url: URL) =>
    url.pathname === `/api/model-definitions/${MODEL_ID}` ? response : undefined;
}

function readinessRoute(response: Response) {
  return (url: URL) =>
    url.pathname === `/api/model-definitions/${MODEL_ID}/readiness` ? response : undefined;
}

type SearchValues = Record<string, string | string[] | undefined>;

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const axeConfig = { rules: { region: { enabled: false } } };

async function renderCatalog(searchParams: SearchValues) {
  const ui = await ModelsPage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

async function renderDetail() {
  const ui = await ModelRunPage({ params: Promise.resolve({ runId: RUN_ID }) });
  return render(ui);
}

/** Routes serving the full detail bundle (run + definition + readiness). */
function detailRoutes(extra: Array<(url: URL) => Response | undefined> = []) {
  return [
    runDetailRoute(() => jsonResponse(detailFixture())),
    definitionRoute(jsonResponse(DEFINITION)),
    readinessRoute(jsonResponse(READINESS_READY)),
    ...extra,
    (url: URL) => url.pathname === "/api/auth/session" ? jsonResponse({}, 401) : undefined,
  ];
}

// -- structural invariants over the page sources ------------------------------- //

const MODEL_PAGE_SOURCES = [
  "src/features/models/models-schema.ts",
  "src/features/models/models-api.ts",
  "src/features/models/recorded.ts",
  "src/features/models/ModelRunList.tsx",
  "src/features/models/ModelSpecificationPanel.tsx",
  "src/features/models/ModelRunDetail.tsx",
  "src/app/(public)/models/page.tsx",
  "src/app/(public)/models/[runId]/page.tsx",
  "src/app/(public)/models/not-found.tsx",
];

describe("GET-only access-trigger invariant (NI-054 handoff)", () => {
  it("declares no mutating client call in any page source", () => {
    for (const relative of MODEL_PAGE_SOURCES) {
      const source = readFileSync(path.join(process.cwd(), relative), "utf8");
      expect(source, relative).not.toMatch(/\b(POST|PUT|DELETE|PATCH)\s*\(/);
      expect(source, relative).not.toMatch(/method:\s*"(POST|PUT|DELETE|PATCH)"/);
      // The generated client is used through GET(...) only.
      expect(source, relative).not.toMatch(/\b(POST|PUT|DELETE|PATCH)\(\s*"/);
    }
  });

  it("renders the catalog and the detail with GET requests only", async () => {
    const requests = installApiMock(detailRoutes());
    await renderCatalog({});
    await renderDetail();

    expect(requests.length).toBeGreaterThanOrEqual(4);
    for (const request of requests) {
      expect(request.method, request.url.pathname).toBe("GET");
    }
  });
});

// -- catalog page (/models) ----------------------------------------------------- //

describe("Model catalog page — the honest published-runs catalog", () => {
  it("sends only the validated cursor to the catalog API and renders the cards", async () => {
    const requests = installApiMock([
      (url) =>
        url.pathname === "/api/model-runs"
          ? jsonResponse({
              items: [
                summaryFixture(),
                summaryFixture({
                  run_id: "66666666-6666-4666-8666-666666666666",
                  model_id: "purchases_activity_v1",
                  model_version: 2,
                  gate_verdict: "READY",
                  manifest_url: "/api/model-runs/66666666-6666-4666-8666-666666666666/manifest",
                }),
              ],
              next_cursor: "MjA=",
            })
          : undefined,
    ]);
    await renderCatalog({ cursor: "MTA=" });

    const catalogRequests = requestsTo(requests, "/api/model-runs");
    expect(catalogRequests).toHaveLength(1);
    expect([...catalogRequests[0].searchParams.keys()]).toEqual(["cursor"]);
    expect(catalogRequests[0].searchParams.get("cursor")).toBe("MTA=");

    // NI-097: the cards present the approved readable mapping for the known
    // spec and the identity-preserving fallback for the unknown one. The
    // recorded run id, tolerances and commit live on the detail page now.
    expect(screen.getByText("Gross fees and Intents volume")).toBeInTheDocument();
    expect(screen.getByText("Purchases activity")).toBeInTheDocument();
    expect(screen.getByText("Intents · Fee activity")).toBeInTheDocument();
    expect(screen.getAllByText("Published with limits").length).toBe(1);
    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(screen.getAllByText("90 observations").length).toBe(2);
    expect(screen.getAllByText("6 Aug – 3 Nov 2026").length).toBe(2);
    expect(screen.getAllByText("OLS · daily log changes").length).toBe(1);
    expect(screen.getByText("gross_fee_activity_v1 · version 1")).toBeInTheDocument();
    expect(screen.getByText("purchases_activity_v1 · version 2")).toBeInTheDocument();

    // Links into the detail page (title and View results).
    const titleLink = screen.getByRole("link", { name: "Gross fees and Intents volume" });
    expect(titleLink).toHaveAttribute("href", `/models/${RUN_ID}`);
    const viewLinks = screen.getAllByRole("link", { name: /View results/ });
    expect(viewLinks[0]).toHaveAttribute("href", `/models/${RUN_ID}`);

    // Pagination through the opaque next cursor.
    const next = screen.getByRole("link", { name: "Next page" });
    expect(new URL(next.getAttribute("href") ?? "", "http://localhost").searchParams.get("cursor")).toBe("MjA=");
  });

  it("shows the honest no-published-model empty state instead of a placeholder result", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/model-runs"
          ? jsonResponse({ items: [], next_cursor: null })
          : undefined,
    ]);
    await renderCatalog({});

    expect(screen.getByRole("heading", { name: "No published model yet" })).toBeInTheDocument();
    expect(
      screen.getByText(/No model run has completed the publication process/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "How models are verified and reproduced" }),
    ).toHaveAttribute("href", "/methodology#reproduce");
    // Nothing that could look like a result is rendered: no coefficient
    // table header and no statistic text appear anywhere.
    expect(screen.queryByText("Estimate")).not.toBeInTheDocument();
    expect(screen.queryByText(RUN_ID)).not.toBeInTheDocument();
  });

  it("renders a catalog failure honestly with retry", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/model-runs"
          ? apiError("DEPENDENCY_UNAVAILABLE", "The model API is unavailable", true, 503)
          : undefined,
    ]);
    await renderCatalog({});

    const alert = screen.getByRole("alert");
    expect(within(alert).getByText(/model catalog could not be loaded/)).toBeInTheDocument();
    expect(within(alert).getByText(/unavailable right now/)).toBeInTheDocument();
    expect(within(alert).getByText(/Nothing is shown rather than stale or fabricated runs/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: "Try again" })).toHaveAttribute("href", "/models");
  });

  it("fails honestly when the payload does not match the generated contract", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/model-runs"
          ? jsonResponse({ items: [{ run_id: "broken" }], next_cursor: null })
          : undefined,
    ]);
    await renderCatalog({});
    const alert = screen.getByRole("alert");
    expect(within(alert).getByText(/catalog could not be loaded/)).toBeInTheDocument();
    expect(screen.queryByText("broken")).not.toBeInTheDocument();
  });

  it("drops unapproved URL parameters and a malformed cursor with honest notes", async () => {
    const requests = installApiMock([
      (url) =>
        url.pathname === "/api/model-runs"
          ? jsonResponse({ items: [], next_cursor: null })
          : undefined,
    ]);
    await renderCatalog({ foo: "bar", cursor: "###bad###" });

    const catalogRequests = requestsTo(requests, "/api/model-runs");
    expect([...catalogRequests[0].searchParams.keys()]).toEqual([]);
    const status = screen.getByRole("status");
    expect(within(status).getByText("foo")).toBeInTheDocument();
    expect(within(status).getByText("cursor")).toBeInTheDocument();
    expect(within(status).getByText(/pagination cursor was not recognized/)).toBeInTheDocument();
    // The honest empty state still shows for the (empty) first page.
    expect(screen.getByRole("heading", { name: "No published model yet" })).toBeInTheDocument();
  });

  it("passes axe on the loaded catalog", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/model-runs"
          ? jsonResponse({ items: [summaryFixture()], next_cursor: null })
          : undefined,
    ]);
    const { container } = await renderCatalog({});
    await screen.findByText("Gross fees and Intents volume");
    expect(await axe(container, axeConfig)).toHaveNoViolations();
  });

  it("passes axe on the empty catalog", async () => {
    installApiMock([
      (url) =>
        url.pathname === "/api/model-runs"
          ? jsonResponse({ items: [], next_cursor: null })
          : undefined,
    ]);
    const { container } = await renderCatalog({});
    await screen.findByRole("heading", { name: "No published model yet" });
    expect(await axe(container, axeConfig)).toHaveNoViolations();
  });
});

// -- detail page (/models/{run_id}) --------------------------------------------- //

describe("Model run detail page — limits before coefficients, recorded values verbatim", () => {
  it("returns an anonymous reader to the exact published run after sign-in", async () => {
    const requests = installApiMock(detailRoutes());
    await renderDetail();
    // NI-097: the Add-to-research action lives in the Reproduction tab.
    await userEvent.click(screen.getByRole("tab", { name: "Reproduction" }));
    const link = await screen.findByRole("link", { name: "Sign in to add this model result" });
    expect(link).toHaveAttribute("href", `/login?next=${encodeURIComponent(`/models/${RUN_ID}`)}`);
    expect(requestsTo(requests, "/api/documents")).toHaveLength(0);
  });
  it("renders the scope limit before any number, with every gate limit code recorded", async () => {
    installApiMock(detailRoutes());
    const { container } = await renderDetail();

    // NI-097: the compact scope limit renders before any coefficient, and the
    // full recorded limitation set (prohibited labels, notes, every gate code,
    // admission reasons) stays complete inside the disclosure.
    const scopeLimit = screen.getByText(/Gross fees are calculated from volume through a fee rate/);
    const coefficients = container.querySelector('details[aria-label^="Exact data table"]');
    expect(coefficients).not.toBeNull();
    expect(
      scopeLimit.compareDocumentPosition(coefficients) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    const limitsText = container.textContent ?? "";
    for (const label of LIMITATIONS.prohibited_labels) {
      expect(limitsText).toContain(label);
    }
    const mechanical = screen.getAllByText(/Mechanical construction warning \(fixture\)/)[0];
    expect(
      mechanical.compareDocumentPosition(coefficients) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    for (const code of LIMITATIONS.gate_limit_codes) {
      expect(limitsText).toContain(code);
    }
    expect(limitsText).toContain("SPEC_PROXY_ADMITTED");
    expect(limitsText).toContain("informational");
    expect(limitsText).toContain("limit");
    expect(within(container).getByText(/must never be presented as/)).toBeInTheDocument();
    expect(container.textContent).toContain(RUN_ID);
  });

  it("renders recorded floats verbatim — no rounding, no re-formatting", async () => {
    installApiMock(detailRoutes());
    await renderDetail();

    // Sanity: the fixture literal round-trips through the verbatim conversion.
    expect(String(COEFFICIENTS[0].estimate)).toBe("0.012345678901234");
    // The exact recorded float64 text appears in the table.
    expect(screen.getByText("0.012345678901234")).toBeInTheDocument();
    expect(screen.getByText("0.987654321098765")).toBeInTheDocument();
    expect(screen.getByText("0.000123456789012345")).toBeInTheDocument();
    // NI-097: the inference renders as recorded combined rows.
    expect(screen.getByText("12.3456789012345 / 1.25e-12")).toBeInTheDocument();
    expect(
      screen.getByText(
        `${String(COEFFICIENTS[0].ci95_low)} to ${String(COEFFICIENTS[0].ci95_high)}`,
      ),
    ).toBeInTheDocument();
    // NI-097: the summary surface shows the slope rounded for display, marked
    // as rounded; the intercept is not summarized. "0.9877" (toFixed(4) of the
    // slope) renders in the finding block; "0.0123" (the intercept) stays out.
    expect(screen.getByText("0.9877")).toBeInTheDocument();
    expect(screen.getByText(/The summary above is rounded for display/)).toBeInTheDocument();
    expect(screen.queryByText("0.0123")).not.toBeInTheDocument();
  });

  it("keeps the recorded interpretation reachable verbatim (never paraphrased)", async () => {
    installApiMock(detailRoutes());
    await renderDetail();

    // NI-097: the curated finding sits above; the recorded interpretation
    // block stays complete inside its own disclosure.
    const interpretation = document.querySelector('details[aria-label="Recorded interpretation"]')
      ?? screen.getByText(/The recorded interpretation \(verbatim\)/).closest("details");
    expect(interpretation).not.toBeNull();
    expect((interpretation as HTMLElement).textContent).toContain("bounded_association_v1");
    expect((interpretation as HTMLElement).textContent).toContain("fixed template sentences over recorded numbers only");
    expect((interpretation as HTMLElement).textContent).toContain(INTERPRETATION.sentences[0]);
    expect((interpretation as HTMLElement).textContent).toContain(INTERPRETATION.sentences[1]);
    expect((interpretation as HTMLElement).textContent).toContain("Fixture authoring note");
  });

  it("renders the presented variables and the recorded readiness verdict (NI-097)", async () => {
    installApiMock(detailRoutes());
    await renderDetail();

    // The Specification tab shows the presented variables with their recorded
    // metric ids and sources.
    await userEvent.click(screen.getByRole("tab", { name: "Specification" }));
    const spec = screen.getByRole("region", { name: /What was estimated/ });
    expect(within(spec).getByText(/Provider gross fees · USD · daily log difference/)).toBeInTheDocument();
    expect(within(spec).getByText(/Intents volume · USD · daily log difference/)).toBeInTheDocument();
    expect(within(spec).getByText(/provider_gross_fees_usd \| SRC-LLAMA/)).toBeInTheDocument();
    expect(within(spec).getByText(/R² \/ adjusted R²/)).toBeInTheDocument();

    // The recorded readiness verdict renders as recorded (never invented).
    await userEvent.click(screen.getByRole("tab", { name: "Reproduction" }));
    expect(screen.getByText("READY_WITH_LIMITS (fixture)")).toBeInTheDocument();
    // Reason codes appear in the recorded limitations disclosure.
    await userEvent.click(screen.getByRole("tab", { name: "Result" }));
    expect(screen.getAllByText(/LIMIT_SHORT_SAMPLE/).length).toBeGreaterThan(0);
  });

  it("renders the manifest download link with the offline verify pointer", async () => {
    installApiMock(detailRoutes());
    await renderDetail();
    // NI-097: the reproduction record lives in the Reproduction tab.
    await userEvent.click(screen.getByRole("tab", { name: "Reproduction" }));

    const manifest = screen.getByRole("region", { name: /The reproduction bundle/ });
    const link = within(manifest).getByRole("link", { name: "Download the manifest bundle" });
    expect(link).toHaveAttribute("href", `/api/model-runs/${RUN_ID}/manifest`);
    expect(link).toHaveAttribute("download");
    // The reviewer verify pointer, verbatim.
    expect(
      within(manifest).getByText(
        "python -m near_api.research verify --bundle <downloaded.json> --offline",
      ),
    ).toBeInTheDocument();
    expect(within(manifest).getByText(/served immutably with a run-id ETag/)).toBeInTheDocument();
  });

  it("renders recorded verbatim blocks as JSON without rewriting them", async () => {
    installApiMock(detailRoutes());
    await renderDetail();
    await userEvent.click(screen.getByRole("tab", { name: "Specification" }));
    expect(screen.getByText(/"spec_id": "gross_fee_activity_v1"/)).toBeInTheDocument();
    expect(screen.getByText(/"method": "OLS with Newey-West HAC \(fixture\)"/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Reproduction" }));
    expect(screen.getByText(/"python": "3.13 \(fixture\)"/)).toBeInTheDocument();
    // The approval record renders reviewer and decision as recorded.
    expect(screen.getByText("Fixture reviewer (test) · approve")).toBeInTheDocument();
    expect(screen.getByText("fixture-review-reference-1")).toBeInTheDocument();
  });

  it("lands an unknown, unpublished or malformed identity on the generic 404 boundary", async () => {
    installApiMock([
      runDetailRoute(() => apiError("NOT_FOUND", "Resource was not found", false, 404)),
    ]);
    await expect(
      ModelRunPage({ params: Promise.resolve({ runId: RUN_ID }) }),
    ).rejects.toMatchObject({ digest: "NEXT_HTTP_ERROR_FALLBACK;404" });

    // A malformed identity gets the API's 422 and the same generic boundary —
    // no existence leak in either case.
    installApiMock([
      runDetailRoute(() =>
        jsonResponse(
          { detail: [{ loc: ["path", "run_id"], msg: "Input should be a valid UUID", type: "uuid_parsing" }] },
          422,
        ),
      ),
    ]);
    await expect(
      ModelRunPage({ params: Promise.resolve({ runId: "not-a-uuid" }) }),
    ).rejects.toMatchObject({ digest: "NEXT_HTTP_ERROR_FALLBACK;404" });
  });

  it("renders the generic not-found boundary without an existence leak", () => {
    render(<ModelNotFound />);
    expect(screen.getByRole("heading", { name: "Model run not found" })).toBeInTheDocument();
    expect(screen.getByText(/No published model run corresponds to this address/)).toBeInTheDocument();
    expect(screen.queryByText("Estimate")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open the model catalog" }),
    ).toHaveAttribute("href", "/models");
  });

  it("renders a non-404 resolution failure honestly with retry", async () => {
    installApiMock([
      runDetailRoute(() => apiError("DEPENDENCY_UNAVAILABLE", "The model API is unavailable", true, 503)),
    ]);
    await renderDetail();

    const alert = screen.getByRole("alert");
    expect(within(alert).getByText(/Model run unavailable/)).toBeInTheDocument();
    expect(within(alert).getByText(/could not be loaded right now/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: "Try again" })).toHaveAttribute(
      "href",
      `/models/${RUN_ID}`,
    );
  });

  it("keeps the run rendering when definition or readiness cannot be resolved", async () => {
    installApiMock([
      runDetailRoute(() => jsonResponse(detailFixture())),
      definitionRoute(apiError("NOT_FOUND", "Resource was not found", false, 404)),
      readinessRoute(apiError("DEPENDENCY_UNAVAILABLE", "The model API is unavailable", true, 503)),
    ]);
    await renderDetail();

    // The run's recorded content still renders (NI-097 presentation).
    expect(screen.getByText("0.012345678901234")).toBeInTheDocument();
    // A missing readiness never falls back to an invented verdict: the
    // recorded gate verdict stands in for the overall readiness line.
    await userEvent.click(screen.getByRole("tab", { name: "Reproduction" }));
    expect(screen.getAllByText("READY_WITH_LIMITS").length).toBeGreaterThan(0);
    expect(screen.queryByText(/could not be resolved for this run/)).not.toBeInTheDocument();
  });

  it("passes axe on the rendered run detail", async () => {
    installApiMock(detailRoutes());
    const { container } = await renderDetail();
    await screen.findByText("0.012345678901234");
    expect(await axe(container, axeConfig)).toHaveNoViolations();
  });
});

// -- readiness honesty (ready:false renders as not-admitted) -------------------- //

describe("ModelSpecificationPanel — honest ready:false", () => {
  it("renders a not-admitted verdict honestly without presenting a usable model", () => {
    render(<ModelSpecificationPanel definition={DEFINITION} readiness={READINESS_NOT_READY} />);

    expect(screen.getByText(/Ready: NO — this specification is not admitted/)).toBeInTheDocument();
    expect(screen.getByText(/nothing on this page presents a usable model/)).toBeInTheDocument();
    expect(screen.getByText("NOT_READY")).toBeInTheDocument();
    expect(screen.getByText("OQ01_REVENUE_SERIES_UNRESOLVED")).toBeInTheDocument();
    expect(screen.getByText("Rejecting")).toBeInTheDocument();
  });

  it("states honestly when the definition itself cannot be resolved", () => {
    render(<ModelSpecificationPanel definition={null} readiness={READINESS_READY} />);
    const statuses = screen.getAllByRole("status");
    expect(statuses.length).toBe(1);
    expect(statuses[0]).toHaveTextContent(/could not be resolved for this run/);
  });
});
