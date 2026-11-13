import type { Metadata } from "next";
import { ChartLibraryScreen } from "@/features/charts/library/library-screen";
import type { SearchValues } from "@/features/charts/library/search-values";

export const metadata: Metadata = { title: "Chart library — NEAR Intelligence" };

export default function Page(props: { searchParams: Promise<SearchValues>; }) {
  return ChartLibraryScreen({ ...props, routePrefix: "" });
}
