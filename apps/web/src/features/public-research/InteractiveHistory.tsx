"use client";

import { createApiClient } from "@near-intelligence/shared-types";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ChartView } from "@/features/charts/renderer/ChartView";
import { formatDecimal } from "@/features/charts/renderer/format";
import { shiftDate } from "@/features/charts/renderer/RangeSelect";
import { researchHistorySchema, type ResearchHistory, type PeriodSummary } from "./history-schema";

type Range = { start: string; end: string };
const sources = [{ id: "SRC-LLAMA", label: "DefiLlama" }, { id: "SRC-DASHBOARD", label: "Intents Dashboard" }];
const exact = (value: string | null) => value === null ? "Not available" : formatDecimal(value);

function PeriodTable({ rows, frequency }: { rows: PeriodSummary[]; frequency: string }) {
  return <div role="region" aria-label={`${frequency} history calculations`} tabIndex={0} className="mt-4 max-h-96 overflow-auto rounded-control border border-border">
    <table className="w-full text-left text-metadata tabular-nums">
      <caption className="p-3 text-left text-text-secondary">Observed subtotals in USD. Only periods with full volume and fee coverage are complete. Effective rate = matched fees ÷ matched volume × 10,000 bps.</caption>
      <thead className="bg-surface-muted"><tr>{["UTC period [start, end)", "Coverage", "Volume (USD)", "Gross fees (USD)", "Effective rate (bps)"].map((label) => <th scope="col" key={label} className="p-3 font-medium">{label}</th>)}</tr></thead>
      <tbody>{rows.map((row) => <tr key={row.start} className="border-t border-border">
        <th scope="row" className="p-3 font-medium">{row.start} → {row.end}</th>
        <td className="p-3">{row.complete ? "Complete" : "Partial"}<br />Volume {row.volume_days}/{row.expected_days}; fees {row.fee_days}/{row.expected_days}; matched {row.matched_days}</td>
        <td className="p-3">{exact(row.volume_usd)}</td><td className="p-3">{exact(row.gross_fees_usd)}</td><td className="p-3">{exact(row.effective_gross_fee_bps)}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

function CustomRange({ current, onChange }: { current: Range; onChange: (range: Range) => void }) {
  const [start, setStart] = useState(current.start);
  const [end, setEnd] = useState(current.end);
  const [error, setError] = useState<string | null>(null);
  return <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={(event) => {
    event.preventDefault();
    const days = (Date.parse(end) - Date.parse(start)) / 86_400_000;
    if (!Number.isFinite(days) || days <= 0 || days > 730) { setError("Choose an end after the start, with at most 730 days."); return; }
    setError(null); onChange({ start, end });
  }}>
    <div><Label htmlFor="history-start">Start date (UTC)</Label><Input id="history-start" type="date" required value={start} onChange={(event) => setStart(event.target.value)} /></div>
    <div><Label htmlFor="history-end">End date (UTC, excluded)</Label><Input id="history-end" type="date" required value={end} onChange={(event) => setEnd(event.target.value)} /></div>
    <Button variant="secondary" type="submit">Apply period</Button>
    {error ? <p role="alert" className="text-ui text-danger">{error}</p> : null}
  </form>;
}

/** One pinned source-qualified panel. Range changes recalculate on the server. */
export function InteractiveHistory() {
  const [source, setSource] = useState("SRC-LLAMA");
  const [range, setRange] = useState<Range | null>(null);
  const [data, setData] = useState<ResearchHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [frequency, setFrequency] = useState("Monthly");
  const pin = useRef<string | null>(null);
  const purchasePin = useRef<ResearchHistory["purchases"] | undefined>(undefined);
  const allRange = useRef<Range | null>(null);
  const chooseRange = (next: Range | null) => { setLoading(true); setError(null); setRange(next); };
  useEffect(() => {
    const controller = new AbortController();
    const client = createApiClient(window.location.origin);
    void client.GET("/api/research/history", { params: { query: {
      source, ...(range ?? {}), ...(pin.current ? { dataset_version: pin.current } : {}),
    } }, signal: controller.signal, cache: "no-store" }).then((result) => {
      if (!result.response.ok) throw new Error("History is unavailable for this selection. Recorded claims below remain available.");
      const parsed = researchHistorySchema.safeParse(result.data);
      if (!parsed.success) throw new Error("The history response could not be verified. No replacement values are shown.");
      if (controller.signal.aborted) return;
      pin.current = parsed.data.volume.dataset.id;
      if (purchasePin.current === undefined) purchasePin.current = parsed.data.purchases;
      allRange.current ??= { start: parsed.data.volume.dataset.start, end: parsed.data.volume.dataset.end };
      setData({ ...parsed.data, purchases: purchasePin.current }); setLoading(false);
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) { setError(cause instanceof Error ? cause.message : "Research history could not be loaded."); setLoading(false); }
    });
    return () => controller.abort();
  }, [source, range, retry]);

  return <section id="interactive-history" aria-labelledby="interactive-history-heading" className="mt-12 min-w-0">
    <p className="eyebrow">The longer view</p><h2 id="interactive-history-heading" className="mt-2 font-serif text-title leading-title">Explore the history behind the thesis</h2>
    <p className="mt-3 max-w-(--width-prose) text-body leading-body text-text-secondary">Follow Intents volume and gross fees across the available history. Observed NEAR purchases remain a separate 90-day cohort. Gross fees are not net protocol revenue.</p>
    <div role="group" aria-label="History source" className="mt-5 flex flex-wrap gap-2">{sources.map((item) => <Button key={item.id} variant={source === item.id ? "primary" : "secondary"} aria-pressed={source === item.id} onClick={() => {
      if (source === item.id) return;
      pin.current = null; purchasePin.current = undefined; allRange.current = null; setLoading(true); setError(null); setData(null); setRange(null); setSource(item.id);
    }}>{item.label}</Button>)}</div>
    {loading ? <p role="status" className="mt-4 text-ui text-text-secondary">Loading the selected history…</p> : null}
    {error ? <div role="alert" className="mt-4 rounded-surface border-2 border-panel-border p-4"><p>{error}</p><Button className="mt-3" variant="secondary" onClick={() => { setLoading(true); setError(null); setRetry((value) => value + 1); }}>Retry history</Button></div> : null}
    {data ? <div aria-busy={loading} className="mt-5">
      <div role="group" aria-label="Research period" className="flex flex-wrap gap-2">
        <Button variant={range === null ? "primary" : "secondary"} onClick={() => { if (range !== null) chooseRange(null); }}>All history</Button>
        {[90, 365].map((days) => <Button variant="secondary" key={days} onClick={() => {
          const end = allRange.current?.end ?? data.volume.dataset.end;
          chooseRange({ start: shiftDate(end, -days), end });
        }}>Last {days} days</Button>)}
      </div>
      <CustomRange key={`${data.summary.start}:${data.summary.end}`} current={data.summary} onChange={chooseRange} />
      <div className="mt-5 rounded-surface bg-sage p-5 text-ui text-text">
        <p className="font-medium">Resolved period: {data.summary.start} → {data.summary.end} UTC (end excluded)</p>
        <p className="mt-2">Volume: {data.summary.volume_days} days · fees: {data.summary.fee_days} days · matched: {data.summary.matched_days} days · source-reported fee zeros: {data.summary.zero_fee_days}.</p>
        <p className="mt-2">Effective gross fee rate: <strong>{exact(data.summary.effective_gross_fee_bps)} bps</strong>, calculated from the sums on matched dates. This is not the protocol’s retained share.</p>
      </div>
      <div className="mt-5 grid gap-5">
        {[data.volume, data.fees].map((view) => <ChartView key={view.definition.id} definition={view.definition} selection={view.selection} view={view} mode="historical" height={340} />)}
      </div>
      <div className="mt-6 flex gap-2" role="group" aria-label="Calculation frequency">{["Monthly", "Quarterly"].map((item) => <Button key={item} aria-pressed={frequency === item} variant={frequency === item ? "primary" : "secondary"} onClick={() => setFrequency(item)}>{item}</Button>)}</div>
      <PeriodTable rows={frequency === "Monthly" ? data.monthly : data.quarterly} frequency={frequency} />
      {data.purchases ? <div className="mt-8"><h3 className="mb-3 text-heading">The observed purchase channel</h3><p className="mb-4 text-ui text-text-secondary">This cohort has its own shorter period. Selecting a longer business history does not extend purchase attribution.</p><ChartView definition={data.purchases.definition} selection={data.purchases.selection} view={data.purchases} mode="historical" height={320} /></div> : <p className="mt-4 text-ui text-text-secondary">Daily purchase history is unavailable. The original recorded cohort claims remain below.</p>}
      <ul className="mt-5 list-disc space-y-2 pl-5 text-ui text-text-secondary">{data.limitations.map((note) => <li key={note}>{note}</li>)}</ul>
    </div> : null}
  </section>;
}
