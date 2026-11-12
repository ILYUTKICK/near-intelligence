"use client";

import Link from "next/link";
import { useCallback, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { createDocument, DocumentApiError, getDocument, listDocuments } from "@/features/documents/list/documents-api";
import { MAX_BODY_PLAIN_CHARS } from "@/features/editor/canonical";
import { useOwnedData } from "@/features/charts/saved/use-owned-data";
import { usePublicSession } from "@/lib/auth/use-public-session";
import { insertModel, interpretationLines, type InsertModelInput } from "./api";
import type { ModelRunSummary } from "../models-schema";

type RunIdentity = Pick<ModelRunSummary, "run_id" | "model_id" | "model_version" | "gate_verdict">;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function AddModelToResearch({ run }: { run: RunIdentity }) {
  const { session, recheck } = usePublicSession();
  if (session.status === "anonymous") {
    const next = `/models/${encodeURIComponent(run.run_id)}`;
    return <Button variant="secondary" asChild>
      <Link href={`/login?next=${encodeURIComponent(next)}`}>Sign in to add this model result</Link>
    </Button>;
  }
  return <>
    {session.subject ? <ModelDestinationPicker key={`${session.subject}:${run.run_id}`} run={run}
      accountSignal={session.status === "authenticated" ? session.signal : null} /> : null}
    {session.status === "unknown" ? <div className="flex items-center gap-2">
      <p role="status">The sign-in state could not be checked.</p>
      <Button variant="quiet" onClick={recheck}>Retry sign-in check</Button>
    </div> : null}
  </>;
}

function ModelDestinationPicker({ run, accountSignal }: { run: RunIdentity; accountSignal: AbortSignal | null }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [destination, setDestination] = useState("new");
  const [createdDestination, setCreatedDestination] = useState<{ id: string; title: string } | null>(null);
  const [title, setTitle] = useState("Research with model result");
  const [datasetVersionId, setDatasetVersionId] = useState("");
  const [interpretation, setInterpretation] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<{ key: string; createKey: string; title: string; documentId: string | null; input: InsertModelInput } | null>(null);
  const busy = useRef(false);
  const loader = useCallback((signal: AbortSignal) => open && accountSignal
    ? listDocuments({ query, cursor, signal: AbortSignal.any([signal, accountSignal]) })
    : Promise.resolve({ items: [], nextCursor: null }), [open, accountSignal, query, cursor]);
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
    if (!accountSignal || !signal || accountSignal.aborted || signal.aborted || busy.current || !canConfirm) return;
    const operationSignal = AbortSignal.any([signal, accountSignal]);
    busy.current = true; setPending(true); setConfirmed(true); setError(null);
    request.current ??= { key: crypto.randomUUID(), createKey: crypto.randomUUID(),
      title: title.trim(), documentId: destination === "new" ? null : destination,
      input: { model_run_id: run.run_id, dataset_version_id: datasetVersionId.trim().toLowerCase(), interpretation: interpretationLines(interpretation) } };
    const attempt = request.current;
    try {
      if (!attempt.documentId) {
        const created = await createDocument({ title: attempt.title, idempotencyKey: attempt.createKey, signal: operationSignal });
        operationSignal.throwIfAborted();
        attempt.documentId = created.id;
        setCreatedDestination({ id: created.id, title: created.title });
        setDestination(created.id);
      }
      const current = await getDocument(attempt.documentId, operationSignal);
      operationSignal.throwIfAborted();
      const inserted = await insertModel(attempt.documentId, current.revision, attempt.input, attempt.key, operationSignal);
      operationSignal.throwIfAborted();
      setDocumentId(inserted.document.id);
      setOpen(false);
    } catch (error) {
      if (!operationSignal.aborted && error instanceof DocumentApiError && error.status === 422 && error.code !== "UNKNOWN_ERROR") {
        request.current = null;
        setConfirmed(false);
      }
      setError(operationSignal.aborted ? "The request was interrupted. Retry the same insertion."
        : error instanceof Error ? error.message : "The insertion failed. Try again.");
    }
    finally { busy.current = false; setPending(false); }
  }
  const frozen = pending || confirmed;
  const canConfirm = UUID_PATTERN.test(datasetVersionId.trim()) && interpretation.trim().length > 0
    && (destination !== "new" || title.trim().length > 0);
  if (!accountSignal) return null;
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
          </dl>
          <div>
            <Label htmlFor={`${id}-dataset`}>Approved dataset version (UUID)</Label>
            <Input id={`${id}-dataset`} value={datasetVersionId} maxLength={36} disabled={frozen}
              onChange={event => setDatasetVersionId(event.target.value)}
              aria-invalid={datasetVersionId.length > 0 && !UUID_PATTERN.test(datasetVersionId.trim())} />
            <p className="mt-1 text-metadata text-text-secondary">Choose the approved dataset version your interpretation reads against.</p>
          </div>
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
              {createdDestination && !data?.items.some(document => document.id === createdDestination.id)
                ? <option value={createdDestination.id}>{createdDestination.title}</option> : null}
              {data?.items.map((document) => <option key={document.id} value={document.id}>{document.title}</option>)}
            </select>
          </div>
          {data?.nextCursor ? <Button variant="quiet" disabled={frozen} onClick={() => { setCursor(data.nextCursor); setDestination("new"); }}>Next destinations</Button> : null}
          {cursor ? <Button variant="quiet" disabled={frozen} onClick={() => { setCursor(null); setDestination("new"); }}>First destinations</Button> : null}
          {destination === "new" ? <div><Label htmlFor={`${id}-title`}>New research title</Label><Input id={`${id}-title`} value={title} maxLength={200} disabled={frozen} onChange={(event) => setTitle(event.target.value)} /></div> : null}
          {data?.items.length === 0 ? <p className="text-ui text-text-secondary">No existing research matches. You can create a new document above.</p> : null}
          {error ? <p role="alert" className="text-danger text-ui">{error}</p> : null}
          <Button onClick={() => void confirm()} pending={pending} disabled={!canConfirm || !signal || loading || Boolean(loadError)}>
            {confirmed ? "Retry confirmed insertion" : "Confirm Add Model"}</Button>
        </div>
      </DialogContent>
    </Dialog>
    {documentId ? <><p role="status" className="text-ui">One model result added with its pinned run and dataset.</p><Link className="text-accent underline" href={`/workspace/research/${documentId}`}>Open research</Link></> : null}
  </div>;
}
