/**
 * NI-012 landing evidence metrics.
 *
 * Matrix driven through the real fetch → validate → render path:
 * - approved saved input renders exact decimal strings with definition and
 *   dataset references and archive dates (API-to-render integration against
 *   a fixture shaped exactly like the implemented NI-032 contract; the true
 *   cluster/HTTP integration lives in apps/api/tests/test_landing_integration.py);
 * - 503 DATA_NOT_READY, all-null series, unreachable API and malformed or
 *   contract-invalid payloads render typed fallback states — never zeros;
 * - stale data keeps the values and shows the stale notice;
 * - claim citations trace into the thesis anchors and the claim registry;
 * - CTAs reach /research, /methodology and /workspace; no live badge exists;
 * - content-width discipline, DOM order, axe and private-metadata checks.
 *
 * Fixtures are synthetic and visibly labeled (ni012-fixture dataset keys);
 * they never stand in for real production metrics.
 */
import { axe } from "jest-axe";
import { NextResponse } from "next/server";
import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/(public)/page";
import { claimRegistry, thesisToc } from "@/features/public-research/content";
import {
  getLandingClaim,
  landingFindings,
} from "@/features/public-research/landing-findings";
import {
  landingDatasetHref,
  landingDefinitionHref,
  landingMetricSources,
  landingSelectionWindow,
} from "@/features/public-research/landing-metrics";

// The server env contract must resolve before fetchLandingMetrics runs
// (loadServerEnv caches on first success); process.env wins over any .env.
process.env.APP_ENV = process.env.APP_ENV ?? "test";
process.env.APP_ORIGIN = process.env.APP_ORIGIN ?? "http://localhost:3000";
process.env.API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

/** Registry facts mirrored into the fixture (single source: apps/api registry). */
const fixtureMetrics = {
  observed_near_purchases: {
    title: "Observed NEAR purchases (treasury-linked cohort)",
    unit: "NEAR",
    availability: "A" as const,
    limitation: "Acquisitions within the observed pool, not all-market NEAR demand.",
  },
  treasury_payouts_near: {
    title: "Treasury payouts from intents.near (three named wallets)",
    unit: "NEAR",
    availability: "A" as const,
    limitation: "Cash transfers out of the intents contract, not accrual revenue or profit.",
  },
  provider_gross_fees_usd: {
    title: "Provider-reported Intents gross fees (source-qualified)",
    unit: "USD",
    availability: "P" as const,
    limitation: "Not revenue retained by NEAR and not attributable protocol revenue.",
  },
} as const;

type FixtureMetricId = keyof typeof fixtureMetrics;

const okQuality = {
  status: "ok" as const,
  bound_kind: "exact" as const,
  reasons: [],
  coverage: { observed: 90, expected: 90 },
  freshness_target_seconds: null,
};

const fixtureDataset = {
  id: "7b0d3f52-6b0a-4d5e-9f8a-1c2b3d4e5f60",
  dataset_key: "ni012-fixture-approved-dataset",
  version: 3,
  status: "approved" as const,
  start: landingSelectionWindow.start,
  end: landingSelectionWindow.end,
  source_as_of: "2026-11-04T00:00:00Z",
  retrieved_at: "2026-11-05T06:30:00Z",
  pipeline_version: "ni012-fixture",
  content_sha256: "fixture-content-sha256",
  quality: okQuality,
  manifest_url: null,
  supersedes_id: null,
};

function fixtureSource(sourceId: string) {
  return {
    id: sourceId,
    name: `Fixture source ${sourceId}`,
    docs_url: null,
    verified_at: "2026-11-04T00:00:00Z",
    license_status: "verified" as const,
    access_status: "approved" as const,
    lineage: ["fixture lineage"],
    expected_update_frequency: null,
    last_success_at: null,
  };
}

/** All UTC days of the recorded selection window, 2026-08-06 .. 2026-11-03. */
function selectionDays(): string[] {
  const days: string[] = [];
  const current = new Date(`${landingSelectionWindow.start}T00:00:00Z`);
  const end = new Date(`${landingSelectionWindow.end}T00:00:00Z`);
  while (current < end) {
    days.push(current.toISOString().slice(0, 10));
    current.setUTCDate(current.getUTCDate() + 1);
  }
  return days;
}

