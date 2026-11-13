import { privateFetch } from "@/lib/auth/private-fetch";
import { modelRunDetailSchema, modelRunListSchema, type ModelRunDetail, type ModelRunList } from "@/features/models/models-schema";

/**
 * Client-side reads of the NI-054 published-run catalog through the
 * same-origin session gateway (NI-055). Mirrors `chart-api.ts` pin
 * integrity: the validated response is accepted only when the returned run
 * is EXACTLY the requested identity, so a displayed summary can never drift
 * onto a different published run. Every value is the recorded projection of
 * the immutable `app.model_runs` row — never recomputed, never rounded.
 */

const RUN_DETAIL_NOT_AVAILABLE = "The pinned model run could not be loaded. The document keeps its pinned ids; try again.";
const RUN_DETAIL_MISMATCH = "The returned model run does not match the pinned identity. Nothing was changed.";

/** GET /api/model-runs — the published-run catalog for the Add Model chooser. */
export async function fetchPublishedRuns(params: { cursor?: string } = {},
signal?: AbortSignal): Promise<ModelRunList> {
  const query = new URLSearchParams();
  if (params.cursor) {
    query.set("cursor", params.cursor);
  }
  const response = await privateFetch(`/api/model-runs${query.size ? `?${query}` : ""}`, {
    method: "GET", signal,
  });
  if (!response.ok) {
    throw new Error("The published model runs could not be loaded. Try again.");
  }
  return modelRunListSchema.parse(await response.json());
}

/** GET /api/model-runs/{run_id} — one published run (identity-verified). */
export async function loadPinnedRun(runId: string, signal?: AbortSignal): Promise<ModelRunDetail> {
  const response = await privateFetch(`/api/model-runs/${runId}`, {
    method: "GET", signal,
  });
  if (!response.ok) {
    throw new Error(RUN_DETAIL_NOT_AVAILABLE);
  }
  let run: ModelRunDetail;
  try {
    run = modelRunDetailSchema.parse(await response.json());
  } catch {
    throw new Error(RUN_DETAIL_NOT_AVAILABLE);
  }
  if (run.run_id !== runId) {
    throw new Error(RUN_DETAIL_MISMATCH);
  }
  return run;
}
