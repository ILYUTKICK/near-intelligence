"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";

import {
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  UnavailableState,
} from "@/components/data-state/DataState";
import type { DataMetadata } from "@/components/data-state/quality";
import { ChartFrame } from "@/features/charts/ChartFrame";
import type { ChartMode, ChartPresentation } from "@/features/charts/chart-frame-types";

import { RangeSelect } from "./RangeSelect";
import { SeriesTable } from "./SeriesTable";
import { buildChart, displayUnits } from "./option-builder";
import type { ChartFactory, EChartsLike } from "./chart-factory";
import { defaultChartFactory } from "./chart-factory";
import type { FiltersSelection } from "../filters/filter-values";
import type { ChartDefinitionResponse, ChartViewResponse } from "./view-types";
import { RENDERER_VERSION } from "./view-types";

/** The selection the renderer resolves (dates are "YYYY-MM-DD", half-open). */
export interface ChartSelection {
  start: string;
  end: string;
  /**
   * Values already validated against the definition's closed filter schema:
   * one approved string, or a list for a `multi_value` dimension (NI-071
   * comparison form; the resolved view carries one series per value).
   */
  filters?: FiltersSelection;
}

/**
 * Context-supplied resolver for the public/editor data layer. The renderer
 * itself stays transport-agnostic: the caller owns the fetch/URL/cache
 * policy and MUST honor the AbortSignal (stale requests are cancelled).
 */
export type ChartViewLoader = (args: {
  chartId: string;
  definitionId: string;
  start: string;
  end: string;
  filters: FiltersSelection;
  signal: AbortSignal;
}) => Promise<ChartViewResponse>;

export interface ChartViewProps {
  /** The immutable chart definition version being rendered. */
  definition: ChartDefinitionResponse;
  selection: ChartSelection;
  /**
   * Public/editor data resolver. When omitted, `view` must be provided.
   * Requests are debounced, aborted when superseded and aborted on unmount.
   */
  loader?: ChartViewLoader;
  /**
   * Controlled resolved view (pinned historical / already resolved). When
   * provided, no fetching happens — the pinned context is authoritative.
   */
  view?: ChartViewResponse | null;
  mode: ChartMode;
  /** Context-specific permitted actions (Save / Add to Research / …). */
  actions?: ReactNode;
  /** Range changes; when absent the range presets are not rendered. */
  onSelectionChange?: (selection: ChartSelection) => void;
  /** Explicit plot size; omit to let the container size the chart. */
  width?: number;
  height?: number;
  /** Saved previews show one context line and put exact values under the summary. */
  presentation?: ChartPresentation;
  /** NI-095: the minimalist dashboard card chrome (default: full detail chrome). */
  variant?: "card" | "full";
  /** NI-095: when set, the card title links into the full detail page. */
  titleHref?: string;
  /** Injectable ECharts mount (tests inject a recording fake). */
  factory?: ChartFactory;
  className?: string;
  /** Human instance context for repeated exact-table landmarks. */
  instanceLabel?: string;
}

const FETCH_DEBOUNCE_MS = 200;

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error && error.name === "AbortError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error && error.message
    ? error.message
    : "The chart data could not be resolved.";
}

/** Union of the series' sanitized sources, deduplicated by id. */
function sourcesOf(view: ChartViewResponse): ChartViewResponse["series"][number]["sources"] {
  const seen = new Map<string, ChartViewResponse["series"][number]["sources"][number]>();
  for (const series of view.series) {
    for (const source of series.sources) {
      if (!seen.has(source.id)) {
        seen.set(source.id, source);
      }
    }
  }
  return [...seen.values()];
}

function metadataOf(view: ChartViewResponse, definition: ChartDefinitionResponse): DataMetadata {
  const note = definition.source_lineage["note"];
  return {
    units: displayUnits(view),
    period: `${view.selection.start} … ${view.selection.end} UTC`,
    asOf:
      view.dataset.source_as_of ??
      view.dataset.retrieved_at ??
      view.resolved_at,
    limitation: typeof note === "string" && note ? note : undefined,
  };
}

