/**
 * Pure typed chart option builder (NI-033).
 *
 * Converts the generated, renderer-agnostic `ChartViewResponse` contract into
 * (a) an ECharts option, (b) an accessible exact-value table model and
 * (c) a manual accessible summary — all as pure data with no side effects,
 * no DOM access and no ECharts runtime import. The same builder must be
 * reusable by the browser renderer and the future Node static-export script
 * (CHART_SYSTEM.md), so `buildChart(view, { interactions: false })` returns a
 * JSON-serializable option (no function values).
 *
 * Numeric decision (ADR-019, tested): decimal strings delivered by the API
 * are the only source of exact values — the table and tooltip lookups render
 * the original strings with grouping separators and bound labels. Parsing to
 * `Number` happens in exactly one place (`toCoordinate`), only for plot
 * coordinates and axis scale, where a 29+ significant-digit value losing
 * digits affects nothing but sub-pixel position. A coordinate that does not
 * parse to a finite number is treated as missing (never fabricated).
 *
 * Series semantics (documented renderer contract):
 * - The API orders `view.series` by registry series role, but the response
 *   contract carries no role field; the renderer therefore uses only what
 *   the contract guarantees: response order, per-series `metric.unit` and
 *   the definition's `visualization_type`.
 * - Series with different units NEVER share a value axis: they are laid out
 *   as separate aligned panels (one grid per unit group). This implements
 *   CHART_SYSTEM "no dual-axis implication" generically.
 * - Scatter pairs series[0] (X) with series[1] (Y) — the registry binds
 *   required_x_axis before required_y_axis, which is the response order.
 * - Missing points stay missing: line/area use `connectNulls: false` and
 *   null values, bars render no bar; nothing is interpolated or zero-filled.
 * - Bars, areas and lines are anchored at zero (no hidden truncation);
 *   scatter axes scale to the data (association view, labeled as such).
 */
import type { BarSeriesOption, LineSeriesOption, ScatterSeriesOption } from "echarts/charts";
import type { ComposeOption } from "echarts/core";
import type {
  AriaComponentOption,
  AxisPointerComponentOption,
  GridComponentOption,
  LegendComponentOption,
  TooltipComponentOption,
} from "echarts/components";

import { canonicalFilters } from "../filters/filter-values";
import { boundPrefix, compactAxisNumber, formatDecimal, utcDateLabel } from "./format";
import { rendererSupports } from "./view-types";
import type { ChartViewResponse, Observation, SeriesResponse } from "./view-types";

export type ChartOption = ComposeOption<
  | LineSeriesOption
  | BarSeriesOption
  | ScatterSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | AriaComponentOption
  | LegendComponentOption
  | AxisPointerComponentOption
>;

type SeriesList = Extract<NonNullable<ChartOption["series"]>, unknown[]>;
type XAxisList = Extract<NonNullable<ChartOption["xAxis"]>, unknown[]>;
type YAxisList = Extract<NonNullable<ChartOption["yAxis"]>, unknown[]>;
type GridList = Extract<NonNullable<ChartOption["grid"]>, unknown[]>;

/**
 * The v1 renderer palette is shared by interactive charts and frozen exports.
 * Keep it stable so a saved revision reproduces the same static assets.
 */
export const CHART_SERIES_COLORS = ["#214D3B", "#5A7189", "#99662D", "#86657E"] as const;

const AXIS_TEXT = "#4B5C54";
const AXIS_LINE = "#D8DDD2";
const FONT_STACK = "Inter, ui-sans-serif, system-ui, sans-serif";

export interface TableValueCell {
  kind: "value";
  /** The exact decimal string exactly as delivered by the API. */
  exact: string;
  /** Display form: grouping separators + bound prefix; no float conversion. */
  display: string;
  /** Bound label ("lower bound") when the point quality declares one. */
  bound: string | null;
}

export interface TableMissingCell {
  kind: "missing";
  /** Why nothing was observed — a gap is never rendered as zero. */
  reason: string;
}

export type TableCell = TableValueCell | TableMissingCell;

export interface TableModel {
  /** One column per series (scatter: X then Y). */
  columns: { label: string; unit: string }[];
  /** One row per UTC date on the union grid of all series. */
  rows: { date: string; cells: TableCell[] }[];
}

