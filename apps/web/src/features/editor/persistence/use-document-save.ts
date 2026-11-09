"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { SaveCoordinator, type SaveStatus } from "./save-coordinator";
import { clearStoredDraft, readStoredDraft, writeStoredDraft } from "./draft";
import { saveRevision, type SaveRequestBody } from "./save-transport";

import {
  CANONICAL_SCHEMA_VERSION,
  CanonicalDocumentError,
  validateCanonicalDocument,
} from "../canonical";

/**
 * React binding for the save coordinator (NI-040, card: "document query
 * hooks"). Owns the coordinator instance, mirrors its status into render
 * state, persists the recovery draft on every capture, warns before losing
 * unacknowledged content on unload, and retries the retained attempt when
 * the browser reports the connection back (`online` event — offline/
 * reconnect). The draft is read ONCE on mount and offered to the shell;
 * restoring or discarding it is always an explicit user decision.
 */

export interface DraftOffer {
  baseRevision: number;
  capturedAt: string;
  body: SaveRequestBody;
  /** Set when the stored content no longer passes canonical validation. */
  invalidReason: string | null;
}

export interface DocumentSaveController {
  status: SaveStatus;
  revision: number;
  /** Adopts the editor content as the acknowledged baseline (initial load). */
  adoptBaseline(revision: number): void;
  /** Editor update signal — schedules autosave when unacknowledged edits exist. */
  markChanged(): void;
  saveNow(): void;
  retry(): void;
  /** Explicit conflict resolution (dialog action) against the server revision. */
  overwriteConflict(revision: number): void;
  /** Adopts the editor content as the acknowledged server state. */
  adoptServerState(revision: number, savedAt?: string): void;
  isClean(expectedRevision: number): boolean;
  /** Captures the current editor content for download / new-copy actions. */
  captureLocal(): SaveRequestBody;
  draft: DraftOffer | null;
  restoreDraft(): void;
  discardDraft(): void;
}

export interface UseDocumentSaveOptions {
  documentId: string;
  initialRevision: number;
  /** Captures the editor state; kept current through the coordinator. */
  capture: () => SaveRequestBody;
}

/**
 * A draft is only restorable when its content still passes the canonical
 * validator (same rule as persisted content — never reinterpret unknown
 * nodes). An invalid draft is offered with "discard" only, plus the reason.
 */
function describeDraftValidity(body: SaveRequestBody): string | null {
  if (body.schema_version !== CANONICAL_SCHEMA_VERSION) {
    return `the draft uses schema version ${String(body.schema_version)}, this editor supports version ${CANONICAL_SCHEMA_VERSION} only`;
  }
  try {
    validateCanonicalDocument(body.content);
    return null;
  } catch (error) {
    const issue =
      error instanceof CanonicalDocumentError && error.issues[0]
        ? error.issues[0]
        : { path: "content", reason: "invalid_value" };
    return `the draft failed the canonical validation (${issue.path}: ${issue.reason})`;
  }
}

