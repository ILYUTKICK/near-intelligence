import { z } from "zod";

/**
 * Client-side validation of the private document API payloads (NI-023). These
 * schemas mirror the generated contracts in @near-intelligence/shared-types —
 * they are a render-boundary check, never a second DTO source: any mismatch
 * fails honestly instead of rendering a malformed response. The server stays
 * the sole authority for ownership and content.
 */
export const documentProgressSchema = z.object({
  headings: z.number().int().nonnegative(),
  charts: z.number().int().nonnegative(),
  insights: z.number().int().nonnegative(),
});

/** Maximum title length, mirrored from the API contract (`DocumentCreateRequest`). */
export const DOCUMENT_TITLE_MAX_LENGTH = 200;
/** Organization bounds mirrored from the API contract (NI-072). */
export const DOCUMENT_ORGANIZATION_MAX_TAGS = 20;
/** Maximum normalized tag length, mirrored from the API contract (NI-072). */
export const DOCUMENT_TAG_MAX_LENGTH = 40;
/** Maximum tags combined in one list filter, mirrored from the API contract. */
export const DOCUMENT_LIST_MAX_FILTER_TAGS = 5;

export const documentSummarySchema = z.object({
  id: z.uuid(),
  title: z.string().min(1).max(200),
  revision: z.number().int().positive(),
  schema_version: z.number().int().positive(),
  current_version_id: z.uuid().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  progress: documentProgressSchema,
  // NI-072 private organization metadata. The API documents these with the
  // empty defaults (`@default []` / `@default false`), so the mirror applies
  // exactly those defaults when a payload omits them — an honest render
  // boundary, never a second DTO source.
  tags: z.array(z.string().min(1).max(DOCUMENT_TAG_MAX_LENGTH))
    .max(DOCUMENT_ORGANIZATION_MAX_TAGS).default([]),
  favorite: z.boolean().default(false),
});

export const documentListResponseSchema = z.object({
  items: z.array(documentSummarySchema),
  next_cursor: z.string().max(64).nullable(),
});

export const documentResponseSchema = documentSummarySchema.extend({
  content: z.record(z.string(), z.unknown()),
  resolved_contexts: z.record(z.string(), z.unknown()),
});

export const documentOrganizationResponseSchema = z.object({
  document_id: z.uuid(),
  tags: z.array(z.string().min(1).max(DOCUMENT_TAG_MAX_LENGTH))
    .max(DOCUMENT_ORGANIZATION_MAX_TAGS),
  favorite: z.boolean(),
  updated_at: z.string(),
});

export const apiErrorDetailSchema = z.object({
  path: z.string(),
  reason: z.string(),
});

export const apiErrorResponseSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string(),
    retryable: z.boolean(),
    details: z.array(apiErrorDetailSchema).nullish(),
  }),
});

export type DocumentSummary = z.infer<typeof documentSummarySchema>;
export type DocumentListResponse = z.infer<typeof documentListResponseSchema>;
export type DocumentResponse = z.infer<typeof documentResponseSchema>;
export type DocumentOrganizationResponse = z.infer<typeof documentOrganizationResponseSchema>;
export type ApiErrorResponse = z.infer<typeof apiErrorResponseSchema>;
