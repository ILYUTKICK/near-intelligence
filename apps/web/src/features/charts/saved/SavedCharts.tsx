"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { LoadingPanel } from "@/components/data-state/DataState";
import { PageIntro } from "@/components/layout/PageIntro";
import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { deleteSaved, getSaved, listSaved, renameSaved, type SavedChart, type SavedDetail } from "./api";
import { useOwnedData } from "./use-owned-data";

/**
 * Saved-card preview (NI-078, NI-076 D4): every card carries the same
 * bounded plot preview through the shared renderer. The detail fetch is
 * lazy — it fires only when the card approaches the viewport (an
 * IntersectionObserver; without the API it resolves immediately), so a long
 * list never fetches off-screen cards, and every fetch honours the session
 * signal (account changes abort stale previews). The saved frozen view is
 * rendered through the controlled `view` prop — no re-resolve.
 */
function SavedChartPreview({ chartId, sessionSignal }: { chartId: string; sessionSignal: AbortSignal }) {
  const [detail, setDetail] = useState<SavedDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [host, setHost] = useState<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!host) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px" },
    );
    observer.observe(host);
    return () => observer.disconnect();
  }, [host]);
  useEffect(() => {
    if (!visible) return;
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, sessionSignal]);
    void getSaved(chartId, signal).then((value) => {
      if (!signal.aborted) setDetail(value);
    }, () => {
      if (!signal.aborted) setFailed(true);
    });
    return () => controller.abort();
  }, [chartId, sessionSignal, visible]);

  return (
    <div ref={setHost} className="min-w-0">
      {failed ? <p className="text-metadata text-text-secondary">Open the saved chart to retry loading its data.</p> : null}
      {!failed && !detail ? <LoadingPanel label="Loading saved selection" /> : null}
      {detail ? (
        <ChartView
          definition={detail.view.definition}
          view={detail.view}
          selection={detail.saved_chart.selection}
          mode={detail.saved_chart.mode === "snapshot" ? "historical" : "live"}
          height={208}
          compact
          className="border-0 bg-transparent p-0 shadow-none lg:p-0"
        />
      ) : null}
    </div>
  );
}

function SavedItem({ chart, reload, previewSignal }: { chart: SavedChart; reload: () => void; previewSignal?: AbortSignal }) {
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
  const filtersSummary = Object.entries(chart.selection.filters).map(([key, value]) => `${key}: ${value}`).join(" · ") || "No filters";
  return <li className="paper-panel min-w-0 space-y-3 p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <h2 className="text-heading">
        <Link href={`/workspace/saved-charts/${chart.id}`} className="text-text hover:underline [overflow-wrap:anywhere]">{chart.label ?? "Untitled saved chart"}</Link>
      </h2>
      <span className="rounded-full bg-sage px-2.5 py-1 text-metadata font-medium text-accent">
        {chart.mode === "snapshot" ? "Pinned snapshot" : "Live selection"}
      </span>
    </div>
    {/* One concise context line: period and filters; the plot preview and the
        exact-value disclosure follow below (NI-076 D4). */}
    <p className="text-ui text-text-secondary">
      {chart.selection.start} – {chart.selection.end} (UTC, end exclusive) · {filtersSummary}
    </p>
    {previewSignal ? <SavedChartPreview chartId={chart.id} sessionSignal={previewSignal} /> : null}
    <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
      <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); void mutate(false); }}>
        <div><Label htmlFor={`saved-label-${chart.id}`}>Label</Label><Input id={`saved-label-${chart.id}`} value={label} maxLength={200} onChange={(event) => setLabel(event.target.value)} /></div>
        <Button type="submit" variant="secondary" pending={pending && !confirm}>Update label</Button>
      </form>
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogTrigger asChild><Button variant="quiet" disabled={pending}>Remove</Button></DialogTrigger>
        <DialogContent>
          <DialogTitle>Remove this saved chart?</DialogTitle>
          <DialogDescription>This removes the selection from Saved Charts.</DialogDescription>
          {error ? <p role="alert" className="mt-3 text-ui text-danger">{error}</p> : null}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirm(false)}>Cancel</Button>
            <Button variant="destructive" pending={pending} onClick={() => void mutate(true)}>Confirm removal</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
    {error && !confirm ? <p role="alert" className="text-danger text-ui">{error}</p> : null}
  </li>;
}

export function SavedCharts() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const loader = useCallback((signal: AbortSignal) => listSaved(query, cursor, signal), [query, cursor]);
  const { data, loading, error, reload, signal } = useOwnedData(loader);
  return <div className="min-w-0 space-y-6">
    <PageIntro compact eyebrow="Saved Charts" title="Evidence worth keeping."
      description="Return to a saved range and filters. Live selections resolve the latest approved dataset."
      action={<Button asChild><Link href="/charts">Explore charts <ProductIcon name="arrow" /></Link></Button>} />
    <form role="search" className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); setCursor(null); setQuery(search.trim()); }}>
      <div><Label htmlFor="saved-search">Search saved charts</Label><Input id="saved-search" type="search" value={search} maxLength={200}
        className="rounded-full text-ui" placeholder="Search by label" onChange={(event) => setSearch(event.target.value)} /></div>
      <Button type="submit" variant="secondary">Search</Button>
      {query ? <Button variant="quiet" onClick={() => { setSearch(""); setCursor(null); setQuery(""); }}>Clear</Button> : null}
    </form>
    {loading ? <LoadingPanel label="Loading saved charts" /> : null}
    {error ? <div role="alert" className="paper-panel space-y-3 p-6"><p>{error}</p><Button variant="secondary" onClick={reload}>Try again</Button></div> : null}
    {data?.items.length === 0 ? (
      <div className="paper-panel p-9 text-center">
        <ProductIcon name={query ? "search" : "chart"} className="mx-auto mb-3 size-7 text-accent" />
        <p role="status" className="font-serif text-heading">No saved charts match this selection.</p>
        <p className="mt-2 text-ui text-text-secondary">
          {query ? "Clear the search to see the other saved selections." : <><Link href="/charts" className="underline">Explore the chart library</Link> to save a chart.</>}
        </p>
      </div>
    ) : null}
    {data?.items.length ? <ul className="grid items-start gap-5 lg:grid-cols-2">
      {data.items.map((chart) => (
        <SavedItem key={chart.id} chart={chart} reload={reload} previewSignal={signal ?? undefined} />
      ))}
    </ul> : null}
    {data?.next_cursor ? <Button variant="secondary" onClick={() => setCursor(data.next_cursor)}>Next page</Button> : null}
    {cursor ? <Button variant="quiet" onClick={() => setCursor(null)}>Back to first page</Button> : null}
  </div>;
}
