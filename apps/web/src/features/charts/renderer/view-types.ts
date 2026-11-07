/**
 * Named aliases of the NI-032 generated API contracts (NI-033 renderer).
 *
 * These are derived ONLY from packages/shared-types (the OpenAPI-generated
 * client): the renderer never re-declares a response field. The generated
 * package exports TypeScript source, so these are type-only imports and add
 * no runtime dependency to the bundle.
 */
import type { components } from "@near-intelligence/shared-types";

export type ChartDefinitionResponse =
  components["schemas"]["ChartDefinitionResponse"];
export type ChartViewResponse = components["schemas"]["ChartViewResponse"];
export type SeriesResponse = components["schemas"]["SeriesResponse"];
export type MetricResponse = components["schemas"]["MetricResponse"];
export type Observation = components["schemas"]["Observation"];
export type DatasetResponse = components["schemas"]["DatasetResponse"];
export type DataSourceResponse = components["schemas"]["DataSourceResponse"];
export type ResolvedSelection = components["schemas"]["ResolvedSelection"];
export type DataQuality = components["schemas"]["DataQuality"];
export type QualityStatus = components["schemas"]["DataQuality"]["status"];

/**
 * The renderer capability set this implementation provides. It MUST equal
 * `RENDERER_VERSION` in apps/api/src/near_api/charts/registry.py: chart
 * definitions pin the renderer they target, and a definition pinned to a
 * different capability set is refused (honest unsupported-renderer state)
 * instead of best-effort redrawn. A test asserts the two constants agree.
 */
export const RENDERER_VERSION = "echarts-modular-svg@1";

/** True when the definition targets the renderer this module implements. */
export function rendererSupports(definition: ChartDefinitionResponse): boolean {
  return definition.renderer_version === RENDERER_VERSION;
}
