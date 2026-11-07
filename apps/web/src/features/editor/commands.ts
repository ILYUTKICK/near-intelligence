import type { Editor, JSONContent } from "@tiptap/core";
import { Extension } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { NodeSelection, TextSelection } from "@tiptap/pm/state";

import { newBlockId } from "./block-id";
import {
  canonicalBlockTypeOf,
  type CanonicalBlock,
  type CanonicalDocument,
} from "./canonical";
import { canonicalBlockToTiptap, tiptapToCanonicalDocument } from "./serialize";

/**
 * P0 structural block operations (NI-039, EDITOR_SPECIFICATION "Block
 * operations and focus"):
 *
 * - insert after the selected top-level position (insert menu / slash menu);
 * - remove, with dependent evidence/insight/risk links previewed and removed
 *   ONLY through an explicit confirmation (never silently);
 * - reorder up/down, preserving block ids, entity ids and insights;
 * - duplicate, allocating new block and entity ids while relationships that
 *   point OUTSIDE the copied block stay intact ("A duplicated single evidence
 *   block may still link to its existing hypothesis in the same document").
 *
 * The planners below are pure and canonical-shaped so the acceptance matrix
 * ("every operation serializes valid schema") runs without an editor. Every
 * editor command serializes its result through `tiptapToCanonicalDocument`
 * (which throws on anything not representable canonically) at the call site,
 * so an invalid state can never be persisted or announced as done.
 */

// --------------------------------------------------------------------------- //
// Pure planners (canonical blocks)
// --------------------------------------------------------------------------- */

export interface DependentBlock {
  blockId: string;
  blockType: CanonicalBlock["type"];
  /** Human-readable reason for the delete-confirmation preview. */
  reason: string;
}

const BLOCK_LABELS: Record<CanonicalBlock["type"], string> = {
  paragraph: "Paragraph",
  heading: "Heading",
  bullet_list: "Bullet list",
  ordered_list: "Ordered list",
  liveChart: "Live chart",
  dataTable: "Data table",
  insight: "Insight",
  hypothesis: "Hypothesis",
  evidence: "Evidence",
  risk: "Risk",
  divider: "Divider",
};

export function blockLabel(type: CanonicalBlock["type"]): string {
  return BLOCK_LABELS[type];
}

/**
 * Blocks that link to the target and would lose their reference if it were
 * deleted. Evidence targets of kind `chart_block` reference the chart's
 * block_id; `insight` targets reference the insight entity id.
 */
export function findDependentBlocks(
  content: readonly CanonicalBlock[],
  targetBlockId: string,
): DependentBlock[] {
  const target = content.find((block) => block.attrs.block_id === targetBlockId);
  if (!target) {
    return [];
  }
  const dependents: DependentBlock[] = [];
  const push = (block: CanonicalBlock, reason: string) => {
    dependents.push({
      blockId: block.attrs.block_id,
      blockType: block.type,
      reason,
    });
  };
  if (target.type === "hypothesis") {
    const hypothesisId = target.attrs.hypothesis_id;
    for (const block of content) {
      if (block.type === "evidence" && block.attrs.hypothesis_id === hypothesisId) {
        push(block, "Evidence links this hypothesis");
      }
      if (block.type === "insight" && block.attrs.hypothesis_id === hypothesisId) {
        push(block, "Insight links this hypothesis");
      }
      if (block.type === "risk" && block.attrs.related_hypothesis_id === hypothesisId) {
        push(block, "Risk references this hypothesis");
      }
    }
  }
  if (target.type === "insight") {
    const insightId = target.attrs.insight_id;
    for (const block of content) {
      if (block.type === "evidence" && block.attrs.target_kind === "insight" && block.attrs.target_id === insightId) {
        push(block, "Evidence targets this insight");
      }
    }
  }
  if (target.type === "liveChart") {
    const chartBlockId = target.attrs.block_id;
    for (const block of content) {
      if (block.type === "evidence" && block.attrs.target_kind === "chart_block" && block.attrs.target_id === chartBlockId) {
        push(block, "Evidence targets this chart block");
      }
    }
  }
  return dependents;
}

/**
 * One canonical copy of a single block (NI-039 duplicate semantics for a
 * one-block copy set): new block_id, new entity id for the annotation
 * families, every reference preserved — the targets still exist in the same
 * document, so the copy stays valid.
 */
export function duplicateBlock(
  block: CanonicalBlock,
  allocateId: () => string = newBlockId,
): CanonicalBlock {
  const attrs: Record<string, unknown> = { ...block.attrs, block_id: allocateId() };
  if (block.type === "insight") {
    attrs.insight_id = allocateId();
  } else if (block.type === "hypothesis") {
    attrs.hypothesis_id = allocateId();
  } else if (block.type === "evidence") {
    attrs.evidence_id = allocateId();
  }
  return JSON.parse(JSON.stringify({ ...block, attrs })) as CanonicalBlock;
}

// --------------------------------------------------------------------------- //
// Editor-level helpers
// --------------------------------------------------------------------------- */

const ATOMIC_TYPES = new Set([
  "liveChart", "dataTable", "insight", "hypothesis", "evidence", "risk", "divider",
]);

