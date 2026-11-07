"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { createDocument, deleteDocument, DocumentApiError, renameDocument } from "./documents-api";
import { DOCUMENT_TITLE_MAX_LENGTH, type DocumentResponse, type DocumentSummary } from "./documents-schema";

/**
 * Create/rename/delete dialogs (NI-023). Pending blocks a second submit;
 * validation and transport errors keep the dialog open with the typed values
 * retained. Revision conflicts (409) are reported to the list so the item
 * stays visible with an error and the refreshed current revision — the dialog
 * never silently retries or overwrites.
 */

/** Client-generated UUID Idempotency-Key (API contract: POST /documents). */
function newIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID: a v4-shaped unique
  // string. Idempotency keys need uniqueness, not cryptographic strength.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    const value = character === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function describeMutationError(error: unknown, fallback: string): string {
  if (error instanceof DocumentApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again and retry — your input is kept.";
    }
    return error.message || fallback;
  }
  return fallback;
}

export function CreateDocumentDialog({
  onOpenChange,
  onCreated,
}: {
  onOpenChange: (open: boolean) => void;
  /** Called after the API confirms the persisted document (201). */
  onCreated: (document: DocumentResponse) => void;
}) {
  const router = useRouter();
  // State initialises fresh per mount: the list renders this dialog only
  // while it is open, so no open-transition reset effect is needed.
  const [title, setTitle] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) {
      return;
    }
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Give the document a title before creating it.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const document = await createDocument({ title: trimmed, idempotencyKey: newIdempotencyKey() });
      onOpenChange(false);
      onCreated(document);
      // The persisted editor route is the canonical destination of a created
      // document (INFORMATION_ARCHITECTURE: /workspace/research/[documentId]).
      router.push(`/workspace/research/${document.id}`);
    } catch (submitError) {
      setError(describeMutationError(submitError, "The document could not be created. Your title is kept."));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>New research document</DialogTitle>
        <DialogDescription>
          Creates a private document owned by your account. The first empty revision is saved
          server-side immediately; you will continue in the editor.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="create-document-title">Title</Label>
            <Input
              id="create-document-title"
              value={title}
              maxLength={DOCUMENT_TITLE_MAX_LENGTH}
              required
              autoComplete="off"
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          {error ? (
            <p role="alert" className="text-ui leading-ui text-danger font-medium">
              {error}
            </p>
          ) : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" pending={pending}>
              Create document
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function RenameDocumentDialog({
  target,
  onOpenChange,
  onRenamed,
  onRevisionConflict,
}: {
  target: DocumentSummary;
  onOpenChange: (open: boolean) => void;
  onRenamed: (updated: DocumentSummary) => void;
  onRevisionConflict: (documentId: string) => void;
}) {
  const [title, setTitle] = useState(target.title);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) {
      return;
    }
    const trimmed = title.trim();
    if (!trimmed) {
      setError("The title cannot be empty.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      // If-Match carries the revision this dialog was opened with; a stale
      // value is the server's 409, reported to the list — never overwritten.
      const updated = await renameDocument({
        documentId: target.id,
        title: trimmed,
        revision: target.revision,
      });
      onOpenChange(false);
      onRenamed(updated);
    } catch (submitError) {
      if (submitError instanceof DocumentApiError && submitError.status === 409) {
        onOpenChange(false);
        onRevisionConflict(target.id);
        return;
      }
      setError(describeMutationError(submitError, "The document could not be renamed. Your title is kept."));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Rename document</DialogTitle>
        <DialogDescription>
          Renaming creates a new immutable revision with the same content.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rename-document-title">Title</Label>
            <Input
              id="rename-document-title"
              value={title}
              maxLength={DOCUMENT_TITLE_MAX_LENGTH}
              required
              autoComplete="off"
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          {error ? (
            <p role="alert" className="text-ui leading-ui text-danger font-medium">
              {error}
            </p>
          ) : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" pending={pending}>
              Save new title
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function DeleteDocumentDialog({
  target,
  onOpenChange,
  onDeleted,
  onRevisionConflict,
}: {
  target: DocumentSummary;
  onOpenChange: (open: boolean) => void;
  onDeleted: (deletedId: string) => void;
  onRevisionConflict: (documentId: string) => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      await deleteDocument({ documentId: target.id, revision: target.revision });
      onOpenChange(false);
      onDeleted(target.id);
    } catch (submitError) {
      if (submitError instanceof DocumentApiError && submitError.status === 409) {
        onOpenChange(false);
        onRevisionConflict(target.id);
        return;
      }
      setError(describeMutationError(submitError, "The document could not be deleted. Nothing was removed."));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Delete document</DialogTitle>
        <DialogDescription>
          Delete “{target.title}”? This permanently removes the document with all of its
          revisions. Shared scientific data — datasets, metrics, model artifacts — is not
          affected.
        </DialogDescription>
        {error ? (
          <p role="alert" className="text-ui leading-ui text-danger font-medium mt-4">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap justify-end gap-2 mt-4">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Keep document
          </Button>
          <Button type="button" variant="destructive" pending={pending} onClick={handleConfirm}>
            Delete permanently
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
