import { Extension } from "@tiptap/core";
import { Plugin, Selection } from "@tiptap/pm/state";
import type { ResolvedPos } from "@tiptap/pm/model";

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
 *
 * The real-browser signal is the `beforeinput` DOM event (see the plugin
 * comment for the prosemirror-view constraint that defeats a
 * handleTextInput-only trigger); the desktop e2e keyboard suite drives the
 * real typing path against the production build.
 */
export const SlashMenuTrigger = Extension.create({
  name: "slashMenuTrigger",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        props: {
          // NI-064 desktop-QA fix: prosemirror-view's DOM-diff path
          // (readDOMChange) only invokes handleTextInput when the edited
          // parent ALREADY contains a text child, and its keypress path only
          // covers non-composing browsers without beforeinput — so typing
          // "/" into an empty paragraph (the canonical trigger) never reached
          // the plugin in a real browser. The beforeinput DOM event is the
          // reliable cross-browser signal for a plain text insertion; the
          // handleTextInput path below is kept for input routes that bypass
          // beforeinput.
          handleDOMEvents: {
            beforeinput: (view, event) => {
              const input = event as InputEvent;
              if (input.inputType !== "insertText" || input.data !== "/") {
                return false;
              }
              if (view.composing) {
                return false;
              }
              const { $from, emptyDocument } = caretContext(view);
              const triggers = emptyDocument
                || ($from !== null && topLevelEmptyTextPosition($from));
              if (triggers) {
                const position = $from?.pos ?? view.state.selection.from;
                window.setTimeout(() => emitSlashTrigger(view.dom, position), 0);
              }
              return false;
            },
          },
          handleTextInput: (view, from, _to, text) => {
            if (text !== "/" || view.composing) {
              return false;
            }
            if (topLevelEmptyTextPosition(view.state.doc.resolve(from))) {
              // Defer: the slash must land in the document before the menu
              // renders, and the caller reads positions from the updated view.
              window.setTimeout(() => emitSlashTrigger(view.dom, from), 0);
            }
            return false;
          },
        },
      }),
    ];
  },
});

/** True when the resolved position sits at the start of an empty top-level
 *  paragraph or heading (the EDITOR_SPECIFICATION "/" trigger shape). */
function topLevelEmptyTextPosition($position: ResolvedPos): boolean {
  // Top-level text block only: the parent IS the top-level node.
  if ($position.depth !== 1) {
    return false;
  }
  const parentName = $position.parent.type.name;
  if (parentName !== "paragraph" && parentName !== "heading") {
    return false;
  }
  return $position.parentOffset === 0 && $position.parent.textContent === "";
}

/**
 * The caret the browser will insert at, plus whether the document is still
 * the canonical EMPTY document (no top-level blocks at all — the loaded
 * `content: []` state, where the "/" typed by the author creates the very
 * first block, so no empty paragraph exists yet to resolve into).
 */
function caretContext(view: {
  state: {
    selection: { $from: ResolvedPos; from: number };
    doc: { resolve(pos: number): ResolvedPos; childCount: number };
  };
}): { $from: ResolvedPos | null; emptyDocument: boolean } {
  if (view.state.doc.childCount === 0) {
    return { $from: null, emptyDocument: true };
  }
  const selection = view.state.selection;
  if (selection.$from.depth >= 1) {
    return { $from: selection.$from, emptyDocument: false };
  }
  try {
    return {
      $from: Selection.near(view.state.doc.resolve(selection.from), 1).$from,
      emptyDocument: false,
    };
  } catch {
    return { $from: null, emptyDocument: false };
  }
}
