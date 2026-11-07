"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/data-state/Skeleton";

import { getDocument, DocumentApiError } from "./documents-api";
import { formatUpdated } from "./format";

/**
 * Persisted-document view for /workspace/research/[documentId] (NI-023).
 *
 * The research editor itself is NI-039/NI-040; until it lands this route
 * shows the persisted truth from GET /api/documents/{id} — owner-checked,
 * so an absent or foreign document is the same honest not-found state — and
 * states plainly that the editing surface does not exist yet. No content is
 * rendered as a fake editor and no sample document is ever substituted.
 */

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; document: Awaited<ReturnType<typeof getDocument>> }
  | { kind: "not-found" }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string };

export function DocumentStubView({ documentId }: { documentId: string }) {
  // The initial state derives from the id itself: a malformed id is honest
  // not-found without a request. The page keys this view by documentId, so a
  // navigation between documents remounts with fresh state.
  const [state, setState] = useState<LoadState>(() =>
    UUID_PATTERN.test(documentId) ? { kind: "loading" } : { kind: "not-found" },
  );
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!UUID_PATTERN.test(documentId)) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const document = await getDocument(documentId);
        if (!cancelled) {
          setState({ kind: "ready", document });
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error instanceof DocumentApiError && error.status === 404) {
          setState({ kind: "not-found" });
        } else if (error instanceof DocumentApiError && error.status === 401) {
          setState({ kind: "unauthorized" });
        } else {
          setState({
            kind: "error",
            message:
              "The document could not be loaded. Nothing was changed — try again.",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId, reloadKey]);

  if (state.kind === "loading") {
    return (
      <div className="mt-6 flex flex-col gap-3" role="status" aria-label="Loading document">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (state.kind === "not-found") {
    return (
      <div className="mt-6">
        <p role="alert" className="text-ui leading-ui text-danger font-medium">
          This document does not exist or does not belong to your account.
        </p>
        <p className="text-body leading-body text-text-secondary mt-2">
          <Link
            href="/workspace/research"
            className="underline underline-offset-2 hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Back to My Research
          </Link>
        </p>
      </div>
    );
  }

  if (state.kind === "unauthorized") {
    return (
      <div className="mt-6">
        <p role="alert" className="text-ui leading-ui text-danger font-medium">
          Your session has expired. Sign in again to open your documents.
        </p>
        <p className="text-body leading-body text-text-secondary mt-2">
          <Link
            href="/login"
            className="underline underline-offset-2 hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Sign in
          </Link>
        </p>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="mt-6">
        <p role="alert" className="text-ui leading-ui text-danger font-medium">
          {state.message}
        </p>
        <button
          type="button"
          onClick={() => setReloadKey((key) => key + 1)}
          className="mt-3 rounded-control border border-control-border bg-surface px-4 text-ui leading-ui text-text h-11 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          Try again
        </button>
      </div>
    );
  }

  const { document } = state;
  return (
    <div className="mt-6">
      <h1 className="font-serif text-title leading-title">{document.title}</h1>
      <p className="text-metadata leading-metadata text-text-secondary mt-2">
        Updated <time dateTime={document.updated_at}>{formatUpdated(document.updated_at)}</time>
        {" · "}Revision {document.revision} · Schema version {document.schema_version}
      </p>
      <div
        role="note"
        aria-label="Editor availability"
        className="mt-6 rounded-surface border border-border bg-surface-muted p-6"
      >
        <p className="font-ui text-ui leading-ui font-medium text-text">
          The editor is not here yet
        </p>
        <p className="text-body leading-body text-text-secondary mt-2">
          This document and all of its revisions are persisted on the server. The writing
          editor arrives with the next workspace tasks (NI-039/NI-040); until it exists there
          is nothing to edit on this page — and nothing that can be lost.
        </p>
      </div>
      <p className="text-body leading-body text-text-secondary mt-6">
        <Link
          href="/workspace/research"
          className="underline underline-offset-2 hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          Back to My Research
        </Link>
      </p>
    </div>
  );
}
