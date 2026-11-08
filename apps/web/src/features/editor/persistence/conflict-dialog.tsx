"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * 409 conflict recovery (NI-040). The API answers a stale save with 409
 * REVISION_CONFLICT including the server's current revision for the owned
 * document; EDITOR_SPECIFICATION: "On 409 stop autosaving, preserve local
 * version, show conflict options; never silently overwrite."
 *
 * The dialog is the explicit decision surface: it names what the server
 * holds and what the editor holds, and every destructive path is a labeled
 * button whose consequence is written next to it — overwrite only happens
 * after this explicit confirmation, never automatically. Safe paths
 * (download, new-document copy) are offered so recovery never requires
 * giving content up.
 */

export interface ConflictRecoveryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The revision this editor attempted to save against (stale). */
  localRevision: number;
  /** The server's current revision from the typed 409 (may be unknown). */
  serverRevision: number | null;
  /** One of the async actions (overwrite/reload/new-copy) is running. */
  busy: boolean;
  /** A failed recovery action, surfaced without losing the choices. */
  actionError: string | null;
  onOverwrite: () => void;
  onReloadServerVersion: () => void;
  onDownloadLocalCopy: () => void;
  onSaveAsNewCopy: () => void;
}

export function ConflictRecoveryDialog({
  open,
  onOpenChange,
  localRevision,
  serverRevision,
  busy,
  actionError,
  onOverwrite,
  onReloadServerVersion,
  onDownloadLocalCopy,
  onSaveAsNewCopy,
}: ConflictRecoveryDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="conflict-dialog" aria-describedby="conflict-dialog-description">
        <DialogTitle>This document changed in another session</DialogTitle>
        <DialogDescription id="conflict-dialog-description">
          Your editor holds revision {localRevision}. The server&apos;s current revision is{" "}
          {serverRevision !== null ? serverRevision : "unknown"} — another tab, device or session
          saved after this page loaded. Nothing was overwritten: your changes are kept in this
          editor and autosave stays paused until you choose below.
        </DialogDescription>

        {actionError ? (
          <p role="alert" data-testid="conflict-action-error" className="text-ui leading-ui text-danger font-medium mt-4">
            {actionError}
          </p>
        ) : null}

        <div className="mt-5 flex flex-col items-stretch gap-4">
          <div>
            <Button
              variant="destructive"
              onClick={onOverwrite}
              pending={busy}
              block
              data-testid="conflict-overwrite"
            >
              Overwrite server version
              {serverRevision !== null ? ` (revision ${serverRevision})` : ""}
            </Button>
            <p className="text-metadata leading-metadata text-text-secondary mt-1">
              Saves your local content as a new revision on top of the server&apos;s current
              revision. The other session&apos;s revision stays in the document&apos;s version
              history.
            </p>
          </div>

          <div>
            <Button
              variant="secondary"
              onClick={onReloadServerVersion}
              pending={busy}
              block
              data-testid="conflict-reload"
            >
              Load server version — discards your local edits
            </Button>
            <p className="text-metadata leading-metadata text-text-secondary mt-1">
              Replaces this editor with the server&apos;s current content. Download a local copy
              first if you want to keep your edits.
            </p>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <Button variant="secondary" onClick={onDownloadLocalCopy} block data-testid="conflict-download">
              Download local copy
            </Button>
            <Button
              variant="secondary"
              onClick={onSaveAsNewCopy}
              pending={busy}
              block
              data-testid="conflict-new-copy"
            >
              Save a copy as a new document
            </Button>
          </div>

          <Button variant="quiet" onClick={() => onOpenChange(false)} block data-testid="conflict-keep-editing">
            Keep editing — decide later
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
