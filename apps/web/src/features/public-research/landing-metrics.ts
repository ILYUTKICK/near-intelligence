/**
 * NI-012 landing evidence metrics — server-side consumption of the NI-032
 * public delivery APIs for the landing page only.
 *
 * Rules implemented here (AGENTS.md / MVP_SCOPE / API_SPECIFICATION):
 * - At most three meaningful metrics are fetched, once, server-side; the
 *   browser makes no provider or API calls from this module.
 * - Decimal values stay exact strings end to end and are rendered verbatim;
 *   nothing is summed, rounded or reformatted into a Number. The only
 *   derived quantity is a non-financial count of observations, used to
 *   distinguish "no observations" from "observations exist".
 * - 503 DATA_NOT_READY, empty responses, failed contract validation and an
 *   unreachable API are honest typed states, never errors shown as zeros.
 * - No live badge: none of the saved evidence carries a recorded freshness
 *   guarantee, so the landing renders "as of <recorded timestamp>" only.
 * - Server-only: imports loadServerEnv, which reads API_INTERNAL_URL outside
 *   any client bundle. This module must never be imported by a client
 *   component.
 */

import { z } from "zod";

import { loadServerEnv } from "@/lib/env";

/**
 * The three landing metrics (the "at most 3" selection recorded in the
 * NI-012 task card). Each carries the mechanism stage it measures and why it
 * earns a place on the evidence-bearing landing:
 * - observed_near_purchases (A): the core measured quantity of the recorded
 *   thesis — exact conversion sums within the treasury-linked cohort; the
 *   subject of the supporting CL-001 and the contrary CL-002.
 * - treasury_payouts_near (A): the cash leg of the mechanism (matched native
 *   payouts to the three selected wallets, CL-003); a different flow from
 *   purchases and never added to it.
 * - provider_gross_fees_usd (P): the fee leg, explicitly gross and
 *   provider-reported (availability P, revisable) — never protocol revenue.
 */
export interface LandingMetricSource {
  readonly metricId: string;
  readonly definitionVersion: number;
}

export const landingMetricSources: readonly LandingMetricSource[] = [
  { metricId: "observed_near_purchases", definitionVersion: 1 },
  { metricId: "treasury_payouts_near", definitionVersion: 1 },
  { metricId: "provider_gross_fees_usd", definitionVersion: 1 },
] as const;

/**
 * Fixed selection window: the recorded 90-day observed cohort
 * (2026-08-06 through 2026-11-04, UTC, end exclusive) — the same window the
 * claim registry scopes every landing claim to. The landing never widens the
 * window from the wall clock: a trailing window would silently depend on
 * server time and could show nothing while approved data exists elsewhere.
 * If a future approved dataset covers a different window, this recorded
 * window honestly reports no covered observations instead of switching.
 */
export const landingSelectionWindow = {
  start: "2026-08-06",
  end: "2026-11-04",
  scope:
    "the recorded 90-day observed cohort, 2026-08-06 through 2026-11-04 (UTC, end exclusive)",
} as const;

/** Stable editorial anchors this module's consumers may link to. */
export const landingDefinitionHref = "/methodology#definitions" as const;
export const landingDatasetHref = "/methodology#collection" as const;

/**
 * Typed mirrors of the NI-032 delivery contract (packages/shared-types
 * generated client types are compile-time only; the server fetch path
 * validates the runtime shape with Zod before anything renders). A payload
 * that fails validation becomes an unavailable state — never a best-effort
 * render and never a fabricated value.
 */
const dataQualitySchema = z.object({
  status: z.enum(["ok", "partial", "missing", "stale", "unavailable", "revised"]),
  bound_kind: z.enum(["exact", "estimate", "lower", "upper"]).nullable(),
  reasons: z.array(z.string()),
  coverage: z.object({ observed: z.number(), expected: z.number() }),
  freshness_target_seconds: z.number().nullable(),
});

