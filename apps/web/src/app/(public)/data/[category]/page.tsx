import { DataCategoryScreen } from "@/features/charts/library/category-screen";
import type { SearchValues } from "@/features/charts/library/search-values";

export { generateMetadata } from "@/features/charts/library/category-screen";

export default function Page(props: { searchParams: Promise<SearchValues>; params: Promise<{ category: string }>;  }) {
  return DataCategoryScreen({ ...props, routePrefix: "" });
}
