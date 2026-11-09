import { useId, useRef, useState } from "react";
import type { components } from "@near-intelligence/shared-types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { DocumentApiError, getDocument } from "@/features/documents/list/documents-api";
import type { AnnotationSave } from "../annotation-mutation";
import { useChartEditorContext } from "../blocks/chart-context";
import { CLASSIFICATIONS, MAX_EXPLANATION_CHARS, TARGET_KINDS, validateCanonicalDocument, type CanonicalDocument } from "../canonical";
import { hypothesisOptions } from "../insights/fields";
import { newIdempotencyKey } from "../persistence/save-transport";
import { createEvidence, deleteEvidence, editEvidence } from "./api";
import { classificationLabels, isPublicEvidenceTarget, localEvidenceTargets, samePrivateEvidenceTarget, targetKindLabels } from "./options";
import { EvidenceTargetSelect, PublicEvidenceTargetPicker, evidenceControl } from "./target-picker";

export type EvidenceAction = { kind: "create" | "edit" | "delete"; blockId: string };
type Draft = Omit<components["schemas"]["EvidenceInput"], "block_id">;

export function EditorEvidenceDialog({ intent, onClose, onSaved, onReload, restoreFocus }: {
  intent: { action: EvidenceAction; content: CanonicalDocument; revision: number };
  onClose: () => void;
  onSaved: (result: AnnotationSave) => void;
  onReload: (content: CanonicalDocument, revision: number, savedAt: string) => void;
  restoreFocus: () => void;
}) {
  const account = useChartEditorContext();
  const { action, content, revision } = intent;
  const selected = content.content.find(block => block.attrs.block_id === action.blockId);
  const prior = selected?.type === "evidence" ? selected.attrs : null;
  const [draft, setDraft] = useState<Draft>(() => prior ? {
    hypothesis_id: prior.hypothesis_id, classification: prior.classification, target_kind: prior.target_kind,
    target_id: prior.target_id, explanation: prior.explanation,
  } : { hypothesis_id: selected?.type === "hypothesis" ? selected.attrs.hypothesis_id : "", classification: "uncertain",
    target_kind: "insight", target_id: "", explanation: "" });
  const [pending, setPending] = useState(false);
  const [stale, setStale] = useState(false);
  const [retryOnly, setRetryOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const busy = useRef(false);
  const attempt = useRef<{ signature: string; key: string; blockId: string } | null>(null);
  const id = useId();
  const hypotheses = hypothesisOptions(content);
  const targets = localEvidenceTargets(content, draft.target_kind);
  const kind = draft.target_kind;
  const publicKind = isPublicEvidenceTarget(kind) ? kind : null;
  const isDelete = action.kind === "delete";
  const title = isDelete ? "Delete evidence link" : action.kind === "edit" ? "Edit evidence link" : "Add evidence link";
  const signal = account?.signal;
  const allowed = Boolean(account?.ready && account.saved && account.revision === revision && signal && !signal.aborted);
  const valid = isDelete || Boolean(draft.explanation.trim() && hypotheses.some(option => option.id === draft.hypothesis_id)
    && draft.target_id && (publicKind || targets.some(option => option.id === draft.target_id)));

  async function submit() {
    if (!account || !signal || signal.aborted || !allowed || !valid || busy.current || stale) return;
    busy.current = true;
    setPending(true);
    setError(null);
    const fields = { ...draft, explanation: draft.explanation.trim() };
    const signature = JSON.stringify(fields);
    if (attempt.current?.signature !== signature) {
      attempt.current = { signature, key: newIdempotencyKey(), blockId: newIdempotencyKey() };
    }
    const { key, blockId } = attempt.current;
    try {
      let result: AnnotationSave;
      if (action.kind === "create") {
        result = await createEvidence(account.documentId, revision, { ...fields, block_id: blockId, after_block_id: action.blockId }, key, signal);
      } else if (prior && isDelete) {
        result = await deleteEvidence(account.documentId, prior.evidence_id, revision, key, signal);
      } else if (prior) {
        result = await editEvidence(account.documentId, prior.evidence_id, revision, fields, key, signal);
      } else {
        throw new Error("The selected evidence link could not be found.");
      }
      signal.throwIfAborted();
      onSaved(result);
    } catch (cause) {
      setStale(cause instanceof DocumentApiError && cause.code === "REVISION_CONFLICT");
      setRetryOnly(signal.aborted || !(cause instanceof DocumentApiError) || cause.status >= 500);
      setError(signal.aborted ? "The request was interrupted. Retry to confirm the same change."
        : cause instanceof Error ? cause.message : "The evidence link could not be saved. Try again.");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function reloadForReview() {
    if (!account || !signal || signal.aborted || !allowed || busy.current) return;
    busy.current = true;
    setPending(true);
    try {
      const document = await getDocument(account.documentId, signal);
      const next = validateCanonicalDocument(document.content);
      const target = next.content.find(block => block.attrs.block_id === action.blockId);
      if (action.kind === "create" && target?.type !== "hypothesis") {
        throw new Error("The anchor hypothesis was removed. Copy your explanation and reopen the form on another hypothesis.");
      }
      if (action.kind !== "create" && (target?.type !== "evidence" || JSON.stringify(target.attrs) !== JSON.stringify(prior))) {
        throw new Error("This evidence link changed. Copy your explanation and reopen its current revision.");
      }
      signal.throwIfAborted();
      onReload(next, document.revision, document.updated_at);
      const hypothesis = hypothesisOptions(next).some(option => option.id === draft.hypothesis_id) ? draft.hypothesis_id : "";
      const nextTarget = isDelete || publicKind || samePrivateEvidenceTarget(content, next, kind, draft.target_id) ? draft.target_id : "";
      setDraft({ ...draft, hypothesis_id: hypothesis, target_id: nextTarget });
      setNotice(hypothesis === draft.hypothesis_id && nextTarget === draft.target_id
        ? "The current revision is loaded. Review your retained changes before confirming."
        : "A selection changed or was removed in the current revision. Review the available choices before saving.");
      attempt.current = null;
      setStale(false);
      setRetryOnly(false);
      setError(null);
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
      <DialogDescription>{isDelete ? "Remove this relationship from the current research revision."
        : "Link a saved target to a hypothesis and explain how it bears on your question."}</DialogDescription>
      {!account?.ready || !signal ? <div className="mt-4 space-y-4">
        <p role="status" className="text-ui">Waiting for a verified session. Sign in again if the form stays unavailable.</p>
        <Button variant="secondary" disabled={pending} onClick={onClose}>Cancel</Button>
      </div> : <form className="mt-4 space-y-4" onSubmit={event => { event.preventDefault(); void submit(); }}>
        {isDelete ? <p className="text-body break-words">{prior?.explanation}</p> :
          <fieldset disabled={pending || retryOnly} className="space-y-3">
            <div>
              <Label htmlFor={`${id}-hypothesis`}>Hypothesis</Label>
              <select id={`${id}-hypothesis`} className={evidenceControl} value={draft.hypothesis_id}
                onChange={event => setDraft({ ...draft, hypothesis_id: event.target.value })} required>
                <option value="">Choose a hypothesis</option>
                {hypotheses.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
              </select>
            </div>
            <div>
              <Label htmlFor={`${id}-classification`}>Evidence classification</Label>
              <select id={`${id}-classification`} className={evidenceControl} value={draft.classification} aria-describedby={`${id}-meaning`}
                onChange={event => setDraft({ ...draft, classification: event.target.value as Draft["classification"] })}>
                {CLASSIFICATIONS.map(value => <option key={value} value={value}>{classificationLabels[value]}</option>)}
              </select>
              <p id={`${id}-meaning`} className="text-metadata text-text-secondary">Classification records your interpretation of the link.</p>
            </div>
            <div>
              <Label htmlFor={`${id}-kind`}>Target type</Label>
              <select id={`${id}-kind`} className={evidenceControl} value={kind}
                onChange={event => setDraft({ ...draft, target_kind: event.target.value as Draft["target_kind"], target_id: "" })}>
                {TARGET_KINDS.map(value => <option key={value} value={value}>{targetKindLabels[value]}</option>)}
              </select>
            </div>
            {publicKind ? <PublicEvidenceTargetPicker key={publicKind} documentId={account.documentId} kind={publicKind}
              signal={signal} id={`${id}-target`} value={draft.target_id} onChange={target_id => setDraft({ ...draft, target_id })} />
              : <>
                <EvidenceTargetSelect id={`${id}-target`} options={targets} value={draft.target_id}
                  onChange={target_id => setDraft({ ...draft, target_id })} />
                {targets.length === 0 ? <p className="text-metadata text-text-secondary">Save a target of this kind in the research to link it.</p> : null}
              </>}
            <div>
              <Label htmlFor={`${id}-explanation`}>Explanation</Label>
              <textarea id={`${id}-explanation`} className={evidenceControl} rows={4} maxLength={MAX_EXPLANATION_CHARS} required
                value={draft.explanation} onChange={event => setDraft({ ...draft, explanation: event.target.value })} />
            </div>
          </fieldset>}
        {!allowed ? <p role="status" className="text-ui">Save the current edits and reopen this form to use the latest revision.</p> : null}
        {error ? <p role="alert" className="text-ui text-danger">{error}</p> : null}
        {notice ? <p role="status" className="text-ui">{notice}</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={isDelete ? "destructive" : "primary"} pending={pending} disabled={!allowed || stale || !valid}>
            {retryOnly ? "Retry same change" : isDelete ? "Confirm deletion" : "Save evidence link"}
          </Button>
          {stale ? <Button variant="secondary" disabled={!allowed || pending} onClick={() => void reloadForReview()}>Reload and review</Button> : null}
          <Button variant="secondary" disabled={pending} onClick={onClose}>Cancel</Button>
        </div>
      </form>}
    </DialogContent>
  </Dialog>;
}
