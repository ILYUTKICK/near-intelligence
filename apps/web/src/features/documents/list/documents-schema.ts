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

export const documentSummarySchema = z.object({
  id: z.uuid(),
  title: z.string().min(1).max(200),
  revision: z.number().int().positive(),
  schema_version: z.number().int().positive(),
  current_version_id: z.uuid().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  progress: documentProgressSchema,
});

export const documentListResponseSchema = z.object({
  items: z.array(documentSummarySchema),
  next_cursor: z.string().max(64).nullable(),
});

export const documentResponseSchema = documentSummarySchema.extend({
  content: z.record(z.string(), z.unknown()),
  resolved_contexts: z.record(z.string(), z.unknown()),
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
export type ApiErrorResponse = z.infer<typeof apiErrorResponseSchema>;

/** Maximum title length, mirrored from the API contract (`DocumentCreateRequest`). */
export const DOCUMENT_TITLE_MAX_LENGTH = 200;
