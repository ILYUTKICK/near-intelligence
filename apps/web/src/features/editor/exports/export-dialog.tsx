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
  exportFilename,
  ExportApiError,
  newExportIdempotencyKey,
  pollExport,
  type ExportFormat,
  type ExportJob,
} from "./export-api";

/**
 * Export lifecycle for one acknowledged revision (NI-058 Markdown ZIP,
 * NI-059 PDF). The dialog first asks for the bundle format (a per-dialog
 * choice — reopening resets it to the default Markdown ZIP), then POSTs the
 * export job, polls its typed state and streams the artifact when it is
 * ready — every terminal state is shown honestly:
 *
 * - `choosing` while the format radio group waits for the explicit start
 *   (the export never starts without the user's choice);
 * - `processing` while the job is queued/running on the server (bounded
 *   polling: the dialog never pretends an export finished);
 * - `ready` after the automatic download, with a manual re-download;
 * - `failed` with the server's typed error code (the job stays failed —
 *   retrying means creating a NEW export, never a silent re-run);
 * - `expired` when the artifact TTL passed before the download;
 * - typed transport/HTTP errors (404 owner denial, 401 expired session).
 *
 * Both formats render the SAME frozen revision evidence: the Markdown ZIP
 * carries research.md + chart assets + manifest.json; the PDF is the
 * deterministic static report of the same plan (no live data, no
 * screenshots). The export always targets the acknowledged revision passed
 * in — unsaved local edits are never exported (the trigger is disabled
 * while the editor is dirty), so the artifact matches what the server
 * holds, not what this tab holds.
 */

const POLL_INTERVAL_MS = 1000;
const MAX_POLL_ATTEMPTS = 120;

type Phase =
  | "choosing"
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
  /**
   * The opener control (the workbench Export button). The dialog is opened
   * from a plain controlled button rather than a Radix DialogTrigger, so
   * Escape/close must restore focus to it explicitly (NI-064 keyboard QA).
   */
  returnFocusRef?: React.RefObject<HTMLButtonElement | null>;
}

