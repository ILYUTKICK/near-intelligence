import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";

import { seriesResponseSchema } from "@/features/charts/library/catalog-schema";
import { savedSchema } from "@/features/charts/saved/api";
import { documentSummarySchema } from "@/features/documents/list/documents-schema";
import { privateFetch } from "@/lib/auth/private-fetch";

export type Home = components["schemas"]["HomeResponse"];
// Render-boundary validation only; DTOs are generated from Pydantic/OpenAPI.
const homeSchema: z.ZodType<Home> = z.object({
  recent_documents: z.array(documentSummarySchema).max(5),
  recent_charts: z.array(savedSchema).max(5),
  recent_insights: z.array(z.object({
    insight_id: z.uuid(), document_id: z.uuid(), document_title: z.string(), block_id: z.uuid(),
    type: z.enum(["observation", "hypothesis", "risk", "conclusion"]),
    classification: z.enum(["supporting", "contradicting", "uncertain"]), modified_at: z.string(), excerpt: z.string().max(280),
  })).max(5),
  indicators: z.array(z.object({
    chart_id: z.string(), chart_version: z.number().int().positive().nullable(), title: z.string(), status: z.enum(["available", "unavailable"]),
    series: seriesResponseSchema.nullable(), reason: z.string().nullable(),
  })).max(3),
  counts: z.object({ documents: z.number().int().nonnegative() }),
});

export async function getHome(signal: AbortSignal): Promise<Home> {
  const response = await privateFetch("/api/home", { signal });
  if (!response.ok) throw new Error(response.status === 401 || response.status === 403
    ? "Your session has changed. Sign in again to see your research."
    : "Your research could not be loaded. Try again.");
  const parsed = homeSchema.safeParse(await response.json());
  if (!parsed.success) throw new Error("The research overview could not be read. Try again.");
  return parsed.data;
}
