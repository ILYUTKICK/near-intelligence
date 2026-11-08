import type { Metadata } from "next";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { ResearchDocumentEditor } from "@/features/editor/workbench";

export const metadata: Metadata = { title: "Document — NEAR Intelligence" };

/**
 * Research editor route (INFORMATION_ARCHITECTURE:
 * /workspace/research/[documentId]; NI-039). The persisted, owner-checked
 * document (NI-023 client) is loaded into the three-pane editor — outline,
 * paper and context tools — with the P0 block operations. Saving itself
 * arrives with NI-040 and the editor says so honestly; invalid or
 * unsupported stored content opens the read-only recovery view instead of
 * being reinterpreted.
 */
export default async function ResearchDocumentPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return (
    <div className="w-full min-w-0">
      <Breadcrumbs
        items={[
          { label: "Workspace", href: "/workspace" },
          { label: "My Research", href: "/workspace/research" },
          { label: "Document" },
        ]}
      />
      <ResearchDocumentEditor key={documentId} documentId={documentId} />
    </div>
  );
}
