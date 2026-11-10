/**
 * NI-064 slash-menu trigger regression (synthetic, labeled).
 *
 * The desktop e2e keyboard suite proved the recorded NI-039 slash trigger
 * NEVER fired in a real browser: prosemirror-view's DOM-diff input path only
 * invokes handleTextInput when the edited parent already holds a text child,
 * so typing "/" into an empty paragraph (the canonical trigger) reached
 * neither the handleTextInput path nor any other. The fix listens for the
 * `beforeinput` DOM event; these tests drive that handler on a real editor
 * (jsdom cannot reproduce Chromium's event generation — the real typing path
 * is covered by the production e2e keyboard suite).
 */
import { Editor } from "@tiptap/core";
import { afterEach, describe, expect, it, vi } from "vitest";

import { insertBlock } from "@/features/editor/commands";
import { EDITOR_EXTENSIONS } from "@/features/editor/extensions";
import { EDITOR_SLASH_TRIGGER } from "@/features/editor/ui-bridge";

const editors: Editor[] = [];

function buildEditor(content: Record<string, unknown>): Editor {
  const editor = new Editor({
    extensions: EDITOR_EXTENSIONS,
    content,
  });
  editors.push(editor);
  return editor;
}

afterEach(() => {
  for (const editor of editors.splice(0)) {
    editor.destroy();
  }
});

/**
 * jsdom has no InputEvent; a bubbling Event with the two input properties
 * assigned is exactly the surface the handler reads.
 */
function fireBeforeinput(element: Element, inputType: string, data: string | null): void {
  const event = new Event("beforeinput", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "inputType", { value: inputType });
  Object.defineProperty(event, "data", { value: data });
  element.dispatchEvent(event);
}

describe("slash menu trigger (beforeinput path)", () => {
  it("emits the slash trigger when / is typed at the start of an empty top-level paragraph", async () => {
    const editor = buildEditor({
      type: "doc",
      content: [{ type: "paragraph" }],
    });
    editor.commands.focus("end");
    const events: Array<Record<string, unknown>> = [];
    editor.view.dom.addEventListener(EDITOR_SLASH_TRIGGER, (event) => {
      events.push((event as CustomEvent).detail as Record<string, unknown>);
    });
    // The "/" must NOT be swallowed: the handler lets the default input run.
    const preventDefault = vi.spyOn(Event.prototype, "preventDefault");

    fireBeforeinput(editor.view.dom, "insertText", "/");
    // The emit is deferred (macrotask) so the slash lands in the document first.
    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(events).toHaveLength(1);
    expect(typeof events[0]?.position).toBe("number");
    expect(events[0]?.position).toBeGreaterThan(0);
    // The handler returns false: the slash is inserted normally, the menu
    // then replaces the block.
    expect(preventDefault).not.toHaveBeenCalled();
  });

  it("does not emit for non-slash text, other input types, or non-empty blocks", () => {
    const editor = buildEditor({
      type: "doc",
      content: [{ type: "paragraph" }],
    });
    editor.commands.focus("end");
    const events: Array<Record<string, unknown>> = [];
    editor.view.dom.addEventListener(EDITOR_SLASH_TRIGGER, (event) => {
      events.push((event as CustomEvent).detail as Record<string, unknown>);
    });

    fireBeforeinput(editor.view.dom, "insertText", "x");
    fireBeforeinput(editor.view.dom, "insertParagraph", null);
    expect(events).toHaveLength(0);

    // A block with text never triggers (only EMPTY top-level blocks do).
    editor.commands.setContent({ type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Some prose" }] }] });
    editor.commands.focus("start");
    fireBeforeinput(editor.view.dom, "insertText", "/");
    expect(events).toHaveLength(0);
  });

  it("does not emit inside nested blocks (top-level text blocks only)", () => {
    const editor = buildEditor({
      type: "doc",
      content: [{
        type: "bulletList",
        content: [{
          type: "listItem",
          content: [{ type: "paragraph" }],
        }],
      }],
    });
    editor.commands.focus("end");
    const events: Array<Record<string, unknown>> = [];
    editor.view.dom.addEventListener(EDITOR_SLASH_TRIGGER, (event) => {
      events.push((event as CustomEvent).detail as Record<string, unknown>);
    });
    fireBeforeinput(editor.view.dom, "insertText", "/");
    expect(events).toHaveLength(0);
  });

  it("emits on the canonical empty document (no top-level blocks yet)", async () => {
    // The loaded `content: []` document has NO paragraph in editor state;
    // typing "/" creates the very first block, so the trigger must fire
    // without any empty paragraph to resolve into.
    const editor = buildEditor({ type: "doc", content: [] });
    expect(editor.state.doc.childCount).toBe(0);
    const events: Array<Record<string, unknown>> = [];
    editor.view.dom.addEventListener(EDITOR_SLASH_TRIGGER, (event) => {
      events.push((event as CustomEvent).detail as Record<string, unknown>);
    });
    fireBeforeinput(editor.view.dom, "insertText", "/");
    await new Promise((resolve) => setTimeout(resolve, 5));
    expect(events).toHaveLength(1);
  });

  it("replaces the slash trigger block so the / never stays behind", () => {
    const editor = buildEditor({
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: "/" }] }],
    });
    const applied = insertBlock(editor, "heading", { headingLevel: 1 });
    expect(applied).toBe(true);
    expect(editor.state.doc.childCount).toBe(1);
    expect(editor.state.doc.child(0).type.name).toBe("heading");
    expect(editor.state.doc.textContent).not.toContain("/");
  });
});