export interface CurrentBlock {
  index: number;
  blockId: string | null;
  /** Tiptap node type name (canonical for everything except the list family). */
  type: string;
  canonicalType: CanonicalBlock["type"];
  isAtomic: boolean;
}

/**
 * The top-level block the current selection starts in (or on, for
 * NodeSelections). Returns null only for an impossible empty doc.
 */
export function currentTopLevelBlock(editor: Editor): CurrentBlock | null {
  const doc = editor.state.doc;
  if (doc.childCount === 0) {
    return null;
  }
  const index = currentTopLevelIndex(editor);
  const child = doc.child(index);
  const canonicalType = canonicalBlockTypeOf(child.toJSON());
  return {
    index,
    blockId: (child.attrs.block_id as string | null) ?? null,
    type: child.type.name,
    canonicalType: canonicalType ?? "paragraph",
    isAtomic: ATOMIC_TYPES.has(child.type.name),
  };
}

export function currentTopLevelIndex(editor: Editor): number {
  const doc = editor.state.doc;
  const from = editor.state.selection.from;
  // Walk the top-level children; a position exactly on a child boundary
  // (e.g. a NodeSelection's start) belongs to the child that starts there.
  let offset = 0;
  for (let index = 0; index < doc.childCount; index += 1) {
    const size = doc.child(index).nodeSize;
    if (from < offset + size) {
      return index;
    }
    offset += size;
  }
  return Math.max(0, doc.childCount - 1);
}

function topLevelRange(doc: ProseMirrorNode, index: number): { from: number; to: number } {
  let from = 0;
  for (let i = 0; i < index; i += 1) {
    from += doc.child(i).nodeSize;
  }
  return { from, to: from + doc.child(index).nodeSize };
}

/**
 * Canonical snapshot of the current editor state (validated). Throws
 * CanonicalDocumentError when the state is not canonically representable —
 * callers must abort the operation instead of persisting or announcing it.
 */
export function canonicalSnapshot(editor: Editor): CanonicalDocument {
  return tiptapToCanonicalDocument(editor.getJSON());
}

// --------------------------------------------------------------------------- //
// Operations
// --------------------------------------------------------------------------- */

export type InsertableBlockType =
  | "paragraph"
  | "heading"
  | "bullet_list"
  | "ordered_list"
  | "dataTable"
  | "risk"
  | "divider";

/**
 * Insertable P0 types for NI-039. `liveChart` insertion is NI-041 (Add Chart
 * to owned research); `insight`/`hypothesis`/`evidence` authoring flows are
 * NI-047/NI-048/NI-049. All four families still load, render and take part in
 * every structural operation once present in the document.
 */
export const INSERTABLE_BLOCK_TYPES: readonly InsertableBlockType[] = [
  "paragraph", "heading", "bullet_list", "ordered_list", "dataTable", "risk", "divider",
];

const ATOMIC_INSERT_TYPES: ReadonlySet<InsertableBlockType> = new Set([
  "dataTable", "risk", "divider",
]);

function initialBlock(type: InsertableBlockType, headingLevel: number | null): JSONContent {
  const blockId = newBlockId();
  switch (type) {
    case "paragraph":
      return { type: "paragraph", attrs: { block_id: blockId } };
    case "heading":
      return { type: "heading", attrs: { block_id: blockId, level: headingLevel ?? 2 } };
    case "bullet_list":
    case "ordered_list":
      return {
        type: type === "ordered_list" ? "orderedList" : "bulletList",
        attrs: { block_id: blockId },
        content: [{ type: "listItem", content: [{ type: "paragraph" }] }],
      };
    case "dataTable":
      // A small authored draft the author edits in the properties panel;
      // cells are strings so no float parsing ever touches authored values.
      return {
        type: "dataTable",
        attrs: {
          block_id: blockId,
          columns: [
            { key: "column_1", label: "Column 1", type: "string" },
            { key: "column_2", label: "Column 2", type: "string" },
          ],
          rows: [["", ""]],
        },
      };
    case "risk":
      return {
        type: "risk",
        attrs: {
          block_id: blockId,
          title: "New risk",
          body: [{ type: "paragraph", content: [] }],
        },
      };
    case "divider":
      return { type: "divider", attrs: { block_id: blockId } };
  }
}

/**
 * Insert a new block of `type` after the current top-level block (or replace
 * a lone empty paragraph on a fresh document) and focus its first editable
 * position. Returns false when the editor rejected the transaction.
 */
export function insertBlock(
  editor: Editor,
  type: InsertableBlockType,
  options: { headingLevel?: number } = {},
): boolean {
  const json = initialBlock(type, options.headingLevel ?? null);
  const doc = editor.state.doc;
  const freshDocument =
    doc.childCount === 1 && doc.child(0).type.name === "paragraph" && doc.child(0).content.size === 0;
  const { from, to } = topLevelRange(doc, freshDocument ? 0 : currentTopLevelIndex(editor));
  const insertPos = freshDocument ? from : to;

  const applied = freshDocument
    ? editor.chain().focus().insertContentAt({ from, to }, json).run()
    : editor.chain().focus().insertContentAt(to, json).run();
  if (!applied) {
    return false;
  }
  // After insertion focus the first editable field: cursor inside for text
  // blocks, node selection for atomic cards (keyboard-reachable properties).
  if (ATOMIC_INSERT_TYPES.has(type)) {
    return editor.chain().focus().setNodeSelection(insertPos).run();
  }
  return editor.chain().focus().setTextSelection(insertPos + 1).run();
}

