import { shortId } from "../blocks/display";
import type { CanonicalDocument, Classification, EvidenceTargetKind } from "../canonical";
import { insightText } from "../insights/fields";
import type { EvidenceTargetPage, PublicEvidenceKind } from "./api";

export type EvidenceOption = EvidenceTargetPage["items"][number];

export const classificationLabels: Record<Classification, string> = {
  supporting: "Supporting",
  contradicting: "Contradicting",
  uncertain: "Uncertain",
};

export const targetKindLabels: Record<EvidenceTargetKind, string> = {
  insight: "Insight in this research",
  chart_block: "Chart in this research",
  model_run: "Published model run",
  citation: "Public citation",
};

export function isPublicEvidenceTarget(kind: EvidenceTargetKind): kind is PublicEvidenceKind {
  return kind === "model_run" || kind === "citation";
}

export function localEvidenceTargets(document: CanonicalDocument, kind: EvidenceTargetKind): EvidenceOption[] {
  const options: EvidenceOption[] = [];
  for (const block of document.content) {
    if (kind === "insight" && block.type === "insight") {
      const { insight_id: id, body, context } = block.attrs;
      const text = insightText(body).replace(/\s+/g, " ").trim();
      options.push({ id, label: `${text.slice(0, 100) || "Insight"} · ${shortId(id)} · Dataset ${shortId(context.dataset_version_id)}` });
    } else if (kind === "chart_block" && block.type === "liveChart") {
      const { block_id: id, selection, observed_dataset_version_id } = block.attrs;
      options.push({ id, label: `Chart ${shortId(id)} · ${selection.start} to ${selection.end} UTC · Dataset ${shortId(observed_dataset_version_id)}` });
    }
  }
  return options;
}

export function samePrivateEvidenceTarget(before: CanonicalDocument, after: CanonicalDocument, kind: EvidenceTargetKind, id: string): boolean {
  const find = (document: CanonicalDocument) => document.content.find(block =>
    (kind === "insight" && block.type === "insight" && block.attrs.insight_id === id)
    || (kind === "chart_block" && block.type === "liveChart" && block.attrs.block_id === id));
  const original = find(before);
  const current = find(after);
  return Boolean(original && current && JSON.stringify(original.attrs) === JSON.stringify(current.attrs));
}
