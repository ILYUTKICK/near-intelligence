"use client";
import Link from "next/link";
import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { getSaved } from "./api";
import { useOwnedData } from "./use-owned-data";

export function SavedChartDetail({ instanceId }: { instanceId: string }) {
  const loader = useCallback((signal: AbortSignal) => getSaved(instanceId, signal), [instanceId]);
  const { data, loading, error, reload } = useOwnedData(loader);
  return <section className="min-w-0 max-w-full space-y-4">
    <Link href="/workspace/saved-charts" className="text-accent underline">Saved Charts</Link>
    <h1 className="break-words font-serif text-display">{data?.saved_chart.label ?? "Saved chart"}</h1>
    {loading ? <p role="status">Loading saved chart…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    <Button variant="secondary" onClick={reload} pending={loading}>Refresh live view</Button>
    {data ? <>
      <p className="break-words text-ui text-text-secondary">Live view · latest approved dataset {data.view.dataset.id}. Your saved definition, range and filters are retained.</p>
      {data.dataset_changed ? <p role="status" className="text-ui">Data changed since the last saved-chart observation. This view uses the newer approved dataset.</p> : null}
      <ChartView definition={data.view.definition} view={data.view} mode="live" selection={{ start: data.saved_chart.selection.start, end: data.saved_chart.selection.end, filters: data.saved_chart.selection.filters }} />
    </> : null}
  </section>;
}
