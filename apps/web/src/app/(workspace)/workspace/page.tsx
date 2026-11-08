import type { Metadata } from "next";
import { WorkspaceHome } from "@/features/workspace/home/WorkspaceHome";

export const metadata: Metadata = { title: "Workspace — NEAR Intelligence" };

export default function WorkspaceHomePage() {
  return <WorkspaceHome />;
}