/** Exact per-point value metadata backing tooltips without precision loss. */
interface ExactCell {
  date: string;
  name: string;
  unit: string;
  exact: string | null;
  display: string;
  bound: string | null;
  note: string | null;
}

export interface BuiltChart {
  option: ChartOption;
  table: TableModel;
  summary: string;
  hasPlottableData: boolean;
  /** Number of aligned value panels (unit groups); scatter counts as one. */
  panelCount: number;
}

export type BuiltChartResult =
  | ({ kind: "ok" } & BuiltChart)
  | { kind: "unsupported-renderer"; rendererVersion: string; expected: string };

export interface BuildOptions {
  /**
   * When true (browser) the option carries interaction closures (tooltip
   * formatters, compact axis labels) that reference exact values. When
   * false the option is pure JSON data — the static-export entry point.
   */
  interactions?: boolean;
  /** Respect prefers-reduced-motion: animations off when false. */
  animation?: boolean;
}

const INTERACTIONS_DEFAULT = true;
const ANIMATION_DEFAULT = true;

/**
 * The single documented Number() boundary: decimal string -> plot
 * coordinate. Non-finite results become missing points.
 */
function toCoordinate(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function pointBoundLabel(point: Observation): string | null {
  const bound = point.quality.bound_kind;
  return bound && bound !== "exact" ? `${bound} bound` : null;
}

function missingCell(reason: string): TableMissingCell {
  return { kind: "missing", reason };
}

function valueCell(point: Observation): TableCell {
  if (point.value === null) {
    return missingCell(point.quality.reasons.join("; ") || "no observation");
  }
  return {
    kind: "value",
    exact: point.value,
    display: `${boundPrefix(point.quality.bound_kind)}${formatDecimal(point.value)}`,
    bound: pointBoundLabel(point),
  };
}

function exactCell(
  point: Observation | undefined,
  name: string,
  unit: string,
  date: string,
): ExactCell {
  if (!point || point.value === null) {
    const note = point ? point.quality.reasons.join("; ") || "no observation" : "no observation";
    return { date, name, unit, exact: null, display: "not observed", bound: null, note };
  }
  return {
    date,
    name,
    unit,
    exact: point.value,
    display: `${boundPrefix(point.quality.bound_kind)}${formatDecimal(point.value)}`,
    bound: pointBoundLabel(point),
    note: null,
  };
}

/** Union UTC-date grid across series, ascending, duplicates removed. */
function unionGrid(seriesList: SeriesResponse[]): string[] {
  const dates = new Set<string>();
  for (const series of seriesList) {
    for (const point of series.points) {
      dates.add(utcDateLabel(point.start));
    }
  }
  return [...dates].sort();
}

function pointsByDate(series: SeriesResponse): Map<string, Observation> {
  const map = new Map<string, Observation>();
  for (const point of series.points) {
    const date = utcDateLabel(point.start);
    if (!map.has(date)) {
      map.set(date, point);
    }
  }
  return map;
}

/** Group consecutive series into panels by unit (different units never share an axis). */
function unitGroups(seriesList: SeriesResponse[]): SeriesResponse[][] {
  const groups: SeriesResponse[][] = [];
  for (const series of seriesList) {
    const last = groups[groups.length - 1];
    if (last && last[0].metric.unit === series.metric.unit) {
      last.push(series);
    } else {
      groups.push([series]);
    }
  }
  return groups;
}

function panelLayout(panelCount: number, legendSpace: number): { top: string; height: string }[] {
  const budget = 92 - legendSpace;
  const band = budget / panelCount;
  return Array.from({ length: panelCount }, (_, index) => ({
    top: `${(4 + legendSpace + index * band).toFixed(2)}%`,
    height: `${(band - 7).toFixed(2)}%`,
  }));
}

function buildSummary(
  view: ChartViewResponse,
  gridDates: string[],
  observedCount: number,
  missingCount: number,
  boundedCount: number,
): string {
  const units = [...new Set(view.series.map((s) => s.metric.unit))].join(" · ");
  const parts: string[] = [`${view.definition.title}.`];
  if (gridDates.length === 0) {
    parts.push("No periods are covered by the resolved data; nothing is plotted and nothing is zero.");
    return parts.join(" ");
  }
  parts.push(
    `${gridDates.length} period${gridDates.length === 1 ? "" : "s"} from ${gridDates[0]} to ${
      gridDates[gridDates.length - 1]
    } (UTC) across ${view.series.length} series, units: ${units}.`,
  );
  parts.push(
    `${observedCount} value${observedCount === 1 ? "" : "s"} observed; ${missingCount} shown as gaps, not zero.`,
  );
  if (boundedCount > 0) {
    parts.push(
      `${boundedCount} value${boundedCount === 1 ? " is" : "s are"} a bound or estimate and labeled as such, never presented as exact.`,
    );
  }
  return parts.join(" ");
}


/**
 * NI-071: one display name per series. A multi-value comparison fan-out
 * resolves several series of the same bound metric; they are distinguished
 * by their exact-match filter values (the server echoes one selected value
 * per series), while every other view keeps the bare metric title.
 */
export function describeSeries(view: ChartViewResponse): Array<{ id: string; name: string }> {
  const repeated = new Set<string>();
  const seen = new Set<string>();
  for (const series of view.series) {
    if (seen.has(series.metric.id)) {
      repeated.add(series.metric.id);
    }
    seen.add(series.metric.id);
  }
  return view.series.map((series) => {
    if (!repeated.has(series.metric.id)) {
      return { id: series.metric.id, name: series.metric.title };
    }
    const filters = canonicalFilters(series.selection.filters);
    const suffix = filters.map(([key, values]) => `${key}: ${values.join(", ")}`)
      .join("; ");
    return {
      id: JSON.stringify([series.metric.id, filters]),
      name: suffix ? `${series.metric.title} — ${suffix}` : series.metric.title,
    };
  });
}

function seriesColor(index: number): string {
  return CHART_SERIES_COLORS[index % CHART_SERIES_COLORS.length];
}

interface CartesianBuild {
  view: ChartViewResponse;
  gridDates: string[];
  interactions: boolean;
  animation: boolean;
  summary: string;
}

function buildCartesianOption(build: CartesianBuild): ChartOption {
  const { view, gridDates, interactions, animation, summary } = build;
  const groups = unitGroups(view.series);
  const legendSpace = view.series.length > 1 ? 10 : 0;
  const layout = panelLayout(groups.length, legendSpace);

  // NI-071: compared fan-out series carry their distinguishing filter values.
  const labels = describeSeries(view);
  // Exact-value lookup per series/grid index for the tooltip formatter.
  const exactSeries: ExactCell[][] = view.series.map((seriesResponse, index) => {
    const byDate = pointsByDate(seriesResponse);
    return gridDates.map((date) =>
      exactCell(byDate.get(date), labels[index].name, seriesResponse.metric.unit, date),
    );
  });

  const series: SeriesList = [];
  let seriesIndex = 0;
  for (const [gridIndex, group] of groups.entries()) {
    for (const seriesResponse of group) {
      const byDate = pointsByDate(seriesResponse);
      const isBar = view.definition.visualization_type === "bar";
      const data: (number | null)[] = gridDates.map((date) => {
        const point = byDate.get(date);
        if (!point || point.value === null) {
          return null;
        }
        return toCoordinate(point.value);
      });
      if (isBar) {
        series.push({
          id: labels[seriesIndex].id,
          name: labels[seriesIndex].name,
          type: "bar",
          xAxisIndex: gridIndex,
          yAxisIndex: gridIndex,
          data,
          barMaxWidth: 32,
          itemStyle: { color: seriesColor(seriesIndex) },
        });
      } else {
        series.push({
          id: labels[seriesIndex].id,
          name: labels[seriesIndex].name,
          type: "line",
          xAxisIndex: gridIndex,
          yAxisIndex: gridIndex,
          data,
          connectNulls: false,
          symbol: "circle",
          symbolSize: 6,
          lineStyle: { color: seriesColor(seriesIndex) },
          itemStyle: { color: seriesColor(seriesIndex) },
          ...(view.definition.visualization_type === "area"
            ? { areaStyle: { opacity: 0.25 } }
            : {}),
        });
      }
      seriesIndex += 1;
    }
  }

  return {
    animation,
    aria: { enabled: true, label: { description: summary } },
    textStyle: { color: AXIS_TEXT, fontFamily: FONT_STACK },
    color: [...CHART_SERIES_COLORS],
    grid: layout.map((slot): GridList[number] => ({
      left: 8,
      right: 16,
      top: slot.top,
      height: slot.height,
      containLabel: true,
    })),
    xAxis: layout.map((_, gridIndex): XAxisList[number] => ({
      type: "category",
      gridIndex,
      data: gridDates,
      axisLine: { lineStyle: { color: AXIS_LINE } },
      axisTick: { lineStyle: { color: AXIS_LINE } },
      axisLabel: { color: AXIS_TEXT },
    })),
    yAxis: groups.map((group, gridIndex): YAxisList[number] => ({
      type: "value",
      gridIndex,
      min: 0,
      name: group[0].metric.unit,
      nameTextStyle: { color: AXIS_TEXT },
      axisLabel: interactions ? { formatter: (value: number) => compactAxisNumber(value) } : undefined,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: AXIS_LINE } },
    })),
    series,
    legend:
      view.series.length > 1
        ? {
            top: 0,
            data: labels.map(series => series.name),
            textStyle: { color: AXIS_TEXT, fontFamily: FONT_STACK },
          }
        : undefined,
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    tooltip: {
      trigger: "axis",
      confine: true,
      formatter: interactions
        ? (params) => {
            const list = Array.isArray(params) ? params : [params];
            const lines: string[] = [];
            for (const item of list) {
              const cell =
                item.seriesIndex !== undefined
                  ? exactSeries[item.seriesIndex]?.[item.dataIndex]
                  : undefined;
              if (!cell) {
                continue;
              }
              if (lines.length === 0) {
                lines.push(`${cell.date} (UTC)`);
              }
              lines.push(
                cell.exact === null
                  ? `${cell.name} (${cell.unit}): not observed — ${cell.note ?? "gap, not zero"}`
                  : `${cell.name} (${cell.unit}): ${cell.display}${cell.bound ? ` — ${cell.bound}` : ""}`,
              );
            }
            return lines.join("\n");
          }
        : undefined,
    },
  };
}