function describeError(error: unknown): string {
  if (error instanceof ExportApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again to access your exports.";
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

const FORMAT_LABELS: Record<ExportFormat, string> = {
  markdown_zip: "Markdown bundle (ZIP)",
  pdf: "PDF report",
};

function readyCopy(format: ExportFormat): string {
  return format === "pdf"
    ? "The PDF report was downloaded. It is the frozen static report of the saved revision — attribution and pins on the first page, exact chart values in the appendix, and no live data."
    : "The export bundle was downloaded. It contains research.md, the chart assets and a manifest with SHA-256 hashes.";
}

export function ExportDialog(props: ExportDialogProps) {
  const { open, ...sessionProps } = props;
  // One dialog session per open: the key remount gives every open a fresh
  // format choice and lifecycle state (initial state, no effect-driven
  // state reset), and unmounting the previous session invalidates its
  // in-flight run through the mount-effect cleanup below.
  return (
    <ExportDialogSession
      key={open ? "session-open" : "session-closed"}
      open={open}
      {...sessionProps}
    />
  );
}

function ExportDialogSession({
  open,
  onOpenChange,
  documentId,
  versionId,
  onAnnounce,
  returnFocusRef,
}: ExportDialogProps) {
  const [phase, setPhase] = useState<Phase>("choosing");
  const [format, setFormat] = useState<ExportFormat>("markdown_zip");
  const [job, setJob] = useState<ExportJob | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const runRef = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const attemptKeys = useRef<Partial<Record<ExportFormat, string>>>({});

  const deliver = useCallback(async (finished: ExportJob, signalRun: number, signal: AbortSignal) => {
    setJob(finished);
    try {
      const blob = await downloadExportBundle(finished.document_id, finished.id, signal);
      if (signal.aborted || runRef.current !== signalRun) return;
      downloadBlob(blob, exportFilename(finished));
      setPhase("ready");
    } catch (error) {
      if (signal.aborted || runRef.current !== signalRun) return;
      if (error instanceof ExportApiError
        && (error.status === 410 || error.code === "EXPORT_EXPIRED")) {
        setPhase("expired");
        return;
      }
      throw error;
    }
  }, []);

  const run = useCallback((signalRun: number, exportFormat: ExportFormat) => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    return (async () => {
      try {
        setPhase("starting");
        setErrorText(null);
        setJob(null);
        const key = attemptKeys.current[exportFormat] ??= newExportIdempotencyKey();
        const created = await createExport(documentId, versionId, exportFormat, key, controller.signal);
        if (runRef.current !== signalRun) return;
        if (created.status === "expired") {
          setJob(created);
          setPhase("expired");
          return;
        }
        if (created.status === "failed") {
          delete attemptKeys.current[exportFormat];
          setJob(created);
          setPhase("failed");
          return;
        }
        if (created.status === "succeeded") {
          // A replayed already-finished job downloads immediately too — the
          // ready state never claims a download that did not happen.
          await deliver(created, signalRun, controller.signal);
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
            await deliver(polled, signalRun, controller.signal);
            return;
          }
          setJob(polled);
          if (polled.status === "failed") {
            delete attemptKeys.current[exportFormat];
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
      } finally {
        if (activeRequest.current === controller) activeRequest.current = null;
      }
    })();
  }, [documentId, versionId, deliver]);

  useEffect(() => {
    // An unmount (close, or the dialog being reopened as a new session)
    // invalidates any in-flight run: its polling and download stop touching
    // state after this session is gone. The fresh session itself starts at
    // the initial state above (choosing, Markdown ZIP default).
    return () => {
      runRef.current += 1;
      activeRequest.current?.abort();
    };
  }, []);

  const handleStart = useCallback(() => {
    runRef.current += 1;
    const signalRun = runRef.current;
    onAnnounce?.(`Starting a ${FORMAT_LABELS[format]} export.`);
    void run(signalRun, format);
  }, [format, onAnnounce, run]);

  const handleDownloadAgain = useCallback(async () => {
    if (!job) return;
    const signalRun = runRef.current;
    const controller = new AbortController();
    activeRequest.current = controller;
    setDownloading(true);
    try {
      const blob = await downloadExportBundle(documentId, job.id, controller.signal);
      if (controller.signal.aborted || runRef.current !== signalRun) return;
      downloadBlob(blob, exportFilename(job));
      onAnnounce?.("The export was downloaded again.");
    } catch (error) {
      if (controller.signal.aborted || runRef.current !== signalRun) return;
      if (error instanceof ExportApiError && (error.status === 410
        || error.code === "EXPORT_EXPIRED")) {
        setPhase("expired");
        onAnnounce?.("The export has expired.");
      } else {
        setErrorText(describeError(error));
        setPhase("error");
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
      if (runRef.current === signalRun) setDownloading(false);
    }
  }, [documentId, job, onAnnounce]);

  const handleRetry = useCallback(() => {
    onAnnounce?.(phase === "failed" ? "Starting a new export." : "Resuming the export.");
    runRef.current += 1;
    void run(runRef.current, format);
  }, [format, onAnnounce, phase, run]);

  const handleBackToChoice = useCallback(() => {
    setPhase("choosing");
    setJob(null);
    setErrorText(null);
  }, []);

  const handleClose = useCallback((next: boolean) => {
    if (!next) {
      runRef.current += 1;
      activeRequest.current?.abort();
      onAnnounce?.(phase === "ready"
        ? "Export finished; it was downloaded."
        : phase === "choosing"
          ? "Export dialog closed without starting an export."
          : "Export dialog closed. A queued export keeps processing on the server.");
    }
    onOpenChange(next);
  }, [onAnnounce, onOpenChange, phase]);

  const formatChoice = (
    <fieldset
      data-testid="export-format-choice"
      className="mt-4 border-0 p-0"
      disabled={phase !== "choosing"}
    >
      <legend className="font-ui text-ui text-text mb-1">Export format</legend>
      <div className="flex flex-col gap-2">
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="radio"
            name="export-format"
            value="markdown_zip"
            checked={format === "markdown_zip"}
            onChange={() => setFormat("markdown_zip")}
            data-testid="export-format-markdown"
            className="mt-1"
          />
          <span className="font-ui text-ui leading-ui text-text">
            Markdown bundle (ZIP)
            <span className="block font-ui text-metadata leading-metadata text-text-secondary">
              research.md, static chart files (SVG + CSV) and a manifest with
              verifiable hashes.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="radio"
            name="export-format"
            value="pdf"
            checked={format === "pdf"}
            onChange={() => setFormat("pdf")}
            data-testid="export-format-pdf"
            className="mt-1"
          />
          <span className="font-ui text-ui leading-ui text-text">
            PDF report
            <span className="block font-ui text-metadata leading-metadata text-text-secondary">
              A static PDF of the same frozen evidence — paginated, with the
              exact chart values in an appendix. Not editable, never refreshed.
            </span>
          </span>
        </label>
      </div>
    </fieldset>
  );

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        data-testid="export-dialog"
        aria-describedby="export-dialog-description"
        onCloseAutoFocus={(event) => {
          if (returnFocusRef?.current) {
            event.preventDefault();
            returnFocusRef.current.focus();
          }
        }}
      >
        <DialogTitle>Export this revision</DialogTitle>
        <DialogDescription id="export-dialog-description">
          The export is the frozen record of the saved revision {versionId ? `(revision currently on the server)` : ""}.
          Later edits never change an export.
        </DialogDescription>

        {phase === "choosing" ? (
          <div data-testid="export-choosing">
            {formatChoice}
            <div className="mt-5 flex justify-end">
              <Button onClick={handleStart} data-testid="export-start">
                Start export
              </Button>
            </div>
          </div>
        ) : null}

        {phase === "starting" ? (
          <p role="status" data-testid="export-starting" className="text-ui leading-ui text-text mt-4">
            Starting the {FORMAT_LABELS[format]} export…
          </p>
        ) : null}

        {phase === "processing" || phase === "slow" ? (
          <p role="status" data-testid="export-processing" className="text-ui leading-ui text-text mt-4">
            The export is being prepared on the server
            {job?.status === "queued" ? " (queued)" : ""}.
          </p>
        ) : null}

        {phase === "slow" ? (
          <div className="mt-2 space-y-3">
            <p data-testid="export-slow" className="text-metadata leading-metadata text-text-secondary">
              The export is taking longer than expected.
            </p>
            <Button variant="secondary" onClick={handleRetry}>Check again</Button>
          </div>
        ) : null}

        {phase === "ready" ? (
          <div className="mt-4">
            <p role="status" data-testid="export-ready" className="text-ui leading-ui text-text">
              {job ? readyCopy(job.format) : readyCopy(format)}
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
            <div className="mt-3 flex gap-2 justify-end">
              <Button variant="quiet" onClick={handleBackToChoice} data-testid="export-failed-back">
                Change format
              </Button>
              <Button variant="secondary" onClick={handleRetry} data-testid="export-retry">
                Start a new export
              </Button>
            </div>
          </div>
        ) : null}

        {phase === "expired" ? (
          <p role="alert" data-testid="export-expired" className="text-ui leading-ui text-danger font-medium mt-4">
            The export has expired and was removed. Start a new export to
            download a fresh copy of the current revision.
          </p>
        ) : null}

        {phase === "error" && errorText ? (
          <div className="mt-4">
            <p role="alert" data-testid="export-error" className="text-ui leading-ui text-danger font-medium">
              {errorText}
            </p>
            <div className="mt-3 flex gap-2 justify-end">
              <Button variant="quiet" onClick={handleBackToChoice} data-testid="export-error-back">
                Change format
              </Button>
              <Button variant="secondary" onClick={handleRetry} data-testid="export-error-retry">
                Try again
              </Button>
            </div>
          </div>
        ) : null}

        {phase !== "choosing" ? (
          <div className="mt-5 flex justify-end">
            <Button variant="quiet" onClick={() => handleClose(false)} data-testid="export-close">
              {phase === "ready" ? "Done" : "Close"}
            </Button>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
