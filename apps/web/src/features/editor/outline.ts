import type { JSONContent } from "@tiptap/core";

/**
 * Heading outline derivation (NI-039, EDITOR_SPECIFICATION "Outline follows
 * heading IDs"). Entries anchor to the heading's stable block_id — never to
 * mutable text slugs — so the outline stays accurate after undo, reorder and
 * text edits. Pure and canonical-shaped for direct testing.
 */
export interface OutlineEntry {
  blockId: string;
  level: 1 | 2 | 3;
  text: string;
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
    if (node.type !== "heading") {
      continue;
    }
    const level = node.attrs?.level;
    const blockId = node.attrs?.block_id;
    if (typeof blockId !== "string" || (level !== 1 && level !== 2 && level !== 3)) {
      // The stable-ID plugin guarantees block ids; headings outside 1-3 do
      // not exist in the assembled schema. Skip defensively, never guess.
      continue;
    }
    entries.push({ blockId, level, text: headingText(node) });
  }
  return entries;
}
