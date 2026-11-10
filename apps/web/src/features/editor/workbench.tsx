"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/data-state/Skeleton";

import { DocumentApiError, getDocument } from "@/features/documents/list/documents-api";
import { CanonicalDocumentError, validateCanonicalDocument, CANONICAL_SCHEMA_VERSION } from "./canonical";
import { downloadJson } from "./persistence/download";
import { clearStoredDraft } from "./persistence/draft";
import { useSessionOwnerGuard } from "./persistence/session-owner";
import { EditorShell } from "./editor-shell";

/**
 * Research editor route data layer (NI-039). The document comes from the
 * NI-023 owner-checked client (GET /api/documents/{id}, same-origin session;
 * ownership is re-verified server-side on every call). Content that is not a
 * valid canonical editor document is NEVER rendered: unsupported schema
 * versions and validation failures open an honest read-only recovery view
 * with the raw content available for download (EDITOR_SPECIFICATION
 * "unsupported versions open read-only with a recovery download and
 * actionable message"; "Never reinterpret unknown nodes and discard their
 * content").
 */

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; title: string; revision: number; updatedAt: string; currentVersionId: string | null; content: ReturnType<typeof validateCanonicalDocument> }
  | { kind: "not-found" }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string }
  | { kind: "recovery"; title: string; reason: string; path: string; rawContent: unknown };

export function RecoveryView({
  documentId,
  title,
  reason,
  path,
  rawContent,
}: {
  documentId: string;
  title: string;
  reason: string;
  path: string;
  rawContent: unknown;
}) {
  return (
    <div className="mt-6" data-testid="recovery-view">
      <p role="alert" className="text-ui leading-ui text-danger font-medium">
        This document opens read-only: {reason} ({path}).
      </p>
      <p className="text-body leading-body text-text-secondary mt-2">
        The editor never reinterprets or discards content it cannot represent. The document&apos;s
        stored content is untouched — download it below or contact the operator with the reason
        shown above.
      </p>
      <button
        type="button"
        data-testid="download-content"
        onClick={() => downloadJson(rawContent, `document-content-${documentId}.json`)}
        className="mt-3 inline-flex min-h-11 items-center rounded-control border border-control-border bg-surface px-4 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      >
        Download stored content
      </button>
      <p className="text-metadata leading-metadata text-text-secondary mt-4">
        Document: {title}
      </p>
    </div>
  );
}

export function ResearchDocumentEditor({ documentId }: { documentId: string }) {
  const [state, setState] = useState<LoadState>(() =>
    UUID_PATTERN.test(documentId) ? { kind: "loading" } : { kind: "not-found" },
  );
  const [reloadKey, setReloadKey] = useState(0);
  // NI-062: the loaded content belongs to the first verified session subject.
  // A cross-tab account switch (a verified DIFFERENT subject) must not leave
  // the previous principal's document in any buffer of this tab.
  const guard = useSessionOwnerGuard();
  useEffect(() => guard.onChanged(() => {
    clearStoredDraft(documentId);
    setState({ kind: "unauthorized" });
  }), [guard, documentId]);

  useEffect(() => {
    if (!UUID_PATTERN.test(documentId)) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const document = await getDocument(documentId);
        if (cancelled) {
          return;
        }
        const rawContent = document.content;
        if (rawContent.schema_version !== CANONICAL_SCHEMA_VERSION) {
          setState({
            kind: "recovery",
            title: document.title,
            reason: `the stored schema version ${String(rawContent.schema_version)} is not supported by this editor (version ${CANONICAL_SCHEMA_VERSION} only)`,
            path: "document.schema_version",
            rawContent,
          });
          return;
        }
        try {
          const validated = validateCanonicalDocument(rawContent);
          setState({
            kind: "ready",
            title: document.title,
            revision: document.revision,
            updatedAt: document.updated_at,
            currentVersionId: document.current_version_id,
            content: validated,
          });
        } catch (error) {
          const issue =
            error instanceof CanonicalDocumentError && error.issues[0]
              ? error.issues[0]
              : { path: "document", reason: "invalid_value" };
          setState({
            kind: "recovery",
            title: document.title,
            reason: "the stored content failed the canonical document validation",
            path: `${issue.path}: ${issue.reason}`,
            rawContent,
          });
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
            message: "The document could not be loaded. Nothing was changed — try again.",
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
        <Skeleton className="h-64 w-full" />
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
          Your session has ended or changed. Sign in again to open your documents.
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

  if (state.kind === "recovery") {
    return (
      <RecoveryView
        documentId={documentId}
        title={state.title}
        reason={state.reason}
        path={state.path}
        rawContent={state.rawContent}
      />
    );
  }

  return (
    <EditorShell
      documentId={documentId}
      title={state.title}
      revision={state.revision}
      updatedAt={state.updatedAt}
      currentVersionId={state.currentVersionId}
      content={state.content}
      sessionOwner={guard.owner}
      verifySessionOwner={guard.verify}
    />
  );
}
