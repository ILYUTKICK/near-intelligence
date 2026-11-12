"use client";

import Link from "next/link";

import { QualityBadge } from "@/components/data-state/QualityBadge";
import { detailHrefFor } from "@/features/charts/library/selection-url";
import type { Home } from "./api";

/** A contextual observation, never a home-specific financial calculation. */
export function HomeIndicators({ indicators }: { indicators: Home["indicators"] }) {
  return <section aria-labelledby="home-context-heading">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 id="home-context-heading">Data context</h2>
      <Link className="inline-flex min-h-11 items-center text-link underline" href="/data/intents">Explore data</Link>
    </div>
    <p className="mt-2 text-ui text-text-secondary">One day from the latest approved dataset for each chart. Historical data keeps its actual dates. These observations are context for research.</p>
    {!indicators.length ? <p role="status" className="mt-3">No approved contextual indicators are available.</p> : null}
    <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-3">
      {indicators.map((indicator) => {
        const series = indicator.series;
        const point = series?.points[0];
        const href = series && indicator.chart_version !== null ? detailHrefFor("/charts", indicator.chart_id, {
          version: indicator.chart_version, datasetVersion: series.dataset.id,
          start: series.selection.start, end: series.selection.end,
          // The server-validated canonical values (lists included) travel
          // through unchanged — the detail URL re-pins the exact selection.
          filters: series.selection.filters,
        }) : "/charts";
        return <article key={indicator.chart_id} aria-label={indicator.title} className="min-w-0 rounded-surface border border-border p-4 [overflow-wrap:anywhere]">
          <h3 className="font-medium">{indicator.title}</h3>
          {series ? <>
            <p className="mt-2 text-metadata text-text-secondary">{series.metric.title}</p>
            <p className="mt-2 font-mono text-title tabular-nums [overflow-wrap:anywhere]">{point?.value ?? "Unavailable — this is not zero"}</p>
            <p className="text-ui text-text-secondary">{series.metric.unit}</p>
            <div className="mt-3"><QualityBadge quality={point?.quality ?? series.dataset.quality} /></div>
            {point?.quality.status === "stale" || series.dataset.quality.status === "stale" ? <p role="status" className="mt-2 text-warning">Stale data — showing the last approved observation.</p> : null}
            <dl className="mt-3 space-y-2 text-metadata text-text-secondary">
              <div><dt className="font-medium">UTC period [start, end)</dt><dd>{series.selection.start} → {series.selection.end}</dd></div>
              <div><dt className="font-medium">Source as of</dt><dd>{series.dataset.source_as_of ?? "Not recorded"}</dd></div>
              <div><dt className="font-medium">Retrieved</dt><dd>{series.dataset.retrieved_at ?? "Not recorded"}</dd></div>
              <div><dt className="font-medium">Sources</dt><dd>{series.sources.map((source) => source.name).join(", ") || "Not recorded"}</dd></div>
              <div><dt className="font-medium">Versions</dt><dd>Metric {series.metric.metric_id} v{series.metric.version} · Chart v{indicator.chart_version} · Dataset {series.dataset.id}</dd></div>
              <div><dt className="font-medium">Calculation</dt><dd>{series.metric.formula}</dd></div>
            </dl>
            {[...new Set([...(point?.quality.reasons ?? []), ...series.dataset.quality.reasons, ...series.metric.limitations])].length ? <ul className="mt-3 list-disc pl-4 text-metadata text-text-secondary">{[...new Set([...(point?.quality.reasons ?? []), ...series.dataset.quality.reasons, ...series.metric.limitations])].map((reason) => <li key={reason}>{reason}</li>)}</ul> : null}
          </> : <p role="status" className="mt-3 text-text-secondary">Unavailable — {indicator.reason ?? "Approved data could not be resolved."} This is not zero. Your documents remain available.</p>}
          <Link className="mt-3 inline-flex min-h-11 items-center text-link underline" href={href}>Explore {indicator.title}</Link>
        </article>;
      })}
    </div>
  </section>;
}
