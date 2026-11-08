import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { fetchChartCatalog } from "@/features/charts/library/catalog-api";
import { explorerCategoryBySlug } from "@/features/charts/library/explorer-categories";
import { dropUnknownParams } from "@/features/charts/library/search-values";
import {
  categoryWordings,
  updateFrequencyWordings,
  visualizationWordings,
} from "@/features/charts/library/wording";

type SearchValues = Record<string, string | string[] | undefined>;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ category: string }>;
}): Promise<Metadata> {
  const { category } = await params;
  const explorer = explorerCategoryBySlug(category);
  return { title: explorer ? `${explorer.label} — NEAR Intelligence` : "Data — NEAR Intelligence" };
}

/**
 * Public data category (NI-015) at /data/[category]: the same analytical
 * components as the workspace Data Explorer category (INFORMATION_ARCHITECTURE.md).
 *
 * The category's registry categories (the closed API `category` values the
 * explorer mapping records) are each fetched through GET /api/charts?category=…
 * — the same catalog request the chart library makes — and the returned
 * definitions render with their honest data status. A category with no
 * registered charts renders its recorded explanation instead of placeholder
 * cards; unavailable charts stay listed with their reason and are never
 * hidden and never shown as zero. No URL parameter is approved on this page:
 * anything present is dropped with an honest note and never forwarded.
 */
export default async function DataCategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ category: string }>;
  searchParams: Promise<SearchValues>;
}) {
  const { category: slug } = await params;
  const values = await searchParams;
  const explorer = explorerCategoryBySlug(slug);
  if (explorer === null) {
    notFound();
  }

  const dropped = dropUnknownParams(values, []);

  // One bounded catalog request per mapped registry category; a category
  // with no registry categories makes no request at all (its explanation is
  // recorded, not derived from an empty response).
  const results = await Promise.all(
    explorer.registryCategories.map((registryCategory) =>
      fetchChartCatalog({ category: registryCategory }),
    ),
  );
  const failure = results.find((result): result is Extract<typeof result, { ok: false }> => !result.ok);
  const items = results.flatMap((result) => (result.ok ? result.data.items : []));

  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <Breadcrumbs items={[{ label: "Data", href: "/data" }, { label: explorer.label }]} />
      <h1 className="mt-4">{explorer.label}</h1>
      <p className="text-lg leading-body text-text mt-2 max-w-prose">{explorer.question}</p>
      <p className="text-body leading-body text-text-secondary mt-2 max-w-prose">
        {explorer.scopeNote}
      </p>
      <p className="text-ui leading-ui text-text-secondary mt-2 max-w-prose">
        {explorer.registryCategories.length === 0
          ? "No registry category is mapped to this explorer category yet."
          : `Registry categories mapped here: ${explorer.registryCategories
              .map((registryCategory) => categoryWordings[registryCategory] ?? registryCategory)
              .join(", ")}.`}
        {" "}The flat catalog of every registered chart remains the{" "}
        <Link href="/charts" className="text-accent underline underline-offset-2 hover:text-accent-hover">
          chart library
        </Link>
        .
      </p>

      {dropped.length > 0 ? (
        <div role="status" className="mt-4 rounded-surface border border-border bg-surface-muted p-4 max-w-prose">
          <p className="font-ui text-ui leading-ui font-medium">
            Some URL parameters were not used — the catalog request carries only supported fields.
          </p>
          <ul className="mt-2 list-disc pl-5 text-ui leading-ui text-text-secondary">
            {dropped.map((item, index) => (
              <li key={`${item.param}-${index}`}>
                <span className="font-medium">{item.param}</span>: {item.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {failure !== undefined ? (
        <div role="alert" className="mt-8 rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
          <h2>The catalog could not be loaded</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            {failure.status === 503
              ? "The chart API is unavailable right now. Nothing is shown rather than stale or fabricated entries."
              : "The catalog request failed. Nothing is shown rather than partial or fabricated entries."}
          </p>
          <Link
            href={`/data/${explorer.slug}`}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Try again
          </Link>
        </div>
      ) : items.length === 0 ? (
        <div className="mt-8 rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
          <h2>{explorer.emptyExplanation.heading}</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            {explorer.emptyExplanation.body}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link
              href="/charts"
              className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              Browse the chart library
            </Link>
            <Link
              href="/methodology#definitions"
              className="inline-flex h-11 items-center rounded-control border border-transparent px-4 font-ui text-ui leading-ui text-text underline underline-offset-2 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              Metric definitions
            </Link>
          </div>
        </div>
      ) : (
        <ul className="mt-8 flex flex-col gap-4 max-w-prose">
          {items.map((item) => (
            <li key={item.chart_id} className="rounded-surface border border-border bg-surface p-6 flex flex-col gap-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h2 className="text-lg">
                  <Link
                    href={`/data/${explorer.slug}/${item.chart_id}`}
                    className="hover:underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                  >
                    {item.title}
                  </Link>
                </h2>
                {item.data_status === "available" ? (
                  <span className="font-ui text-ui leading-ui font-medium text-accent">Available</span>
                ) : (
                  <span className="font-ui text-ui leading-ui font-medium text-danger">
                    Unavailable — this is not zero
                  </span>
                )}
              </div>
              <p className="text-body leading-body text-text-secondary">{item.description}</p>
              {item.data_status === "unavailable" && item.unavailable_reason ? (
                <p className="text-ui leading-ui text-text-secondary">
                  Reason: {item.unavailable_reason}
                </p>
              ) : null}
              <p className="text-ui leading-ui text-text-secondary">
                {categoryWordings[item.category] ?? item.category} ·{" "}
                {visualizationWordings[item.visualization_type] ?? item.visualization_type} ·{" "}
                {updateFrequencyWordings[item.update_frequency] ?? item.update_frequency} · Units:{" "}
                {[...new Set(Object.values(item.units))].join(", ")}
              </p>
              <div>
                <Link
                  href={`/data/${explorer.slug}/${item.chart_id}`}
                  aria-label={`Open chart: ${item.title}`}
                  className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  Open chart
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
