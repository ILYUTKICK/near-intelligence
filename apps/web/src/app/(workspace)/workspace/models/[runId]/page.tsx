import type { Metadata } from "next";
import { ModelDetailScreen } from "@/features/models/detail-screen";

export const metadata: Metadata = { title: "Model run — NEAR Intelligence" };

export default function Page(props: { params: Promise<{ runId: string }>; }) {
  return ModelDetailScreen({ ...props, routePrefix: "/workspace" });
}
