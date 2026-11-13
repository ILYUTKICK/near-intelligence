"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { LoadingPanel } from "@/components/data-state/DataState";
import { PageIntro } from "@/components/layout/PageIntro";
import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { deleteSnapshot, getSnapshot, listSnapshots, type Snapshot, type SnapshotDetail } from "./api";
import { useOwnedData } from "../saved/use-owned-data";

/** Owner-scoped storage metadata shown with every frozen snapshot. */
function SnapshotMetadata({ snapshot }: { snapshot: Snapshot }) {
  return <div className="space-y-1 text-metadata text-text-secondary">
    <p>Frozen {new Date(snapshot.created_at).toISOString().replace("T", " ").slice(0, 16)} UTC</p>
    <p>Dataset pin {snapshot.dataset_version_id}</p>
    <p className="break-all">Content hash {snapshot.content_sha256}</p>
  </div>;
}

/** Small frozen preview; failures never block list management. */
function SnapshotPreview({ snapshotId, sessionSignal }: { snapshotId: string; sessionSignal: AbortSignal }) {
  const [detail, setDetail] = useState<SnapshotDetail | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, sessionSignal]);
    void getSnapshot(snapshotId, signal).then((value) => {
      if (!signal.aborted) setDetail(value);
    }, () => {
      if (!signal.aborted) setFailed(true);
    });
    return () => controller.abort();
  }, [snapshotId, sessionSignal]);

  if (failed) return <p className="text-metadata text-text-secondary">Open the snapshot to retry loading its data.</p>;
  if (!detail) return <LoadingPanel label="Loading frozen selection" />;
  return (
    <ChartView
      definition={detail.view.definition}
      view={detail.view}
      selection={detail.snapshot.selection}
      mode="historical"
      height={208}
      className="border-0 bg-transparent p-0 shadow-none lg:p-0"
    />
  );
}

function SnapshotItem({ snapshot, reload, previewSignal }: { snapshot: Snapshot; reload: () => void; previewSignal?: AbortSignal }) {
  const [pending, setPending] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function remove() {
    if (pending) return;
    setPending(true); setError(null);
    try {
      await deleteSnapshot(snapshot.id);
      reload();
    } catch (error) { setError(error instanceof Error ? error.message : "The removal failed."); }
    finally { setPending(false); }
  }
  return <li className="paper-panel min-w-0 space-y-3 p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <h2 className="text-heading">
        <Link href={`/workspace/saved-charts/snapshots/${snapshot.id}`} className="text-text hover:underline [overflow-wrap:anywhere]">Frozen chart snapshot</Link>
      </h2>
      <span className="rounded-full bg-sage px-2.5 py-1 text-metadata font-medium text-accent">Immutable snapshot</span>
    </div>
    <p className="text-ui text-text-secondary">{snapshot.selection.start} through {snapshot.selection.end} (UTC, end exclusive)</p>
    <p className="text-ui text-text-secondary">{Object.entries(snapshot.selection.filters).map(([key, value]) => `${key}: ${value}`).join(" · ") || "No filters"}</p>
    <SnapshotMetadata snapshot={snapshot} />
    {previewSignal ? <SnapshotPreview snapshotId={snapshot.id} sessionSignal={previewSignal} /> : null}
    <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
      <Button asChild variant="secondary"><Link href={`/workspace/saved-charts/snapshots/${snapshot.id}`}>Open snapshot</Link></Button>
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogTrigger asChild><Button variant="quiet" disabled={pending}>Remove</Button></DialogTrigger>
        <DialogContent>
          <DialogTitle>Remove this snapshot?</DialogTitle>
          <DialogDescription>This deletes the frozen evidence copy. A snapshot a saved chart still references cannot be removed.</DialogDescription>
          {error ? <p role="alert" className="mt-3 text-ui text-danger">{error}</p> : null}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirm(false)}>Cancel</Button>
            <Button variant="destructive" pending={pending} onClick={() => void remove()}>Confirm removal</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
    {error && !confirm ? <p role="alert" className="text-danger text-ui">{error}</p> : null}
  </li>;
}

export function Snapshots() {
  const [cursor, setCursor] = useState<string | null>(null);
  const loader = useCallback((signal: AbortSignal) => listSnapshots(cursor, signal), [cursor]);
  const { data, loading, error, reload, signal } = useOwnedData(loader, "snapshots");
  return <div className="min-w-0 space-y-6">
    <PageIntro compact eyebrow="Chart snapshots" title="Evidence frozen on purpose."
      description="A snapshot keeps one inspected dataset version and selection fixed. Nothing here refreshes on its own."
      action={<Button asChild variant="secondary"><Link href="/workspace/saved-charts">Back to Saved Charts</Link></Button>} />
    {loading ? <LoadingPanel label="Loading snapshots" /> : null}
    {error ? <div role="alert" className="paper-panel space-y-3 p-6"><p>{error}</p><Button variant="secondary" onClick={reload}>Try again</Button></div> : null}
    {data?.items.length === 0 ? (
      <div className="paper-panel p-9 text-center">
        <ProductIcon name="shield" className="mx-auto mb-3 size-7 text-accent" />
        <p role="status" className="font-serif text-heading">No snapshots yet.</p>
        <p className="mt-2 text-ui text-text-secondary">
          Freeze one from any <Link href="/workspace/charts" className="underline">chart detail</Link> once you have resolved a view.
        </p>
      </div>
    ) : null}
    {data?.items.length ? <ul className="grid items-start gap-5 lg:grid-cols-2">
      {data.items.map((snapshot, index) => (
        <SnapshotItem key={snapshot.id} snapshot={snapshot} reload={reload} previewSignal={index < 2 ? signal ?? undefined : undefined} />
      ))}
    </ul> : null}
    {data?.next_cursor ? <Button variant="secondary" onClick={() => setCursor(data.next_cursor)}>Next page</Button> : null}
    {cursor ? <Button variant="quiet" onClick={() => setCursor(null)}>Back to first page</Button> : null}
  </div>;
}
