import type { components } from "@near-intelligence/shared-types";
import { z } from "zod";
import { apiErrorResponseSchema, chartViewResponseSchema } from "../library/catalog-schema";

type Schemas = components["schemas"];
export type Snapshot = Schemas["SnapshotResponse"];
export type SnapshotDetail = Schemas["SnapshotDetailResponse"];
export type SnapshotCompare = Schemas["SnapshotCompareResponse"];
export type FreezeInput = Schemas["SnapshotCreateRequest"];
const selectionSchema = z.object({ start: z.string(), end: z.string(), frequency: z.literal("day"), filters: z.record(z.string(), z.string()) });
const calculationContextSchema = z.object({
  context_hash: z.string().regex(/^[0-9a-f]{64}$/),
  metric_definition_versions: z.array(z.string().min(1)).min(1),
  renderer_version: z.string().min(1),
});
export const snapshotSchema: z.ZodType<Snapshot> = z.object({
  id: z.uuid(), chart_definition_version_id: z.uuid(), dataset_version_id: z.uuid(),
  selection: selectionSchema, calculation_context: calculationContextSchema,
  artifact_id: z.uuid().nullable(), content_sha256: z.string().regex(/^[0-9a-f]{64}$/),
  created_at: z.string(),
});
const detailSchema: z.ZodType<SnapshotDetail> = z.object({ snapshot: snapshotSchema, view: chartViewResponseSchema });
const listSchema = z.object({ items: z.array(snapshotSchema), next_cursor: z.string().nullable() });
const compareSchema: z.ZodType<SnapshotCompare> = z.object({
  snapshot: snapshotSchema, frozen_view: chartViewResponseSchema,
  live_view: chartViewResponseSchema, dataset_changed: z.boolean(),
});

/** One error surface for every snapshot mutation/read (NI-044). */
async function snapshotError(response: Response, fallback: string): Promise<string> {
  if (response.status === 401 || response.status === 403) return "Your session has changed. Sign in again.";
  if (response.status === 404) return "This snapshot is unavailable.";
  try {
    const error = apiErrorResponseSchema.parse(await response.json()).error;
    if (error.code === "REFERENCE_IN_USE") return "This snapshot is referenced by a saved chart and cannot be deleted.";
    return error.message;
  } catch {
    return fallback;
  }
}

export async function snapshotRequest<T>(path: string, schema: z.ZodType<T>, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.method && options.method !== "GET") {
    const csrf = await fetch("/api/auth/csrf", { credentials: "same-origin", cache: "no-store" });
    if (!csrf.ok) throw new Error("Your session could not be checked. Try again.");
    const token = z.object({ token: z.string() }).parse(await csrf.json()).token;
    headers.set("x-csrf-token", token);
    headers.set("content-type", "application/json");
  }
  const response = await fetch(path, { ...options, headers, credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error(await snapshotError(response, "The snapshot could not be managed. Try again."));
  return schema.parse(response.status === 204 ? null : await response.json());
}
export const freezeSnapshot = (input: FreezeInput, key: string) => snapshotRequest("/api/snapshots", snapshotSchema,
  { method: "POST", headers: { "idempotency-key": key }, body: JSON.stringify(input) });
export const getSnapshot = (id: string, signal?: AbortSignal) => snapshotRequest(`/api/snapshots/${id}`, detailSchema, { signal });
export const compareSnapshot = (id: string, signal?: AbortSignal) =>
  snapshotRequest(`/api/snapshots/${id}/compare-live`, compareSchema, { signal });
export const listSnapshots = (cursor: string | null, signal?: AbortSignal) => {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  return snapshotRequest(`/api/snapshots?${params}`, listSchema, { signal });
};
export const deleteSnapshot = (id: string) => snapshotRequest(`/api/snapshots/${id}`, z.null(), { method: "DELETE" });
