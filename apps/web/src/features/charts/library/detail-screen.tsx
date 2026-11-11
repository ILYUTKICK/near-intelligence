import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { PageIntro } from "@/components/layout/PageIntro";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { ChartDetailClient } from "@/features/charts/library/ChartDetailClient";
import { DefinitionQualityPanel } from "@/features/charts/library/DefinitionQualityPanel";
import {
  fetchChartDefinition,
  fetchChartView,
  fetchDataset,
  fetchMetric,
} from "@/features/charts/library/catalog-api";
import type { ApiFailure } from "@/features/charts/library/catalog-api";
import {
  defaultRangeFor,
  parseSelectionUrl,
  todayUtc,
} from "@/features/charts/library/selection-url";
import type { DroppedParam, SerializedSelection } from "@/features/charts/library/selection-url";
import { firstValue, toPairs } from "@/features/charts/library/search-values";
import type { SearchValues } from "@/features/charts/library/search-values";
import { categoryWordings } from "./wording";

/**
 * Shared chart-detail screen (NI-015 extraction of the NI-034 detail flow).
 *
 * One server component renders the whole validated chart-detail experience —
 * definition load, the single selection-URL gate (`parseSelectionUrl`),
 * range anchoring, metric/quality provenance and the resolved view — under
 * any public detail route base. The same serialized selection produces the
 * same view request under /charts and /data.
 *
 * Everything route-specific is parameterized by {@link ChartDetailLinks}:
 * the mounted base (selection URLs, retry/reset links, sign-in continuation)
 * and the category listing the page links back to. Behavior is otherwise
 * identical to the NI-034 detail: every URL value failing validation is
 * dropped with a rendered honest note and never forwarded; unavailable
 * charts render their recorded reason and never request a view.
 */

export interface ChartDetailLinks {
  /** Route base this detail is mounted at (e.g. "/charts", "/data/revenue"). */
  basePath: string;
  /** The category/library listing to link back to. */
  categoryHref?: string;
  /** Visible label of that listing (e.g. the explorer category label). */
  categoryLabel?: string;
  /** Breadcrumb entries before the chart title crumb. */
  breadcrumbRoots: Array<{ label: string; href?: string }>;
  /**
   * When set, a definition whose registry category is not listed is answered
   * with the 404 boundary (the data explorer only serves charts that belong
   * to the mapped explorer category's registry categories).
   */
  expectedRegistryCategories?: readonly string[];
}

const VERSION_PATTERN = /^[0-9]+$/;

