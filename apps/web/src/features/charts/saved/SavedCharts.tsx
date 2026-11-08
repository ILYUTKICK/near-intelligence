"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { deleteSaved, listSaved, renameSaved, type SavedChart } from "./api";
import { useOwnedData } from "./use-owned-data";

function SavedItem({ chart, reload }: { chart: SavedChart; reload: () => void }) {
  const [label, setLabel] = useState(chart.label ?? "");
  const [pending, setPending] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function mutate(remove: boolean) {
    if (pending) return;
    setPending(true); setError(null);
    try {
      if (remove) await deleteSaved(chart.id); else await renameSaved(chart.id, label.trim() || null);
      reload();
    } catch (error) { setError(error instanceof Error ? error.message : "The change failed."); }
    finally { setPending(false); }
  }
  return <li className="rounded-surface border border-border bg-surface p-4 space-y-3">
    <Link href={`/workspace/saved-charts/${chart.id}`} className="text-accent underline font-medium">{chart.label ?? "Untitled saved chart"}</Link>
    <p className="text-ui text-text-secondary">Live · {chart.selection.start} through {chart.selection.end} (UTC, end exclusive)</p>
    <p className="text-ui text-text-secondary">{Object.entries(chart.selection.filters).map(([key, value]) => `${key}: ${value}`).join(" · ") || "No filters"}</p>
    <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); void mutate(false); }}>
      <div><Label htmlFor={`saved-label-${chart.id}`}>Label</Label><Input id={`saved-label-${chart.id}`} value={label} maxLength={200} onChange={(event) => setLabel(event.target.value)} /></div>
      <Button type="submit" variant="secondary" pending={pending}>Update label</Button>
      <Button type="button" variant="quiet" onClick={() => setConfirm(true)} disabled={pending}>Remove</Button>
    </form>
    {confirm ? <div role="group" aria-label="Confirm chart removal" className="flex flex-wrap items-center gap-2">
      <p>Remove this saved chart?</p><Button variant="secondary" pending={pending} onClick={() => void mutate(true)}>Confirm removal</Button><Button variant="quiet" onClick={() => setConfirm(false)}>Cancel</Button>
    </div> : null}
    {error ? <p role="alert" className="text-danger text-ui">{error}</p> : null}
  </li>;
}

export function SavedCharts() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const loader = useCallback((signal: AbortSignal) => listSaved(query, cursor, signal), [query, cursor]);
  const { data, loading, error, reload } = useOwnedData(loader);
  return <section aria-labelledby="saved-title" className="max-w-3xl space-y-4">
    <h1 id="saved-title" className="font-serif text-display">Saved Charts</h1>
    <p className="text-body text-text-secondary">Resume a saved range and filters. Live views resolve the latest approved dataset and label changes.</p>
    <form className="flex gap-2 items-end" onSubmit={(event) => { event.preventDefault(); setCursor(null); setQuery(search); }}>
      <div className="flex-1"><Label htmlFor="saved-search">Search saved charts</Label><Input id="saved-search" value={search} maxLength={200} onChange={(event) => setSearch(event.target.value)} /></div><Button type="submit">Search</Button>
    </form>
    {loading ? <p role="status">Loading saved charts…</p> : null}
    {error ? <div role="alert"><p>{error}</p><Button variant="secondary" onClick={reload}>Try again</Button></div> : null}
    {data?.items.length === 0 ? <p>No saved charts match this selection. <Link href="/charts" className="text-accent underline">Explore the chart library</Link> to save a chart.</p> : null}
    {data ? <ul className="space-y-4">{data.items.map((chart) => <SavedItem key={chart.id} chart={chart} reload={reload} />)}</ul> : null}
    {data?.next_cursor ? <Button variant="secondary" onClick={() => setCursor(data.next_cursor)}>Next page</Button> : null}
    {cursor ? <Button variant="quiet" onClick={() => setCursor(null)}>Back to first page</Button> : null}
  </section>;
}
