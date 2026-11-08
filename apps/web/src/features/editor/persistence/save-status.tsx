"use client";

import { Button } from "@/components/ui/button";

import type { SaveStatus } from "./save-coordinator";

/**
 * Truthful save status line (NI-040, EDITOR_SPECIFICATION: "truthful saved
 * status"). Every state names what the user actually has: acknowledged
 * (with the saved-at time), unsaved with autosave scheduled, saving, held
 * offline (queue is honest — no fabricated success), conflict (autosave
 * paused), or a typed error with the content retained. Times render in UTC
 * like the rest of the product (NI-023 convention), so the label matches the
 * server's `updated_at` semantics.
 */

const UTC_TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  timeZone: "UTC",
});

export function formatSavedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return `${UTC_TIME_FORMAT.format(date)} UTC`;
}

export interface SaveStatusBarProps {
  status: SaveStatus;
  onSave: () => void;
  onRetry: () => void;
  onOpenConflict: () => void;
  onDownloadCopy: () => void;
}

export function SaveStatusBar({
  status,
  onSave,
  onRetry,
  onOpenConflict,
  onDownloadCopy,
}: SaveStatusBarProps) {
  const saving = status.kind === "saving";
  const saveDisabled = status.kind === "clean" || saving || status.kind === "conflict";

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2" data-testid="save-status-bar">
      <Button
        variant="secondary"
        onClick={onSave}
        disabled={saveDisabled}
        pending={saving}
        aria-label="Save now"
        data-testid="save-now"
      >
        Save
      </Button>
      {status.kind === "clean" ? (
        <p role="status" data-testid="save-status" className="text-ui leading-ui text-text-secondary">
          {status.savedAt
            ? `All changes saved at ${formatSavedAt(status.savedAt)} · Revision ${status.revision}`
            : `No unsaved changes · Revision ${status.revision}`}
        </p>
      ) : null}
      {status.kind === "dirty" ? (
        <p
          role="status"
          data-testid="save-status"
          className="text-ui leading-ui text-warning font-medium"
        >
          Unsaved changes — autosave runs after 1s idle (at most 5s)
        </p>
      ) : null}
      {status.kind === "saving" ? (
        <p
          role="status"
          data-testid="save-status"
          className="text-ui leading-ui text-warning font-medium"
        >
          Saving…
        </p>
      ) : null}
      {status.kind === "queued" ? (
        <>
          <p
            role="status"
            data-testid="save-status"
            className="text-ui leading-ui text-warning font-medium"
          >
            Offline — saving is paused. Your changes are held in this tab and will save when the
            connection returns; nothing was lost.
          </p>
          <Button variant="secondary" onClick={onRetry} data-testid="retry-queued">
            Retry now
          </Button>
        </>
      ) : null}
      {status.kind === "conflict" ? (
        <>
          <p
            role="status"
            data-testid="save-status"
            className="text-ui leading-ui text-warning font-medium"
          >
            Saving is paused — this document changed in another session
            {status.serverRevision !== null ? ` (server revision ${status.serverRevision})` : ""}.
            Your edits are kept here. Review the conflict to continue.
          </p>
          <Button variant="secondary" onClick={onOpenConflict} data-testid="review-conflict">
            Review conflict
          </Button>
        </>
      ) : null}
      {status.kind === "error" ? (
        <>
          <p
            role="alert"
            data-testid="save-status"
            className="text-ui leading-ui text-danger font-medium"
          >
            {status.message}
          </p>
          {status.retryable ? (
            <Button variant="secondary" onClick={onRetry} data-testid="retry-save">
              Retry save
            </Button>
          ) : null}
          <Button variant="secondary" onClick={onDownloadCopy} data-testid="download-copy">
            Download local copy
          </Button>
        </>
      ) : null}
    </div>
  );
}
