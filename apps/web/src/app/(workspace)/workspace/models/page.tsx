import type { Metadata } from "next";
import { ModelCatalogScreen } from "@/features/models/catalog-screen";

export const metadata: Metadata = { title: "Models — NEAR Intelligence" };

export default function Page(props: { searchParams: Promise<Record<string, string | string[] | undefined>>; }) {
  return ModelCatalogScreen({ ...props, routePrefix: "/workspace" });
}
