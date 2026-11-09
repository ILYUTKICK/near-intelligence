import { useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { DocumentApiError, getDocument } from "@/features/documents/list/documents-api";
import type { AnnotationSave } from "../annotation-mutation";
import { useChartEditorContext } from "../blocks/chart-context";
import { ASSESSMENTS, MAX_STATEMENT_CHARS, validateCanonicalDocument, type CanonicalDocument } from "../canonical";
import { findDependentBlocks } from "../commands";
import { newIdempotencyKey } from "../persistence/save-transport";
import { createHypothesis, deleteHypothesis, editHypothesis } from "./api";
import { assessmentLabels, type HypothesisAssessment } from "./assessment";

export type HypothesisAction = { kind: "create"; afterBlockId?: string } | { kind: "edit" | "delete"; blockId: string };
export interface HypothesisIntent {
  action: HypothesisAction;
  content: CanonicalDocument;
  revision: number;
}

const control = "w-full min-h-11 rounded-control border border-control-border bg-surface px-3 py-2 text-body text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

export function EditorHypothesisDialog({ intent, onClose, onSaved, onReload, restoreFocus }: {
  intent: HypothesisIntent;
  onClose: () => void;
  onSaved: (result: AnnotationSave) => void;
  onReload: (content: CanonicalDocument, revision: number, savedAt: string) => void;
  restoreFocus: () => void;
}) {
  const account = useChartEditorContext();
  const { action, content, revision } = intent;
  const selected = action.kind === "create" ? null : content.content.find(block => block.attrs.block_id === action.blockId);
  const prior = selected?.type === "hypothesis" ? selected.attrs : null;
  const [statement, setStatement] = useState(prior?.statement ?? "");
  const [assessment, setAssessment] = useState<HypothesisAssessment>(prior?.assessment ?? "untested");
  const [removeLinks, setRemoveLinks] = useState(false);
  const [pending, setPending] = useState(false);
  const [retryOnly, setRetryOnly] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState(false);
  const busy = useRef(false);
  const attempt = useRef<{ signature: string; key: string; blockId: string } | null>(null);
  const id = useId();
  const isDelete = action.kind === "delete";
  const linked = isDelete ? findDependentBlocks(content.content, action.blockId) : [];
  const evidenceCount = linked.filter(block => block.blockType === "evidence").length;
  const detachedCount = linked.length - evidenceCount;
  const allowed = account?.ready && account.saved && account.revision === revision && Boolean(account.signal);
  const valid = isDelete ? linked.length === 0 || removeLinks : statement.trim().length > 0;
  const title = isDelete ? "Delete hypothesis" : action.kind === "edit" ? "Edit hypothesis" : "Add hypothesis";

  async function submit() {
    const signal = account?.signal;
    if (!account || !allowed || !signal || signal.aborted || busy.current || stale || !valid) return;
    busy.current = true;
    setPending(true);
    setError(null);
    const fields = { statement: statement.trim(), assessment };
    const signature = JSON.stringify([fields, removeLinks]);
    if (attempt.current?.signature !== signature) {
      attempt.current = { signature, key: newIdempotencyKey(), blockId: newIdempotencyKey() };
    }
    const { key, blockId } = attempt.current;
    try {
      let result: AnnotationSave;
      if (action.kind === "create") {
        result = await createHypothesis(account.documentId, revision, {
          ...fields, block_id: blockId, after_block_id: action.afterBlockId,
        }, key, signal);
      } else if (prior && isDelete) {
        result = await deleteHypothesis(account.documentId, prior.hypothesis_id, revision, { remove_evidence_links: removeLinks }, key, signal);
      } else if (prior) {
        result = await editHypothesis(account.documentId, prior.hypothesis_id, revision, fields, key, signal);
      } else {
        throw new Error("The selected hypothesis could not be found.");
      }
      signal.throwIfAborted();
      onSaved(result);
    } catch (cause) {
      setStale(cause instanceof DocumentApiError && cause.code === "REVISION_CONFLICT");
      setRetryOnly(signal.aborted || !(cause instanceof DocumentApiError) || cause.status >= 500);
      setError(signal.aborted ? "The request was interrupted. Retry to confirm the same change."
        : cause instanceof Error ? cause.message : "The hypothesis could not be saved. Try again.");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function reloadForReview() {
    const signal = account?.signal;
    if (!account || !allowed || !signal || signal.aborted || busy.current) return;
    busy.current = true;
    setPending(true);
    try {
      const document = await getDocument(account.documentId, signal);
      const next = validateCanonicalDocument(document.content);
      if (action.kind === "create") {
        if (action.afterBlockId && !next.content.some(block => block.attrs.block_id === action.afterBlockId)) {
          throw new Error("The insertion point was removed. Copy your statement and reopen the form at another block.");
        }
      } else {
        const target = next.content.find(block => block.attrs.block_id === action.blockId);
        if (target?.type !== "hypothesis" || target.attrs.hypothesis_id !== prior?.hypothesis_id
          || target.attrs.statement !== prior.statement || target.attrs.assessment !== prior.assessment) {
          throw new Error("This hypothesis changed. Keep a copy of your statement and reopen its current revision.");
        }
      }
      signal.throwIfAborted();
      onReload(next, document.revision, document.updated_at);
      attempt.current = null;
      setRemoveLinks(false);
      setStale(false);
      setRetryOnly(false);
      setError(null);
      setReview(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The current revision could not be loaded.");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  return <Dialog open onOpenChange={open => { if (!open && !busy.current) onClose(); }}>
    <DialogContent className="max-h-[90dvh] overflow-y-auto" onCloseAutoFocus={event => { event.preventDefault(); restoreFocus(); }}>
      <DialogTitle>{title}</DialogTitle>
      <DialogDescription>{isDelete ? "Remove this hypothesis from the current research revision."
        : "Record an independent statement and your assessment of the evidence."}</DialogDescription>
      {!account?.ready ? <div className="mt-4 space-y-4">
        <p role="status" className="text-ui">Waiting for a verified session. Sign in again if the form stays unavailable.</p>
        <Button variant="secondary" disabled={pending} onClick={onClose}>Cancel</Button>
      </div> : <form className="mt-4 space-y-4" onSubmit={event => { event.preventDefault(); void submit(); }}>
        <fieldset disabled={pending || retryOnly} className="space-y-3">
          {isDelete ? <>
            <p className="text-body break-words">{prior?.statement}</p>
            {linked.length > 0 ? <>
              <ul className="list-disc space-y-1 pl-5 text-ui">
                {evidenceCount > 0 ? <li>Remove {evidenceCount} linked evidence {evidenceCount === 1 ? "block" : "blocks"}.</li> : null}
                {detachedCount > 0 ? <li>Clear the hypothesis link on {detachedCount} insight or risk {detachedCount === 1 ? "block" : "blocks"} and keep the authored content.</li> : null}
              </ul>
              <label className="flex items-center gap-2 text-ui">
                <input type="checkbox" checked={removeLinks} onChange={event => setRemoveLinks(event.target.checked)} />
                Confirm linked cleanup
              </label>
            </> : null}
          </> : <>
            <div>
              <Label htmlFor={`${id}-statement`}>Hypothesis statement</Label>
              <textarea id={`${id}-statement`} className={control} rows={4} maxLength={MAX_STATEMENT_CHARS} required
                value={statement} onChange={event => setStatement(event.target.value)} />
            </div>
            <div>
              <Label htmlFor={`${id}-assessment`}>Author assessment</Label>
              <select id={`${id}-assessment`} className={control} value={assessment} aria-describedby={`${id}-assessment-help`}
                onChange={event => setAssessment(event.target.value as HypothesisAssessment)}>
                {ASSESSMENTS.map(value => <option key={value} value={value}>{assessmentLabels[value]}</option>)}
              </select>
              <p id={`${id}-assessment-help`} className="mt-1 text-metadata text-text-secondary">Your judgment is recorded separately from linked evidence.</p>
            </div>
          </>}
        </fieldset>
        {!allowed ? <p role="status" className="text-ui">Save the current edits and reopen this form to use the latest revision.</p> : null}
        {error ? <p role="alert" className="text-ui text-danger">{error}</p> : null}
        {review && !stale ? <p role="status" className="text-ui">The current revision is loaded. Review before confirming.</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={isDelete ? "destructive" : "primary"} pending={pending} disabled={!allowed || stale || !valid}>
            {retryOnly ? "Retry same change" : isDelete ? "Confirm deletion" : "Save hypothesis"}
          </Button>
          {stale ? <Button type="button" variant="secondary" disabled={!allowed || pending} onClick={() => void reloadForReview()}>Reload and review</Button> : null}
          <Button type="button" variant="secondary" disabled={pending} onClick={onClose}>Cancel</Button>
        </div>
      </form>}
    </DialogContent>
  </Dialog>;
}