export function useDocumentSave(options: UseDocumentSaveOptions): DocumentSaveController {
  const { documentId, initialRevision } = options;

  // One coordinator per mount (stable identity; construction is side-effect
  // free). The capture is kept current through setCapture (below).
  const [coordinator] = useState(
    () =>
      new SaveCoordinator(documentId, initialRevision, {
        transport: (attempt) => saveRevision(attempt),
        capture: options.capture,
        onCapture: (body, revision) => {
          writeStoredDraft(documentId, {
            baseRevision: revision,
            capturedAt: new Date().toISOString(),
            body,
          });
        },
      }),
  );

  useEffect(() => {
    coordinator.setCapture(options.capture);
  });

  // The draft offer is read exactly once per mount, BEFORE the coordinator
  // can clear anything: the initial adoptBaseline (clean) must not destroy
  // the recovery offer of an interrupted session.
  const [draft, setDraft] = useState<DraftOffer | null>(() => {
    const stored = readStoredDraft(documentId);
    if (stored === null) {
      return null;
    }
    return {
      baseRevision: stored.baseRevision,
      capturedAt: stored.capturedAt,
      body: stored.body,
      invalidReason: describeDraftValidity(stored.body),
    };
  });

  const [status, setStatus] = useState<SaveStatus>(coordinator.getStatus());
  const statusRef = useRef(status);
  useEffect(() => {
    statusRef.current = status;
  });

  useEffect(() => {
    let previousKind: SaveStatus["kind"] = coordinator.getStatus().kind;
    const unsubscribe = coordinator.onStatus((next) => {
      setStatus(next);
      // A transition INTO clean from an unacknowledged state means the server
      // now holds the content (save acknowledged) or the user explicitly
      // adopted the server state (conflict reload): the draft has served its
      // purpose. The mount-time baseline adoption (clean → clean) must NOT
      // clear the stored draft — it carries an interrupted session's offer.
      if (next.kind === "clean" && previousKind !== "clean") {
        clearStoredDraft(documentId);
      }
      previousKind = next.kind;
    });
    return () => {
      // Unsubscribe only: React Strict Mode re-runs effects on the same
      // instance, and the coordinator turns inert on its own once nothing
      // listens (a pending autosave timer that outlives the editor skips
      // instead of firing a stray request).
      unsubscribe();
    };
  }, [coordinator, documentId]);

  // Offline/reconnect: a transport failure retains the attempt; the browser's
  // `online` event retries it with the SAME idempotency key.
  useEffect(() => {
    const onOnline = () => {
      coordinator.retry();
    };
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("online", onOnline);
    };
  }, [coordinator]);

  // Unload warning: never close a tab with unacknowledged content without
  // asking (card testing requirement). The freshest content is written to the
  // draft first (best effort) so a confirmed leave is still recoverable.
  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!coordinator.hasUnsavedWork()) {
        return;
      }
      try {
        const body = coordinator.captureLocal();
        writeStoredDraft(documentId, {
          baseRevision: statusRef.current.revision,
          capturedAt: new Date().toISOString(),
          body,
        });
      } catch {
        // The editor state could not be serialized; the last captured draft
        // (if any) remains the recovery point.
      }
      event.preventDefault();
      // Legacy Chrome/Edge require returnValue to actually block the close.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [coordinator, documentId]);

  const adoptBaseline = useCallback(
    (revision: number) => {
      coordinator.adoptBaseline(revision);
    },
    [coordinator],
  );

  const markChanged = useCallback(() => {
    coordinator.markChanged();
  }, [coordinator]);

  const saveNow = useCallback(() => {
    coordinator.saveNow();
  }, [coordinator]);

  const retry = useCallback(() => {
    coordinator.retry();
  }, [coordinator]);

  const overwriteConflict = useCallback(
    (revision: number) => {
      coordinator.overwriteConflict(revision);
    },
    [coordinator],
  );

  const adoptServerState = useCallback(
    (revision: number, savedAt?: string) => {
      coordinator.adoptServerState(revision, savedAt);
      setDraft(null);
    },
    [coordinator],
  );
  const isClean = useCallback((expectedRevision: number) => {
    const status = coordinator.getStatus();
    return status.kind === "clean" && status.revision === expectedRevision;
  }, [coordinator]);

  const captureLocal = useCallback(() => coordinator.captureLocal(), [coordinator]);

  const restoreDraft = useCallback(() => {
    // The offer goes away; the STORED draft stays until the first post-
    // restore capture overwrites it (same content) or a save acknowledges —
    // closing the tab within the debounce window must not lose it. The shell
    // replaces the editor content with draft.body.content; the editor's
    // update then marks the coordinator dirty against the loaded revision.
    setDraft(null);
  }, []);

  const discardDraft = useCallback(() => {
    setDraft(null);
    clearStoredDraft(documentId);
  }, [documentId]);

  return useMemo(
    () => ({
      status,
      revision: status.revision,
      adoptBaseline,
      markChanged,
      saveNow,
      retry,
      overwriteConflict,
      adoptServerState,
      isClean,
      captureLocal,
      draft,
      restoreDraft,
      discardDraft,
    }),
    [
      status,
      adoptBaseline,
      markChanged,
      saveNow,
      retry,
      overwriteConflict,
      adoptServerState,
      isClean,
      captureLocal,
      draft,
      restoreDraft,
      discardDraft,
    ],
  );
}
