import type { Metadata } from "next";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { DocumentStubView } from "@/features/documents/list/DocumentStubView";

export const metadata: Metadata = { title: "Document — NEAR Intelligence" };

/**
 * Persisted document route (INFORMATION_ARCHITECTURE:
 * /workspace/research/[documentId]). This is the canonical destination of a
 * created document and of every list link. The editor surface itself is
 * NI-039/NI-040; until then the route shows the persisted, owner-checked
 * document metadata and says so honestly.
 */
export default async function ResearchDocumentPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return (
    <div className="max-w-(--width-prose)">
      <Breadcrumbs
        items={[
          { label: "Workspace", href: "/workspace" },
          { label: "My Research", href: "/workspace/research" },
          { label: "Document" },
        ]}
      />
      <DocumentStubView key={documentId} documentId={documentId} />
    </div>
  );
}
