import { Node, mergeAttributes } from "@tiptap/core";

import { blockIdAttr } from "../attributes";

/**
 * Canonical `divider` block (P0): a semantic separator. It is a real block
 * node (not Tiptap's `horizontalRule`, which is disabled in the assembled
 * extension set because the canonical schema has no `horizontalRule` type),
 * carries a stable block_id, and supports the keyboard/toolbar reorder and
 * delete operations like every other block.
 */
export const Divider = Node.create({
  name: "divider",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
    };
  },

  parseHTML() {
    return [{ tag: "hr[data-block-id]" }];
  },

  renderHTML({ node, HTMLAttributes }) {
    return [
      "hr",
      mergeAttributes(
        {
          "data-editor-divider": "",
          class: "editor-divider",
        },
        HTMLAttributes,
      ),
    ];
  },
});
