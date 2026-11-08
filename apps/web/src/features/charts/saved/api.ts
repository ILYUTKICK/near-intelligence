import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";
import { chartViewResponseSchema } from "../library/catalog-schema";

type Schemas = components["schemas"];
export type SavedChart = Schemas["SavedChartResponse"];
export type SavedDetail = Schemas["SavedChartDetailResponse"];
export type SaveInput = Schemas["SavedChartCreateRequest"];
const selectionSchema = z.object({ start: z.string(), end: z.string(), frequency: z.literal("day"), filters: z.record(z.string(), z.string()) });
const savedSchema: z.ZodType<SavedChart> = z.object({
  id: z.uuid(), label: z.string().nullable(), mode: z.enum(["live", "snapshot"]),
  chart_definition_version_id: z.uuid(), selection: selectionSchema,
  snapshot_id: z.uuid().nullable(), last_resolved_dataset_version_id: z.uuid().nullable(),
  created_at: z.string(), updated_at: z.string(),
});
const detailSchema: z.ZodType<SavedDetail> = z.object({ saved_chart: savedSchema,
  view: chartViewResponseSchema, dataset_changed: z.boolean() });
const listSchema = z.object({ items: z.array(savedSchema), next_cursor: z.string().nullable() });

export async function savedRequest<T>(path: string, schema: z.ZodType<T>, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.method && options.method !== "GET") {
    const csrf = await fetch("/api/auth/csrf", { credentials: "same-origin", cache: "no-store" });
    if (!csrf.ok) throw new Error("Your session could not be checked. Try again.");
    const token = z.object({ token: z.string() }).parse(await csrf.json()).token;
    headers.set("x-csrf-token", token);
    headers.set("content-type", "application/json");
  }
  const response = await fetch(path, { ...options, headers, credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error(response.status === 401 || response.status === 403
    ? "Your session has changed. Sign in again." : response.status === 404
      ? "This saved chart is unavailable." : "The chart could not be saved or loaded. Try again.");
  return schema.parse(response.status === 204 ? null : await response.json());
}
export const saveChart = (input: SaveInput, key: string) => savedRequest("/api/saved-charts", savedSchema,
  { method: "POST", headers: { "idempotency-key": key }, body: JSON.stringify(input) });
export const getSaved = (id: string, signal?: AbortSignal) => savedRequest(`/api/saved-charts/${id}`, detailSchema, { signal });
export const listSaved = (search: string, cursor: string | null, signal?: AbortSignal) => {
  const params = new URLSearchParams({ q: search });
  if (cursor) params.set("cursor", cursor);
  return savedRequest(`/api/saved-charts?${params}`, listSchema, { signal });
};
export const renameSaved = (id: string, label: string | null) => savedRequest(`/api/saved-charts/${id}`, savedSchema,
  { method: "PATCH", body: JSON.stringify({ label }) });
export const deleteSaved = (id: string) => savedRequest(`/api/saved-charts/${id}`, z.null(), { method: "DELETE" });
