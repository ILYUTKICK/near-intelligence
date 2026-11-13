import { z } from "zod";

import {
  chartDefinitionResponseSchema,
  chartViewResponseSchema,
  metricResponseSchema,
  resolvedSelectionSchema,
  seriesResponseSchema,
} from "@/features/charts/library/catalog-schema";
import { coefficientSchema, limitationsSchema, runSampleSchema, tolerancesSchema } from "@/features/models/models-schema";
import type { components } from "@near-intelligence/shared-types";

/**
 * Render-boundary validation of the NI-060 share projection
 * (API_SPECIFICATION "Document shares", ADR-021). Derived ONLY from the
 * generated contracts (no second DTO source): the TypeScript types stay the
 * generated `components["schemas"]` aliases and the zod shapes mirror them,
 * so a malformed or privately-leaking payload fails honestly at the
 * boundary instead of rendering. The private-identifier keys (owner_id,
 * document_id/version_id/insight_id/hypothesis_id/evidence_id, authorship
 * timestamps, explanations) are structurally ABSENT from the payload shape —
 * the strict object schemas reject any unexpected field, which keeps a
 * future server regression from silently widening the published scope.
 */

const sha256Hex = z.string().regex(/^[0-9a-f]{64}$/, "expected a sha256 hex digest");

const richTextMarkSchema = z.discriminatedUnion("type", [
  z.strictObject({ type: z.literal("bold") }),
  z.strictObject({ type: z.literal("italic") }),
  z.strictObject({ type: z.literal("link"), attrs: z.strictObject({ href: z.string().min(1).max(2000) }) }),
]);

type Schemas = components["schemas"];
type ShareRichTextRun = Schemas["RichTextRun"];
type ShareRichTextListItem = Schemas["RichTextListItem-Output"];
type ShareRichTextChild = ShareRichTextListItem["content"][number];

const richTextRunSchema: z.ZodType<ShareRichTextRun> = z.strictObject({
  type: z.literal("text"),
  text: z.string().min(1).max(20000),
  marks: z.array(richTextMarkSchema).max(3),
});

const richTextChildSchema: z.ZodType<ShareRichTextChild> = z.lazy(() =>
  z.discriminatedUnion("type", [
    z.strictObject({ type: z.literal("paragraph"), content: z.array(richTextRunSchema) }),
    z.strictObject({ type: z.enum(["bullet_list", "ordered_list"]),
      content: z.array(richTextListItemSchema).min(1) }),
  ]));

const richTextListItemSchema: z.ZodType<ShareRichTextListItem> = z.lazy(() =>
  z.strictObject({ type: z.literal("list_item"), content: z.array(richTextChildSchema).min(1) }));

// The embedded chart view mirrors the GENERATED contract exactly: the two
// fields the API may omit (server-side defaults) stay optional here, so a
// fixture/response checked against the generated type also validates.
const shareChartViewSchema = chartViewResponseSchema.strict().extend({
  definition: chartDefinitionResponseSchema.strict().partial({ unavailable_reason: true }),
  series: z.array(seriesResponseSchema.strict().extend({
    metric: metricResponseSchema.strict().partial({ source_id: true }),
  })),
});

const insightContextSchema = z.union([
  // ResolvedContext (chart pin: public-safe registries only).
  z.strictObject({
    chart_definition_version_id: z.uuid(),
    dataset_version_id: z.uuid(),
    selection: resolvedSelectionSchema.strict(),
    context_hash: sha256Hex,
    renderer_version: z.string().min(1).max(80),
    metric_definition_versions: z.array(z.uuid()),
    resolved_at: z.string(),
  }),
  // ModelContext (published run reference).
  z.strictObject({
    model_run_id: z.uuid(),
    dataset_version_id: z.uuid(),
    specification_version: z.string().min(1).max(80),
    context_hash: sha256Hex,
  }),
]);