function buildPoints(valuesByDay: Partial<Record<string, string>>, qualityStatus: "ok" | "stale") {
  const days = selectionDays();
  return days.map((day) => {
    const value = valuesByDay[day] ?? null;
    const nextDay = new Date(`${day}T00:00:00Z`);
    nextDay.setUTCDate(nextDay.getUTCDate() + 1);
    return {
      start: `${day}T00:00:00Z`,
      end: `${nextDay.toISOString().slice(0, 10)}T00:00:00Z`,
      value,
      quality:
        value === null
          ? {
              status: "missing" as const,
              bound_kind: null,
              reasons: ["fixture: no observation staged for this day"],
              coverage: { observed: 0, expected: 1 },
              freshness_target_seconds: null,
            }
          : {
              status: qualityStatus,
              bound_kind: "exact" as const,
              reasons: [],
              coverage: { observed: 1, expected: 1 },
              freshness_target_seconds: null,
            },
    };
  });
}

function seriesFixture(
  metricId: FixtureMetricId,
  valuesByDay: Partial<Record<string, string>>,
  options: { qualityStatus?: "ok" | "stale"; dataset?: typeof fixtureDataset } = {},
) {
  const meta = fixtureMetrics[metricId];
  return {
    metric: {
      id: `fixture-metric-definition-${metricId}`,
      metric_id: metricId,
      version: 1,
      title: meta.title,
      definition: "Fixture definition text mirroring the registered metric definition.",
      formula: `${metricId}_v1`,
      unit: meta.unit,
      frequency: "daily" as const,
      source_id: "SRC-FIXTURE",
      economic_scope: "Fixture scope text.",
      availability: meta.availability,
      limitations: [meta.limitation],
    },
    dataset: options.dataset ?? fixtureDataset,
    selection: {
      start: landingSelectionWindow.start,
      end: landingSelectionWindow.end,
      frequency: "day" as const,
      filters: {},
    },
    points: buildPoints(valuesByDay, options.qualityStatus ?? "ok"),
    sources: [fixtureSource("SRC-FIXTURE")],
  };
}

/** Exact fixture values; rendered output must match them verbatim. */
const fixtureValues: Record<FixtureMetricId, Partial<Record<string, string>>> = {
  observed_near_purchases: { "2026-11-02": "1234.567890123456789012345678" },
  treasury_payouts_near: { "2026-11-03": "9876.543210987654321098765432" },
  provider_gross_fees_usd: { "2026-11-03": "4242.42" },
};

type Responder = (url: URL) => { status: number; body: unknown } | Response;

