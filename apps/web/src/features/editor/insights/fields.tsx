import { useId } from "react";
import type { components } from "@near-intelligence/shared-types";
import { Label } from "@/components/ui/label";
import { CLASSIFICATIONS, INSIGHT_TYPES, MAX_BODY_PLAIN_CHARS, type CanonicalDocument, type CanonicalResolvedContext, type RichFragment } from "../canonical";

type InsightInput = components["schemas"]["InsightInput"];

export interface InsightDraft {
  type: InsightInput["type"];
  classification: InsightInput["classification"];
  text: string;
  hypothesisId: string;
}

export const emptyInsight: InsightDraft = { type: "observation", classification: "uncertain", text: "", hypothesisId: "" };

export function insightText(body: RichFragment): string {
  return body.map(node => node.type === "paragraph"
    ? node.content.map(run => run.text).join("")
    : node.content.map(item => insightText(item.content)).join("\n")).join("\n");
}

export function insightBody(text: string): InsightInput["body"] {
  return text.trim().split(/\r?\n/).map(line => ({ type: "paragraph",
    content: line ? [{ type: "text", text: line, marks: [] }] : [] }));
}

export function hypothesisOptions(content: CanonicalDocument) {
  return content.content.flatMap(block => block.type === "hypothesis"
    ? [{ id: block.attrs.hypothesis_id, label: block.attrs.statement }]
    : []);
}

const control = "w-full min-h-11 rounded-control border border-control-border bg-surface px-3 py-2 text-body text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

export function InsightFields({ value, onChange, hypotheses = [] }: {
  value: InsightDraft;
  onChange: (draft: InsightDraft) => void;
  hypotheses?: ReturnType<typeof hypothesisOptions>;
}) {
  const id = useId();
  const missingHypothesis = Boolean(value.hypothesisId) && !hypotheses.some(option => option.id === value.hypothesisId);
  return <div className="space-y-3">
    <div className="grid grid-cols-2 gap-3">
      <div>
        <Label htmlFor={`${id}-type`}>Insight type</Label>
        <select id={`${id}-type`} className={`${control} capitalize`} value={value.type}
          onChange={event => onChange({ ...value, type: event.target.value as InsightDraft["type"] })}>
          {INSIGHT_TYPES.map(type => <option key={type} value={type}>{type}</option>)}
        </select>
      </div>
      <div>
        <Label htmlFor={`${id}-classification`}>Evidence classification</Label>
        <select id={`${id}-classification`} className={`${control} capitalize`} value={value.classification}
          onChange={event => onChange({ ...value, classification: event.target.value as InsightDraft["classification"] })}>
          {CLASSIFICATIONS.map(classification => <option key={classification} value={classification}>{classification}</option>)}
        </select>
      </div>
    </div>
    <div>
      <Label htmlFor={`${id}-note`}>Insight text</Label>
      <textarea id={`${id}-note`} className={control} rows={5} maxLength={MAX_BODY_PLAIN_CHARS} required value={value.text}
        onChange={event => onChange({ ...value, text: event.target.value })} />
    </div>
    {hypotheses.length || missingHypothesis ? <div>
      <Label htmlFor={`${id}-hypothesis`}>Linked hypothesis</Label>
      <select id={`${id}-hypothesis`} className={control} value={value.hypothesisId}
        onChange={event => onChange({ ...value, hypothesisId: event.target.value })}>
        <option value="">No linked hypothesis</option>
        {missingHypothesis ? <option value={value.hypothesisId} disabled>Unavailable hypothesis</option> : null}
        {hypotheses.map(({ id, label }) => <option key={id} value={id}>{label}</option>)}
      </select>
    </div> : null}
  </div>;
}

// NI-071: a pin may come from the resolved view (canonical list filters)
// or from a persisted revision (which preserves submitted values verbatim,
// including pre-NI-071 bare strings); the display is value-form agnostic.
export function InsightPin({ context }: { context: InsightInput["context"] | CanonicalResolvedContext }) {
  return "selection" in context ? <div className="space-y-1 text-metadata leading-metadata text-text-secondary">
    <p className="break-all">Dataset {context.dataset_version_id}</p>
    <p>{context.selection.start} through {context.selection.end} UTC, end exclusive</p>
    <p>Filters {Object.entries(context.selection.filters).map(([key, value]) => `${key} = ${value}`).join(", ") || "none"}</p>
    <p>Observed <time dateTime={context.resolved_at}>{context.resolved_at}</time></p>
  </div> : <p className="break-all text-metadata text-text-secondary">Pinned model run {context.model_run_id}</p>;
}
