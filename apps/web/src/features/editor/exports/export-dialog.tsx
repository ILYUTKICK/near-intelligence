"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";

import { downloadBlob } from "@/features/editor/persistence/download";
import {
  createExport,
  downloadExportBundle,
  ExportApiError,
  newExportIdempotencyKey,
  pollExport,
  type ExportJob,
} from "./export-api";

/**
 * Export lifecycle for one acknowledged revision (NI-058). The dialog POSTs
 * the export job, polls its typed state and streams the ZIP when the bundle
 * is ready — every terminal state is shown honestly:
 *
 * - `processing` while the job is queued/running on the server (bounded
 *   polling: the dialog never pretends an export finished);
 * - `ready` after the automatic download, with a manual re-download;
 * - `failed` with the server's typed error code (the job stays failed —
 *   retrying means creating a NEW export, never a silent re-run);
 * - `expired` when the artifact TTL passed before the download;
 * - typed transport/HTTP errors (404 owner denial, 401 expired session).
 *
 * The export always targets the acknowledged revision passed in — unsaved
 * local edits are never exported (the trigger is disabled while the editor
 * is dirty), so the bundle matches what the server holds, not what this
 * tab holds.
 */

const POLL_INTERVAL_MS = 1000;
const MAX_POLL_ATTEMPTS = 120;

type Phase =
  | "starting"
  | "processing"
  | "ready"
  | "failed"
  | "expired"
  | "slow"
  | "error";

export interface ExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  documentId: string;
  /** The acknowledged revision to export (the server validates it is current). */
  versionId: string;
  onAnnounce?: (message: string) => void;
}

function describeError(error: unknown): string {
  if (error instanceof ExportApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again and retry — nothing was exported yet.";
    }
    if (error.status === 404) {
      return "The document or export does not exist for your account.";
    }
    if (error.code === "REVISION_NOT_ACKNOWLEDGED") {
      return "This revision is no longer the document's current revision. Save or reload, then export the current revision.";
    }
    return error.message;
  }
  return "The export could not be started. Try again.";
}