interface ScatterBuild {
  view: ChartViewResponse;
  gridDates: string[];
  interactions: boolean;
  animation: boolean;
  summary: string;
}

function buildScatterOption(build: ScatterBuild): { option: ChartOption; hasPlottableData: boolean } {
  const { view, gridDates, interactions, animation, summary } = build;
  const xSeries = view.series[0];
  const ySeries = view.series[1];
  const xByDate = xSeries ? pointsByDate(xSeries) : new Map<string, Observation>();
  const yByDate = ySeries ? pointsByDate(ySeries) : new Map<string, Observation>();

  // Complete pairs only; incomplete pairs stay visible in the table with reasons.
  const exactScatter: { date: string; x: ExactCell; y: ExactCell }[] = [];
  const data: [number, number][] = [];
  for (const date of gridDates) {
    const xPoint = xByDate.get(date);
    const yPoint = yByDate.get(date);
    if (!xPoint || !yPoint || xPoint.value === null || yPoint.value === null) {
      continue;
    }
    const x = toCoordinate(xPoint.value);
    const y = toCoordinate(yPoint.value);
    if (x === null || y === null) {
      continue;
    }
    data.push([x, y]);
    exactScatter.push({
      date,
      x: exactCell(xPoint, xSeries.metric.title, xSeries.metric.unit, date),
      y: exactCell(yPoint, ySeries.metric.title, ySeries.metric.unit, date),
    });
  }

  const option: ChartOption = {
    animation,
    aria: { enabled: true, label: { description: summary } },
    textStyle: { color: AXIS_TEXT, fontFamily: FONT_STACK },
    color: [...CHART_SERIES_COLORS],
    xAxis: {
      type: "value",
      scale: true,
      name: xSeries?.metric.unit,
      nameTextStyle: { color: AXIS_TEXT },
      axisLabel: interactions ? { formatter: (value: number) => compactAxisNumber(value) } : undefined,
      axisLine: { lineStyle: { color: AXIS_LINE } },
      axisTick: { lineStyle: { color: AXIS_LINE } },
      splitLine: { lineStyle: { color: AXIS_LINE } },
    },
    yAxis: {
      type: "value",
      scale: true,
      name: ySeries?.metric.unit,
      nameTextStyle: { color: AXIS_TEXT },
      axisLabel: interactions ? { formatter: (value: number) => compactAxisNumber(value) } : undefined,
      axisLine: { lineStyle: { color: AXIS_LINE } },
      axisTick: { lineStyle: { color: AXIS_LINE } },
      splitLine: { lineStyle: { color: AXIS_LINE } },
    },
    series: [
      {
        id: "scatter",
        name: xSeries && ySeries ? `${xSeries.metric.title} × ${ySeries.metric.title}` : "scatter",
        type: "scatter",
        symbolSize: 8,
        itemStyle: { color: seriesColor(0) },
        data,
      },
    ],
    tooltip: {
      trigger: "item",
      confine: true,
      formatter: interactions
        ? (params) => {
            const single = Array.isArray(params) ? params[0] : params;
            const entry = single ? exactScatter[single.dataIndex] : undefined;
            if (!entry) {
              return "";
            }
            return [
              `${entry.date} (UTC)`,
              `${entry.x.name} (${entry.x.unit}): ${entry.x.display}${entry.x.bound ? ` — ${entry.x.bound}` : ""}`,
              `${entry.y.name} (${entry.y.unit}): ${entry.y.display}${entry.y.bound ? ` — ${entry.y.bound}` : ""}`,
            ].join("\n");
          }
        : undefined,
    },
  };
  return { option, hasPlottableData: data.length > 0 };
}