const metricSchema = z.object({
  id: z.string(),
  metric_id: z.string(),
  version: z.number(),
  title: z.string(),
  definition: z.string(),
  formula: z.string(),
  unit: z.string(),
  frequency: z.enum(["daily", "weekly", "monthly", "snapshot"]),
  source_id: z.string().nullable().optional(),
  economic_scope: z.string(),
  availability: z.enum(["A", "P", "B", "G"]),
  limitations: z.array(z.string()),
});

const datasetSchema = z.object({
  id: z.string(),
  dataset_key: z.string(),
  version: z.number(),
  status: z.literal("approved"),
  start: z.string(),
  end: z.string(),
  source_as_of: z.string().nullable(),
  retrieved_at: z.string().nullable(),
  pipeline_version: z.string(),
  content_sha256: z.string(),
  quality: dataQualitySchema,
  manifest_url: z.string().nullable(),
  supersedes_id: z.string().nullable(),
});

const observationSchema = z.object({
  start: z.string(),
  end: z.string(),
  value: z.string().nullable(),
  quality: dataQualitySchema,
});

const seriesSchema = z.object({
  metric: metricSchema,
  dataset: datasetSchema,
  selection: z.object({
    start: z.string(),
    end: z.string(),
    frequency: z.literal("day"),
    filters: z.record(z.string(), z.unknown()),
  }),
  points: z.array(observationSchema),
  sources: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      docs_url: z.string().nullable(),
      verified_at: z.string().nullable(),
      license_status: z.enum(["unknown", "unverified", "verified", "prohibited"]),
      access_status: z.enum(["disabled", "documented", "approved"]),
      lineage: z.array(z.string()),
      expected_update_frequency: z.string().nullable(),
      last_success_at: z.string().nullable(),
    }),
  ),
});

export type LandingSeries = z.infer<typeof seriesSchema>;
export type LandingQuality = z.infer<typeof dataQualitySchema>;

/** Internal anchors the metric strip may link to (no other internal links). */
export type LandingMetricHref = typeof landingDefinitionHref | typeof landingDatasetHref;

/**
 * Render states for one landing metric. `observation` carries the latest
 * approved value verbatim; `no-observations` means an approved dataset was
 * resolved but covers none of the recorded window with a value;
 * `unavailable` means the delivery API could not provide an approved answer
 * (503 DATA_NOT_READY, unreachable, malformed, or unknown metric).
 */
export type LandingMetricState =
  | {
      readonly kind: "observation";
      readonly metricId: string;
      readonly metric: LandingSeries["metric"];
      readonly dataset: LandingSeries["dataset"];
      readonly latest: {
        readonly value: string;
        readonly unit: string;
        readonly start: string;
        readonly end: string;
        readonly quality: LandingQuality;
      };
      /** Non-financial count: how many periods in the window hold a value. */
      readonly observationCount: number;
      readonly totalPeriods: number;
      /** Archive timestamp rendered as "as of" — never a live badge. */
      readonly asOf: string | null;
    }
  | {
      readonly kind: "no-observations";
      readonly metricId: string;
      readonly metricTitle: string;
      readonly dataset: LandingSeries["dataset"] | null;
      readonly unit: string;
      readonly reasons: readonly string[];
    }
  | {
      readonly kind: "unavailable";
      readonly metricId: string;
      readonly metricTitle: string;
      readonly reason: string;
    };

function unavailable(
  metricId: string,
  metricTitle: string,
  reason: string,
): LandingMetricState {
  return { kind: "unavailable", metricId, metricTitle, reason };
}

/**
 * The "as of" timestamp: source_as_of (the provider-side archive date) wins
 * over retrieved_at (our retrieval timestamp); both are recorded archive
 * facts. Neither is a freshness guarantee, so consumers render it as
 * "as of <date>" and never as a live indicator.
 */
function archiveAsOf(dataset: LandingSeries["dataset"]): string | null {
  return dataset.source_as_of ?? dataset.retrieved_at;
}