export function ExportDialog({
  open,
  onOpenChange,
  documentId,
  versionId,
  onAnnounce,
}: ExportDialogProps) {
  const [phase, setPhase] = useState<Phase>("starting");
  const [job, setJob] = useState<ExportJob | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const runRef = useRef(0);

  const deliver = useCallback(async (finished: ExportJob) => {
    setJob(finished);
    try {
      const blob = await downloadExportBundle(finished.document_id, finished.id,
        new AbortController().signal);
      downloadBlob(blob, `near-export-${finished.id}.zip`);
      setPhase("ready");
    } catch (error) {
      if (error instanceof ExportApiError
        && (error.status === 410 || error.code === "EXPORT_EXPIRED")) {
        setPhase("expired");
        return;
      }
      throw error;
    }
  }, []);

  const run = useCallback((signalRun: number) => {
    const controller = new AbortController();
    return (async () => {
      try {
        setPhase("starting");
        setErrorText(null);
        setJob(null);
        const created = await createExport(documentId, versionId,
          newExportIdempotencyKey(), controller.signal);
        if (runRef.current !== signalRun) return;
        if (created.status === "expired") {
          setJob(created);
          setPhase("expired");
          return;
        }
        if (created.status === "failed") {
          setJob(created);
          setPhase("failed");
          return;
        }
        if (created.status === "succeeded") {
          // A replayed already-finished job downloads immediately too — the
          // ready state never claims a download that did not happen.
          await deliver(created);
          return;
        }
        setJob(created);
        setPhase("processing");
        for (let attempt = 1; attempt <= MAX_POLL_ATTEMPTS; attempt += 1) {
          await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          if (runRef.current !== signalRun) return;
          const polled = await pollExport(documentId, created.id, controller.signal);
          if (runRef.current !== signalRun) return;
          if (polled.status === "succeeded") {
            await deliver(polled);
            return;
          }
          setJob(polled);
          if (polled.status === "failed") {
            setPhase("failed");
            return;
          }
          if (polled.status === "expired") {
            setPhase("expired");
            return;
          }
        }
        setPhase("slow");
      } catch (error) {
        if (runRef.current !== signalRun
          || (error instanceof DOMException && error.name === "AbortError")) {
          return;
        }
        if (error instanceof ExportApiError && error.status === 410) {
          setPhase("expired");
          return;
        }
        setErrorText(describeError(error));
        setPhase("error");
      }
    })();
  }, [documentId, versionId, deliver]);

  useEffect(() => {
    if (!open) {
      return;
    }
    runRef.current += 1;
    const signalRun = runRef.current;
    void run(signalRun);
    return () => {
      runRef.current += 1;
    };
  }, [open, run]);

  const handleDownloadAgain = useCallback(async () => {
    if (!job) return;
    setDownloading(true);
    try {
      const blob = await downloadExportBundle(documentId, job.id, new AbortController().signal);
      downloadBlob(blob, `near-export-${job.id}.zip`);
      onAnnounce?.("The export bundle was downloaded again.");
    } catch (error) {
      if (error instanceof ExportApiError && (error.status === 410
        || error.code === "EXPORT_EXPIRED")) {
        setPhase("expired");
        onAnnounce?.("The export bundle has expired.");
      } else {
        setErrorText(describeError(error));
        setPhase("error");
      }
    } finally {
      setDownloading(false);
    }
  }, [documentId, job, onAnnounce]);

  const handleRetry = useCallback(() => {
    onAnnounce?.("Starting a new export.");
    runRef.current += 1;
    void run(runRef.current);
  }, [onAnnounce, run]);

  const handleClose = useCallback((next: boolean) => {
    if (!next) {
      runRef.current += 1;
      onAnnounce?.(phase === "ready"
        ? "Export finished; the bundle was downloaded."
        : "Export dialog closed. A queued export keeps processing on the server.");
    }
    onOpenChange(next);
  }, [onAnnounce, onOpenChange, phase]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent data-testid="export-dialog" aria-describedby="export-dialog-description">
        <DialogTitle>Export this revision as Markdown bundle</DialogTitle>
        <DialogDescription id="export-dialog-description">
          The export is the frozen ZIP of the saved revision {versionId ? `(revision currently on the server)` : ""}:
          research.md, static chart files (SVG + CSV) and a manifest with
          verifiable hashes. Later edits never change an export.
        </DialogDescription>

        {phase === "starting" ? (
          <p role="status" data-testid="export-starting" className="text-ui leading-ui text-text mt-4">
            Starting the export…
          </p>
        ) : null}

        {phase === "processing" || phase === "slow" ? (
          <p role="status" data-testid="export-processing" className="text-ui leading-ui text-text mt-4">
            The export is being prepared on the server
            {job?.status === "queued" ? " (queued)" : ""}. This dialog updates
            automatically — you can also close it and reopen Export later.
          </p>
        ) : null}

        {phase === "slow" ? (
          <p data-testid="export-slow" className="text-metadata leading-metadata text-text-secondary mt-2">
            The export is taking longer than expected. It stays on the server;
            reopening Export shows its current state.
          </p>
        ) : null}

        {phase === "ready" ? (
          <div className="mt-4">
            <p role="status" data-testid="export-ready" className="text-ui leading-ui text-text">
              The export bundle was downloaded. It contains research.md, the
              chart assets and a manifest with SHA-256 hashes.
            </p>
            <div className="mt-3">
              <Button variant="secondary" pending={downloading} onClick={() => void handleDownloadAgain()}
                data-testid="export-download-again">
                Download again
              </Button>
            </div>
          </div>
        ) : null}

        {phase === "failed" ? (
          <div className="mt-4">
            <p role="alert" data-testid="export-failed" className="text-ui leading-ui text-danger font-medium">
              The export failed on the server
              {job?.error_code ? ` (${job.error_code})` : ""}. Nothing was
              downloaded.
            </p>
            <p className="text-metadata leading-metadata text-text-secondary mt-1">
              The failed job stays failed for the record. Starting a new export
              retries the current revision.
            </p>
            <div className="mt-3">
              <Button variant="secondary" onClick={handleRetry} data-testid="export-retry">
                Start a new export
              </Button>
            </div>
          </div>
        ) : null}

        {phase === "expired" ? (
          <p role="alert" data-testid="export-expired" className="text-ui leading-ui text-danger font-medium mt-4">
            The export bundle has expired and was removed. Start a new export to
            download a fresh copy of the current revision.
          </p>
        ) : null}

        {phase === "error" && errorText ? (
          <div className="mt-4">
            <p role="alert" data-testid="export-error" className="text-ui leading-ui text-danger font-medium">
              {errorText}
            </p>
            <div className="mt-3">
              <Button variant="secondary" onClick={handleRetry} data-testid="export-error-retry">
                Try again
              </Button>
            </div>
          </div>
        ) : null}

        <div className="mt-5 flex justify-end">
          <Button variant="quiet" onClick={() => handleClose(false)} data-testid="export-close">
            {phase === "ready" ? "Done" : "Close"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