function unavailableQuality(reason: string) {
  return {
    status: "unavailable" as const,
    bound_kind: null,
    reasons: [reason],
    coverage: { observed: 0, expected: 0 },
    freshness_target_seconds: null,
  };
}

/**
 * The reusable interactive chart renderer (NI-033). Public pages, the
 * workspace explorer and editor node views all render through this one
 * component: same option builder, same accessible table, same states
 * (CHART_SYSTEM.md). Mounts ECharts lazily (IntersectionObserver, with an
 * immediate fallback where the API is unavailable), cancels stale requests
 * via AbortController, and disposes the instance on unmount or rebuild.
 */
export function ChartView({
  definition,
  selection,
  loader,
  view: controlledView,
  mode,
  actions,
  onSelectionChange,
  width,
  height,
  presentation,
  variant = "full",
  titleHref,
  factory = defaultChartFactory,
  className,
  instanceLabel,
}: ChartViewProps) {
  const [fetchedView, setFetchedView] = useState<ChartViewResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(loader) && controlledView === undefined);
  const [error, setError] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [visible, setVisible] = useState(typeof IntersectionObserver === "undefined");

  const plotHostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsLike | null>(null);
  const zoomRef = useRef({ start: 0, end: 100 });
  const [zoomWindow, setZoomWindow] = useState({ start: 0, end: 100 });

  const controlled = controlledView !== undefined;
  const activeView = controlled ? controlledView : fetchedView;
  const filtersKey = JSON.stringify(selection.filters ?? {});
  const prefersReducedMotion = useMemo(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return false;
    }
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  // Data resolution (loader mode only): debounced, cancellable, stale-safe.
  useEffect(() => {
    if (!loader || controlled) {
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      loader({
        chartId: definition.chart_id,
        definitionId: definition.id,
        start: selection.start,
        end: selection.end,
        filters: selection.filters ?? {},
        signal: controller.signal,
      })
        .then((resolved) => {
          if (!cancelled) {
            setFetchedView(resolved);
            setLoading(false);
            setError(null);
          }
        })
        .catch((cause: unknown) => {
          if (cancelled || isAbortError(cause)) {
            return;
          }
          setError(errorMessage(cause));
          setLoading(false);
        });
    }, FETCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- filters are keyed by their stable JSON form
  }, [loader, controlled, definition.chart_id, definition.id, selection.start, selection.end, filtersKey, retryToken]);

  const retry = useCallback(() => setRetryToken((token) => token + 1), []);

  // Lazy mount: defer the chart until the host approaches the viewport.
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") {
      return;
    }
    const host = plotHostRef.current;
    if (!host) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "120px" },
    );
    observer.observe(host);
    return () => observer.disconnect();
  }, [activeView]);

  const built = useMemo(() => {
    if (!activeView) {
      return null;
    }
    return buildChart(activeView, { interactions: true, animation: !prefersReducedMotion });
  }, [activeView, prefersReducedMotion]);

  const plottable =
    built?.kind === "ok" && built.hasPlottableData && definition.data_status === "available";

  // Chart mount/update with full resource cleanup: an outdated instance is
  // disposed whether the teardown happens before or after the async factory.
  useEffect(() => {
    if (!visible || !plottable || !built || built.kind !== "ok" || !plotHostRef.current) {
      return;
    }
    let disposed = false;
    let instance: EChartsLike | null = null;
    let unsubscribeZoom: (() => void) | undefined;
    const option = built.option;
    const host = plotHostRef.current;
    Promise.resolve().then(() => factory(host, {
        ...(width !== undefined ? { width } : {}),
        ...(height !== undefined ? { height } : {}),
      })).then((created) => {
      if (disposed) {
        created.dispose();
        return;
      }
      instance = created;
      chartRef.current = created;
      created.setOption(option);
      zoomRef.current = { start: 0, end: 100 };
      setZoomWindow(zoomRef.current);
      unsubscribeZoom = created.onZoom?.((start, end) => {
        zoomRef.current = { start, end };
        setZoomWindow({ start, end });
      });
      setRenderError(null);
    }).catch(() => {
      if (!disposed) {
        instance?.dispose(); instance = null; chartRef.current = null;
        setRenderError("The plot could not render. The exact data table and prose remain available.");
      }
    });
    return () => {
      disposed = true;
      unsubscribeZoom?.();
      if (instance) {
        instance.dispose();
      }
      chartRef.current = null;
    };
  }, [visible, plottable, built, factory, width, height, retryToken]);

  // Container-driven resize (real browsers; the test stub is a no-op).
  useEffect(() => {
    if (typeof ResizeObserver === "undefined" || width !== undefined) {
      return;
    }
    const host = plotHostRef.current;
    if (!host) {
      return;
    }
    const observer = new ResizeObserver(() => {
      chartRef.current?.resize();
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, [width, visible, plottable]);

  const refreshing = loading && activeView !== null;
  const zoomable = built?.kind === "ok" && Boolean(built.option.dataZoom);
  const zoomDates = built?.kind === "ok" && built.table.rows.length ? [
    built.table.rows[Math.floor((built.table.rows.length - 1) * zoomWindow.start / 100)].date,
    built.table.rows[Math.ceil((built.table.rows.length - 1) * zoomWindow.end / 100)].date,
  ] : null;
  const navigatePlot = (factor: number | "reset") => {
    const current = zoomRef.current;
    const span = factor === "reset" ? 100 : Math.min(100, Math.max(1, (current.end - current.start) * factor));
    const center = (current.start + current.end) / 2;
    const start = factor === "reset" ? 0 : Math.max(0, Math.min(100 - span, center - span / 2));
    const next = { start, end: start + span };
    zoomRef.current = next;
    setZoomWindow(next);
    chartRef.current?.zoom?.(next.start, next.end);
  };
  const metadata = activeView ? metadataOf(activeView, definition) : undefined;
  const savedPreview = presentation === "saved-preview";
  const previewValues = savedPreview && plottable && built?.kind === "ok"
    ? <SeriesTable model={built.table} title={definition.title} instanceLabel={instanceLabel} className="mt-3" />
    : undefined;

  const plot = () => {
    if (definition.data_status === "unavailable") {
      return (
        <UnavailableState
          quality={unavailableQuality(
            definition.unavailable_reason ?? "This chart is not available; no data is rendered.",
          )}
          metadata={metadata}
        />
      );
    }
    if (!activeView) {
      if (error) {
        return <ErrorPanel message={error} onRetry={retry} />;
      }
      return <LoadingPanel label="Loading chart data" />;
    }
    if (!built || built.kind !== "ok") {
      return (
        <UnavailableState
          quality={unavailableQuality(
            built && built.kind === "unsupported-renderer"
              ? `The definition targets renderer ${built.rendererVersion}, but this application provides ${built.expected}; nothing is rendered rather than a best-effort redraw.`
              : "The resolved chart cannot be rendered by this application.",
          )}
          metadata={metadata}
        />
      );
    }
    if (!built.hasPlottableData) {
      if (activeView.quality.status === "missing" || activeView.quality.status === "unavailable") {
        return <UnavailableState quality={activeView.quality} metadata={metadata} />;
      }
      return <EmptyState metadata={metadata} />;
    }
    return (
      <div className="flex flex-col gap-3">
        {refreshing ? (
          <p role="status" className="text-ui leading-ui text-text-secondary">
            Updating to the latest selection; showing the last resolved values.
          </p>
        ) : null}
        {error ? <ErrorPanel message={error} onRetry={retry} /> : null}
        {renderError ? <ErrorPanel message={renderError} onRetry={retry} /> : null}
        {/* NI-095: the dashboard card drops the zoom buttons — the plot keeps
            its direct drag/scroll dataZoom interaction. */}
        {zoomable && variant !== "card" ? (
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label={`${definition.title} — plot navigation`}>
            <Button variant="secondary" onClick={() => navigatePlot(0.5)} disabled={zoomWindow.end - zoomWindow.start <= 1}>Zoom in</Button>
            <Button variant="secondary" onClick={() => navigatePlot(2)}>Zoom out</Button>
            <Button variant="secondary" onClick={() => navigatePlot("reset")}>Reset zoom</Button>
            {zoomDates ? <span role="status" className="text-metadata text-text-secondary">Plot view: {zoomDates[0]} → {zoomDates[1]} UTC.</span> : null}
            <span className="text-metadata text-text-secondary">Drag the timeline or Shift + scroll to zoom. Plot zoom leaves period totals unchanged.</span>
          </div>
        ) : null}
        <div
          ref={plotHostRef}
          role="img"
          aria-label={built.summary}
          className="w-full"
          style={{ height: height ?? 320, ...(width !== undefined ? { maxWidth: width } : {}) }}
        />
        {savedPreview ? null : variant === "card" ? (
          // NI-095: the exact-value table stays available to assistive
          // technology; the dashboard card hides it visually.
          <div className="sr-only">
            <SeriesTable model={built.table} title={definition.title} instanceLabel={instanceLabel} />
          </div>
        ) : (
          <SeriesTable model={built.table} title={definition.title} instanceLabel={instanceLabel} />
        )}
      </div>
    );
  };

  // NI-095 compact axis explanation: the actual variables the chart plots.
  // Scatter charts plot metric-on-metric (first binding on X); time-series
  // plot the date axis against every bound series.
  const axisExplanation = (() => {
    if (variant !== "card" || !activeView || activeView.series.length === 0) {
      return undefined;
    }
    const named = activeView.series.map(
      (series) => `${series.metric.title} (${series.metric.unit})`);
    const scatter = definition.visualization_type === "scatter";
    const xLabel = scatter ? named[0] ?? "X" : "Date (UTC)";
    const yLabel = scatter ? named[1] ?? named[0] ?? "Y" : named.join(" · ") || "Y";
    return (
      <p className="text-metadata leading-metadata text-text-secondary">
        <span className="font-medium text-text">X</span> — {xLabel}.{" "}
        <span className="font-medium text-text">Y</span> — {yLabel}.
      </p>
    );
  })();

  return (
    <ChartFrame
      title={definition.title}
      units={activeView ? displayUnits(activeView) : undefined}
      mode={mode}
      quality={activeView?.quality}
      metadata={savedPreview && metadata ? { ...metadata, period: undefined } : metadata}
      summary={
        built && built.kind === "ok"
          ? built.summary
          : `${definition.title}. ${definition.description}`
      }
      sources={activeView ? sourcesOf(activeView) : []}
      definition={definition.description}
      datasetId={activeView?.dataset.id}
      manifestUrl={activeView?.dataset.manifest_url ?? undefined}
      rangeSlot={
        onSelectionChange ? (
          <RangeSelect definition={definition} selection={selection} onChange={onSelectionChange} />
        ) : undefined
      }
      actions={actions}
      stale={activeView?.quality.status === "stale"}
      presentation={presentation}
      previewValues={previewValues}
      variant={variant}
      titleHref={titleHref}
      axisExplanation={axisExplanation}
      className={className}
    >
      {plot()}
    </ChartFrame>
  );
}

/** Re-exported so contexts can display the registry renderer version. */
export { RENDERER_VERSION };
export type { ChartDefinitionResponse, ChartViewResponse };
export type { ChartFactory, EChartsLike } from "./chart-factory";
