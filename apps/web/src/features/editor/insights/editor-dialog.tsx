import { useRef, useState } from "react";
import type { components } from "@near-intelligence/shared-types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { DocumentApiError, getDocument } from "@/features/documents/list/documents-api";
import { inspectionKey } from "@/features/charts/renderer/observation-context";
import { useChartEditorContext } from "../blocks/chart-context";
import { findDependentBlocks } from "../commands";
import { validateCanonicalDocument, type CanonicalDocument } from "../canonical";
import { newIdempotencyKey } from "../persistence/save-transport";
import type { AnnotationSave } from "../annotation-mutation";
import { createInsight, deleteInsight, editInsight } from "./api";
import { emptyInsight, hypothesisOptions, InsightFields, InsightPin, insightBody, insightText, type InsightDraft } from "./fields";

export type InsightAction = { kind: "create"; blockId: string; context: components["schemas"]["ResolvedContext"] }
  | { kind: "edit" | "delete"; blockId: string };

export interface InsightIntent {
  action: InsightAction;
  content: CanonicalDocument;
  revision: number;
}

export function EditorInsightDialog({ intent, onClose, onSaved, onReload, restoreFocus }: {
  intent: InsightIntent;
  onClose: () => void;
  onSaved: (result: AnnotationSave) => void;
  onReload: (content: CanonicalDocument, revision: number, savedAt: string, versionId: string | null) => void;
  restoreFocus: () => void;
}) {
  const account = useChartEditorContext();
  const { action, content, revision } = intent;
  const selected = content.content.find(block => block.attrs.block_id === action.blockId);
  const prior = selected?.type === "insight" ? selected.attrs : null;
  const pin = action.kind === "create" ? action.context : prior?.context;
  const priorText = prior ? insightText(prior.body) : "";
  const [draft, setDraft] = useState<InsightDraft>(() => prior ? {
    type: prior.type, classification: prior.classification, text: priorText, hypothesisId: prior.hypothesis_id ?? "",
  } : emptyInsight);
  const [removeLinks, setRemoveLinks] = useState(false);
  const [pending, setPending] = useState(false);
  const [retryOnly, setRetryOnly] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const busy = useRef(false);
  const attempt = useRef<{ signature: string; key: string; blockId: string } | null>(null);
  const linked = action.kind === "delete" ? findDependentBlocks(content.content, action.blockId) : [];
  const allowed = account?.ready && account.saved && account.revision === revision && Boolean(account.signal);
  const isDelete = action.kind === "delete";
  const title = isDelete ? "Delete insight" : action.kind === "edit" ? "Edit insight" : "Add insight";

  async function submit() {
    const signal = account?.signal;
    if (!account || !allowed || !signal || signal.aborted || busy.current || stale) return;
    if (isDelete ? linked.length > 0 && !removeLinks : !draft.text.trim()) return;
    busy.current = true;
    setPending(true);
    setError(null);
    const signature = JSON.stringify([draft, removeLinks]);
    if (attempt.current?.signature !== signature) {
      attempt.current = { signature, key: newIdempotencyKey(), blockId: newIdempotencyKey() };
    }
    const { key, blockId } = attempt.current;
    try {
      const fields = { type: draft.type, classification: draft.classification, hypothesis_id: draft.hypothesisId || null };
      let result: AnnotationSave;
      if (action.kind === "create") {
        result = await createInsight(account.documentId, revision, { ...fields, block_id: blockId,
          after_block_id: action.blockId, body: insightBody(draft.text), context: action.context }, key, signal);
      } else if (prior && isDelete) {
        result = await deleteInsight(account.documentId, prior.insight_id, revision, { remove_evidence_links: removeLinks }, key, signal);
      } else if (prior) {
        result = await editInsight(account.documentId, prior.insight_id, revision, {
          ...fields, ...(draft.text === priorText ? {} : { body: insightBody(draft.text) }),
        }, key, signal);
      } else {
        throw new Error("The selected insight could not be found.");
      }
      signal.throwIfAborted();
      onSaved(result);
    } catch (cause) {
      setStale(cause instanceof DocumentApiError && cause.code === "REVISION_CONFLICT");
      setRetryOnly(signal.aborted || !(cause instanceof DocumentApiError) || cause.status >= 500);
      setError(signal.aborted ? "The request was interrupted. Retry to confirm the same change."
        : cause instanceof Error ? cause.message : "The insight could not be saved. Try again.");
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
      const target = next.content.find(block => block.attrs.block_id === action.blockId);
      if (action.kind === "create") {
        const { chart_definition_version_id, selection, dataset_version_id } = action.context;
        if (target?.type !== "liveChart" || inspectionKey(target.attrs.chart_definition_version_id,
          target.attrs.selection, target.attrs.observed_dataset_version_id) !== inspectionKey(chart_definition_version_id, selection, dataset_version_id)) {
          throw new Error("The saved chart changed. Copy your note before reopening Add Insight for the chart you want to use.");
        }
      } else if (target?.type !== "insight" || JSON.stringify(target.attrs) !== JSON.stringify(prior)) {
        throw new Error("This insight changed. Keep a copy of your edits before reopening its current revision.");
      }
      signal.throwIfAborted();
      onReload(next, document.revision, document.updated_at, document.current_version_id);
      if (draft.hypothesisId && !hypothesisOptions(next).some(option => option.id === draft.hypothesisId)) {
        setDraft({ ...draft, hypothesisId: "" });
        setNotice("The selected hypothesis was removed. Review the insight before saving.");
      } else {
        setNotice("The current revision is loaded. Review your retained draft before saving.");
      }
      attempt.current = null;
      setRemoveLinks(false);
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

  if (!pin) return null;
  return <Dialog open={Boolean(account?.ready)} onOpenChange={open => { if (!open && !busy.current) onClose(); }}>
    <DialogContent className="max-h-[90dvh] overflow-y-auto" onCloseAutoFocus={event => { event.preventDefault(); if (account?.ready) restoreFocus(); }}>
      <DialogTitle>{title}</DialogTitle>
      <DialogDescription>{isDelete ? "Remove this insight from the current research revision."
        : "Record an insight with the pinned evidence shown below."}</DialogDescription>
      <form className="mt-4 space-y-4" onSubmit={event => { event.preventDefault(); void submit(); }}>
        <InsightPin context={pin} />
        <fieldset disabled={pending || retryOnly}>
          {isDelete ? linked.length > 0 ? <label className="flex items-start gap-2 text-ui">
            <input className="mt-1" type="checkbox" checked={removeLinks} onChange={event => setRemoveLinks(event.target.checked)} />
            <span>Also remove {linked.length} linked {linked.length === 1 ? "evidence block" : "evidence blocks"} from this revision.</span>
          </label> : null : <InsightFields value={draft} onChange={setDraft} hypotheses={hypothesisOptions(content)} />}
        </fieldset>
        {!allowed ? <p role="status" className="text-ui">Save the current edits and reopen this form to use the latest document revision.</p> : null}
        {error ? <p role="alert" className="text-ui text-danger">{error}</p> : null}
        {notice ? <p role="status" className="text-ui">{notice}</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant={isDelete ? "destructive" : "primary"} pending={pending}
            disabled={!allowed || stale || (isDelete ? linked.length > 0 && !removeLinks : !draft.text.trim())}>
            {retryOnly ? "Retry same change" : isDelete ? "Confirm deletion" : "Save insight"}
          </Button>
          {stale ? <Button type="button" variant="secondary" disabled={!allowed || pending} onClick={() => void reloadForReview()}>Reload and review</Button> : null}
          <Button type="button" variant="secondary" disabled={pending} onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </DialogContent>
  </Dialog>;
}
