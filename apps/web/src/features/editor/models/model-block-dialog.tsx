"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { getDocument, DocumentApiError } from "@/features/documents/list/documents-api";
import { MAX_BODY_PLAIN_CHARS, validateCanonicalDocument, type CanonicalDocument } from "../canonical";
import { newIdempotencyKey } from "../persistence/save-transport";
import { getRevision } from "../revision-api";
import { useChartEditorContext } from "../blocks/chart-context";
import { fetchPublishedRuns } from "@/features/editor/blocks/model-run-api";
import { insertModel, interpretationLines } from "@/features/models/add-to-research/api";
import type { ModelRunSummary } from "@/features/models/models-schema";

/**
 * NI-055 Add Model chooser for the open research document (the insert-menu
 * "Model result" item): one published run from the public catalog + one
 * approved dataset version pin + the author's interpretation, inserted via
 * `POST /documents/{id}/model-blocks` with the shell's current revision
 * (If-Match CAS) and an Idempotency-Key. The server re-verifies both pins
 * inside the save transaction — an unknown run or an unapproved dataset is
 * a typed 422 that leaves zero rows — and allocates the block id itself.
 * On success the acknowledged revision is adopted into the paper.
 */

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CONTROL_CLASS = "w-full min-h-11 rounded-control border border-control-border bg-surface px-3 py-2 text-body text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

