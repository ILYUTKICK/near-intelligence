import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { downloadBlob } from "../persistence/download";
import { getRevisionChart, getRevisionCsv } from "../revision-api";

export function HistoricalChart({ documentId, versionId, blockId, sessionSignal, instanceLabel }: {
  documentId: string; versionId: string; blockId: string; sessionSignal: AbortSignal;
  instanceLabel?: string;
}) {
  const [view, setView] = useState<Awaited<ReturnType<typeof getRevisionChart>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const download = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([sessionSignal, controller.signal]);
    void getRevisionChart(documentId, versionId, blockId, signal).then(
      result => { if (!signal.aborted) setView(result); },
      cause => { if (!signal.aborted) setError(cause instanceof Error ? cause.message : "Saved chart could not be loaded."); },
    );
    return () => { controller.abort(); download.current?.abort(); };
  }, [documentId, versionId, blockId, sessionSignal, attempt]);

  async function downloadCsv() {
    if (download.current || sessionSignal.aborted) return;
    const controller = new AbortController();
    const signal = AbortSignal.any([sessionSignal, controller.signal]);
    download.current = controller;
    setDownloading(true);
    setDownloadError(null);
    try {
      const csv = await getRevisionCsv(documentId, versionId, blockId, signal);
      if (!signal.aborted) downloadBlob(csv, `chart-${blockId}-revision-${versionId}.csv`);
    } catch (cause) {
      if (!signal.aborted) setDownloadError(cause instanceof Error ? cause.message : "Saved CSV could not be downloaded.");
    } finally {
      download.current = null;
      if (!signal.aborted) setDownloading(false);
    }
  }

  if (error) return <div className="space-y-2">
    <p role="alert">{error}</p>
    <Button variant="secondary" onClick={() => { setError(null); setAttempt(value => value + 1); }}>Retry saved chart</Button>
  </div>;
  if (!view) return <p role="status">Reconstructing saved chart…</p>;
  return <section className="min-w-0 space-y-3" aria-label={`Saved chart evidence${instanceLabel ? ` — ${instanceLabel}` : ""}`}>
    <ChartView definition={view.definition} view={view} selection={view.selection} mode="historical" instanceLabel={instanceLabel} />
    <p className="break-all text-metadata text-text-secondary">Context hash {view.context_hash}</p>
    <Button variant="secondary" aria-disabled={downloading} onClick={downloadCsv}>
      {downloading ? "Downloading CSV…" : "Download saved CSV"}
    </Button>
    {downloadError ? <p role="alert">{downloadError}</p> : null}
  </section>;
}
