"use client";

import { EditorContent, useEditor } from "@tiptap/react";
import Link from "next/link";
import { useCallback } from "react";
import type { components } from "@near-intelligence/shared-types";
import { LoadingPanel } from "@/components/data-state/DataState";
import { PageIntro } from "@/components/layout/PageIntro";
import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { useOwnedData } from "@/features/charts/saved/use-owned-data";
import { formatUpdated } from "@/features/documents/list/format";
import { HistoricalRevisionContext } from "./blocks/chart-context";
import { CANONICAL_SCHEMA_VERSION, validateCanonicalDocument, type CanonicalDocument } from "./canonical";
import { DOCUMENT_EXTENSIONS } from "./extensions";
import { getRevision, listRevisions } from "./revision-api";
import { canonicalToTiptapDoc } from "./serialize";
import { RecoveryView } from "./workbench";

const linkClass = "text-ui underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

export function ResearchRevisions({ documentId, versionId, cursor }: {
  documentId: string; versionId?: string; cursor?: string;
}) {
  const load = useCallback(async (signal: AbortSignal) => versionId
    ? { kind: "revision" as const, revision: await getRevision(documentId, versionId, signal) }
    : { kind: "history" as const, page: await listRevisions(documentId, cursor, signal) },
  [documentId, versionId, cursor]);
  const { data, error, loading, reload, signal } = useOwnedData(load, "research revisions");
  const editorHref = `/workspace/research/${documentId}`;
  const historyHref = `${editorHref}/versions`;

  return <div className="min-w-0 space-y-4">
    <PageIntro compact eyebrow="Revision history"
      title={versionId ? data?.kind === "revision" ? `Revision ${data.revision.revision}` : "Saved revision" : "A record of your reasoning."}
      description={versionId ? "This read-only revision retains its saved evidence." : "Saved revisions retain the data and chart context seen at that moment."}
      action={<nav aria-label="Research revision navigation" className="flex flex-wrap gap-2">
        {versionId ? <Button asChild variant="quiet"><Link href={historyHref} prefetch={false}>Revision history</Link></Button> : null}
        <Button asChild variant="secondary"><Link href={editorHref} prefetch={false}>Back to editor</Link></Button>
      </nav>}
    />
    {loading ? <LoadingPanel label="Loading saved research" /> : null}
    {error ? <div className="paper-panel space-y-3 p-6">
      <p role="alert">{error}</p>
      <Button variant="secondary" onClick={reload}>Try again</Button>
    </div> : null}
    {data?.kind === "history" ? <>
      <ol className="paper-panel divide-y divide-border">
        {data.page.items.map((revision, index) => (
          <li key={revision.id} className="flex flex-wrap items-center gap-3 p-5">
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-sage text-accent"><ProductIcon name="document" /></span>
            <div className="min-w-0 flex-1">
              <p className="eyebrow">{!cursor && index === 0 ? "Latest saved" : "Read-only revision"}</p>
              <time dateTime={revision.created_at} className="mt-1 block text-ui text-text-secondary">{formatUpdated(revision.created_at)} UTC</time>
            </div>
            <Button asChild variant="secondary">
              <Link href={`${historyHref}?version=${revision.id}`} prefetch={false}>Revision {revision.revision} <ProductIcon name="arrow" /></Link>
            </Button>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-4">
        {cursor ? <Link href={historyHref} prefetch={false} className={linkClass}>Newest revisions</Link> : null}
        {data.page.next_cursor ? <Link href={`${historyHref}?${new URLSearchParams({ cursor: data.page.next_cursor })}`}
          prefetch={false} className={linkClass}>Older revisions</Link> : null}
      </div>
    </> : null}
    {data?.kind === "revision" && signal ? <SavedRevision revision={data.revision} sessionSignal={signal} /> : null}
  </div>;
}

function SavedRevision({ revision, sessionSignal }: {
  revision: components["schemas"]["VersionDetailResponse"]; sessionSignal: AbortSignal;
}) {
  let content: CanonicalDocument;
  try {
    if (revision.schema_version !== CANONICAL_SCHEMA_VERSION) throw new Error("Unsupported stored schema version");
    content = validateCanonicalDocument(revision.content);
  } catch {
    return <RecoveryView documentId={revision.id} title={`Revision ${revision.revision}`} reason="the stored revision could not be displayed"
      path={`schema version ${revision.schema_version}`} rawContent={revision.content} />;
  }

  return <>
    <p className="text-metadata text-text-secondary">Read-only · Saved <time dateTime={revision.created_at}>{revision.created_at}</time></p>
    <p className="break-all text-metadata text-text-secondary">Content hash {revision.content_sha256}</p>
    <HistoricalRevisionContext value={{ documentId: revision.document_id, versionId: revision.id, sessionSignal }}>
      <SavedPaper content={content} />
    </HistoricalRevisionContext>
  </>;
}

function SavedPaper({ content }: { content: CanonicalDocument }) {
  const editor = useEditor({ extensions: DOCUMENT_EXTENSIONS, content: canonicalToTiptapDoc(content),
    editable: false, immediatelyRender: false,
    editorProps: { attributes: { class: "editor-paper", role: "document", "aria-label": "Saved revision content" } } });
  return <article aria-label="Saved research" className="paper-panel min-w-0 p-7">
    <EditorContent editor={editor} />
  </article>;
}
