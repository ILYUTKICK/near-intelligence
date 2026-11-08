import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { ChartView } from "@/features/charts/renderer/ChartView";
import type { ChartDefinitionResponse } from "@/features/charts/renderer/view-types";
import { ChartDetailClient } from "@/features/charts/library/ChartDetailClient";
import { DefinitionQualityPanel } from "@/features/charts/library/DefinitionQualityPanel";
import {
  fetchChartDefinition,
  fetchChartView,
  fetchDataset,
  fetchMetric,
} from "@/features/charts/library/catalog-api";
import {
  defaultRangeFor,
  parseSelectionUrl,
  todayUtc,
} from "@/features/charts/library/selection-url";
import type { DroppedParam, SerializedSelection } from "@/features/charts/library/selection-url";
import { categoryWordings } from "@/features/charts/library/wording";

export const metadata: Metadata = { title: "Chart — NEAR Intelligence" };

type SearchValues = Record<string, string | string[] | undefined>;

const VERSION_PATTERN = /^[0-9]+$/;

/**
 * Chart detail (NI-034): one chart definition version at
 * /charts/{chart_id} with a validated selection URL.
 *
 * The URL pins the immutable definition version (`version`), the half-open
 * range (`start`/`end`), an optional historical dataset (`dataset_version`)
 * and validated filters (`filters`). Everything outside the approved
 * parameter set — and every value failing validation against the definition
 * version's bounded ranges / closed filter schema — is dropped with an
 * honestly rendered note and never forwarded to the API (acceptance: "no
 * arbitrary URL fetch fields"). The resolved view is fetched server-side for
 * exactly that validated selection and handed to the NI-033 renderer.
 */
export default async function ChartDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ chartId: string }>;
  searchParams: Promise<SearchValues>;
}) {
  const { chartId } = await params;
  const values = await searchParams;

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
      <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
        <div role="alert" className="rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
          <h1>Chart unavailable</h1>
          <p className="text-body leading-body text-text-secondary mt-2">
            The chart definition could not be loaded right now. Nothing is shown rather than
            partial or fabricated content.
          </p>
          <Link
            href={`/charts/${encodeURIComponent(chartId)}`}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Try again
          </Link>
        </div>
      </div>
    );
  }
  const definition = definitionResult.data;

  // Full selection validation against the loaded definition version.
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

  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <Breadcrumbs
        items={[
          { label: "Charts", href: "/charts" },
          {
            label: categoryWordings[definition.category] ?? definition.category,
            href: `/charts?category=${definition.category}`,
          },
          { label: definition.title },
        ]}
      />
      <h1 className="mt-4">{definition.title}</h1>
      <p className="text-body leading-body text-text-secondary mt-2 max-w-prose">
        {definition.description}
      </p>
      <p className="text-ui leading-ui text-text-secondary mt-2 max-w-prose">
        Definition version v{definition.version} (pinned in the URL); renderer{" "}
        <span className="font-mono">{definition.renderer_version}</span>.
        {rangeNote !== null ? ` ${rangeNote}` : ""}
      </p>

      {datasetFailure !== null ? (
        <div role="alert" className="mt-6 rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
          <h2>The pinned dataset could not be resolved</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            The dataset version in the URL does not resolve to an approved dataset, so no chart
            view can be rendered for it. Nothing is shown rather than data from another version.
          </p>
          <Link
            href={`/charts/${encodeURIComponent(chartId)}?version=${definition.version}`}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Show the latest approved dataset instead
          </Link>
        </div>
      ) : null}

      {viewResult !== null && !viewResult.ok ? (
        <ViewFailurePanel
          chartId={chartId}
          definition={definition}
          failure={viewResult}
        />
      ) : null}

      {definition.data_status === "unavailable" ? (
        /* The renderer's honest unavailable state: reason visible, no plot,
           no fake loading. The selection prop is required by the renderer's
           contract but unused in this configuration (no loader, no range
           slot), so a minimal value is passed rather than invented dates. */
        <div className="mt-8">
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
        <div className="mt-8">
          <ChartDetailClient
            chartId={chartId}
            definition={definition}
            view={view}
            selection={selection}
            dropped={dropped}
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
          href={`/charts?category=${definition.category}`}
          className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          More charts in {categoryWordings[definition.category] ?? definition.category}
        </Link>
      </p>
    </div>
  );
}

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
  chartId,
  definition,
  failure,
}: {
  chartId: string;
  definition: ChartDefinitionResponse;
  failure: { status: number; code: string | null; message: string | null; retryable: boolean };
}) {
  const retryHref = `/charts/${encodeURIComponent(chartId)}?version=${definition.version}`;
  return (
    <div role="alert" className="mt-6 rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
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
          href={retryHref}
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

function firstValue(values: SearchValues, key: string): string | null {
  const raw = values[key];
  if (raw === undefined) {
    return null;
  }
  return Array.isArray(raw) ? (raw[0] ?? null) : raw;
}

/** Flatten Next.js search values into explicit URL pairs for the parser. */
function toPairs(values: SearchValues): Array<[string, string]> {
  return Object.entries(values).flatMap(([key, raw]) =>
    raw === undefined
      ? []
      : Array.isArray(raw)
        ? raw.map((value): [string, string] => [key, value])
        : [[key, raw]],
  );
}
