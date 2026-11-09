import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { shortId } from "../blocks/display";
import { listEvidenceTargets, type EvidenceTargetPage, type PublicEvidenceKind } from "./api";
import type { EvidenceOption } from "./options";

export const evidenceControl = "w-full min-h-11 rounded-control border border-control-border bg-surface px-3 py-2 text-body text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

interface TargetSelectProps {
  id: string;
  value: string;
  onChange: (id: string) => void;
  options: readonly EvidenceOption[];
  allowCurrent?: boolean;
}

export function EvidenceTargetSelect({ id, value, onChange, options, allowCurrent }: TargetSelectProps) {
  const showCurrent = Boolean(allowCurrent && value && !options.some(option => option.id === value));
  return <div>
    <Label htmlFor={id}>Evidence target</Label>
    <select id={id} className={evidenceControl} value={value} onChange={event => onChange(event.target.value)} required>
      <option value="">Choose a target</option>
      {showCurrent ? <option value={value}>Selected public target · {shortId(value)}</option> : null}
      {options.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
    </select>
  </div>;
}

export function PublicEvidenceTargetPicker({ documentId, kind, signal, ...props }:
  Omit<TargetSelectProps, "options" | "allowCurrent"> & { documentId: string; kind: PublicEvidenceKind; signal: AbortSignal }) {
  const [request, setRequest] = useState<{ cursor?: string; attempt: number }>({ attempt: 0 });
  const [page, setPage] = useState<EvidenceTargetPage>({ items: [], next_cursor: null });
  const [pending, setPending] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const local = new AbortController();
    const requestSignal = AbortSignal.any([signal, local.signal]);
    void listEvidenceTargets(documentId, kind, request.cursor, requestSignal).then(next => {
      if (requestSignal.aborted) return;
      setPage(previous => ({ ...next, items: request.cursor
        ? [...new Map([...previous.items, ...next.items].map(option => [option.id, option])).values()]
        : next.items }));
      setPending(false);
    }).catch(() => {
      if (requestSignal.aborted) return;
      setError("Public evidence targets could not be loaded.");
      setPending(false);
    });
    return () => local.abort();
  }, [documentId, kind, request, signal]);

  function requestPage(cursor?: string) {
    setError(null);
    setPending(true);
    setRequest(previous => ({ cursor, attempt: previous.attempt + 1 }));
  }

  return <div className="space-y-2">
    <EvidenceTargetSelect {...props} options={page.items} allowCurrent />
    {pending ? <p role="status" className="text-metadata text-text-secondary">Loading public targets…</p> : null}
    {!pending && !error && page.items.length === 0 ? <p className="text-metadata text-text-secondary">No public targets of this kind are available.</p> : null}
    {error ? <div>
      <p role="alert" className="text-metadata text-danger">{error}</p>
      <Button variant="quiet" onClick={() => requestPage(request.cursor)}>Retry targets</Button>
    </div> : null}
    {page.next_cursor && !error ? <Button variant="quiet" disabled={pending}
      onClick={() => requestPage(page.next_cursor ?? undefined)}>Load more targets</Button> : null}
  </div>;
}
