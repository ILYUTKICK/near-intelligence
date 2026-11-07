/**
 * ECharts instance factory (NI-033).
 *
 * The only place that touches the ECharts runtime. Modular entry points
 * (echarts/core, echarts/charts, echarts/components, echarts/renderers) keep
 * the bundle to the chart types and components the renderer actually uses
 * (ADR-019); the SVG renderer is the accessibility-oriented default.
 *
 * The factory is an injectable seam: ChartView accepts a `factory` prop so
 * tests can drive mounting/disposal with a recording fake, and the future
 * static-export script can mount headless instances without React.
 */
import type { EChartsInitOpts } from "echarts/core";

import type { ChartOption } from "./option-builder";

/** The minimal instance surface the renderer needs. */
export interface EChartsLike {
  setOption(option: ChartOption): void;
  resize(): void;
  dispose(): void;
}

export interface ChartFactoryContext {
  /** Explicit pixel size; omit to auto-measure the container (browser). */
  width?: number;
  height?: number;
}

export type ChartFactory = (
  container: HTMLElement,
  context: ChartFactoryContext,
) => EChartsLike | Promise<EChartsLike>;

/**
 * Default factory: dynamically imports the modular ECharts entries, registers
 * exactly the needed charts/components/renderers and initializes an SVG
 * instance on the container. Dynamic import keeps ECharts out of the server
 * bundle and lets the bundler code-split it.
 */
export const defaultChartFactory: ChartFactory = async (container, context) => {
  // ECharts' component registration function is named `use`, which trips the
  // React hooks lint rules; alias it to its documented meaning.
  const [{ init, use: registerComponents }, charts, components, renderers, features] =
    await Promise.all([
      import("echarts/core"),
      import("echarts/charts"),
      import("echarts/components"),
      import("echarts/renderers"),
      import("echarts/features"),
    ]);
  registerComponents([
    charts.LineChart,
    charts.BarChart,
    charts.ScatterChart,
    components.GridComponent,
    components.TooltipComponent,
    components.AriaComponent,
    components.LegendComponent,
    components.AxisPointerComponent,
    // v6 moved `grid.containLabel` behind this legacy feature; the panel
    // layout relies on it so axis labels never clip.
    features.LegacyGridContainLabel,
    renderers.SVGRenderer,
  ]);

  const initOpts: EChartsInitOpts = { renderer: "svg" };
  if (context.width !== undefined) {
    initOpts.width = context.width;
  }
  if (context.height !== undefined) {
    initOpts.height = context.height;
  }
  const chart = init(container, undefined, initOpts);
  return {
    setOption: (option) => chart.setOption(option),
    resize: () => chart.resize(),
    dispose: () => chart.dispose(),
  };
};
