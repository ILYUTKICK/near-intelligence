"use client";

import type { ReactNode } from "react";

import { QualityBadge } from "@/components/data-state/QualityBadge";
import { StaleNotice } from "@/components/data-state/DataState";
import type { DataMetadata, DataQuality } from "@/components/data-state/quality";
import { DataTable } from "./DataTable";
import { SourceDrawer } from "./SourceDrawer";
import type { ChartMode, DataSource, FrameTableRow } from "./chart-frame-types";

import { cn } from "@/lib/utils";

/**
 * Analytical chart frame (NI-010) — the consistent container the public
 * site, workspace and later exports share (CHART_SYSTEM.md). It owns:
 * title, units, mode, quality badge, freshness metadata, range/actions
 * toolbar slots, an accessible summary and the equivalent data table.
 * It performs no fetching: data comes in through props, the plot itself is
 * a child slot (interactive renderer arrives with NI-033).
 *
 * Freshness and bound metadata always render (wrapping, never hidden) —
 * they survive small screens; the source drawer reflows instead.
 */
export function ChartFrame({
  title,
  units,
  mode,
  quality,
  metadata,
  summary,
  sources = [],
  definition,
  formulaUrl,
  manifestUrl,
  tableRows,
  valueHeader,
  rangeSlot,
  actions,
  stale,
  children,
  className,
}: {
  title: string;
  /** Measurement units, e.g. "NEAR / day" — always visible. */
  units?: string;
  mode: ChartMode;
  quality?: DataQuality;
  metadata?: DataMetadata;
  /** Concise manual summary announced to assistive technology. */
  summary: string;
  sources?: DataSource[];
  definition?: string;
  formulaUrl?: string;
  manifestUrl?: string;
  tableRows?: FrameTableRow[];
  valueHeader?: string;
  /** Range/selection controls (keyboard reachable; renderer supplies them). */
  rangeSlot?: ReactNode;
  /** Permitted actions for the current context (public/editor/export). */
  actions?: ReactNode;
  /** When true, shows the stale notice while retaining the last good values. */
  stale?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <figure className={cn("rounded-surface border border-border bg-surface p-6", className)}>
      <figcaption className="flex flex-col gap-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-heading leading-heading font-serif text-text">{title}</p>
            {units ? (
              <p className="text-ui leading-ui text-text-secondary">
                Units: <span className="font-medium">{units}</span>
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-ui text-ui leading-ui rounded-control border border-border px-2 py-1 text-text-secondary">
              {mode === "live" ? "Live — latest approved data" : "Historical — pinned version"}
            </span>
            {quality ? <QualityBadge quality={quality} /> : null}
          </div>
        </div>
        {/* Freshness/bounds metadata: always present, wraps on small screens. */}
        {metadata && (metadata.period || metadata.asOf) ? (
          <p className="text-metadata leading-metadata text-text-secondary">
            {metadata.period ? <span>Period: {metadata.period}. </span> : null}
            {metadata.asOf ? <span>Last observed: {metadata.asOf}.</span> : null}
          </p>
        ) : null}
        {stale && quality ? <StaleNotice quality={quality} metadata={metadata} /> : null}
      </figcaption>

      {/* Toolbar: wraps on narrow screens; all controls are real buttons. */}
      {rangeSlot || actions ? (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {rangeSlot}
          {actions}
        </div>
      ) : null}

      <div className="mt-4">{children}</div>

      <div className="mt-4 flex flex-col gap-3">
        <details className="rounded-control border border-border bg-surface-muted p-4">
          <summary className="text-ui leading-ui font-medium cursor-pointer">
            Accessible summary
          </summary>
          <p className="text-body leading-body text-text-secondary mt-2">{summary}</p>
        </details>
        {tableRows ? (
          <DataTable
            caption={`${title} — equivalent data`}
            rows={tableRows}
            valueHeader={units ? `Value (${units})` : valueHeader}
          />
        ) : null}
        <div className="text-ui leading-ui text-text-secondary flex flex-wrap items-center gap-x-4 gap-y-1">
          <SourceDrawer
            label="Sources & definitions"
            sources={sources}
            formulaUrl={formulaUrl}
            manifestUrl={manifestUrl}
            definition={definition}
          />
          <span className="text-metadata leading-metadata">
            Source timestamps and bounds stay visible at every screen size — open the drawer
            for full provenance.
          </span>
        </div>
      </div>
    </figure>
  );
}
