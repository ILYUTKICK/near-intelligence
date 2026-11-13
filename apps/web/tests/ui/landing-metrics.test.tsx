/**
 * Retained NI-012 financial loader contracts. NI-086 makes Overview a static
 * editorial introduction; source validation and exact data delivery are still
 * independently tested here, without requiring obsolete cards on the homepage.
 * Every value in these tests is a labeled synthetic fixture.
 */
import { NextResponse } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchLandingMetrics,
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

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe("Retained exact landing-series loader contract", () => {
  it("resolves approved exact decimal strings, definitions, immutable dataset and source cutoff", async () => {
    const fetcher = stubSeriesFetch(approvedResponder());
    const states = await fetchLandingMetrics();
    expect(fetcher).toHaveBeenCalledTimes(3);
    for (const state of states) {
      expect(state.kind).toBe("observation");
      if (state.kind !== "observation") throw new Error("Expected approved observation");
      const metricId = state.metricId as FixtureMetricId;
      expect(state.latest.value).toBe(Object.values(fixtureValues[metricId])[0]);
      expect(state.metric.version).toBe(1);
      expect(state.dataset.id).toBe(fixtureDataset.id);
      expect(state.dataset.version).toBe(fixtureDataset.version);
      expect(state.asOf).toBe(fixtureDataset.source_as_of);
      expect(state.observationCount).toBe(1);
      expect(state.totalPeriods).toBe(90);
    }
  });

  it("keeps the latest available observation rather than summing financial values", async () => {
    stubSeriesFetch((url) => {
      const id = url.pathname.match(/([a-z_]+)\/series$/)![1] as FixtureMetricId;
      return { status: 200, body: seriesFixture(id, { "2026-11-01": "1000000.1234567890123456789", "2026-11-03": "0" }) };
    });
    const states = await fetchLandingMetrics();
    for (const state of states) {
      expect(state.kind).toBe("observation");
      if (state.kind === "observation") {
        expect(state.latest.value).toBe("0");
        expect(state.observationCount).toBe(2);
        expect(state.latest.start).toBe("2026-11-03T00:00:00Z");
      }
    }
  });

  it("keeps source-qualified stale data and exact original values", async () => {
    stubSeriesFetch((url) => {
      const id = url.pathname.match(/([a-z_]+)\/series$/)![1] as FixtureMetricId;
      return { status: 200, body: seriesFixture(id, fixtureValues[id], { qualityStatus: "stale" }) };
    });
    for (const state of await fetchLandingMetrics()) {
      expect(state.kind).toBe("observation");
      if (state.kind === "observation") {
        expect(state.latest.quality.status).toBe("stale");
        expect(state.latest.value).toBe(Object.values(fixtureValues[state.metricId as FixtureMetricId])[0]);
      }
    }
  });

  it("distinguishes all-null observations from economic zero and deduplicates provider ambiguity", async () => {
    const reason = "Synthetic fixture: multiple provider variants require an approved filter";
    stubSeriesFetch((url) => {
      const id = url.pathname.match(/([a-z_]+)\/series$/)![1] as FixtureMetricId;
      const body = seriesFixture(id, {});
      body.points.forEach((point) => { point.quality.reasons = [reason]; });
      return { status: 200, body };
    });
    for (const state of await fetchLandingMetrics()) {
      expect(state.kind).toBe("no-observations");
      if (state.kind === "no-observations") {
        expect(state.reasons).toEqual([reason]);
        expect(state.dataset?.id).toBe(fixtureDataset.id);
      }
    }
  });

  it.each([503, 404, 500])("preserves unavailable state for HTTP %s without a numeric fallback", async (status) => {
    stubSeriesFetch(() => ({ status, body: { error: { code: "DATA_NOT_READY" } } }));
    for (const state of await fetchLandingMetrics()) {
      expect(state.kind).toBe("unavailable");
      if (state.kind === "unavailable") expect(state.reason).toContain("not zero");
      expect(state).not.toHaveProperty("latest");
    }
  });

  it("returns typed unavailability when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("connection refused"); }));
    for (const state of await fetchLandingMetrics()) {
      expect(state.kind).toBe("unavailable");
      if (state.kind === "unavailable") expect(state.reason).toMatch(/could not be reached/);
    }
  });

  it("rejects numeric values that violate exact decimal-string transport", async () => {
    stubSeriesFetch((url) => {
      const id = url.pathname.match(/([a-z_]+)\/series$/)![1] as FixtureMetricId;
      const body = seriesFixture(id, { "2026-11-03": "42.5" }) as Record<string, unknown>;
      (body.points as { value: unknown }[])[89].value = 0;
      return { status: 200, body };
    });
    for (const state of await fetchLandingMetrics()) {
      expect(state.kind).toBe("unavailable");
      if (state.kind === "unavailable") expect(state.reason).toMatch(/contract validation/);
    }
  });

  it("rejects malformed JSON instead of substituting data", async () => {
    stubSeriesFetch(() => new NextResponse("<html>maintenance</html>", { status: 200 }));
    for (const state of await fetchLandingMetrics()) expect(state.kind).toBe("unavailable");
  });
});
