"use client";

import { useEffect, useRef, useState } from "react";

import { defaultChartFactory } from "@/features/charts/renderer/chart-factory";
import { CHART_SERIES_COLORS } from "@/features/charts/renderer/option-builder";

/** Recorded categorical summaries, not fabricated daily observations or dataset IDs. */
export function RecordedQuantityPlot({ labels, values, unit, title }: {
  labels: string[];
  values: string[];
  unit: string;
  title: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!host.current) return;
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    const container = host.current;
    void Promise.resolve(defaultChartFactory(container, {})).then((chart) => {
      if (cancelled) { chart.dispose(); return; }
      chart.setOption({
        animation: false,
        color: [...CHART_SERIES_COLORS],
        grid: { left: 12, right: 24, top: 24, bottom: 36, containLabel: true },
        xAxis: { type: "value", min: 0, name: unit, nameLocation: "middle", nameGap: 27 },
        yAxis: { type: "category", data: labels, inverse: true, axisLabel: { width: 125, overflow: "break" } },
        series: [{ type: "bar", name: unit, barMaxWidth: 26,
          // Only plot geometry crosses the Number boundary; labels retain source strings.
          data: values.map((value) => Number(value.replaceAll(",", ""))) }],
        tooltip: { trigger: "axis", renderMode: "richText", confine: true,
          formatter: (params) => {
            const item = Array.isArray(params) ? params[0] : params;
            return `${labels[item.dataIndex]}\n${values[item.dataIndex]} ${unit}`;
          } },
      });
      const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => chart.resize());
      observer?.observe(container);
      cleanup = () => { observer?.disconnect(); chart.dispose(); };
      setFailed(false);
    }).catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; cleanup?.(); };
  }, [labels, values, unit]);
  return <>
    {failed ? <p role="status" className="mt-3 text-ui text-text-secondary">The plot could not render. Recorded values remain available below.</p> : null}
    <div ref={host} role="img" aria-label={`${title}. ${labels.map((label, i) => `${label}: ${values[i]} ${unit}`).join("; ")}. Exact values also follow in text.`} className="mt-4 h-56 w-full" />
  </>;
}
