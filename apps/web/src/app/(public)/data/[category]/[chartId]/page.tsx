import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ChartDetailScreen } from "@/features/charts/library/detail-screen";
import { explorerCategoryBySlug } from "@/features/charts/library/explorer-categories";

export const metadata: Metadata = { title: "Chart — NEAR Intelligence" };

type SearchValues = Record<string, string | string[] | undefined>;

/**
 * Public data-explorer chart detail (NI-015) at /data/[category]/[chartId].
 *
 * This page owns no selection logic of its own: the entire flow — definition
 * load, the single selection-URL gate, range anchoring, provenance and the
 * resolved view — is the shared {@link ChartDetailScreen}, which passes the
 * same `parseSelectionUrl`/`catalog-api` gates as the NI-034 chart detail at
 * /charts/{chart_id}. The serialized selection is identical for both routes,
 * so an identical selection URL resolves to an identical pinned view request
 * and the same values (acceptance: "identical public/private queries give
 * same pinned values"); only the mounted base differs. A chart whose
 * registry category is not mapped to this explorer category is answered with
 * the 404 boundary rather than rendered out of context.
 */
export default async function DataChartDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ category: string; chartId: string }>;
  searchParams: Promise<SearchValues>;
}) {
  const { category: slug, chartId } = await params;
  const values = await searchParams;
  const explorer = explorerCategoryBySlug(slug);
  if (explorer === null) {
    notFound();
  }

  return (
    <ChartDetailScreen
      chartId={chartId}
      values={values}
      links={{
        basePath: `/data/${explorer.slug}`,
        categoryHref: `/data/${explorer.slug}`,
        categoryLabel: explorer.label,
        breadcrumbRoots: [
          { label: "Data", href: "/data" },
          { label: explorer.label, href: `/data/${explorer.slug}` },
        ],
        expectedRegistryCategories: explorer.registryCategories,
      }}
    />
  );
}