/**
 * Build the complete rendering model for one resolved chart view.
 * Pure: same input -> deep-equal output, no side effects, no DOM.
 */
export function buildChart(view: ChartViewResponse, options: BuildOptions = {}): BuiltChartResult {
  const interactions = options.interactions ?? INTERACTIONS_DEFAULT;
  const animation = options.animation ?? ANIMATION_DEFAULT;

  if (!rendererSupports(view.definition)) {
    return {
      kind: "unsupported-renderer",
      rendererVersion: view.definition.renderer_version,
      expected: "echarts-modular-svg@1",
    };
  }

  const gridDates = unionGrid(view.series);
  const isScatter = view.definition.visualization_type === "scatter";
  // NI-071: compared fan-out series carry their distinguishing filter values.
  const displayNames = describeSeries(view).map(series => series.name);

  // The accessible exact-value table.
  let table: TableModel;
  if (isScatter) {
    const xSeries = view.series[0];
    const ySeries = view.series[1];
    const xByDate = xSeries ? pointsByDate(xSeries) : new Map<string, Observation>();
    const yByDate = ySeries ? pointsByDate(ySeries) : new Map<string, Observation>();
    table = {
      columns:
        xSeries && ySeries
          ? [
              { label: `X — ${xSeries.metric.title}`, unit: xSeries.metric.unit },
              { label: `Y — ${ySeries.metric.title}`, unit: ySeries.metric.unit },
            ]
          : [],
      rows: gridDates.map((date) => {
        const xPoint = xByDate.get(date);
        const yPoint = yByDate.get(date);
        return {
          date,
          cells: [
            xPoint ? valueCell(xPoint) : missingCell("no observation"),
            yPoint ? valueCell(yPoint) : missingCell("no observation"),
          ],
        };
      }),
    };
  } else {
    table = {
      columns: view.series.map((s, index) => ({ label: displayNames[index], unit: s.metric.unit })),
      rows: gridDates.map((date) => ({
        date,
        cells: view.series.map((seriesResponse) => {
          const point = pointsByDate(seriesResponse).get(date);
          return point ? valueCell(point) : missingCell("no observation");
        }),
      })),
    };
  }

  let observedCount = 0;
  let missingCount = 0;
  let boundedCount = 0;
  for (const row of table.rows) {
    for (const cell of row.cells) {
      if (cell.kind === "value") {
        observedCount += 1;
        if (cell.bound !== null) {
          boundedCount += 1;
        }
      } else {
        missingCount += 1;
      }
    }
  }

  const summary = buildSummary(view, gridDates, observedCount, missingCount, boundedCount);

  if (isScatter) {
    const built = buildScatterOption({ view, gridDates, interactions, animation, summary });
    return {
      kind: "ok",
      option: built.option,
      table,
      summary,
      hasPlottableData: built.hasPlottableData,
      panelCount: 1,
    };
  }

  return {
    kind: "ok",
    option: buildCartesianOption({ view, gridDates, interactions, animation, summary }),
    table,
    summary,
    hasPlottableData: observedCount > 0,
    panelCount: unitGroups(view.series).length,
  };
}

/** Display units line for the frame metadata ("NEAR · USD"), in series order. */
export function displayUnits(view: ChartViewResponse): string {
  return [...new Set(view.series.map((s) => s.metric.unit))].join(" · ");
}
