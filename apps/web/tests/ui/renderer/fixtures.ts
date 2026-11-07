/**
 * Synthetic chart fixtures for NI-033 renderer tests.
 *
 * EVERY value here is synthetic and labeled — none of it is production or
 * research data. Shapes come from the generated NI-032 contracts
 * (packages/shared-types); tests must stay valid against the contract.
 */
import type { ChartDefinitionResponse, ChartViewResponse, MetricResponse, Observation, SeriesResponse } from "@/features/charts/renderer/view-types";
import { RENDERER_VERSION } from "@/features/charts/renderer/view-types";

let fixtureCounter = 0;

function fixtureUuid(): string {
  fixtureCounter += 1;
  const suffix = fixtureCounter.toString(16).padStart(12, "0");
  return `00000000-0000-4000-8000-${suffix}`;
}

export function okQuality() {
  return {
    status: "ok" as const,
    bound_kind: null,
    reasons: [],
    coverage: { observed: 1, expected: 1 },
    freshness_target_seconds: 86_400,
  };
}

export function missingQuality(reason = "no observation for the period") {
  return {
    status: "missing" as const,
    bound_kind: null,
    reasons: [reason],
    coverage: { observed: 0, expected: 1 },
    freshness_target_seconds: null,
  };
}

export function lowerBoundQuality() {
  return {
    status: "ok" as const,
    bound_kind: "lower" as const,
    reasons: [],
    coverage: { observed: 1, expected: 1 },
    freshness_target_seconds: 86_400,
  };
}

export function observation(
  day: string,
  value: string | null,
  quality: Observation["quality"] = value === null ? missingQuality() : okQuality(),
): Observation {
  return {
    start: `${day}T00:00:00Z`,
    end: `${nextDay(day)}T00:00:00Z`,
    value,
    quality,
  };
}

function nextDay(day: string): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

export function metric(unit: string, title: string, metricId: string): MetricResponse {
  return {
    id: fixtureUuid(),
    metric_id: metricId,
    version: 1,
    title,
    definition: "Synthetic metric definition for renderer tests (fixture).",
    formula: "synthetic_sum (fixture)",
    unit,
    frequency: "daily",
    source_id: "SRC-FIXTURE",
    economic_scope: "Synthetic scope; test fixture only.",
    availability: "A",
    limitations: ["Synthetic fixture — never published data."],
  };
}

export function series(
  metricDefinition: MetricResponse,
  points: Observation[],
  window: { start: string; end: string } = { start: "2026-11-01", end: "2026-11-06" },
): SeriesResponse {
  return {
    metric: metricDefinition,
    dataset: dataset(window),
    selection: { start: window.start, end: window.end, frequency: "day", filters: {} },
    points,
    sources: [fixtureSource()],
  };
}

export function dataset(window: { start: string; end: string }) {
  return {
    id: fixtureUuid(),
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

export function fixtureSource() {
  return {
    id: "SRC-FIXTURE",
    name: "Synthetic fixture source (test fixture)",
    docs_url: "https://docs.example.test/fixture",
    verified_at: null,
    license_status: "verified" as const,
    access_status: "documented" as const,
    lineage: ["fixture step: synthetic"],
    expected_update_frequency: null,
    last_success_at: null,
  };
}

export function definition(overrides: Partial<ChartDefinitionResponse> = {}): ChartDefinitionResponse {
  return {
    id: fixtureUuid(),
    chart_id: "synthetic-volume",
    version: 1,
    title: "Synthetic daily volume (fixture)",
    description: "Synthetic chart description for renderer tests (fixture).",
    category: "activity",
    metric_definition_ids: [],
    visualization_type: "line",
    units: { required_primary: "USD" },
    filter_schema: { type: "object", properties: {}, additionalProperties: false },
    available_ranges: { presets_days: [7, 30, 90], max_days: 366 },
    renderer_version: RENDERER_VERSION,
    update_frequency: "daily",
    data_status: "available",
    unavailable_reason: null,
    source_lineage: { sources: ["SRC-FIXTURE"], note: "Synthetic lineage note (fixture)." },
    ...overrides,
  };
}

export function view(
  definitionFixture: ChartDefinitionResponse,
  seriesList: SeriesResponse[],
  overrides: Partial<ChartViewResponse> = {},
): ChartViewResponse {
  return {
    definition: definitionFixture,
    selection: seriesList[0]?.selection ?? {
      start: "2026-11-01",
      end: "2026-11-06",
      frequency: "day",
      filters: {},
    },
    dataset: seriesList[0]?.dataset ?? dataset({ start: "2026-11-01", end: "2026-11-06" }),
    series: seriesList,
    resolved_at: "2026-11-06T12:00:00Z",
    context_hash: "b".repeat(64),
    quality: {
      status: "ok",
      bound_kind: null,
      reasons: [],
      coverage: { observed: 5, expected: 5 },
      freshness_target_seconds: 86_400,
    },
    ...overrides,
  };
}

/** A 30-significant-digit decimal string — far beyond float precision. */
export const HUGE_DECIMAL = "123456789012345678901234567890.5";