async function fetchMetricState(
  baseUrl: string,
  source: LandingMetricSource,
): Promise<LandingMetricState> {
  const url = new URL(`/api/metrics/${source.metricId}/series`, baseUrl);
  url.searchParams.set("definition_version", String(source.definitionVersion));
  url.searchParams.set("start", landingSelectionWindow.start);
  url.searchParams.set("end", landingSelectionWindow.end);
  url.searchParams.set("dataset_version", "latest");
  url.searchParams.set("frequency", "day");

  let response: Response;
  try {
    response = await fetch(url, {
      // Public latest-pointer reads are cached at the API for at most 60s;
      // the landing itself keeps no second cache layer.
      cache: "no-store",
      headers: { accept: "application/json" },
      signal: abortSignal(),
    });
  } catch {
    return unavailable(
      source.metricId,
      source.metricId,
      "The delivery API could not be reached, so no approved value is shown. This is not zero.",
    );
  }

  if (!response.ok) {
    if (response.status === 503) {
      return unavailable(
        source.metricId,
        source.metricId,
        "No approved dataset is published for this metric yet (the delivery API reports it is not ready). This is not zero.",
      );
    }
    if (response.status === 404) {
      return unavailable(
        source.metricId,
        source.metricId,
        "The delivery API does not publish this metric definition. This is not zero.",
      );
    }
    return unavailable(
      source.metricId,
      source.metricId,
      "The delivery API returned an unexpected response. This is not zero.",
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return unavailable(
      source.metricId,
      source.metricId,
      "The delivery API response was not valid JSON. This is not zero.",
    );
  }
  const parsed = seriesSchema.safeParse(payload);
  if (!parsed.success) {
    return unavailable(
      source.metricId,
      source.metricId,
      "The delivery API response failed contract validation. This is not zero.",
    );
  }
  const series = parsed.data;

  const valuedPoints = series.points.filter((point) => point.value !== null);
  const latestPoint = valuedPoints.at(-1);
  if (!latestPoint || latestPoint.value === null) {
    return {
      kind: "no-observations",
      metricId: source.metricId,
      metricTitle: series.metric.title,
      dataset: series.dataset,
      unit: series.metric.unit,
      // Point-level ambiguity/missing reasons must survive the API -> UI
      // boundary even when the dataset itself is approved. Deduplicate the
      // daily repetitions and bound the list shown on the landing.
      reasons: [...new Set([
        ...series.points.flatMap((point) => point.quality.reasons),
        ...series.dataset.quality.reasons,
      ])].slice(0, 20),
    };
  }

  return {
    kind: "observation",
    metricId: source.metricId,
    metric: series.metric,
    dataset: series.dataset,
    latest: {
      value: latestPoint.value,
      unit: series.metric.unit,
      start: latestPoint.start,
      end: latestPoint.end,
      quality: latestPoint.quality,
    },
    observationCount: valuedPoints.length,
    totalPeriods: series.points.length,
    asOf: archiveAsOf(series.dataset),
  };
}

/**
 * A bounded per-request abort so a hung API cannot hold the landing render.
 * Uses AbortSignal.timeout when the runtime provides it and falls back to a
 * manual timer otherwise (jsdom test runtimes may lack it).
 */
function abortSignal(): AbortSignal | undefined {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(10_000);
  }
  const controller = new AbortController();
  setTimeout(() => controller.abort(), 10_000);
  return controller.signal;
}

/**
 * Fetches the three landing metrics through the delivery API. Every failure
 * mode resolves to a typed state, so the landing page always renders and
 * never shows fabricated values in place of unavailable data.
 */
export async function fetchLandingMetrics(): Promise<LandingMetricState[]> {
  let baseUrl: string;
  try {
    baseUrl = loadServerEnv().API_INTERNAL_URL;
  } catch {
    return landingMetricSources.map((source) =>
      unavailable(
        source.metricId,
        source.metricId,
        "The web server configuration is invalid, so no approved value can be fetched. This is not zero.",
      ),
    );
  }
  return Promise.all(
    landingMetricSources.map((source) => fetchMetricState(baseUrl, source)),
  );
}
