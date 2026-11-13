import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";

import { chartViewResponseSchema } from "@/features/charts/library/catalog-schema";

export type ResearchHistory = components["schemas"]["ResearchHistoryResponse"];
export type PeriodSummary = components["schemas"]["ResearchPeriodSummary"];
const decimal = z.string().regex(/^-?\d+(\.\d+)?$/).nullable();
const day = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const count = z.number().int().nonnegative();
const periodSchema = z.object({
  start: day, end: day, expected_days: count, volume_days: count,
  fee_days: count, matched_days: count, zero_fee_days: count,
  volume_usd: decimal, gross_fees_usd: decimal, matched_volume_usd: decimal,
  matched_gross_fees_usd: decimal, effective_gross_fee_bps: decimal,
  complete: z.boolean(),
});

/** Validation at the browser boundary; DTO types remain OpenAPI-generated. */
export const researchHistorySchema: z.ZodType<ResearchHistory> = z.object({
  volume: chartViewResponseSchema,
  fees: chartViewResponseSchema,
  purchases: chartViewResponseSchema.nullable(),
  summary: periodSchema,
  monthly: z.array(periodSchema),
  quarterly: z.array(periodSchema),
  limitations: z.array(z.string()),
});
