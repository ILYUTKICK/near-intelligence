import Link from "next/link";

import { qualityPresentation } from "@/components/data-state/quality";
import type { ChartDefinitionResponse, ChartViewResponse, MetricResponse } from "@/features/charts/renderer/view-types";

import { availabilityWordings, categoryWordings, recordedOr, updateFrequencyWordings, visualizationWordings } from "./wording";

/**
 * Definitions and quality panel of the chart detail page (NI-034).
 *
 * Every quantitative publication needs a source, a definition version, a
 * dataset version, the calculation and its limitations (AGENTS.md): this
 * panel pins the definition identity (id, version, renderer), the bound
 * metric definitions with their A/P/B/G availability in words, the resolved
 * dataset version with coverage and quality, and the source lineage. Nothing
 * here refreshes silently — it renders exactly the resolved view that was
 * fetched for the URL selection. Missing values render "not recorded",
 * never fabricated placeholders.
 */
export function DefinitionQualityPanel({
  definition,
  view,
  metrics,
}: {
  definition: ChartDefinitionResponse;
  /** The resolved view for the current selection; null when nothing resolved. */
  view: ChartViewResponse | null;
  /** Per bound metric definition id: the fetched metric or null when unavailable. */
  metrics: Array<{ id: string; metric: MetricResponse | null }>;
}) {
  const quality = view?.quality;
  const qualityPresentationValue = quality ? qualityPresentation[quality.status] : null;
  const lineageSources = lineageListOf(definition);

  return (
    <section aria-labelledby="chart-quality-heading" className="mt-10 rounded-surface border border-border bg-surface-muted p-6">
      <h2 id="chart-quality-heading">Definition, dataset and quality</h2>
      <p className="text-body leading-body text-text-secondary mt-1 max-w-prose">
        This panel pins exactly what was resolved for the current URL selection: definition version,
        bound metric definitions, dataset version and quality. Links:{" "}
        <Link href="/methodology#definitions" className="text-accent underline underline-offset-2 hover:text-accent-hover">
          metric definitions
        </Link>{" "}
        and{" "}
        <Link href="/methodology#collection" className="text-accent underline underline-offset-2 hover:text-accent-hover">
          collection and cleaning
        </Link>
        .
      </p>

      <h3 className="mt-6">Chart definition</h3>
      <dl className="mt-2 grid grid-cols-1 gap-x-8 gap-y-1 max-w-prose sm:grid-cols-[max-content_1fr]">
        <dt>Chart id</dt><dd className="font-mono">{definition.chart_id}</dd>
        <dt>Version</dt><dd>v{definition.version} (immutable)</dd>
        <dt>Definition id</dt><dd className="font-mono break-all">{definition.id}</dd>
        <dt>Category</dt><dd>{categoryWordings[definition.category] ?? definition.category}</dd>
        <dt>Visualization</dt><dd>{visualizationWordings[definition.visualization_type] ?? definition.visualization_type}</dd>
        <dt>Series units</dt>
        <dd>{Object.entries(definition.units).map(([role, unit]) => `${role}: ${unit}`).join("; ")}</dd>
        <dt>Update frequency</dt>
        <dd>{updateFrequencyWordings[definition.update_frequency] ?? definition.update_frequency}</dd>
        <dt>Renderer</dt><dd className="font-mono">{definition.renderer_version}</dd>
        <dt>Allowed ranges</dt>
        <dd>
          presets {definition.available_ranges.presets_days.join(", ")} days; at most {definition.available_ranges.max_days} days per view
        </dd>
        <dt>Data status</dt>
        <dd>
          {definition.data_status === "available"
            ? "Available — an approved dataset resolves this chart."
            : `Unavailable — ${definition.unavailable_reason ?? "no reason recorded"}`}
        </dd>
      </dl>

      <h3 className="mt-6">Metric definitions</h3>
      <ul className="mt-2 flex flex-col gap-3 max-w-prose">
        {metrics.map(({ id, metric }) => (
          <li key={id} className="rounded-surface border border-border bg-surface p-4">
            {metric === null ? (
              <p className="text-ui leading-ui text-text-secondary">
                The metric definition details for <span className="font-mono">{id}</span> could not be
                resolved right now; availability is not guessed.
              </p>
            ) : (
              <>
                <p className="font-ui text-ui leading-ui font-medium">
                  {metric.title} — <span className="font-mono">{metric.metric_id}</span> v{metric.version}
                  <span className="text-text-secondary"> ({metric.unit})</span>
                </p>
                <p className="text-ui leading-ui text-text-secondary mt-1">
                  Availability: <span className="font-medium text-text">
                    {availabilityWordings[metric.availability].label}
                  </span>{" "}
                  — {availabilityWordings[metric.availability].description}
                </p>
                <p className="text-ui leading-ui text-text-secondary mt-1">
                  Calculation: <span className="font-mono">{metric.formula}</span> (registered computation
                  identifier, not executable input).
                </p>
                {metric.limitations.length > 0 ? (
                  <ul className="mt-1 list-disc pl-5 text-ui leading-ui text-text-secondary">
                    {metric.limitations.map((limitation) => (
                      <li key={limitation}>{limitation}</li>
                    ))}
                  </ul>
                ) : null}
              </>
            )}
          </li>
        ))}
      </ul>

      <h3 className="mt-6">Dataset and quality</h3>
      {view === null ? (
        <p className="text-ui leading-ui text-text-secondary mt-2 max-w-prose">
          No dataset is pinned for this chart right now — nothing is resolved, so no dataset
          version or coverage is shown rather than placeholders.
        </p>
      ) : (
        <dl className="mt-2 grid grid-cols-1 gap-x-8 gap-y-1 max-w-prose sm:grid-cols-[max-content_1fr]">
          <dt>Dataset</dt>
          <dd><span className="font-mono">{view.dataset.dataset_key}</span> v{view.dataset.version} ({view.dataset.status})</dd>
          <dt>Dataset id</dt><dd className="font-mono break-all">{view.dataset.id}</dd>
          <dt>Coverage window</dt>
          <dd>{view.dataset.start} … {view.dataset.end} (UTC, end exclusive)</dd>
          <dt>Observation coverage</dt>
          <dd>{view.quality.coverage.observed} of {view.quality.coverage.expected} expected periods</dd>
          <dt>Quality</dt>
          <dd>
            {qualityPresentationValue?.label ?? view.quality.status}
            {quality && quality.reasons.length > 0 ? ` — ${quality.reasons.join("; ")}` : ""}
          </dd>
          <dt>Source as of</dt><dd>{recordedOr(view.dataset.source_as_of)}</dd>
          <dt>Retrieved at</dt><dd>{recordedOr(view.dataset.retrieved_at)}</dd>
          <dt>Pipeline version</dt><dd className="font-mono">{view.dataset.pipeline_version}</dd>
          <dt>Dataset content hash</dt>
          <dd className="font-mono break-all">{view.dataset.content_sha256}</dd>
          <dt>Resolved at</dt><dd>{view.resolved_at}</dd>
        </dl>
      )}

      <h3 className="mt-6">Sources and lineage</h3>
      <p className="text-ui leading-ui text-text-secondary mt-2 max-w-prose">
        Registered lineage sources: {lineageSources}. Per-source license, access and verification
        details are in the chart&apos;s source drawer above.
      </p>
      {typeof definition.source_lineage["note"] === "string" && definition.source_lineage["note"] !== "" ? (
        <p className="text-ui leading-ui text-text-secondary mt-2 max-w-prose">
          {definition.source_lineage["note"]}
        </p>
      ) : null}
    </section>
  );
}

function lineageListOf(definition: ChartDefinitionResponse): string {
  const sources = definition.source_lineage["sources"];
  if (!Array.isArray(sources) || sources.length === 0) {
    return "none recorded";
  }
  return sources.filter((source): source is string => typeof source === "string").join(", ");
}
