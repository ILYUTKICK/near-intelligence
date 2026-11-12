import { z } from "zod";

/**
 * Render-boundary validation of the NI-032 public delivery payloads (NI-034).
 *
 * These schemas mirror the generated contracts in
 * @near-intelligence/shared-types exactly as documents/list/documents-schema.ts
 * mirrors the document contracts: they are a validation boundary, never a
 * second DTO source — the TypeScript types stay derived from the generated
 * package, and any API/contract drift fails honestly here instead of
 * rendering a malformed response.
 */

const isoDate = z.string().regex(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/, "expected YYYY-MM-DD");
const sha256Hex = z.string().regex(/^[0-9a-f]{64}$/, "expected a sha256 hex digest");

export const dataQualitySchema = z.object({
  status: z.enum(["ok", "partial", "missing", "stale", "unavailable", "revised"]),
  bound_kind: z.enum(["exact", "estimate", "lower", "upper"]).nullable(),
  reasons: z.array(z.string()),
  coverage: z.object({ observed: z.number().int().nonnegative(), expected: z.number().int().nonnegative() }),
  freshness_target_seconds: z.number().int().nonnegative().nullable(),
});

export const metricResponseSchema = z.object({
  id: z.uuid(),
  metric_id: z.string().min(1).max(80),
  version: z.number().int().positive(),
  title: z.string().min(1).max(200),
  definition: z.string().min(1),
  formula: z.string().min(1).max(80),
  unit: z.string().min(1).max(40),
  frequency: z.enum(["daily", "weekly", "monthly", "snapshot"]),
  source_id: z.string().min(1).max(40).nullable(),
  economic_scope: z.string().min(1),
  availability: z.enum(["A", "P", "B", "G"]),
  limitations: z.array(z.string()),
});

export const dataSourceResponseSchema = z.object({
  id: z.string().min(1).max(40),
  name: z.string().min(1).max(200),
  docs_url: z.string().nullable(),
  verified_at: z.string().nullable(),
  license_status: z.enum(["unknown", "unverified", "verified", "prohibited"]),
  access_status: z.enum(["disabled", "documented", "approved"]),
  lineage: z.array(z.string()),
  expected_update_frequency: z.string().nullable(),
  last_success_at: z.string().nullable(),
});

export const datasetResponseSchema = z.object({
  id: z.uuid(),
  dataset_key: z.string().min(1).max(120),
  version: z.number().int().positive(),
  status: z.literal("approved"),
  start: isoDate,
  end: isoDate,
  source_as_of: z.string().nullable(),
  retrieved_at: z.string().nullable(),
  pipeline_version: z.string().min(1).max(80),
  content_sha256: sha256Hex,
  quality: dataQualitySchema,
  manifest_url: z.string().nullable(),
  supersedes_id: z.uuid().nullable(),
});

export const observationSchema = z.object({
  start: z.string(),
  end: z.string(),
  value: z.string().nullable(),
  quality: dataQualitySchema,
});

export const availableRangesSchema = z.object({
  presets_days: z.array(z.number().int().positive()).min(1),
  max_days: z.number().int().positive(),
});

export const chartDefinitionResponseSchema = z.object({
  id: z.uuid(),
  chart_id: z.string().min(1).max(80),
  version: z.number().int().positive(),
  title: z.string().min(1).max(200),
  description: z.string().min(1).max(1000),
  category: z.enum(["activity", "fees", "treasury", "supply", "model"]),
  metric_definition_ids: z.array(z.uuid()),
  visualization_type: z.enum(["line", "area", "bar", "scatter", "panels"]),
  units: z.record(z.string(), z.string()),
  filter_schema: z.record(z.string(), z.unknown()),
  available_ranges: availableRangesSchema,
  renderer_version: z.string().min(1).max(80),
  update_frequency: z.enum(["daily", "weekly", "monthly", "snapshot"]),
  data_status: z.enum(["available", "unavailable"]),
  unavailable_reason: z.string().nullable(),
  source_lineage: z.record(z.string(), z.unknown()),
});

export const chartListResponseSchema = z.object({
  items: z.array(chartDefinitionResponseSchema),
  next_cursor: z.string().nullable(),
});

export const resolvedSelectionSchema = z.object({
  start: isoDate,
  end: isoDate,
  frequency: z.literal("day"),
  filters: z.record(z.string(), z.union([z.string().min(1), z.array(z.string().min(1)).min(1).max(32)])),
});

export const seriesResponseSchema = z.object({
  metric: metricResponseSchema,
  dataset: datasetResponseSchema,
  selection: resolvedSelectionSchema,
  points: z.array(observationSchema),
  sources: z.array(dataSourceResponseSchema),
});

export const chartViewResponseSchema = z.object({
  definition: chartDefinitionResponseSchema,
  selection: resolvedSelectionSchema,
  dataset: datasetResponseSchema,
  series: z.array(seriesResponseSchema),
  resolved_at: z.string(),
  context_hash: sha256Hex,
  quality: dataQualitySchema,
});

export const apiErrorResponseSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string(),
    retryable: z.boolean(),
    details: z.array(z.object({ path: z.string(), reason: z.string() })).nullish(),
  }),
});
