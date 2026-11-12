"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { LoadingPanel } from "@/components/data-state/DataState";
import { PageIntro } from "@/components/layout/PageIntro";
import { Button } from "@/components/ui/button";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { compareSnapshot, getSnapshot, type FreezeInput, type SnapshotCompare } from "@/features/charts/snapshots/api";
import { FreezeSnapshotButton } from "@/features/charts/snapshots/FreezeSnapshotButton";
import { getSaved, type SavedDetail } from "./api";
import { useOwnedData } from "./use-owned-data";

/**
 * Saved-chart detail (NI-035) with NI-044 snapshot contexts.
 *
 * A ``live`` context resolves the latest approved dataset at read time and
 * offers the Freeze control (the current inspected view becomes one
 * immutable snapshot). A ``snapshot`` context renders the FROZEN view — the
 * referenced snapshot's pinned dataset version, never latest — with its
 * owner-scoped storage metadata and the explicit Compare-to-live read.
 * Neither control rewrites the saved context or the snapshot.
 */
/** The current live context as a freeze request: inspected view triple only. */
function freezeInput(data: SavedDetail): FreezeInput {
  return { chart_definition_version_id: data.view.definition.id, dataset_version_id: data.view.dataset.id,
    selection: { ...data.view.selection, filters: data.saved_chart.selection.filters } };
}

export function SavedChartDetail({ instanceId }: { instanceId: string }) {
  const loader = useCallback((signal: AbortSignal) => getSaved(instanceId, signal), [instanceId]);
  const { data, loading, error, reload } = useOwnedData(loader);
  const [comparison, setComparison] = useState<SnapshotCompare | null>(null);
  const [comparePending, setComparePending] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  const snapshotMode = data?.saved_chart.mode === "snapshot" && data.saved_chart.snapshot_id !== null;
  async function compareLive() {
    if (!data?.saved_chart.snapshot_id || comparePending) return;
    setComparePending(true); setCompareError(null);
    try { setComparison(await compareSnapshot(data.saved_chart.snapshot_id)); }
    catch (error) { setCompareError(error instanceof Error ? error.message : "The comparison failed."); }
    finally { setComparePending(false); }
  }
  return <section className="min-w-0 max-w-full space-y-4">
    <PageIntro compact eyebrow="Saved chart" title={data?.saved_chart.label ?? "Saved chart"}
      action={<Button asChild variant="secondary"><Link href="/workspace/saved-charts">Back to Saved Charts</Link></Button>} />
    {loading ? <LoadingPanel label="Loading saved chart" /> : null}
    {error ? <p role="alert" className="paper-panel p-6 text-danger">{error}</p> : null}
    {data ? <>
      {snapshotMode
        ? <p className="break-words text-ui text-text-secondary">Frozen snapshot view · pinned dataset {data.view.dataset.id}. This context never adopts newer data.</p>
        : <p className="break-words text-ui text-text-secondary">Live view · latest approved dataset {data.view.dataset.id}. Your saved definition, range and filters are retained.</p>}
      {!snapshotMode && data.dataset_changed ? <p role="status" className="text-ui">Data changed since the last saved-chart observation. This view uses the newer approved dataset.</p> : null}
      {snapshotMode && data.saved_chart.snapshot_id ? <SnapshotPanel snapshotId={data.saved_chart.snapshot_id} /> : null}
      <ChartView definition={data.view.definition} view={data.view}
        mode={snapshotMode ? "historical" : "live"} selection={data.saved_chart.selection}
        actions={snapshotMode
          ? <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" onClick={() => void compareLive()} pending={comparePending}>
                {comparison ? "Refresh comparison" : "Compare to live"}
              </Button>
              <Button variant="quiet" onClick={reload} pending={loading}>Re-read frozen view</Button>
            </div>
          : <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" onClick={reload} pending={loading}>Refresh live view</Button>
              <FreezeSnapshotButton input={freezeInput(data)} />
            </div>} />
      {comparison ? <>
        <h2 className="text-heading">Compare to live</h2>
        <p className="text-ui text-text-secondary">
          {comparison.dataset_changed
            ? "The latest approved dataset differs from the pinned one. The frozen snapshot and this saved context are unchanged."
            : "The latest approved dataset is the same one this snapshot pins."}
        </p>
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="min-w-0 space-y-2">
            <h3 className="text-ui font-medium">Frozen snapshot</h3>
            <ChartView definition={comparison.frozen_view.definition} view={comparison.frozen_view}
              mode="historical" selection={data.saved_chart.selection} height={260}
              className="border-0 bg-transparent p-0 shadow-none lg:p-0" />
          </div>
          <div className="min-w-0 space-y-2">
            <h3 className="text-ui font-medium">Latest live view</h3>
            <ChartView definition={comparison.live_view.definition} view={comparison.live_view}
              mode="live" selection={data.saved_chart.selection} height={260}
              className="border-0 bg-transparent p-0 shadow-none lg:p-0" />
          </div>
        </div>
      </> : null}
      {compareError ? <p role="alert" className="text-ui text-danger">{compareError}</p> : null}
    </> : null}
    {error ? <Button variant="secondary" onClick={reload}>Try again</Button> : null}
  </section>;
}

/** Owner-scoped storage metadata for the referenced snapshot (NI-044). */
function SnapshotPanel({ snapshotId }: { snapshotId: string }) {
  const loader = useCallback((signal: AbortSignal) => getSnapshot(snapshotId, signal), [snapshotId]);
  const { data, loading, error } = useOwnedData(loader, "snapshots");
  if (loading) return <LoadingPanel label="Loading snapshot metadata" />;
  if (error || !data) return <p role="status" className="text-metadata text-text-secondary">
    Snapshot metadata is temporarily unavailable; the frozen view above still resolves from the saved context.</p>;
  return <div className="paper-panel space-y-1 p-5 text-metadata text-text-secondary">
    <p>Frozen {new Date(data.snapshot.created_at).toISOString().replace("T", " ").slice(0, 16)} UTC · <Link className="underline" href={`/workspace/saved-charts/snapshots/${snapshotId}`}>Open snapshot</Link></p>
    <p>Dataset pin {data.snapshot.dataset_version_id} (approved)</p>
    <p className="break-all">Content hash {data.snapshot.content_sha256}</p>
  </div>;
}
