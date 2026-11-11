import type { Metadata } from "next";

import { ChartDetailScreen } from "@/features/charts/library/detail-screen";
import type { SearchValues } from "@/features/charts/library/search-values";

export const metadata: Metadata = { title: "Chart — NEAR Intelligence" };

export default async function ChartDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ chartId: string }>;
  searchParams: Promise<SearchValues>;
}) {
  const [{ chartId }, values] = await Promise.all([params, searchParams]);
  return ChartDetailScreen({
    chartId,
    values,
    links: {
      basePath: "/charts",
      breadcrumbRoots: [{ label: "Charts", href: "/charts" }],
    },
  });
}
