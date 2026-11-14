/** Resolve implicit presets against actual approved coverage, never wall-clock data. */
import type { ChartDefinitionResponse, ChartViewResponse } from "../renderer/view-types";
import type { FiltersSelection } from "../filters/filter-values";
import { fetchChartView, type ApiResult } from "./catalog-api";
import {
  defaultFiltersFor,
  defaultRangeFor,
  hasNoExplicitFilters,
  todayUtc,
  type UrlRange,
} from "./selection-url";

export async function fetchLatestDefaultView(
  definition: ChartDefinitionResponse,
  filters: FiltersSelection = {},
): Promise<{ range: UrlRange; result: ApiResult<ChartViewResponse> }> {
  // NI-092 implicit default: when the URL carries no filter choice, the first
  // approved option of every registered dimension is preselected (disclosed
  // by the filter chips). Providers are never summed; explicit URLs win.
  const effectiveFilters = hasNoExplicitFilters(filters)
    ? defaultFiltersFor(definition)
    : filters;
  // A bounded request discovers the latest approved dataset's coverage even
  // when its observations do not overlap today's dates. This response is not
  // shown as the final selection when it needs re-anchoring.
  const probeRange = defaultRangeFor(definition, todayUtc());
  const probe = await fetchChartView(definition.chart_id, {
    definitionVersion: definition.version,
    ...probeRange,
    datasetVersion: "latest",
    filters: effectiveFilters,
  });
  if (!probe.ok) return { range: probeRange, result: probe };

  const range = defaultRangeFor(definition, probe.data.dataset.end);
  // NI-092: the implicit window is clamped to the approved coverage — a
  // 730-day preset on a 90-day dataset defaults to the covered days, not to
  // honest "outside coverage" placeholders.
  const coverageStart = probe.data.dataset.start;
  const clampedRange = typeof coverageStart === "string" && range.start < coverageStart
    ? { ...range, start: coverageStart }
    : range;
  if (clampedRange.start === probeRange.start && clampedRange.end === probeRange.end) {
    return { range: clampedRange, result: probe };
  }
  // Pin the discovered immutable version: a concurrent publication must not
  // switch datasets between discovering the coverage and loading its values.
  const result = await fetchChartView(definition.chart_id, {
    definitionVersion: definition.version,
    ...clampedRange,
    datasetVersion: probe.data.dataset.id,
    filters: effectiveFilters,
  });
  return { range: clampedRange, result };
}