/**
 * Remove the top-level blocks at `indices` in one undoable transaction.
 * Callers derive indices from `findDependentBlocks` on the SAME snapshot, so
 * a dependent removal always deletes target + dependents together.
 */
export function removeTopLevelBlocks(editor: Editor, indices: number[]): boolean {
  if (indices.length === 0) {
    return false;
  }
  const doc = editor.state.doc;
  // Descending order: deleting a later range never moves earlier positions.
  const ranges = [...indices]
    .sort((a, b) => b - a)
    .map((index) => topLevelRange(doc, index));
  return editor.commands.command(({ tr, dispatch }) => {
    if (dispatch) {
      for (const range of ranges) {
        tr.delete(range.from, range.to);
      }
      dispatch(tr);
    }
    return true;
  });
}

/**
 * Move the block at `index` by `delta` positions. The block object itself is
 * re-inserted, so its block_id, entity ids and pinned contexts are preserved
 * exactly; the selection rides the moved block.
 */
export function moveTopLevelBlock(editor: Editor, index: number, delta: -1 | 1): boolean {
  const doc = editor.state.doc;
  const target = index + delta;
  if (target < 0 || target >= doc.childCount) {
    return false;
  }
  const node = doc.child(index);
  const { from, to } = topLevelRange(doc, index);
  // New start position of the moved node, valid AFTER the deletion below:
  // up-move lands at the previous sibling's start (unaffected by the
  // deletion), down-move lands right after the following sibling.
  const newFrom = delta === -1 ? from - doc.child(index - 1).nodeSize : from + doc.child(index + 1).nodeSize;
  return editor.commands.command(({ tr, dispatch }) => {
    if (dispatch) {
      tr.delete(from, to);
      tr.insert(newFrom, node);
      if (ATOMIC_TYPES.has(node.type.name)) {
        tr.setSelection(NodeSelection.create(tr.doc, newFrom));
      } else {
        tr.setSelection(TextSelection.create(tr.doc, newFrom + 1));
      }
      dispatch(tr);
    }
    return true;
  });
}

/**
 * Duplicate the block at `index` (planner semantics: new block/entity ids,
 * references preserved) and insert the copy right after the original, with
 * the selection on the copy.
 */
export function duplicateTopLevelBlock(editor: Editor, index: number): boolean {
  const doc = editor.state.doc;
  const { to } = topLevelRange(doc, index);
  const canonical = canonicalSnapshot(editor);
  const block = canonical.content[index];
  if (!block) {
    return false;
  }
  const copy = duplicateBlock(block);
  const copyJson = canonicalBlockToTiptap(copy);
  return editor
    .chain()
    .insertContentAt(to, copyJson)
    .command(({ tr, dispatch }) => {
      if (dispatch) {
        // The copy now occupies [to, to + size); select it.
        if (ATOMIC_TYPES.has(copy.type)) {
          tr.setSelection(NodeSelection.create(tr.doc, to));
        } else {
          tr.setSelection(TextSelection.create(tr.doc, to + 1));
        }
        dispatch(tr);
      }
      return true;
    })
    .run();
}

// --------------------------------------------------------------------------- //
// Keyboard alternatives
// --------------------------------------------------------------------------- */

/**
 * Keyboard shortcuts for the structural operations. The block toolbar buttons
 * are the pointer/screen-reader alternatives and run the very same commands;
 * a keyboard delete of a block with dependent links routes through the
 * shell's confirmation dialog instead of bypassing the explicit-link rule.
 */
export const BlockOperationShortcuts = Extension.create({
  name: "blockOperationShortcuts",

  addKeyboardShortcuts() {
    return {
      "Mod-Alt-ArrowUp": () => moveTopLevelBlock(this.editor, currentTopLevelIndex(this.editor), -1),
      "Mod-Alt-ArrowDown": () => moveTopLevelBlock(this.editor, currentTopLevelIndex(this.editor), 1),
      "Mod-Shift-d": () => duplicateTopLevelBlock(this.editor, currentTopLevelIndex(this.editor)),
      "Mod-Shift-Backspace": () => {
        const editor = this.editor;
        const index = currentTopLevelIndex(editor);
        const snapshot = canonicalSnapshot(editor);
        const block = snapshot.content[index];
        if (!block) {
          return false;
        }
        if (findDependentBlocks(snapshot.content, block.attrs.block_id).length > 0) {
          // Route through the confirmation flow; the shell previews the
          // affected links and performs the removal only on explicit choice.
          editor.storage.editorUiBridge.requestBlockDelete(index);
          return false;
        }
        return removeTopLevelBlocks(editor, [index]);
      },
    };
  },
});
