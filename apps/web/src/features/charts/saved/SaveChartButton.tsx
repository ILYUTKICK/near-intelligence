"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { saveChart, type SaveInput } from "./api";

export function SaveChartButton({ input, suspended = false }: { input: SaveInput; suspended?: boolean }) {
  const key = useRef<string | null>(null);
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  async function save() {
    if (suspended || inFlight.current || savedId) return;
    inFlight.current = true; setPending(true); setError(null);
    key.current ??= crypto.randomUUID();
    try { setSavedId((await saveChart(input, key.current)).id); }
    catch (error) { setError(error instanceof Error ? error.message : "The chart could not be saved."); }
    finally { inFlight.current = false; setPending(false); }
  }
  // Keep the attempt mounted while the same account is being revalidated.
  if (suspended) return null;
  return <div className="flex flex-col gap-2">
    {savedId ? <Link href={`/workspace/saved-charts/${savedId}`} className="text-accent underline">Open saved chart</Link>
      : <Button variant="secondary" onClick={save} pending={pending}>Save chart</Button>}
    {savedId ? <p role="status" className="text-ui">Chart saved. Your range and filters are preserved.</p> : null}
    {error ? <p role="alert" className="text-ui text-danger">{error}</p> : null}
  </div>;
}
