import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";

/**
 * Stable block identities (NI-039, EDITOR_SPECIFICATION "Outline/navigation
 * uses stable IDs, not mutable text slugs" and "moving a block updates order,
 * preserves ID/insights").
 *
 * Every top-level node carries an immutable `attrs.block_id` (UUID). The
 * invariant is maintained in the editor itself: after any transaction that
 * leaves a top-level node without a block id (Tiptap normalizing an empty
 * document to one empty paragraph, Enter splitting a paragraph, pasted
 * fragments), this plugin allocates one in the same transaction — an id is
 * allocated once and then never remapped by editing, reordering or undo.
 * Duplicates deliberately allocate NEW ids (never copies) in the commands
 * layer; entity ids (insight_id/hypothesis_id/evidence_id) are uuid4 and
 * persist unchanged across text edits per NI-046.
 */

const stableBlockIdsKey = new PluginKey("stableBlockIds");

/** Client-generated UUID (block ids need uniqueness, never content-derivation). */
export function newBlockId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID: a v4-shaped unique
  // string (same fallback pattern as the document API client).
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    const value = character === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export const StableBlockIds = Extension.create({
  name: "stableBlockIds",

  onCreate() {
    // The initial document never passes through appendTransaction (Tiptap
    // normalizes its content — e.g. an empty document to one empty
    // paragraph — at construction), so the same fill/repair runs once here.
    const { doc } = this.editor.state;
    const transaction = this.editor.state.tr;
    let modified = false;
    const seen = new Set<string>();
    doc.forEach((node, offset) => {
      const blockId = node.attrs.block_id as string | null | undefined;
      if (blockId == null || seen.has(blockId)) {
        const fresh = newBlockId();
        transaction.setNodeMarkup(offset, undefined, { ...node.attrs, block_id: fresh });
        seen.add(fresh);
        modified = true;
      } else {
        seen.add(blockId);
      }
    });
    if (modified) {
      this.editor.view.dispatch(transaction);
    }
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: stableBlockIdsKey,
        appendTransaction: (transactions, _oldState, newState) => {
          if (!transactions.some((transaction) => transaction.docChanged)) {
            return null;
          }
          const transaction = newState.tr;
          let modified = false;
          const seen = new Set<string>();
          // Fill missing ids AND repair duplicates: ProseMirror's splitBlock
          // copies attrs, so pressing Enter inside a block yields two nodes
          // with the same id. The first occurrence keeps the original id
          // (ids are allocated once, never remapped); the split-off copy is
          // a NEW block and gets a fresh id.
          newState.doc.forEach((node, offset) => {
            const blockId = node.attrs.block_id as string | null | undefined;
            if (blockId == null || seen.has(blockId)) {
              const fresh = newBlockId();
              transaction.setNodeMarkup(offset, undefined, {
                ...node.attrs,
                block_id: fresh,
              });
              seen.add(fresh);
              modified = true;
            } else {
              seen.add(blockId);
            }
          });
          return modified ? transaction : null;
        },
      }),
    ];
  },
});
