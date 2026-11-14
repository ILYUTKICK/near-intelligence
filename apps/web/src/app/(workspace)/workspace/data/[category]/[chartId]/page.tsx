import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ChartDetailScreen } from "@/features/charts/library/detail-screen";
import { explorerCategoryBySlug } from "@/features/charts/library/explorer-categories";

export const metadata: Metadata = { title: "Chart — NEAR Intelligence" };

type SearchValues = Record<string, string | string[] | undefined>;

/** Workspace category detail reuses the canonical selection/data screen in its own shell. */
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

  return ChartDetailScreen({
    chartId,
    values,
    links: {
      basePath: `/workspace/data/${explorer.slug}`,
      categoryHref: `/workspace/data/${explorer.slug}`,
      categoryLabel: explorer.label,
      breadcrumbRoots: [
        { label: "Data", href: "/workspace/data" },
        { label: explorer.label, href: `/workspace/data/${explorer.slug}` },
      ],
      expectedRegistryCategories: explorer.registryCategories,
    },
  });
}
