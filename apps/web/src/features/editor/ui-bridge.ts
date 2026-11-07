import { Extension } from "@tiptap/core";

/**
 * UI bridge between Tiptap node views and the React workbench (NI-039).
 *
 * Node views live inside the ProseMirror surface; the three-pane shell (and
 * especially its mobile drawers) is React state. Atomic cards expose an
 * accessible "Edit properties" control (UI_SCREEN_SPECIFICATIONS: "Nested
 * charts/atomic cards are non-editable node views with accessible Edit
 * Properties controls") that selects the node and asks the shell to open the
 * properties panel — on phones that means opening the tools drawer. The
 * workbench registers the real callbacks at mount; the storage defaults are
 * inert so the editor stays usable unmounted.
 */

export interface EditorUiBridgeStorage {
  /** Select the block and reveal its properties (opens the tools pane/drawer). */
  openBlockProperties: (blockId: string | null) => void;
  /**
   * Request deletion of the block with the given top-level index through the
   * delete-confirmation flow (the shell previews dependent evidence links
   * before anything is removed). Returns false when nothing was requested.
   */
  requestBlockDelete: (topLevelIndex: number) => boolean;
}

/** Storage of the slash-menu trigger extension (see slash-menu.ts). */
export interface SlashMenuStorage {
  /**
   * Called when the user types "/" at the start of an empty top-level text
   * block; the argument is the document position of the trigger. The shell
   * replaces this no-op at mount to open the positioned insert menu.
   */
  onTrigger: (position: number) => void;
}

export const EditorUiBridge = Extension.create({
  name: "editorUiBridge",

  addStorage() {
    return {
      openBlockProperties: (_blockId: string | null) => {},
      requestBlockDelete: (_topLevelIndex: number) => false,
    } satisfies EditorUiBridgeStorage;
  },
});

declare module "@tiptap/core" {
  interface Storage {
    editorUiBridge: EditorUiBridgeStorage;
    slashMenuTrigger: SlashMenuStorage;
  }
}
