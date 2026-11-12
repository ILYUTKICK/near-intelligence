"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { LoadingPanel } from "@/components/data-state/DataState";
import { PageIntro } from "@/components/layout/PageIntro";
import { Button } from "@/components/ui/button";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { compareSnapshot, deleteSnapshot, getSnapshot, type SnapshotCompare } from "./api";
import { useOwnedData } from "../saved/use-owned-data";

/**
 * Snapshot detail (NI-044): renders the FROZEN view — the pinned dataset
 * version and stored selection — through the shared renderer in historical
 * mode, shows the owner-scoped storage metadata and offers the explicit
 * compare-to-live read. Comparing never rewrites the snapshot, and removal
 * refuses a snapshot a saved chart still references (typed 409).
 */
export function SnapshotDetail({ snapshotId }: { snapshotId: string }) {
  const loader = useCallback((signal: AbortSignal) => getSnapshot(snapshotId, signal), [snapshotId]);
  const { data, loading, error, reload } = useOwnedData(loader, "snapshots");
  const [comparison, setComparison] = useState<SnapshotCompare | null>(null);
  const [comparePending, setComparePending] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [removed, setRemoved] = useState(false);

  async function compareLive() {
    if (comparePending) return;
    setComparePending(true); setCompareError(null);
    try { setComparison(await compareSnapshot(snapshotId)); }
    catch (error) { setCompareError(error instanceof Error ? error.message : "The comparison failed."); }
    finally { setComparePending(false); }
  }
  async function remove() {
    if (removed) return;
    setRemoveError(null);
    try {
      await deleteSnapshot(snapshotId);
      setRemoved(true);
    } catch (error) { setRemoveError(error instanceof Error ? error.message : "The removal failed."); }
  }

  if (removed) {
    return <section className="min-w-0 max-w-full space-y-4">
      <PageIntro compact eyebrow="Chart snapshot" title="Snapshot removed."
        action={<Button asChild variant="secondary"><Link href="/workspace/saved-charts/snapshots">Back to snapshots</Link></Button>} />
      <p role="status" className="paper-panel p-6 text-ui">The frozen copy is deleted. Saved charts that referenced it stay untouched.</p>
    </section>;
  }
  return <section className="min-w-0 max-w-full space-y-4">
    <PageIntro compact eyebrow="Chart snapshot" title={data ? data.view.definition.title : "Frozen snapshot"}
      action={<Button asChild variant="secondary"><Link href="/workspace/saved-charts/snapshots">Back to snapshots</Link></Button>} />
    {loading ? <LoadingPanel label="Loading snapshot" /> : null}
    {error ? <p role="alert" className="paper-panel p-6 text-danger">{error}</p> : null}
    {error ? <Button variant="secondary" onClick={reload}>Try again</Button> : null}
    {data ? <>
      <p className="break-words text-ui text-text-secondary">
        Frozen view · pinned dataset {data.snapshot.dataset_version_id}. This view never adopts newer data.
      </p>
      <div className="paper-panel space-y-1 p-5 text-metadata text-text-secondary">
        <p>Frozen {new Date(data.snapshot.created_at).toISOString().replace("T", " ").slice(0, 16)} UTC</p>
        <p>Dataset pin {data.snapshot.dataset_version_id} (approved)</p>
        <p className="break-all">Content hash {data.snapshot.content_sha256}</p>
        <p className="break-all">Context hash {data.snapshot.calculation_context.context_hash}</p>
        <p>Renderer {data.snapshot.calculation_context.renderer_version}</p>
      </div>
      <ChartView definition={data.view.definition} view={data.view} mode="historical"
        selection={data.snapshot.selection} />
      {comparison ? <>
        <h2 className="text-heading">Compare to live</h2>
        <p className="text-ui text-text-secondary">
          {comparison.dataset_changed
            ? "The latest approved dataset differs from the pinned one. The frozen snapshot is unchanged."
            : "The latest approved dataset is the same one this snapshot pins."}
        </p>
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="min-w-0 space-y-2">
            <h3 className="text-ui font-medium">Frozen snapshot</h3>
            <ChartView definition={comparison.frozen_view.definition} view={comparison.frozen_view}
              mode="historical" selection={data.snapshot.selection} height={260}
              className="border-0 bg-transparent p-0 shadow-none lg:p-0" />
          </div>
          <div className="min-w-0 space-y-2">
            <h3 className="text-ui font-medium">Latest live view</h3>
            <ChartView definition={comparison.live_view.definition} view={comparison.live_view}
              mode="live" selection={data.snapshot.selection} height={260}
              className="border-0 bg-transparent p-0 shadow-none lg:p-0" />
          </div>
        </div>
      </> : null}
      {compareError ? <p role="alert" className="text-ui text-danger">{compareError}</p> : null}
      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button variant="secondary" onClick={() => void compareLive()} pending={comparePending}>
          {comparison ? "Refresh comparison" : "Compare to live"}
        </Button>
        <Button variant="quiet" onClick={() => void remove()}>Remove snapshot</Button>
      </div>
      {removeError ? <p role="alert" className="text-ui text-danger">{removeError}</p> : null}
    </> : null}
  </section>;
}
