/**
 * Server-side access to the NI-032 public delivery APIs for the chart
 * library and chart detail pages (NI-034).
 *
 * Requests go through the generated OpenAPI client
 * (@near-intelligence/shared-types `createApiClient`) against the web
 * runtime's `API_INTERNAL_URL` — the same-origin /api proxy for the delivery
 * surface is packaging scope (NI-066), so pages resolve the API directly on
 * the server. Every response is validated against the render-boundary
 * schemas (catalog-schema.ts) before it reaches JSX; failures are honest
 * typed results, never fabricated payloads.
 *
 * Server module: reads loadServerEnv() and must never be imported from a
 * client component (the internal API URL is not a client value).
 */
import { createApiClient } from "@near-intelligence/shared-types";
import type { components } from "@near-intelligence/shared-types";

import { loadServerEnv } from "@/lib/env";

import type { FiltersSelection } from "../filters/filter-values";

import {
  apiErrorResponseSchema,
  chartDefinitionResponseSchema,
  chartListResponseSchema,
  chartViewResponseSchema,
  datasetResponseSchema,
} from "./catalog-schema";

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

type Schemas = components["schemas"];

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

/**
 * GET /api/charts — the public catalog (search q, category, opaque cursor).
 * `limit` (API maximum 100) is optional and only used by callers that need a
 * wider page (the NI-015 explorer overview); the chart library keeps the
 * API's default page size.
 */
export async function fetchChartCatalog(
  params: { q?: string; category?: string; cursor?: string; limit?: number },
): Promise<ApiResult<Schemas["ChartListResponse"]>> {
  const { GET } = apiClient();
  const result = await GET("/api/charts", {
    params: {
      query: {
        ...(params.q !== undefined ? { q: params.q } : {}),
        ...(params.category !== undefined ? { category: params.category } : {}),
        ...(params.cursor !== undefined ? { cursor: params.cursor } : {}),
        ...(params.limit !== undefined ? { limit: params.limit } : {}),
      },
    },
  });
  if (!result.response.ok) {
    return failure(result.response.status, result.error);
  }
  const parsed = chartListResponseSchema.safeParse(result.data);
  return parsed.success
    ? { ok: true, data: parsed.data as Schemas["ChartListResponse"] }
    : failure(result.response.status, null);
}

/** GET /api/charts/{chart_id} — one definition version (latest when unpinned). */
export async function fetchChartDefinition(
  chartId: string,
  version: number | null,
): Promise<ApiResult<Schemas["ChartDefinitionResponse"]>> {
  const { GET } = apiClient();
  const result = await GET("/api/charts/{chart_id}", {
    params: {
      path: { chart_id: chartId },
      query: version !== null ? { version } : {},
    },
  });
  if (!result.response.ok) {
    return failure(result.response.status, result.error);
  }
  const parsed = chartDefinitionResponseSchema.safeParse(result.data);
  return parsed.success
    ? { ok: true, data: parsed.data as Schemas["ChartDefinitionResponse"] }
    : failure(result.response.status, null);
}

/** GET /api/datasets/{version_id} — the coverage anchor for pinned datasets. */
export async function fetchDataset(
  versionId: string,
): Promise<ApiResult<Schemas["DatasetResponse"]>> {
  const { GET } = apiClient();
  const result = await GET("/api/datasets/{version_id}", {
    params: { path: { version_id: versionId } },
  });
  if (!result.response.ok) {
    return failure(result.response.status, result.error);
  }
  const parsed = datasetResponseSchema.safeParse(result.data);
  return parsed.success
    ? { ok: true, data: parsed.data as Schemas["DatasetResponse"] }
    : failure(result.response.status, null);
}

/** The resolved view request, built only from validated selection values. */
export interface ChartViewRequest {
  definitionVersion: number;
  start: string;
  end: string;
  /** "latest" or a pinned immutable dataset version id. */
  datasetVersion: string;
  /**
   * Values already validated against the definition version's filter
   * schema: one approved string, or a list for a `multi_value` dimension
   * (NI-071 comparison form; the server fans out one series per value).
   */
  filters: FiltersSelection;
}

/** GET /api/charts/{chart_id}/view — resolved ChartView for one selection. */
export async function fetchChartView(
  chartId: string,
  request: ChartViewRequest,
): Promise<ApiResult<Schemas["ChartViewResponse"]>> {
  const { GET } = apiClient();
  const filtersDocument =
    Object.keys(request.filters).length > 0 ? JSON.stringify(request.filters) : null;
  const result = await GET("/api/charts/{chart_id}/view", {
    params: {
      path: { chart_id: chartId },
      query: {
        definition_version: request.definitionVersion,
        start: request.start,
        end: request.end,
        ...(request.datasetVersion !== "latest" ? { dataset_version: request.datasetVersion } : {}),
        ...(filtersDocument !== null ? { filters: filtersDocument } : {}),
      },
    },
  });
  if (!result.response.ok) {
    return failure(result.response.status, result.error);
  }
  const parsed = chartViewResponseSchema.safeParse(result.data);
  return parsed.success
    ? { ok: true, data: parsed.data as Schemas["ChartViewResponse"] }
    : failure(result.response.status, null);
}
