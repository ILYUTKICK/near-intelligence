/**
 * Server-side access to the NI-054 public model APIs for the /models pages
 * (the role-A completion of the NI-054 handoff).
 *
 * Requests go through the generated OpenAPI client
 * (@near-intelligence/shared-types `createApiClient`) against the web
 * runtime's `API_INTERNAL_URL` — the same render-boundary pattern as
 * features/charts/library/catalog-api.ts. Every response is validated
 * against the render-boundary schemas (models-schema.ts) before it reaches
 * JSX; failures are honest typed results, never fabricated payloads.
 *
 * GET-only by construction: this module declares no mutating call, so page
 * rendering can never require a POST or any non-GET request (the NI-054
 * handoff's access-trigger invariant, asserted by the UI test suite).
 *
 * Server module: reads loadServerEnv() and must never be imported from a
 * client component (the internal API URL is not a client value).
 */
import { createApiClient } from "@near-intelligence/shared-types";

import { loadServerEnv } from "@/lib/env";

import {
  apiErrorResponseSchema,
  modelDefinitionSchema,
  modelReadinessSchema,
  modelRunDetailSchema,
  modelRunListSchema,
  type ModelDefinition,
  type ModelReadiness,
  type ModelRunDetail,
  type ModelRunList,
} from "./models-schema";

/** One honest fetch failure carried to the page for rendering. */
export interface ApiFailure {
  ok: false;
  status: number;
  code: string | null;
  message: string | null;
  retryable: boolean;
}

export type ApiResult<T> = { ok: true; data: T } | ApiFailure;

const REQUEST_TIMEOUT_MS = 10_000;

/** Bounded fetcher: fails fast (10 s) instead of hanging the page render. */
const boundedFetcher: typeof globalThis.fetch = (input, init) =>
  globalThis.fetch(input, { ...init, signal: init?.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS) });

function apiClient() {
  return createApiClient(loadServerEnv().API_INTERNAL_URL, boundedFetcher);
}

function failure(status: number, body: unknown): ApiFailure {
  const parsed = apiErrorResponseSchema.safeParse(body);
  if (parsed.success) {
    return {
      ok: false,
      status,
      code: parsed.data.error.code,
      message: parsed.data.error.message,
      retryable: parsed.data.error.retryable,
    };
  }
  return { ok: false, status, code: null, message: null, retryable: status === 503 };
}

/** GET /api/model-runs — the public catalog of published runs (opaque cursor). */
export async function fetchModelRunCatalog(
  params: { cursor?: string },
): Promise<ApiResult<ModelRunList>> {
  const { GET } = apiClient();
  const result = await GET("/api/model-runs", {
    params: {
      query: {
        ...(params.cursor !== undefined ? { cursor: params.cursor } : {}),
      },
    },
  });
  if (!result.response.ok) {
    return failure(result.response.status, result.error);
  }
  const parsed = modelRunListSchema.safeParse(result.data);
  return parsed.success ? { ok: true, data: parsed.data } : failure(result.response.status, null);
}

/** GET /api/model-runs/{run_id} — one published run with its recorded results. */
export async function fetchModelRunDetail(
  runId: string,
): Promise<ApiResult<ModelRunDetail>> {
  const { GET } = apiClient();
  const result = await GET("/api/model-runs/{run_id}", {
    params: { path: { run_id: runId } },
  });
  if (!result.response.ok) {
    return failure(result.response.status, result.error);
  }
  const parsed = modelRunDetailSchema.safeParse(result.data);
  return parsed.success ? { ok: true, data: parsed.data } : failure(result.response.status, null);
}

/** GET /api/model-definitions/{model_id} — the public specification record. */
export async function fetchModelDefinition(
  modelId: string,
): Promise<ApiResult<ModelDefinition>> {
  const { GET } = apiClient();
  const result = await GET("/api/model-definitions/{model_id}", {
    params: { path: { model_id: modelId } },
  });
  if (!result.response.ok) {
    return failure(result.response.status, result.error);
  }
  const parsed = modelDefinitionSchema.safeParse(result.data);
  return parsed.success ? { ok: true, data: parsed.data } : failure(result.response.status, null);
}

/** GET /api/model-definitions/{model_id}/readiness — the recorded gate verdict. */
export async function fetchModelReadiness(
  modelId: string,
): Promise<ApiResult<ModelReadiness>> {
  const { GET } = apiClient();
  const result = await GET("/api/model-definitions/{model_id}/readiness", {
    params: { path: { model_id: modelId } },
  });
  if (!result.response.ok) {
    return failure(result.response.status, result.error);
  }
  const parsed = modelReadinessSchema.safeParse(result.data);
  return parsed.success ? { ok: true, data: parsed.data } : failure(result.response.status, null);
}
