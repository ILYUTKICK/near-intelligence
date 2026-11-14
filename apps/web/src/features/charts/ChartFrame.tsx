"use client";

import type { ReactNode } from "react";
import Link from "next/link";

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
 * NI-095 `variant="card"` / NI-096 `variant="full"`: both dashboard cards and
 * detail pages share the minimalist editorial chrome — serif title, units
 * subtitle, one compact Live badge, one toolbar (range presets, source
 * selector, single primary action), the plot as the focal point and a compact
 * axis-explanation footer. The long mode pill, quality badge,
 * period/last-observed line, source drawer, visible exact-value tables and
 * accessible-summary accordions collapse into visually-hidden nonvisual
 * semantics — the underlying data model and honesty contracts are unchanged:
 * unavailable/stale states stay visible, and the live badge only appears when
 * the resolved view genuinely is the latest approved data.
 */
export function ChartFrame({
  title,
  units,
  mode,
  quality,
  metadata,
  summary,
  sources = [],
  sourceDrawer = true,
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
  /** NI-096: the provenance drawer renders on working surfaces (editor
   * blocks, default); redesigned public surfaces announce provenance
   * nonvisually instead. */
  sourceDrawer?: boolean;
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
  /** NI-095: the minimalist dashboard card chrome (compact paddings, linked title). */
  variant?: "card" | "full";
  /** When set, the card title links into the full chart detail page. */
  titleHref?: string;
  /** NI-095 compact axis/series explanation rendered under the plot. */
  axisExplanation?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const card = variant === "card";
  const liveBadge = stale || quality?.status === "stale" ? (
    <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-metadata font-medium text-warning">
      Last good values
    </span>
  ) : quality?.status === "ok" && mode === "live" ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-sage px-2.5 py-0.5 text-metadata font-medium text-accent">
      <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" />
      Live
    </span>
  ) : (
    <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-metadata font-medium text-text-secondary">
      {mode === "live" ? "Unavailable" : "Pinned version"}
    </span>
  );

  const nonvisualBlock = (
    // NI-095/NI-096: the summary, the exact-value equivalent table and the
    // source provenance stay available to assistive technology; the
    // minimalist chrome hides them visually instead of dropping the
    // accessibility and provenance contracts.
    <div className="sr-only">
      <p>{summary}</p>
      {datasetId ? <p>{`Dataset version: ${datasetId}`}</p> : null}
      {metadata && (metadata.period || metadata.asOf) ? (
        <p>{[
          metadata.period ? `Period: ${metadata.period}.` : null,
          metadata.asOf ? `Last observed: ${metadata.asOf}.` : null,
        ].filter(Boolean).join(" ")}</p>
      ) : null}
      {sources.length > 0 ? (
        <ul>
          {sources.map((source) => (
            <li key={source.id}>{`${source.id} — ${source.name}`}</li>
          ))}
        </ul>
      ) : null}
      {previewValues}
      {tableRows ? (
        <DataTable
          caption={`${title} — equivalent data`}
          rows={tableRows}
          valueHeader={units ? `Value (${units})` : valueHeader}
        />
      ) : null}
    </div>
  );

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

        {nonvisualBlock}
      </figure>
    );
  }

  return (
    <figure className={cn("paper-panel min-w-0 p-6 lg:p-8", className)}>
      <figcaption className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
          <div className="min-w-0">
            {presentation ? null : (
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

      {/* Toolbar: range presets, source selector and the single primary action
          share one wrapped row (NI-096); all controls are real buttons. The
          provenance drawer renders only on working surfaces that opt in
          (editor blocks); detail pages announce provenance nonvisually. */}
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        {rangeSlot}
        {actions}
        {sourceDrawer ? (
          <SourceDrawer
            label="Sources & definitions"
            sources={sources}
            formulaUrl={formulaUrl}
            datasetId={datasetId}
            manifestUrl={manifestUrl}
            definition={definition}
            triggerClassName="ml-auto"
          />
        ) : null}
      </div>

      <div className={presentation ? "mt-3" : "mt-4"}>{children}</div>

      {axisExplanation ? (
        <div className="mt-4 border-t border-border pt-3">
          {axisExplanation}
        </div>
      ) : null}

      {presentation === "saved-preview" ? (
        // The saved-chart preview keeps its visible exact-value block: the
        // workspace surface pins one dataset and shows what is saved. The
        // freshness metadata stays announced nonvisually.
        <div className="mt-4 flex flex-col gap-3">
          <details className="rounded-control border border-border bg-surface-muted p-4">
            <summary className="text-ui leading-ui font-medium cursor-pointer">
              Exact values and summary
            </summary>
            <p className="text-body leading-body text-text-secondary mt-2">{summary}</p>
            {previewValues}
          </details>
          <div className="sr-only">
            {metadata && (metadata.period || metadata.asOf) ? (
              <p>{[
                metadata.period ? `Period: ${metadata.period}.` : null,
                metadata.asOf ? `Last observed: ${metadata.asOf}.` : null,
              ].filter(Boolean).join(" ")}</p>
            ) : null}
          </div>
        </div>
      ) : nonvisualBlock}
    </figure>
  );
}
