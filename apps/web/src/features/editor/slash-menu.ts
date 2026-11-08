import { Extension } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";

import { emitSlashTrigger } from "./ui-bridge";

/**
 * Slash-menu trigger (NI-039, EDITOR_SPECIFICATION "Insert via slash menu").
 * Typing "/" at the start of an empty top-level paragraph or heading asks
 * the shell (through a bubbling DOM event, see ui-bridge.ts) to open the
 * positioned insert menu; choosing an item replaces that block, so the "/"
 * never stays behind in the document. No dependency is added — the trigger
 * is a plain ProseMirror plugin and the menu itself is React
 * (UI_SCREEN_SPECIFICATIONS: labeled types; the toolbar menu is the
 * guaranteed keyboard/AT alternative).
 */
export const SlashMenuTrigger = Extension.create({
  name: "slashMenuTrigger",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        props: {
          handleTextInput: (view, from, _to, text) => {
            if (text !== "/") {
              return false;
            }
            const $from = view.state.doc.resolve(from);
            // Top-level text block only: the parent IS the top-level node.
            if ($from.depth !== 1) {
              return false;
            }
            const parentName = $from.parent.type.name;
            if (parentName !== "paragraph" && parentName !== "heading") {
              return false;
            }
            if ($from.parentOffset !== 0 || $from.parent.textContent !== "") {
              return false;
            }
            // Defer: the slash must land in the document before the menu
            // renders, and the caller reads positions from the updated view.
            window.setTimeout(() => emitSlashTrigger(view.dom, from), 0);
            return false;
          },
        },
      }),
    ];
  },
});
