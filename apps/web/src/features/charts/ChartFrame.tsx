"use client";

import type { ReactNode } from "react";
import Link from "next/link";

import { QualityBadge } from "@/components/data-state/QualityBadge";
import { StaleNotice } from "@/components/data-state/DataState";
import type { DataMetadata, DataQuality } from "@/components/data-state/quality";
import { DataTable } from "./DataTable";
import { SourceDrawer } from "./SourceDrawer";
import type { ChartMode, ChartPresentation, DataSource, FrameTableRow } from "./chart-frame-types";

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
 *
 * NI-095 `variant="card"`: the minimalist dashboard card. One serif title
 * (optionally a link into the full detail page), one units subtitle, one
 * compact Live badge, one right-aligned action slot above the plot and one
 * compact axis-explanation footer. The long mode pill, quality badge,
 * period/last-observed line, source drawer and the visible summary/table
 * collapse into visually-hidden nonvisual semantics — the underlying data
 * model is unchanged and the honest unavailable/stale states stay visible.
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
  datasetId,
  manifestUrl,
  tableRows,
  valueHeader,
  rangeSlot,
  actions,
  stale,
  presentation,
  previewValues,
  variant = "full",
  titleHref,
  axisExplanation,
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
  datasetId?: string;
  manifestUrl?: string;
  tableRows?: FrameTableRow[];
  valueHeader?: string;
  /** Range/selection controls (keyboard reachable; renderer supplies them). */
  rangeSlot?: ReactNode;
  /** Permitted actions for the current context (public/editor/export). */
  actions?: ReactNode;
  /** When true, shows the stale notice while retaining the last good values. */
  stale?: boolean;
  presentation?: ChartPresentation;
  /** In a saved-card preview the exact table shares the summary disclosure. */
  previewValues?: ReactNode;
  /** NI-095: the minimalist dashboard card chrome. */
  variant?: "card" | "full";
  /** When set, the card title links into the full chart detail page. */
  titleHref?: string;
  /** NI-095 compact axis/series explanation rendered under the plot. */
  axisExplanation?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const card = variant === "card";
  const liveBadge = card ? (
    mode === "live" && quality?.status === "ok" ? (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-sage px-2.5 py-0.5 text-metadata font-medium text-accent">
        <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" />
        Live
      </span>
    ) : quality?.status === "stale" ? (
      <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-metadata font-medium text-warning">
        Last good values
      </span>
    ) : (
      <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-metadata font-medium text-text-secondary">
        {mode === "live" ? "Unavailable" : "Pinned version"}
      </span>
    )
  ) : null;

  if (card) {
    return (
      <figure className={cn("paper-panel min-w-0 p-6 lg:p-8", className)}>
        <figcaption className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
            <div className="min-w-0">
              {presentation ? null : titleHref ? (
                <Link
                  href={titleHref}
                  className="font-serif text-heading leading-heading font-semibold text-text hover:underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  {title}
                </Link>
              ) : (
                <p className="font-serif text-heading leading-heading font-semibold text-text">{title}</p>
              )}
              {units ? (
                <p className="text-ui leading-ui text-text-secondary">{units}</p>
              ) : null}
            </div>
            {liveBadge}
          </div>
          {stale && quality ? <StaleNotice quality={quality} metadata={metadata} /> : null}
        </figcaption>

        {actions ? (
          <div className="mt-3 flex flex-wrap items-center justify-end gap-2 border-t border-border pt-3">
            {actions}
          </div>
        ) : null}

        <div className="mt-3">{children}</div>

        {axisExplanation ? (
          <div className="mt-4 rounded-control bg-surface-muted px-3 py-2">
            {axisExplanation}
          </div>
        ) : null}

        {/* Nonvisual semantics: the summary and the exact-value table stay in
            the DOM for assistive technology; the dashboard card hides them
            visually (NI-095) instead of dropping the accessibility contract. */}
        <div className="sr-only">
          <p>{summary}</p>
          {previewValues}
          {tableRows ? (
            <DataTable
              caption={`${title} — equivalent data`}
              rows={tableRows}
              valueHeader={units ? `Value (${units})` : valueHeader}
            />
          ) : null}
        </div>
      </figure>
    );
  }

  return (
    <figure className={cn("paper-panel min-w-0 p-5 lg:p-7", className)}>
      <figcaption className="flex flex-col gap-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {presentation ? null : (
              <p className="font-serif text-heading leading-heading font-medium text-text">{title}</p>
            )}
            {units ? (
              <p className="text-ui leading-ui text-text-secondary">
                Units: <span className="font-medium">{units}</span>
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {presentation !== "saved-preview" ? (
              <span className="rounded-full bg-sage px-2.5 py-1 text-metadata font-medium text-accent">
                {mode === "live" ? "Live — latest approved data" : "Historical — pinned version"}
              </span>
            ) : null}
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
      <div className={cn("flex flex-wrap items-center gap-2 border-y border-border", presentation ? "mt-3 py-2" : "mt-4 py-2.5")}>
        {rangeSlot}
        {actions}
        <SourceDrawer
          label="Sources & definitions"
          sources={sources}
          formulaUrl={formulaUrl}
          datasetId={datasetId}
          manifestUrl={manifestUrl}
          definition={definition}
          triggerClassName="ml-auto"
        />
      </div>

      <div className={presentation ? "mt-3" : "mt-4"}>{children}</div>

      <div className="mt-4 flex flex-col gap-3">
        <details className="rounded-control border border-border bg-surface-muted p-4">
          <summary className="text-ui leading-ui font-medium cursor-pointer">
            {previewValues ? "Exact values and summary" : "Accessible summary"}
          </summary>
          <p className="text-body leading-body text-text-secondary mt-2">{summary}</p>
          {previewValues}
        </details>
        {tableRows ? (
          <DataTable
            caption={`${title} — equivalent data`}
            rows={tableRows}
            valueHeader={units ? `Value (${units})` : valueHeader}
          />
        ) : null}
      </div>
    </figure>
  );
}
