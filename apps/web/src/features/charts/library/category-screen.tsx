import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { PageIntro } from "@/components/layout/PageIntro";
import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { ChartAuthActions } from "@/features/charts/library/ChartAuthActions";
import { ChartCatalogEntry } from "@/features/charts/library/ChartCatalogEntry";
import { fetchChartCatalog } from "@/features/charts/library/catalog-api";
import { explorerCategoryBySlug } from "@/features/charts/library/explorer-categories";
import { dropUnknownParams } from "@/features/charts/library/search-values";
import { detailHrefFor } from "@/features/charts/library/selection-url";
import { categoryWordings } from "@/features/charts/library/wording";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { fetchLatestDefaultView } from "./default-view";

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
export async function DataCategoryScreen({
  params,
  searchParams,
  routePrefix = "",
}: {
  params: Promise<{ category: string }>;
  searchParams: Promise<SearchValues>;
  routePrefix?: "" | "/workspace";
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
  // NI-093: every AVAILABLE chart in the category renders its implicit default
  // view inline (NI-092 defaults — coverage-clamped window, preselected first
  // approved filter) with its own save continuation; a visitor only follows a
  // chart into the full detail page when they want the complete context.
  const unavailableItems = items.filter((item) => item.data_status !== "available");
  const inlineViews = failure ? [] : await Promise.all(
    items
      .filter((item) => item.data_status === "available")
      .map((definition) =>
        fetchLatestDefaultView(definition)
          .then(({ range, result }) => ({ definition, range, result }))),
  );

  return (
    <div className="page-container">
      <Breadcrumbs items={[{ label: "Data", href: `${routePrefix}/data` }, { label: explorer.label }]} />
      <PageIntro className="mt-5" eyebrow="Data explorer" title={explorer.label} description={explorer.question} />

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
        <div role="alert" className="paper-panel mt-8 p-8">
          <h2>The catalog could not be loaded</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            {failure.status === 503
              ? "The chart API is unavailable right now. Nothing is shown rather than stale or fabricated entries."
              : "The catalog request failed. Nothing is shown rather than partial or fabricated entries."}
          </p>
          <Link
            href={`${routePrefix}/data/${explorer.slug}`}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Try again
          </Link>
        </div>
      ) : items.length === 0 ? (
        <div className="paper-panel mt-8 flex flex-col items-center p-10 text-center sm:p-14">
          <span className="mb-4 grid size-12 place-items-center rounded-full bg-sage text-accent">
            <ProductIcon name={slug === "ecosystem" ? "grid" : "globe"} className="size-6" />
          </span>
          <h2 className="text-heading md:text-title">{explorer.emptyExplanation.heading}</h2>
          <p className="mt-2 max-w-[55ch] text-ui text-text-secondary">
            {explorer.emptyExplanation.body}
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Button asChild><Link href={`${routePrefix}/charts`}>Browse the chart library</Link></Button>
            <Button asChild variant="quiet"><Link href="/methodology#definitions">Metric definitions</Link></Button>
          </div>
        </div>
      ) : (
        <>
          {inlineViews.length > 0 ? (
            <div className="mt-8 grid items-start gap-5 lg:grid-cols-2">
              {inlineViews.map(({ definition, range, result }) => {
                const href = detailHrefFor(`${routePrefix}/data/${slug}`, definition.chart_id, {
                  ...range,
                  version: definition.version,
                  datasetVersion: result.ok ? result.data.dataset.id : "latest",
                  filters: {},
                });
                const actions = (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button asChild variant="secondary">
                      <Link href={href}>Inspect range and data <ProductIcon name="arrow" /></Link>
                    </Button>
                    {result.ok ? (
                      <ChartAuthActions
                        nextPath={href}
                        basePath={`${routePrefix}/data/${slug}/`}
                        saveInput={{
                          chart_definition_version_id: definition.id,
                          label: null,
                          mode: "live",
                          selection: result.data.selection,
                          dataset_version_id: result.data.dataset.id,
                          snapshot_id: null,
                        }}
                      />
                    ) : null}
                  </div>
                );
                return result.ok ? (
                  <ChartView key={definition.id} definition={definition} view={result.data}
                    selection={range} mode="live" height={240} actions={actions} />
                ) : (
                  <section key={definition.id} className="paper-panel p-6">
                    <p className="eyebrow">Data unavailable</p>
                    <h2 className="mt-2 text-heading">{definition.title}</h2>
                    <p className="my-3 text-ui text-text-secondary">{result.message ?? "The selected chart could not be resolved."}</p>
                    <Link
                      href={href}
                      className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                    >
                      Open chart: {definition.title}
                    </Link>
                  </section>
                );
              })}
            </div>
          ) : null}
          {unavailableItems.length > 0 ? (
            <>
              <h2 className="mt-10 text-heading">Registered charts</h2>
              <ul className="mt-3 grid gap-4 sm:grid-cols-2">
                {unavailableItems.map((item) => (
                  <ChartCatalogEntry key={item.chart_id} chart={item} href={`${routePrefix}/data/${slug}/${item.chart_id}`} />
                ))}
              </ul>
            </>
          ) : null}
        </>
      )}
      <p className="mt-6 max-w-(--width-prose) text-ui text-text-secondary">{explorer.scopeNote}</p>
      <p className="mt-2 text-metadata text-text-secondary">
        {explorer.registryCategories.length === 0
          ? "No registry category is mapped to this explorer category yet."
          : `Registry categories mapped here: ${explorer.registryCategories.map((category) => categoryWordings[category] ?? category).join(", ")}.`}
      </p>
    </div>
  );
}
