import { useEffect, useState } from "react";
import type { components } from "@near-intelligence/shared-types";
import { ResearchDestination } from "@/features/charts/add-to-research/AddChartToResearch";
import { getDocument } from "@/features/documents/list/documents-api";
import { validateCanonicalDocument } from "../canonical";
import { newIdempotencyKey } from "../persistence/save-transport";
import { createInsight, type InsightCreateRequest } from "./api";
import { emptyInsight, hypothesisOptions, InsightFields, insightBody, type InsightDraft } from "./fields";

export function AddInsightToResearch({ context, suspended }: {
  context: components["schemas"]["ResolvedContext"]; suspended: boolean;
}) {
  const [draft, setDraft] = useState(emptyInsight);
  const [inspection, setInspection] = useState(context);
  return <ResearchDestination kind="insight" pin={inspection} suspended={suspended} canConfirm={Boolean(draft.text.trim())}
    onBegin={() => setInspection(context)} onInserted={() => setDraft(emptyInsight)}
    onDestinationChange={() => setDraft(current => ({ ...current, hypothesisId: "" }))}
    prepare={() => {
      const body: InsightCreateRequest = { block_id: newIdempotencyKey(), context: inspection, type: draft.type,
        classification: draft.classification, body: insightBody(draft.text), hypothesis_id: draft.hypothesisId || null };
      return async (documentId, revision, key, signal) => (await createInsight(documentId, revision, body, key, signal)).document.id;
    }}
    fields={(destination, signal) => <>
      <p className="mb-3 text-metadata text-text-secondary">Observed <time dateTime={inspection.resolved_at}>{inspection.resolved_at}</time></p>
      <DestinationFields key={destination} destination={destination} signal={signal} draft={draft} setDraft={setDraft} />
    </>} />;
}

function DestinationFields({ destination, signal, draft, setDraft }: {
  destination: string; signal: AbortSignal | null; draft: InsightDraft; setDraft: (draft: InsightDraft) => void;
}) {
  const [hypotheses, setHypotheses] = useState<ReturnType<typeof hypothesisOptions>>([]);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    if (destination === "new" || !signal) return;
    const controller = new AbortController();
    const active = AbortSignal.any([signal, controller.signal]);
    void getDocument(destination, active).then(document => {
      const options = hypothesisOptions(validateCanonicalDocument(document.content));
      if (!active.aborted) { setHypotheses(options); setUnavailable(false); }
    }).catch(() => { if (!active.aborted) { setHypotheses([]); setUnavailable(true); } });
    return () => controller.abort();
  }, [destination, signal]);
  return <>
    <InsightFields value={draft} onChange={setDraft} hypotheses={hypotheses} />
    {unavailable ? <p className="mt-2 text-metadata text-text-secondary" role="status">Linked hypotheses could not be loaded.</p> : null}
  </>;
}
