"use client";
import Link from "next/link";
import { useCallback } from "react";
import { LoadingPanel } from "@/components/data-state/DataState";
import { PageIntro } from "@/components/layout/PageIntro";
import { Button } from "@/components/ui/button";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { getSaved } from "./api";
import { useOwnedData } from "./use-owned-data";

export function SavedChartDetail({ instanceId }: { instanceId: string }) {
  const loader = useCallback((signal: AbortSignal) => getSaved(instanceId, signal), [instanceId]);
  const { data, loading, error, reload } = useOwnedData(loader);
  return <section className="min-w-0 max-w-full space-y-4">
    <PageIntro compact eyebrow="Saved chart" title={data?.saved_chart.label ?? "Saved chart"}
      action={<Button asChild variant="secondary"><Link href="/workspace/saved-charts">Back to Saved Charts</Link></Button>} />
    {loading ? <LoadingPanel label="Loading saved chart" /> : null}
    {error ? <p role="alert" className="paper-panel p-6 text-danger">{error}</p> : null}
    {data ? <>
      <p className="break-words text-ui text-text-secondary">Live view · latest approved dataset {data.view.dataset.id}. Your saved definition, range and filters are retained.</p>
      {data.dataset_changed ? <p role="status" className="text-ui">Data changed since the last saved-chart observation. This view uses the newer approved dataset.</p> : null}
      <ChartView definition={data.view.definition} view={data.view} mode="live" selection={data.saved_chart.selection}
        actions={<Button variant="secondary" onClick={reload} pending={loading}>Refresh live view</Button>} />
    </> : null}
    {error ? <Button variant="secondary" onClick={reload}>Try again</Button> : null}
  </section>;
}