export function EditorModelBlockDialog({ documentId, revision, onClose, onInserted, onReload, restoreFocus }: {
  documentId: string;
  revision: number;
  onClose: () => void;
  /** Adopt the acknowledged revision into the paper after a 201. */
  onInserted: (content: CanonicalDocument, revision: number, savedAt: string, versionId: string, blockId: string) => void;
  onReload: (content: CanonicalDocument, revision: number, savedAt: string, versionId: string | null) => void;
  restoreFocus: () => void;
}) {
  const account = useChartEditorContext();
  const [runs, setRuns] = useState<ModelRunSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [runsAttempt, setRunsAttempt] = useState(0);
  const [runId, setRunId] = useState<string>("");
  const [datasetVersionId, setDatasetVersionId] = useState<string>("");
  const [interpretation, setInterpretation] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const busy = useRef(false);
  const attempt = useRef<{ key: string; runId: string; datasetVersionId: string; interpretation: string } | null>(null);
  const signal = account?.signal;
  const ready = Boolean(account?.ready && account.saved && account.revision === revision && signal && !signal.aborted);

  useEffect(() => {
    if (!signal) return;
    const controller = new AbortController();
    const loadSignal = AbortSignal.any([signal, controller.signal]);
    async function load() {
      setRunsLoading(true);
      setRunsError(null);
      try {
        const page = await fetchPublishedRuns(cursor ? { cursor } : {}, loadSignal);
        if (loadSignal.aborted) return;
        setRuns((previous) => cursor ? [...previous, ...page.items] : page.items);
        setNextCursor(page.next_cursor);
        setRunsLoading(false);
        setRunId((current) => current || page.items[0]?.run_id || "");
      } catch (cause) {
        if (loadSignal.aborted) return;
        setRunsLoading(false);
        setRunsError(cause instanceof Error ? cause.message : "The published runs could not be loaded.");
      }
    }
    void load();
    return () => controller.abort();
  }, [signal, cursor, runsAttempt]);

  const frozen = pending || confirmed;

  async function submit() {
    if (!signal || signal.aborted || !canConfirm || stale || busy.current) return;
    busy.current = true;
    setPending(true);
    setConfirmed(true);
    setError(null);
    setNotice(null);
    attempt.current ??= { key: newIdempotencyKey(), runId: runId.toLowerCase(), datasetVersionId: datasetVersionId.toLowerCase(), interpretation };
    const current = attempt.current;
    try {
      const inserted = await insertModel(documentId, revision, {
        model_run_id: current.runId,
        dataset_version_id: current.datasetVersionId,
        interpretation: interpretationLines(current.interpretation),
      }, current.key, signal);

      signal.throwIfAborted();
      const versionId = inserted.document.current_version_id;
      if (!versionId) throw new Error("The insertion response did not identify a saved revision.");
      const saved = await getRevision(documentId, versionId, signal);
      signal.throwIfAborted();
      const content = validateCanonicalDocument(saved.content);
      const blockId = inserted.value.block_id;
      const block = content.content.find(candidate => candidate.attrs.block_id === blockId);
      if (saved.revision !== inserted.document.revision || block?.type !== "modelResult"
        || block.attrs.model_run_id !== current.runId || block.attrs.dataset_version_id !== current.datasetVersionId) {
        throw new Error("The saved revision did not match the confirmed model result.");
      }
      onInserted(content, saved.revision, inserted.document.updated_at, saved.id, blockId);
    } catch (cause) {
      if (cause instanceof DocumentApiError && cause.code === "REVISION_CONFLICT") setStale(true);
      if (cause instanceof DocumentApiError && cause.status === 422 && cause.code !== "UNKNOWN_ERROR") {
        attempt.current = null;
        setConfirmed(false);
      }
      setError(signal.aborted ? "The request was interrupted. Retry the same insertion."
        : cause instanceof Error ? cause.message : "The insertion failed. Try again.");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function reloadForReview() {
    if (!signal || signal.aborted || !ready || busy.current) return;
    busy.current = true;
    setPending(true);
    try {
      const document = await getDocument(documentId, signal);
      signal.throwIfAborted();
      onReload(validateCanonicalDocument(document.content), document.revision, document.updated_at, document.current_version_id);
      attempt.current = null;
      setConfirmed(false);
      setStale(false);
      setError(null);
      setNotice("The current revision is loaded. Review your retained interpretation before confirming.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The current revision could not be loaded.");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  const canConfirm = UUID_PATTERN.test(runId) && UUID_PATTERN.test(datasetVersionId)
    && interpretation.trim().length > 0 && ready;
  return (
    <Dialog open onOpenChange={(next) => { if (!next && !busy.current) onClose(); }}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto" onCloseAutoFocus={event => { event.preventDefault(); restoreFocus(); }}>
        <DialogTitle>Add model result</DialogTitle>
        <DialogDescription>
          Choose a published model run and the approved dataset version your interpretation reads
          against. Both pins are verified server-side; the recorded result itself is never stored in
          this document and never edited.
        </DialogDescription>
        <div className="mt-4 space-y-4">
          {runsLoading ? <p role="status">Loading published runs…</p> : null}
          {runsError ? (
            <div role="alert">
              <p>{runsError}</p>
              <Button variant="secondary" onClick={() => setRunsAttempt(value => value + 1)}>
                Try loading again
              </Button>
            </div>
          ) : null}
          {!runsLoading && !runsError && runs.length === 0 ? (
            <p className="text-ui text-text-secondary">
              No published model runs are available yet. A model result can only pin a published run.
            </p>
          ) : null}
          {runs.length > 0 ? (
            <div>
              <Label htmlFor="model-block-run">Published run</Label>
              <select id="model-block-run" className={CONTROL_CLASS} value={runId}
                disabled={frozen}
                onChange={(event) => setRunId(event.target.value)}>
                {runs.map((run) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.model_id} v{run.model_version} · {run.gate_verdict} · {run.run_id}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {nextCursor ? (
            <Button variant="quiet" disabled={frozen} onClick={() => setCursor(nextCursor)}>More published runs</Button>
          ) : null}
          <div>
            <Label htmlFor="model-block-dataset">Approved dataset version (UUID)</Label>
            <Input id="model-block-dataset" value={datasetVersionId} maxLength={36} disabled={frozen}
              onChange={(event) => setDatasetVersionId(event.target.value)}
              aria-invalid={datasetVersionId.length > 0 && !UUID_PATTERN.test(datasetVersionId)} />
            <p className="mt-1 text-metadata text-text-secondary">
              The id of an approved public dataset version — never substituted with a latest pointer.
            </p>
          </div>
          <div>
            <Label htmlFor="model-block-interpretation">Interpretation (your own prose)</Label>
            <textarea id="model-block-interpretation" aria-label="Interpretation of the pinned model result"
              className={`${CONTROL_CLASS} mt-1`} rows={4} maxLength={MAX_BODY_PLAIN_CHARS}
              required value={interpretation} disabled={frozen}
              onChange={(event) => setInterpretation(event.target.value)} />
            <p className="mt-1 text-metadata text-text-secondary">Required. Each line becomes one paragraph.</p>
          </div>
          {error ? <p role="alert" className="text-danger text-ui">{error}</p> : null}
          {notice ? <p role="status" className="text-ui">{notice}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void submit()} pending={pending} disabled={!canConfirm || stale}>
              {confirmed ? "Retry confirmed insertion" : "Confirm Add Model"}
            </Button>
            {stale ? <Button variant="secondary" disabled={pending || !ready} onClick={() => void reloadForReview()}>Reload and review</Button> : null}
            <Button variant="quiet" disabled={pending} onClick={onClose}>Cancel</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );

}
