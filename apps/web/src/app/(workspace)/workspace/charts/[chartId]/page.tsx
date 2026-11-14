import { ChartDetailScreen } from "@/features/charts/library/detail-screen";
import type { SearchValues } from "@/features/charts/library/search-values";

export default async function Page({ params, searchParams }: {
  params: Promise<{ chartId: string }>;
  searchParams: Promise<SearchValues>;
}) {
  const [{ chartId }, values] = await Promise.all([params, searchParams]);
  return ChartDetailScreen({ chartId, values, links: {
    basePath: "/workspace/charts",
    breadcrumbRoots: [{ label: "Charts", href: "/workspace/charts" }],
  } });
}