export const shareBlockSchema = z.discriminatedUnion("block_type", [
  z.object({ block_type: z.literal("paragraph"), block_id: z.uuid(), runs: z.array(richTextRunSchema) }).strict(),
  z.object({ block_type: z.literal("heading"), block_id: z.uuid(), level: z.number().int().min(1).max(3),
    runs: z.array(richTextRunSchema) }).strict(),
  z.object({ block_type: z.enum(["bullet_list", "ordered_list"]), block_id: z.uuid(),
    items: z.array(richTextListItemSchema).min(1) }).strict(),
  z.object({
    block_type: z.literal("liveChart"), block_id: z.uuid(),
    chart_definition_version_id: z.uuid(), mode: z.literal("live"),
    selection: resolvedSelectionSchema.strict(),
    observed_dataset_version_id: z.uuid(), view: shareChartViewSchema,
  }).strict(),
  z.object({
    block_type: z.literal("dataTable"), block_id: z.uuid(),
    columns: z.array(z.strictObject({ key: z.string().min(1).max(100),
      label: z.string().min(1).max(200), type: z.enum(["string", "number", "date"]),
      unit: z.string().min(1).max(40).nullable() })).min(1).max(100),
    rows: z.array(z.array(z.union([z.string(), z.boolean(), z.null()]))).nullable(),
    dataset: z.strictObject({ dataset_version_id: z.uuid(),
      dataset_key: z.string().min(1).max(120), version: z.number().int().positive(),
      content_sha256: sha256Hex }).nullable(),
  }).strict(),
  z.object({
    block_type: z.literal("insight"), block_id: z.uuid(),
    insight_type: z.enum(["observation", "hypothesis", "risk", "conclusion"]),
    classification: z.enum(["supporting", "contradicting", "uncertain"]),
    body: z.array(richTextChildSchema).min(1), context: insightContextSchema,
  }).strict(),
  z.object({
    block_type: z.literal("hypothesis"), block_id: z.uuid(),
    statement: z.string().min(1).max(2000),
    assessment: z.enum(["untested", "supported", "mixed", "weakened", "insufficient_data"]),
  }).strict(),
  z.object({
    block_type: z.literal("evidence"), block_id: z.uuid(),
    classification: z.enum(["supporting", "contradicting", "uncertain"]),
    target_kind: z.enum(["insight", "chart_block", "model_run", "citation"]),
    target_ref: z.uuid().nullable(),
  }).strict(),
  z.object({
    block_type: z.literal("risk"), block_id: z.uuid(),
    title: z.string().min(1).max(200), body: z.array(richTextChildSchema).min(1),
  }).strict(),
  z.strictObject({
    block_type: z.literal("modelResult"), block_id: z.uuid(),
    model_run_id: z.uuid(), dataset_version_id: z.uuid(),
    spec_id: z.string().regex(/^[a-z][a-z0-9_]{2,79}$/), spec_version: z.number().int().positive(),
    interpretation: z.array(richTextChildSchema).min(1),
    gate_verdict: z.enum(["READY", "READY_WITH_LIMITS"]),
    sample: runSampleSchema.strict(), tolerances: tolerancesSchema.strict(),
    limitations: limitationsSchema.strict(), coefficients: z.array(coefficientSchema.strict()).min(1),
  }),
  z.strictObject({ block_type: z.literal("divider"), block_id: z.uuid() }),
]);

export const shareProjectionSchema = z.object({
  share_projection_version: z.literal(1),
  document: z.object({
    title: z.string().min(1).max(200),
    revision: z.number().int().positive(),
    schema_version: z.number().int().positive(),
    content_sha256: sha256Hex,
    created_at: z.string(),
    limitations: z.string().min(1).max(500),
  }).strict(),
  blocks: z.array(shareBlockSchema).max(200),
  sources: z.array(z.object({ source_id: z.string().min(1).max(40),
    name: z.string().min(1).max(200) }).strict()),
  model_runs: z.array(z.object({ run_id: z.uuid(), spec_id: z.string().min(3).max(80),
    spec_version: z.number().int().positive() }).strict()),
  citations: z.array(z.object({ artifact_id: z.uuid() }).strict()),
}).strict();

export type ShareProjectionPayload = z.infer<typeof shareProjectionSchema>;
export type ShareBlockPayload = z.infer<typeof shareBlockSchema>;
export type ShareDocumentMetaPayload = ShareProjectionPayload["document"];
