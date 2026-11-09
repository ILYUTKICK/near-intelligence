"use client";
import Link from "next/link";
import { useCallback, useId, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { createDocument, getDocument, listDocuments } from "@/features/documents/list/documents-api";
import { useOwnedData } from "../saved/use-owned-data";
import type { SaveInput } from "../saved/api";
import { insertChart, type InsertChartInput } from "./api";

export function AddChartToResearch({ input, suspended = false }: { input: SaveInput; suspended?: boolean }) {
  const payload: InsertChartInput = { chart_definition_version_id: input.chart_definition_version_id,
    dataset_version_id: input.dataset_version_id, selection: input.selection, mode: input.mode,
    ...(input.snapshot_id ? { snapshot_id: input.snapshot_id } : {}) };
  return <ResearchDestination kind="chart" pin={payload} suspended={suspended}
    prepare={() => async (id, revision, key, signal) => (await insertChart(id, revision, payload, key, signal)).document.id} />;
}

type Insert = (documentId: string, revision: number, key: string, signal: AbortSignal) => Promise<string>;

export function ResearchDestination({ kind, pin, prepare, suspended = false, fields, canConfirm = true, onDestinationChange, onBegin, onInserted }: {
  kind: "chart" | "insight";
  pin: Pick<InsertChartInput, "dataset_version_id" | "selection">;
  prepare: () => Insert;
  suspended?: boolean;
  fields?: (destination: string, signal: AbortSignal | null) => ReactNode;
  canConfirm?: boolean;
  onDestinationChange?: () => void;
  onBegin?: () => void;
  onInserted?: () => void;
}) {
  const id = useId();
  const isChart = kind === "chart";
  // Keep the entire confirmed attempt above the modal subtree. Revalidation
  // hides the modal, but same-account retries retain both creation/insertion
  // keys, destination, title and any already acknowledged result.
  const [open, setOpen] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [destination, setDestination] = useState("new");
  const [title, setTitle] = useState(isChart ? "Research with chart" : "Research with insight");
  const [pending, setPending] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<{ key: string; createKey: string; title: string; documentId: string | null; insert: Insert } | null>(null);
  const busy = useRef(false);
  const loader = useCallback((signal: AbortSignal) => open && !suspended
    ? listDocuments({ query, cursor, signal }) : Promise.resolve({ items: [], nextCursor: null }), [open, suspended, query, cursor]);
  const { data, loading, error: loadError, reload, signal } = useOwnedData(loader, "research documents");

  function chooseDestination(value: string) {
    setDestination(value);
    onDestinationChange?.();
  }

  function resetAttempt() {
    request.current = null; setConfirmed(false); setError(null);
  }
  function changeOpen(next: boolean) {
    if (busy.current) return;
    if (next && documentId) { resetAttempt(); setDocumentId(null); }
    if (next && !request.current) onBegin?.();
    setOpen(next);
  }
  async function confirm() {
    if (suspended || busy.current || !signal || signal.aborted || !canConfirm) return;
    busy.current = true; setPending(true); setConfirmed(true); setError(null);
    request.current ??= { key: crypto.randomUUID(), createKey: crypto.randomUUID(), title: title.trim(),
      documentId: destination === "new" ? null : destination, insert: prepare() };
    const attempt = request.current;
    try {
      if (!attempt.documentId) {
        attempt.documentId = (await createDocument({ title: attempt.title, idempotencyKey: attempt.createKey, signal })).id;
      }
      signal.throwIfAborted();
      const current = await getDocument(attempt.documentId, signal);
      signal.throwIfAborted();
      const insertedId = await attempt.insert(current.id, current.revision, attempt.key, signal);
      signal.throwIfAborted();
      setDocumentId(insertedId); setOpen(false); onInserted?.();
    } catch (error) { setError(signal.aborted ? "The request was interrupted. Retry the same insertion."
      : error instanceof Error ? error.message : "The insertion failed. Try again."); }
    finally { busy.current = false; setPending(false); }
  }
  const frozen = pending || confirmed;
  if (suspended) return null;
  return <div className="flex flex-col gap-2">
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild><Button variant="secondary">{isChart ? "Add to research" : "Add Insight"}</Button></DialogTrigger>
      <DialogContent className="max-h-[90dvh] overflow-y-auto">
        <DialogTitle>{isChart ? "Add chart to your research" : "Add insight to your research"}</DialogTitle>
        <DialogDescription>Choose an owned destination. The inspected dataset, range and filters are pinned when you confirm.</DialogDescription>
        <div className="mt-4 space-y-4">
          <p className="break-all text-metadata text-text-secondary">Inspected dataset: {pin.dataset_version_id}</p>
          <p className="text-ui">{pin.selection.start} through {pin.selection.end} (UTC, end exclusive). Filters: {Object.entries(pin.selection.filters).map(([key, value]) => `${key}: ${value}`).join("; ") || "none"}.</p>
          <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); setQuery(draft); setCursor(null); chooseDestination("new"); }}>
            <div className="min-w-0 flex-1"><Label htmlFor={`${id}-search`}>Find your research</Label><Input id={`${id}-search`} value={draft} maxLength={200} disabled={frozen} onChange={(event) => setDraft(event.target.value)} /></div>
            <Button type="submit" variant="secondary" disabled={frozen}>Search</Button>
          </form>
          {loading ? <p role="status">Loading your research…</p> : null}
          {loadError ? <div role="alert"><p>{loadError}</p><Button variant="secondary" onClick={reload}>Try loading again</Button></div> : null}
          <div><Label htmlFor={`${id}-destination`}>Destination</Label>
            <select id={`${id}-destination`} className="w-full min-h-11 rounded-control border border-control-border bg-surface px-3 text-body" value={destination} disabled={frozen} onChange={(event) => chooseDestination(event.target.value)}>
              <option value="new">Create new research</option>
              {data?.items.map((document) => <option key={document.id} value={document.id}>{document.title}</option>)}
            </select>
          </div>
          {data?.nextCursor ? <Button variant="quiet" disabled={frozen} onClick={() => { setCursor(data.nextCursor); chooseDestination("new"); }}>Next destinations</Button> : null}
          {cursor ? <Button variant="quiet" disabled={frozen} onClick={() => { setCursor(null); chooseDestination("new"); }}>First destinations</Button> : null}
          {destination === "new" ? <div><Label htmlFor={`${id}-title`}>New research title</Label><Input id={`${id}-title`} value={title} maxLength={200} disabled={frozen} onChange={(event) => setTitle(event.target.value)} /></div> : null}
          {data?.items.length === 0 ? <p className="text-ui text-text-secondary">No existing research matches. You can create a new document above.</p> : null}
          {fields ? <fieldset disabled={frozen}>{fields(destination, signal)}</fieldset> : null}
          {error ? <p role="alert" className="text-danger text-ui">{error}</p> : null}
          <Button onClick={() => void confirm()} pending={pending} disabled={!canConfirm || !signal || loading || Boolean(loadError) || (destination === "new" && !title.trim())}>{confirmed ? "Retry confirmed insertion" : isChart ? "Confirm Add Chart" : "Confirm Add Insight"}</Button>
          {error && !pending ? <Button variant="quiet" onClick={resetAttempt}>Start a different insertion</Button> : null}
        </div>
      </DialogContent>
    </Dialog>
    {documentId ? <><p role="status" className="text-ui">{isChart ? "One chart" : "One insight"} added with its inspected context.</p><Link className="text-accent underline" href={`/workspace/research/${documentId}`}>Open research</Link></> : null}
  </div>;
}
