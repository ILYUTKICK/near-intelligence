"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { freezeSnapshot, type FreezeInput } from "./api";

/**
 * Freeze control (NI-044): turns the inspected evidence triple — the pinned
 * definition version, the inspected dataset version and the validated
 * selection — into one immutable owner-scoped snapshot. Freezing never
 * changes the live chart, the saved-chart list or any document revision; the
 * confirmation links to the owner's snapshot list.
 */
export function FreezeSnapshotButton({ input, suspended = false }: { input: FreezeInput; suspended?: boolean }) {
  const key = useRef<string | null>(null);
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [frozenId, setFrozenId] = useState<string | null>(null);
  async function freeze() {
    if (suspended || inFlight.current || frozenId) return;
    inFlight.current = true; setPending(true); setError(null);
    key.current ??= crypto.randomUUID();
    try { setFrozenId((await freezeSnapshot(input, key.current)).id); }
    catch (error) { setError(error instanceof Error ? error.message : "The snapshot could not be frozen."); }
    finally { inFlight.current = false; setPending(false); }
  }
  // Keep the attempt mounted while the same account is being revalidated.
  if (suspended) return null;
  return <div className="flex flex-col gap-2">
    {frozenId ? <Link href="/workspace/saved-charts/snapshots" className="text-accent underline">Open snapshots</Link>
      : <Button variant="secondary" onClick={freeze} pending={pending}>Freeze snapshot</Button>}
    {frozenId ? <p role="status" className="text-ui">Snapshot frozen. Its selection, dataset pin and content hash are fixed.</p> : null}
    {error ? <p role="alert" className="text-ui text-danger">{error}</p> : null}
  </div>;
}