function stubSeriesFetch(responder: Responder) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    const result = responder(url);
    if (result instanceof Response) {
      return result;
    }
    return NextResponse.json(result.body, { status: result.status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function approvedResponder(): Responder {
  return (url) => {
    const match = url.pathname.match(/^\/api\/metrics\/([a-z_]+)\/series$/);
    expect(match, `unexpected fetch path ${url.pathname}`).not.toBeNull();
    const metricId = match![1] as FixtureMetricId;
    expect(fixtureMetrics[metricId]).toBeDefined();
    // The request itself must encode the recorded selection and latest semantics.
    expect(url.searchParams.get("definition_version")).toBe("1");
    expect(url.searchParams.get("start")).toBe(landingSelectionWindow.start);
    expect(url.searchParams.get("end")).toBe(landingSelectionWindow.end);
    expect(url.searchParams.get("dataset_version")).toBe("latest");
    expect(url.searchParams.get("frequency")).toBe("day");
    return {
      status: 200,
      body: seriesFixture(metricId, fixtureValues[metricId]),
    };
  };
}

async function renderLanding() {
  const { container } = render(await HomePage());
  return container;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Approved saved input renders source-qualified values", () => {
  it("renders the exact decimal strings with definition/dataset references and archive dates", async () => {
    stubSeriesFetch(approvedResponder());
    const container = await renderLanding();

    for (const source of landingMetricSources) {
      const meta = fixtureMetrics[source.metricId as FixtureMetricId];
      const card = document.getElementById(`${source.metricId}-metric-heading`)?.closest("article");
      expect(card, `card for ${source.metricId}`).not.toBeNull();
      const scope = within(card as HTMLElement);
      // Registry title and the exact metric identity + availability letter.
      expect(scope.getByRole("heading", { name: meta.title })).toBeInTheDocument();
      expect(scope.getByText(source.metricId)).toBeInTheDocument();
      expect(scope.getByText(`v1 — availability ${meta.availability}`)).toBeInTheDocument();
      // The exact decimal string, verbatim, with its unit and half-open period.
      const value = Object.values(fixtureValues[source.metricId as FixtureMetricId])[0]!;
      expect(scope.getByText(value)).toBeInTheDocument();
      expect(scope.getByText(new RegExp(`^${meta.unit.replace(/[()]/g, "\\$&")}$`))).toBeInTheDocument();
      expect(container.textContent).toMatch(/UTC half-open period/);
      // Definition/dataset links and the recorded archive date ("as of").
      const links = Array.from(card!.querySelectorAll("a")).map((a) => a.getAttribute("href"));
      expect(links).toContain(landingDefinitionHref);
      expect(links).toContain(landingDatasetHref);
      expect(scope.getByText("Data as of:")).toBeInTheDocument();
      expect(scope.getByText(fixtureDataset.source_as_of)).toBeInTheDocument();
      // Dataset identity: key, immutable version, approved status, coverage.
      expect(
        scope.getByText(
          `${fixtureDataset.dataset_key} v${fixtureDataset.version} (${fixtureDataset.status}), covering ${fixtureDataset.start} through ${fixtureDataset.end} (UTC, end exclusive)`,
        ),
      ).toBeInTheDocument();
    }
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("never shows a live badge — only the as-of archive date", async () => {
    stubSeriesFetch(approvedResponder());
    await renderLanding();
    // No element presents itself as a live indicator; the only freshness
    // language is the "as of" archive line. (The prose may honestly explain
    // that no live badge exists, so the assertion is structural.)
    for (const label of [/^live$/i, /^live data$/i, /^real-?time$/i]) {
      expect(screen.queryByText(label)).toBeNull();
    }
    expect(screen.getAllByText("Data as of:")).toHaveLength(3);
    expect(screen.getAllByText(/recorded archive timestamp, UTC/)).toHaveLength(3);
  });

  it("counts observation coverage without inventing aggregate values", async () => {
    stubSeriesFetch(approvedResponder());
    await renderLanding();
    // 90 daily periods in the recorded window; each fixture metric carries one value.
    const coverageLines = screen.getAllByText(/1 of 90 periods hold a value/);
    expect(coverageLines).toHaveLength(3);
  });
});

describe("Unavailable-source cases render honest fallbacks, never zeros", () => {
  it("renders the typed unavailable state for 503 DATA_NOT_READY", async () => {
    stubSeriesFetch(() => ({
      status: 503,
      body: {
        error: {
          code: "DATA_NOT_READY",
          message: "No approved dataset exists for latest",
          request_id: "fixture-request",
          retryable: true,
        },
      },
    }));
    const container = await renderLanding();
    expect(screen.getAllByText(/Unavailable — this is not zero/)).toHaveLength(3);
    for (const values of Object.values(fixtureValues)) {
      for (const value of Object.values(values)) {
        expect(document.body.textContent).not.toContain(value);
      }
    }
    // No metric card claims a resolved observation.
    expect(screen.queryAllByText(/Latest approved observation in/)).toHaveLength(0);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("renders the empty state when an approved dataset covers no period with a value", async () => {
    stubSeriesFetch((url) => {
      const metricId = url.pathname.match(/([a-z_]+)\/series$/)![1] as FixtureMetricId;
      return { status: 200, body: seriesFixture(metricId, {}) };
    });
    await renderLanding();
    expect(screen.getAllByText(/No data for this selection/)).toHaveLength(3);
    expect(screen.getAllByText(/An empty result is not zero/).length).toBeGreaterThanOrEqual(3);
    expect(document.body.textContent).not.toContain("1234.567890123456789012345678");
  });

  it("preserves and deduplicates point-level provider ambiguity reasons", async () => {
    const reason = "Synthetic fixture: multiple provider variants require an approved filter";
    stubSeriesFetch((url) => {
      const metricId = url.pathname.match(/([a-z_]+)\/series$/)![1] as FixtureMetricId;
      const body = seriesFixture(metricId, {});
      body.points.forEach((point) => { point.quality.reasons = [reason]; });
      return { status: 200, body };
    });
    await renderLanding();
    expect(screen.getAllByText(reason)).toHaveLength(3);
    expect(screen.queryAllByText(/Latest approved observation in/)).toHaveLength(0);
    expect(screen.getAllByText(/No unambiguous approved value/)).toHaveLength(3);
  });

  it("renders the unavailable state when the delivery API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );
    await renderLanding();
    expect(screen.getAllByText(/Data failed to load|Unavailable — this is not zero/).length).toBe(3);
    expect(document.body.textContent).toMatch(/could not be reached/);
  });

  it("fails contract validation into the unavailable state instead of rendering a numeric value", async () => {
    // A numeric value (0) violates the decimal-string contract; rendering it
    // would silently turn a missing value into a zero.
    stubSeriesFetch((url) => {
      const metricId = url.pathname.match(/([a-z_]+)\/series$/)![1] as FixtureMetricId;
      const body = seriesFixture(metricId, { "2026-11-03": "42.5" }) as Record<string, unknown>;
      (body.points as { value: unknown }[])[89].value = 0;
      return { status: 200, body };
    });
    await renderLanding();
    expect(screen.getAllByText(/Unavailable — this is not zero/)).toHaveLength(3);
    expect(document.body.textContent).not.toContain("42.5");
  });

  it("renders the unavailable state for a non-JSON response body", async () => {
    stubSeriesFetch(() => new NextResponse("<html>maintenance</html>", { status: 200 }));
    await renderLanding();
    expect(screen.getAllByText(/Unavailable — this is not zero/)).toHaveLength(3);
  });
});

describe("Stale data keeps values and shows the stale notice", () => {
  it("renders the stale notice with the last verified values", async () => {
    stubSeriesFetch((url) => {
      const metricId = url.pathname.match(/([a-z_]+)\/series$/)![1] as FixtureMetricId;
      return {
        status: 200,
        body: seriesFixture(metricId, fixtureValues[metricId], { qualityStatus: "stale" }),
      };
    });
    const container = await renderLanding();
    expect(screen.getAllByText(/Showing the last verified values/)).toHaveLength(3);
    expect(document.body.textContent).toContain("1234.567890123456789012345678");
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe("For/against findings cite the claim registry", () => {
  it("renders the four landing claims with their full quantity tables", async () => {
    stubSeriesFetch(approvedResponder());
    await renderLanding();
    const expectedIds = [
      ...landingFindings.forSide.claimIds,
      ...landingFindings.againstSide.claimIds,
    ];
    expect(expectedIds).toEqual(["CL-001", "CL-003", "CL-002", "CL-007"]);
    for (const id of expectedIds) {
      const claim = getLandingClaim(id);
      expect(screen.getByRole("heading", { level: 3, name: claim.title })).toBeInTheDocument();
      expect(
        screen.getByText(`${id} recorded quantities, scopes and sources`),
      ).toBeInTheDocument();
      // The rendered claim is the registry object itself (trace, not a copy).
      const registryClaim = claimRegistry.find((entry) => entry.id === id);
      expect(registryClaim).toBeDefined();
      expect(screen.getByText(claim.observation)).toBeInTheDocument();
    }
  });

  it("links each side into the thesis section that owns the claims", async () => {
    stubSeriesFetch(approvedResponder());
    const container = await renderLanding();
    const tocIds = new Set(thesisToc.map((entry) => entry.id));
    for (const side of [landingFindings.forSide, landingFindings.againstSide]) {
      const anchor = screen.getByRole("link", { name: side.anchorLabel });
      expect(anchor.getAttribute("href")).toBe(side.thesisAnchor);
      const sectionId = side.thesisAnchor.split("#")[1];
      expect(tocIds.has(sectionId), `${side.thesisAnchor} is a real thesis section`).toBe(true);
      expect(
        thesisToc.find((entry) => entry.id === sectionId),
      ).toBeDefined();
    }
    // Every internal href on the landing resolves to an implemented route,
    // a recorded methodology anchor or a thesis section anchor.
    const allowed = new Set<string>([
      "/research",
      "/methodology",
      "/workspace",
      landingDefinitionHref,
      landingDatasetHref,
      landingFindings.forSide.thesisAnchor,
      landingFindings.againstSide.thesisAnchor,
      ...claimRegistry.flatMap((claim) => claim.evidence.map((link) => link.href)),
    ]);
    const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    for (const href of hrefs) {
      expect(
        allowed.has(href as string),
        `unexpected landing link ${href}`,
      ).toBe(true);
    }
  });

  it("keeps the recorded basis statement and never claims live data", async () => {
    stubSeriesFetch(approvedResponder());
    await renderLanding();
    expect(screen.getByText(new RegExp(landingFindings.recordedBasis.slice(0, 60), "i"))).toBeInTheDocument();
    expect(document.body.textContent).toMatch(/2026-08-06/);
    expect(document.body.textContent).toMatch(/2026-11-04/);
    // No rendered element presents live data; only archive dates are claimed.
    expect(screen.queryByText(/^live/i)).toBeNull();
  });
});

describe("CTAs reach the correct destinations", () => {
  it("links research, methodology and the gated workspace", async () => {
    stubSeriesFetch(approvedResponder());
    await renderLanding();
    const research = screen.getAllByRole("link", { name: /Read the (research|full thesis)/ });
    expect(research.map((a) => a.getAttribute("href"))).toEqual(["/research", "/research"]);
    expect(screen.getByRole("link", { name: "How the numbers are made" }).getAttribute("href")).toBe("/methodology");
    expect(screen.getByRole("link", { name: "Check the methodology" }).getAttribute("href")).toBe("/methodology");
    // Two workspace CTAs (header list and closing section), both to /workspace,
    // whose layout redirects unauthenticated visits to /login.
    const workspace = screen.getAllByRole("link", { name: "Open the workspace" });
    expect(workspace).toHaveLength(2);
    workspace.forEach((link) => expect(link.getAttribute("href")).toBe("/workspace"));
  });
});

describe("Layout discipline and DOM order", () => {
  it("keeps content-width classes and the documented section order", async () => {
    stubSeriesFetch(approvedResponder());
    const container = await renderLanding();
    const root = (container as HTMLElement).firstElementChild as HTMLElement;
    expect(root.className).toMatch(/max-w-\(--width-content-max\)/);
    // Prose width on the editorial blocks.
    expect(root.querySelector("p.max-w-\\(--width-prose\\)")).not.toBeNull();
    // Single-column stacking for the metric strip (content maximum, no fixed widths).
    const strip = document.getElementById("evidence")?.querySelector("ul");
    expect(strip?.className).toMatch(/flex-col/);

    const order = (a: Element | null, b: Element | null) =>
      a !== null && b !== null && Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    const evidence = document.getElementById("evidence");
    const findings = document.getElementById(landingFindings.id);
    const mechanism = document.getElementById("mechanism");
    const heading = screen.getByRole("heading", { level: 1, name: "NEAR Intelligence" });
    expect(order(heading, evidence), "h1 before evidence").toBe(true);
    expect(order(evidence, findings), "evidence before findings").toBe(true);
    expect(order(findings, mechanism), "findings before mechanism").toBe(true);
  });
});

describe("No private editor metadata on the public landing", () => {
  const privateMetadataPatterns: RegExp[] = [
    /document[_-]?id/i,
    /revision[_-]?id/i,
    /user[_-]?id/i,
    /owner[_-]?id/i,
    /\bsupabase\b/i,
    /\bBearer\b/,
    /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i,
  ];

  it("keeps identifiers out of the rendered page even when the fixture carries them", async () => {
    stubSeriesFetch(approvedResponder());
    const container = await renderLanding();
    const text = (container.textContent ?? "") + " " + container.innerHTML;
    for (const pattern of privateMetadataPatterns) {
      expect(text).not.toMatch(pattern);
    }
  });
});
