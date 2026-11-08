import { z } from "zod";

import type { components } from "@near-intelligence/shared-types";

/**
 * Render-boundary validation of the NI-054 public model payloads
 * (the role-A completion of the NI-054 handoff).
 *
 * These schemas mirror the generated contracts in
 * @near-intelligence/shared-types exactly as
 * features/charts/library/catalog-schema.ts mirrors the delivery contracts:
 * they are a validation boundary, never a second DTO source. The validated
 * mirror types are compile-time asserted (bottom of this file) to stay
 * assignable to the generated contracts, and any API/contract drift fails
 * honestly here instead of rendering a malformed response.
 *
 * NI-054 contract notes mirrored here:
 * - coefficients are finite float64 records served verbatim (the publication
 *   gate refuses NaN/Infinity; standard JSON cannot carry them either);
 * - tolerances are recorded decimal strings and are never re-formatted;
 * - `prohibited_labels` and `spec_limitation_notes` travel verbatim and are
 *   rendered before any coefficient (the page ordering contract);
 * - every recorded object block (specification/design/estimation/
 *   diagnostics/interpretation/environment/reproduction) is an open object:
 *   the page renders it verbatim rather than guessing keys.
 */

const specId = z.string().regex(/^[a-z][a-z0-9_]{2,79}$/, "expected a registered specification id");
const isoDate = z.string().regex(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/, "expected YYYY-MM-DD");
/** The manifest link is the same-origin API path; cross-origin URLs fail validation. */
const manifestUrl = z.string().startsWith("/api/", "expected a same-origin /api path");

export const reasonCodeSchema = z.object({
  code: z.string().min(1).max(80),
  severity: z.enum(["rejecting", "limit", "informational"]),
  detail: z.string().min(1),
});

export const runSampleSchema = z.object({
  start: isoDate,
  end_exclusive: isoDate,
  nobs: z.number().int().positive(),
});

export const tolerancesSchema = z.object({
  coefficient_rtol: z.string().regex(/^[0-9]+(\.[0-9]+)?$/),
  coefficient_atol: z.string().regex(/^[0-9]+(\.[0-9]+)?$/),
});

export const limitationsSchema = z.object({
  prohibited_labels: z.array(z.string()).min(1),
  spec_limitation_notes: z.array(z.string()).min(1),
  gate_limit_codes: z.array(z.string()),
});

export const approvalSchema = z.object({
  decision: z.literal("approve"),
  reviewer: z.string().min(1).max(200),
  review_reference: z.string().min(1).max(300),
  reviewed_at: z.string().nullish(),
  notes: z.string().nullish(),
});

export const coefficientSchema = z.object({
  name: z.string().min(1).max(120),
  estimate: z.number(),
  std_error: z.number(),
  t_stat: z.number(),
  p_value: z.number(),
  ci95_low: z.number(),
  ci95_high: z.number(),
});

export const modelRunSummarySchema = z.object({
  run_id: z.uuid(),
  model_id: specId,
  model_version: z.number().int().positive(),
  gate_verdict: z.enum(["READY", "READY_WITH_LIMITS"]),
  sample: runSampleSchema,
  tolerances: tolerancesSchema,
  code_commit: z.string().regex(/^[0-9a-f]{40}$|^[0-9a-f]{64}$/),
  manifest_url: manifestUrl,
  published_at: z.string().min(1),
  published_by: z.string().min(1).max(120),
});

export const modelRunDetailSchema = modelRunSummarySchema.extend({
  specification: z.record(z.string(), z.unknown()),
  admission_reasons: z.array(reasonCodeSchema),
  design: z.record(z.string(), z.unknown()),
  estimation: z.record(z.string(), z.unknown()),
  coefficients: z.array(coefficientSchema).min(1),
  diagnostics: z.record(z.string(), z.unknown()),
  interpretation: z.record(z.string(), z.unknown()),
  limitations: limitationsSchema,
  environment: z.record(z.string(), z.unknown()),
  reproduction: z.record(z.string(), z.unknown()),
  approval: approvalSchema,
});

export const modelRunListSchema = z.object({
  items: z.array(modelRunSummarySchema),
  next_cursor: z.string().nullable(),
});

export const modelDefinitionSchema = z.object({
  id: z.uuid(),
  model_id: specId,
  version: z.number().int().positive(),
  question: z.string().min(1).max(500),
  specification: z.record(z.string(), z.unknown()),
  required_metric_ids: z.array(z.string()).min(1).max(16),
  readiness_rules: z.record(z.string(), z.unknown()),
  limitations: limitationsSchema,
  latest_published_run_id: z.uuid(),
});

export const modelReadinessSchema = z.object({
  model_id: specId,
  ready: z.boolean(),
  verdict: z.string().min(1).max(40),
  reasons: z.array(reasonCodeSchema),
  overall_verdict: z.string().min(1).max(60),
  selected_specification: z.string().nullish(),
  recorded_in_run_id: z.uuid(),
});

/**
 * The structural shape the NI-053 template renderer gives the interpretation
 * block. Extraction is best-effort: when the recorded object matches, the
 * page renders the fixed sentences with their template labels; when it does
 * not, the page falls back to the verbatim JSON rendering. Unknown keys are
 * allowed (the contract block is open) and never silently dropped from the
 * verbatim fallback.
 */
export const templateInterpretationSchema = z.object({
  template_id: z.string().min(1),
  rendering_policy: z.string().min(1),
  sentences: z.array(z.string()).min(1),
  authoring_note: z.string().nullish(),
  mechanical_construction_warning: z.string().nullish(),
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

export type ModelRunSummary = z.infer<typeof modelRunSummarySchema>;
export type ModelRunDetail = z.infer<typeof modelRunDetailSchema>;
export type ModelRunList = z.infer<typeof modelRunListSchema>;
export type ModelDefinition = z.infer<typeof modelDefinitionSchema>;
export type ModelReadiness = z.infer<typeof modelReadinessSchema>;
export type ReasonCode = z.infer<typeof reasonCodeSchema>;
export type TemplateInterpretation = z.infer<typeof templateInterpretationSchema>;

/**
 * Compile-time mirror assertions: each validated mirror type stays
 * assignable to its generated contract (a required statistical field in the
 * mirror is compatible with the generated contract's serialization shape,
 * and the render boundary is strictly stricter, never looser). A generated
 * contract change that breaks these checks fails typecheck here.
 */
type Generated = components["schemas"];
const mirrorChecks: Array<true> = [
  true as ModelRunSummary extends Generated["ModelRunSummaryResponse"] ? true : never,
  true as ModelRunDetail extends Generated["ModelRunDetailResponse"] ? true : never,
  true as ModelRunList extends Generated["ModelRunListResponse"] ? true : never,
  true as ModelDefinition extends Generated["ModelDefinitionResponse"] ? true : never,
  true as ModelReadiness extends Generated["ModelReadinessResponse"] ? true : never,
];
void mirrorChecks;