export async function ChartDetailScreen({
  chartId,
  values,
  links,
}: {
  chartId: string;
  values: SearchValues;
  links: ChartDetailLinks;
}) {
  // The definition version is needed before the definition exists to
  // validate against; a malformed version falls back to latest and is
  // reported by the full parse below.
  const rawVersion = firstValue(values, "version");
  const urlVersion =
    rawVersion !== null && VERSION_PATTERN.test(rawVersion) && Number(rawVersion) >= 1
      ? Number(rawVersion)
      : null;

  const definitionResult = await fetchChartDefinition(chartId, urlVersion);
  if (!definitionResult.ok) {
    if (definitionResult.status === 404) {
      notFound();
    }
    return (
      <div className="page-container">
        <div role="alert" className="paper-panel p-8">
          <h1 className="text-page">Chart unavailable</h1>
          <p className="text-body leading-body text-text-secondary mt-2">
            The chart definition could not be loaded right now. Nothing is shown rather than
            partial or fabricated content.
          </p>
          <Link
            href={`${links.basePath}/${encodeURIComponent(chartId)}`}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Try again
          </Link>
        </div>
      </div>
    );
  }
  const definition = definitionResult.data;

  if (
    links.expectedRegistryCategories !== undefined
    && !links.expectedRegistryCategories.includes(definition.category)
  ) {
    notFound();
  }

  // Full selection validation against the loaded definition version — the
  // single gate between URL and fetch.
  const parsed = parseSelectionUrl(toPairs(values), definition);
  const dropped: DroppedParam[] = parsed.dropped;

  // Range resolution: an explicit validated range, or the version's default
  // preset anchored to the pinned dataset's coverage end (historical) or the
  // current UTC day (live). Anchoring is never silent — the default-source
  // note is rendered.
  let range = parsed.range;
  let rangeNote: string | null = null;
  let datasetFailure: DroppedParam | null = null;
  if (range === null) {
    const pinnedDataset = parsed.datasetVersion !== null && parsed.datasetVersion !== "latest"
      ? parsed.datasetVersion
      : null;
    if (pinnedDataset !== null) {
      const datasetResult = await fetchDataset(pinnedDataset);
      if (datasetResult.ok) {
        range = defaultRangeFor(definition, datasetResult.data.end);
        rangeNote =
          `No range was given in the URL; the chart version's default preset is anchored `
          + `to the pinned dataset's coverage end (${datasetResult.data.end} UTC).`;
      } else {
        datasetFailure = {
          param: "dataset_version",
          reason:
            "the pinned dataset version could not be resolved, so no view can be rendered for it",
        };
      }
    } else {
      range = defaultRangeFor(definition, todayUtc());
    }
  }

  // Bounded metric definitions for the quality panel (each may fail alone).
  const metrics = await Promise.all(
    definition.metric_definition_ids.map(async (id) => {
      const metricResult = await fetchMetric(id);
      return { id, metric: metricResult.ok ? metricResult.data : null };
    }),
  );

  const selection: SerializedSelection | null = range === null ? null : {
    version: definition.version,
    start: range.start,
    end: range.end,
    datasetVersion: parsed.datasetVersion ?? "latest",
    filters: parsed.filters,
  };

  // Resolved view — only for available charts and a resolvable selection.
  const viewResult =
    definition.data_status === "available" && selection !== null && datasetFailure === null
      ? await fetchChartView(chartId, {
          definitionVersion: definition.version,
          start: selection.start,
          end: selection.end,
          datasetVersion: selection.datasetVersion,
          filters: selection.filters,
        })
      : null;

  const view = viewResult !== null && viewResult.ok ? viewResult.data : null;

  /** The retry/reset URL: only the definition version re-pinned. */
  const resetHref = `${links.basePath}/${encodeURIComponent(chartId)}?version=${definition.version}`;
  const category = {
    label: links.categoryLabel ?? categoryWordings[definition.category] ?? definition.category,
    href: links.categoryHref ?? `/charts?category=${definition.category}`,
  };

  return (
    <div className="page-container pt-10">
      <Breadcrumbs items={[
        ...links.breadcrumbRoots,
        ...(links.categoryHref ? [] : [category]),
        { label: definition.title },
      ]} />
      <PageIntro className="mt-5" eyebrow={category.label} title={definition.title} description={definition.description} />
      <p className="mt-2 max-w-prose text-metadata text-text-secondary">
        Definition version v{definition.version} (pinned in the URL); renderer{" "}
        <span className="font-mono">{definition.renderer_version}</span>.
        {rangeNote !== null ? ` ${rangeNote}` : ""}
      </p>

      {datasetFailure !== null ? (
        <div role="alert" className="paper-panel mt-6 p-8">
          <h2>The pinned dataset could not be resolved</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            The dataset version in the URL does not resolve to an approved dataset, so no chart
            view can be rendered for it. Nothing is shown rather than data from another version.
          </p>
          <Link
            href={resetHref}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Show the latest approved dataset instead
          </Link>
        </div>
      ) : null}

      {viewResult !== null && !viewResult.ok ? (
        <ViewFailurePanel failure={viewResult} resetHref={resetHref} />
      ) : null}

      {definition.data_status === "unavailable" ? (
        /* The renderer's honest unavailable state: reason visible, no plot,
           no fake loading. The selection prop is required by the renderer's
           contract but unused in this configuration (no loader, no range
           slot), so a minimal value is passed rather than invented dates. */
        <div className="mt-5">
          <ChartView
            definition={definition}
            view={null}
            selection={selection !== null
              ? { start: selection.start, end: selection.end, filters: selection.filters }
              : { start: "", end: "" }}
            mode="live"
          />
          {dropped.length > 0 ? <DroppedNotice dropped={dropped} /> : null}
        </div>
      ) : selection !== null && datasetFailure === null && view !== null ? (
        <div className="mt-5">
          <ChartDetailClient
            chartId={chartId}
            definition={definition}
            view={view}
            selection={selection}
            dropped={dropped}
            basePath={links.basePath}
          />
        </div>
      ) : dropped.length > 0 ? (
        /* Definition available but the view failed (panel above) or the
           dataset anchor failed: nothing is rendered rather than a fake
           loading state, and URL notes stay visible. */
        <DroppedNotice dropped={dropped} />
      ) : null}

      <DefinitionQualityPanel definition={definition} view={view} metrics={metrics} />

      <p className="mt-8 max-w-prose">
        <Link
          href={category.href}
          className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          More charts in {category.label}
        </Link>
      </p>
    </div>
  );
}

/**
 * Breadcrumbs are rendered by the shared Breadcrumbs component from
 * `breadcrumbRoots` plus the chart title, giving "Data → category → chart"
 * for the explorer routes (INFORMATION_ARCHITECTURE.md).
 */

function DroppedNotice({ dropped }: { dropped: DroppedParam[] }) {
  return (
    <div role="status" className="mt-6 rounded-surface border border-border bg-surface-muted p-4 max-w-prose">
      <p className="font-ui text-ui leading-ui font-medium">
        Some URL parameters were not used — the chart request carries only supported fields.
      </p>
      <ul className="mt-2 list-disc pl-5 text-ui leading-ui text-text-secondary">
        {dropped.map((item, index) => (
          <li key={`${item.param}-${index}`}>
            <span className="font-medium">{item.param}</span>: {item.reason}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ViewFailurePanel({
  failure,
  resetHref,
}: {
  failure: ApiFailure;
  resetHref: string;
}) {
  return (
    <div role="alert" className="paper-panel mt-6 p-8">
      <h2>The chart data could not be resolved</h2>
      <p className="text-body leading-body text-text-secondary mt-2">
        {failure.status === 503
          ? "No approved dataset is ready for this chart yet — this is not zero, and no values are invented."
          : failure.status === 422
            ? "The server rejected this selection as unsupported. The URL selection is validated before any request, so this indicates a range or filter this chart version does not serve."
            : "The resolution request failed. Nothing is shown rather than partial or fabricated values."}
        {failure.message !== null ? ` The API reported: ${failure.message}` : ""}
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Link
          href={resetHref}
          className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          {failure.retryable ? "Try again" : "Reset to the default selection"}
        </Link>
        <Link
          href="/methodology#collection"
          className="inline-flex h-11 items-center rounded-control border border-transparent px-4 font-ui text-ui leading-ui text-text underline underline-offset-2 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          How this data is collected
        </Link>
      </div>
    </div>
  );
}
