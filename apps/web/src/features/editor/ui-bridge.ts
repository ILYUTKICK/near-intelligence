/**
 * Node view / keyboard -> shell bridge (NI-039), built on bubbling DOM
 * CustomEvents instead of mutable editor storage: node views and the
 * keyboard shortcuts dispatch events on the editor DOM, and the React shell
 * listens on the paper container. This keeps the ProseMirror side free of
 * React state writes and the shell free of storage mutation.
 */

export const EDITOR_OPEN_BLOCK_PROPERTIES = "editor-open-block-properties";
export const EDITOR_REQUEST_BLOCK_DELETE = "editor-request-block-delete";
export const EDITOR_SLASH_TRIGGER = "editor-slash-trigger";

function dispatchDetail(host: HTMLElement | null, type: string, detail: Record<string, unknown>): void {
  host?.dispatchEvent(new CustomEvent(type, { detail, bubbles: true }));
}

/** Select the block and reveal its properties (opens the tools pane/drawer). */
export function emitOpenBlockProperties(editor: { view: { dom: HTMLElement } }, blockId: string | null): void {
  dispatchDetail(editor.view.dom, EDITOR_OPEN_BLOCK_PROPERTIES, { blockId });
}

/**
 * Request deletion of the top-level block at `index` through the shell's
 * delete-confirmation flow (dependent evidence links are previewed before
 * anything is removed).
 */
export function emitRequestBlockDelete(editor: { view: { dom: HTMLElement } }, index: number): void {
  dispatchDetail(editor.view.dom, EDITOR_REQUEST_BLOCK_DELETE, { index });
}

/** Slash menu trigger: "/" typed at the start of an empty top-level block. */
export function emitSlashTrigger(host: HTMLElement | null, position: number): void {
  dispatchDetail(host, EDITOR_SLASH_TRIGGER, { position });
}

export interface BridgeDetail<T> {
  detail: T;
}

export function detailOf<T>(event: Event, fallback: T): T {
  return ((event as CustomEvent).detail as T | undefined) ?? fallback;
}
