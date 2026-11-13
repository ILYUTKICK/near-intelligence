/** Resolve implicit presets against actual approved coverage, never wall-clock data. */
import type { ChartDefinitionResponse, ChartViewResponse } from "../renderer/view-types";
import type { FiltersSelection } from "../filters/filter-values";
import { fetchChartView, type ApiResult } from "./catalog-api";
import { defaultRangeFor, todayUtc, type UrlRange } from "./selection-url";

export async function fetchLatestDefaultView(
  definition: ChartDefinitionResponse,
  filters: FiltersSelection = {},
): Promise<{ range: UrlRange; result: ApiResult<ChartViewResponse> }> {
  // A bounded request discovers the latest approved dataset's coverage even
  // when its observations do not overlap today's dates. This response is not
  // shown as the final selection when it needs re-anchoring.
  const probeRange = defaultRangeFor(definition, todayUtc());
  const probe = await fetchChartView(definition.chart_id, {
    definitionVersion: definition.version,
    ...probeRange,
    datasetVersion: "latest",
    filters,
  });
  if (!probe.ok) return { range: probeRange, result: probe };

  const range = defaultRangeFor(definition, probe.data.dataset.end);
  if (range.start === probeRange.start && range.end === probeRange.end) {
    return { range, result: probe };
  }
  // Pin the discovered immutable version: a concurrent publication must not
  // switch datasets between discovering the coverage and loading its values.
  const result = await fetchChartView(definition.chart_id, {
    definitionVersion: definition.version,
    ...range,
    datasetVersion: probe.data.dataset.id,
    filters,
  });
  return { range, result };
}
