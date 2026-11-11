"use client";

import Link from "next/link";
import { useCallback, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { createDocument, getDocument, listDocuments } from "@/features/documents/list/documents-api";
import { MAX_BODY_PLAIN_CHARS } from "@/features/editor/canonical";
import { useOwnedData } from "@/features/charts/saved/use-owned-data";
import { insertModel, type InsertModelInput } from "./api";
import type { ModelRunSummary } from "../models-schema";

/**
 * NI-055 Add Model picker (the published-run counterpart of the NI-041
 * AddChartToResearch flow): one confirmed choice appends ONE pinned
 * `modelResult` block to the chosen owned destination. The published run
 * identity and the approved dataset version are pinned server-side (the
 * server rejects an unknown run or an unapproved dataset version with a
 * typed 422 — never substitutes); the interpretation is the author's own
 * prose and the ONLY thing they can edit afterwards. The block never
 * carries coefficients: the document JSON stores ids + narrative only.
 */

/** Lines to canonical rich-text paragraphs (the NI-046 dialog precedent). */
export function interpretationLines(text: string): InsertModelInput["interpretation"] {
  return text.split(/\r?\n/).map((line) => ({
    type: "paragraph",
    content: line ? [{ type: "text", text: line, marks: [] }] : [],
  }));
}

export function AddModelToResearch({ run, datasetVersionId, suspended = false }: {
  run: ModelRunSummary;
  datasetVersionId: string;
  suspended?: boolean;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [destination, setDestination] = useState("new");
  const [title, setTitle] = useState("Research with model result");
  const [interpretation, setInterpretation] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<{ key: string; createKey: string; title: string; documentId: string | null; interpretation: string } | null>(null);
  const busy = useRef(false);
  const loader = useCallback((signal: AbortSignal) => open && !suspended
    ? listDocuments({ query, cursor, signal }) : Promise.resolve({ items: [], nextCursor: null }), [open, suspended, query, cursor]);
  const { data, loading, error: loadError, reload, signal } = useOwnedData(loader, "research documents");

  function resetAttempt() {
    request.current = null; setConfirmed(false); setError(null);
  }
  function changeOpen(next: boolean) {
    if (busy.current) return;
    if (next && documentId) { resetAttempt(); setDocumentId(null); }
    setOpen(next);
  }
  async function confirm() {
    if (suspended || busy.current || !signal || signal.aborted || !interpretation.trim()) return;
    busy.current = true; setPending(true); setConfirmed(true); setError(null);
    request.current ??= { key: crypto.randomUUID(), createKey: crypto.randomUUID(),
      title: title.trim(), documentId: destination === "new" ? null : destination,
      interpretation };
    const attempt = request.current;
    try {
      if (!attempt.documentId) {
        attempt.documentId = (await createDocument({ title: attempt.title, idempotencyKey: attempt.createKey, signal })).id;
      }
      signal.throwIfAborted();
      const current = await getDocument(attempt.documentId, signal);
      signal.throwIfAborted();
      const payload: InsertModelInput = {
        model_run_id: run.run_id,
        dataset_version_id: datasetVersionId,
        interpretation: interpretationLines(attempt.interpretation),
      };
      const inserted = await insertModel(attempt.documentId, current.revision, payload, attempt.key, signal);
      signal.throwIfAborted();
      setDocumentId(inserted.document.id);
      setOpen(false);
    } catch (error) { setError(signal.aborted ? "The request was interrupted. Retry the same insertion."
      : error instanceof Error ? error.message : "The insertion failed. Try again."); }
    finally { busy.current = false; setPending(false); }
  }
  const frozen = pending || confirmed;
  const canConfirm = Boolean(run.run_id) && /^[0-9a-f-]{36}$/i.test(datasetVersionId) && interpretation.trim().length > 0;
  if (suspended) return null;
  return <div className="flex flex-col gap-2">
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild><Button variant="secondary">Add to research</Button></DialogTrigger>
      <DialogContent className="max-h-[90dvh] overflow-y-auto">
        <DialogTitle>Add model result to your research</DialogTitle>
        <DialogDescription>Choose an owned destination. The published run and the dataset version are pinned when you confirm; only your interpretation is editable afterwards.</DialogDescription>
        <div className="mt-4 space-y-4">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-metadata text-text-secondary">
            <dt className="text-text-secondary">Published run</dt>
            <dd className="break-all">{run.run_id}</dd>
            <dt className="text-text-secondary">Specification</dt>
            <dd>{run.model_id} · v{run.model_version}</dd>
            <dt className="text-text-secondary">Gate verdict</dt>
            <dd>{run.gate_verdict}</dd>
            <dt className="text-text-secondary">Pinned dataset version</dt>
            <dd className="break-all">{datasetVersionId}</dd>
          </dl>
          <div>
            <Label htmlFor={`${id}-interpretation`}>Interpretation (your own prose)</Label>
            <textarea id={`${id}-interpretation`} aria-label="Interpretation of the pinned model result"
              className="mt-1 w-full min-h-11 rounded-control border border-control-border bg-surface px-3 py-2 text-body text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
              rows={4} maxLength={MAX_BODY_PLAIN_CHARS} required value={interpretation} disabled={frozen}
              onChange={(event) => setInterpretation(event.target.value)} />
            <p className="mt-1 text-metadata text-text-secondary">Required. Each line becomes one paragraph. The recorded result itself is never edited here.</p>
          </div>
          <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); setQuery(draft); setCursor(null); setDestination("new"); }}>
            <div className="min-w-0 flex-1"><Label htmlFor={`${id}-search`}>Find your research</Label><Input id={`${id}-search`} value={draft} maxLength={200} disabled={frozen} onChange={(event) => setDraft(event.target.value)} /></div>
            <Button type="submit" variant="secondary" disabled={frozen}>Search</Button>
          </form>
          {loading ? <p role="status">Loading your research…</p> : null}
          {loadError ? <div role="alert"><p>{loadError}</p><Button variant="secondary" onClick={reload}>Try loading again</Button></div> : null}
          <div><Label htmlFor={`${id}-destination`}>Destination</Label>
            <select id={`${id}-destination`} className="w-full min-h-11 rounded-control border border-control-border bg-surface px-3 text-body" value={destination} disabled={frozen} onChange={(event) => setDestination(event.target.value)}>
              <option value="new">Create new research</option>
              {data?.items.map((document) => <option key={document.id} value={document.id}>{document.title}</option>)}
            </select>
          </div>
          {data?.nextCursor ? <Button variant="quiet" disabled={frozen} onClick={() => { setCursor(data.nextCursor); setDestination("new"); }}>Next destinations</Button> : null}
          {cursor ? <Button variant="quiet" disabled={frozen} onClick={() => { setCursor(null); setDestination("new"); }}>First destinations</Button> : null}
          {destination === "new" ? <div><Label htmlFor={`${id}-title`}>New research title</Label><Input id={`${id}-title`} value={title} maxLength={200} disabled={frozen} onChange={(event) => setTitle(event.target.value)} /></div> : null}
          {data?.items.length === 0 ? <p className="text-ui text-text-secondary">No existing research matches. You can create a new document above.</p> : null}
          {error ? <p role="alert" className="text-danger text-ui">{error}</p> : null}
          <Button onClick={() => void confirm()} pending={pending} aria-disabled={!canConfirm || !signal || loading || Boolean(loadError) || (destination === "new" && !title.trim())}
            disabled={!canConfirm || !signal || loading || Boolean(loadError) || (destination === "new" && !title.trim())}>
            {confirmed ? "Retry confirmed insertion" : "Confirm Add Model"}</Button>
          {error && !pending ? <Button variant="quiet" onClick={resetAttempt}>Start a different insertion</Button> : null}
        </div>
      </DialogContent>
    </Dialog>
    {documentId ? <><p role="status" className="text-ui">One model result added with its pinned run and dataset.</p><Link className="text-accent underline" href={`/workspace/research/${documentId}`}>Open research</Link></> : null}
  </div>;
}
