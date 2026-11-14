import type { Metadata } from "next";
import { DataExplorerScreen } from "@/features/charts/library/explorer-screen";
import type { SearchValues } from "@/features/charts/library/search-values";

export const metadata: Metadata = { title: "Data explorer — NEAR Intelligence" };

export default function Page(props: { searchParams: Promise<SearchValues>; }) {
  return DataExplorerScreen({ ...props, routePrefix: "" });
}
