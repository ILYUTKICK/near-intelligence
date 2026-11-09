import type { JSONContent } from "@tiptap/core";

/**
 * Outline entries use stable block IDs so heading and hypothesis navigation
 * survives text edits, reorders and undo.
 */
export interface OutlineEntry {
  blockId: string;
  level: 1 | 2 | 3;
  text: string;
  hypothesisId?: string;
}

function headingText(node: JSONContent): string {
  return (node.content ?? [])
    .map((run) => (typeof run.text === "string" ? run.text : ""))
    .join("");
}

export function deriveOutline(doc: JSONContent): OutlineEntry[] {
  const content = doc.type === "doc" ? (doc.content ?? []) : [doc];
  const entries: OutlineEntry[] = [];
  for (const node of content) {
    const blockId = node.attrs?.block_id;
    if (typeof blockId !== "string") continue;
    if (node.type === "hypothesis" && typeof node.attrs?.hypothesis_id === "string" && typeof node.attrs.statement === "string") {
      entries.push({ blockId, level: 2, text: node.attrs.statement, hypothesisId: node.attrs.hypothesis_id });
      continue;
    }
    const level = node.attrs?.level;
    if (node.type === "heading" && (level === 1 || level === 2 || level === 3)) {
      entries.push({ blockId, level, text: headingText(node) });
    }
  }
  return entries;
}
