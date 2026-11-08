/**
 * NI-039 structural operations acceptance (synthetic fixtures, labeled):
 *
 * - every P0 operation (insert / remove / reorder / duplicate / heading /
 *   table / risk / divider) serializes a VALID canonical schema afterwards;
 * - duplicate allocates new block AND entity ids and keeps references that
 *   point outside the copy set ("a duplicated single evidence block may
 *   still link to its existing hypothesis");
 * - deleting a linked target requires the explicit dependent preview; the
 *   combined removal leaves no dangling references;
 * - block ids are stable across reorder/typing (remap never happens), and
 *   the keyboard shortcuts run the same operations;
 * - undo/redo survive the operations.
 */
import { Editor } from "@tiptap/core";
import { describe, expect, it, vi } from "vitest";

import {
  canonicalSnapshot,
  currentTopLevelIndex,
  duplicateBlock,
  duplicateTopLevelBlock,
  findDependentBlocks,
  insertBlock,
  moveTopLevelBlock,
  removeTopLevelBlocks,
} from "@/features/editor/commands";
import { EDITOR_EXTENSIONS } from "@/features/editor/extensions";
import { tiptapToCanonicalDocument } from "@/features/editor/serialize";
import { newBlockId } from "@/features/editor/block-id";
import { buildLinkGraph, type CanonicalBlock } from "@/features/editor/canonical";

const HYPOTHESIS_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const EVIDENCE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const INSIGHT_ID = "99999999-9999-4999-8999-999999999999";
const CHART_BLOCK_ID = "66666666-6666-4666-8666-666666666666";
const CHART_DEF_ID = "88888888-8888-4888-8888-888888888888";
const DATASET_ID = "77777777-7777-4777-8777-777777777777";
const SELECTION = { start: "2026-01-01", end: "2026-02-01", frequency: "day", filters: {} };
const RESOLVED_CONTEXT = {
  chart_definition_version_id: CHART_DEF_ID,
  dataset_version_id: DATASET_ID,
  selection: SELECTION,
  context_hash: "a".repeat(64),
  renderer_version: "echarts-modular-svg@1",
  metric_definition_versions: [],
  resolved_at: "2026-11-08T00:00:00Z",
};

/** Synthetic linked research document (fixture): hypothesis <- evidence,
 * insight (links hypothesis, pinned context), chart targeted by evidence. */
function linkedFixtureBlocks(): CanonicalBlock[] {
  return [
    {
      type: "heading",
      attrs: { block_id: "11111111-1111-4111-8111-111111111111", level: 1 },
      content: [{ type: "text", text: "Linked fixture" }],
    },
    {
      type: "hypothesis",
      attrs: {
        block_id: "22222222-2222-4222-8222-222222222222",
        hypothesis_id: HYPOTHESIS_ID,
        statement: "Adoption drives fee growth (fixture)",
        assessment: "untested",
        authored_at: "2026-11-08T00:00:00Z",
        modified_at: "2026-11-08T00:00:00Z",
      },
    },
    {
      type: "evidence",
      attrs: {
        block_id: "33333333-3333-4333-8333-333333333333",
        evidence_id: EVIDENCE_ID,
        hypothesis_id: HYPOTHESIS_ID,
        classification: "supporting",
        target_kind: "chart_block",
        target_id: CHART_BLOCK_ID,
        explanation: "Chart matches the hypothesis (fixture)",
      },
    },
    {
      type: "liveChart",
      attrs: {
        block_id: CHART_BLOCK_ID,
        chart_definition_version_id: CHART_DEF_ID,
        mode: "live",
        selection: SELECTION,
        observed_dataset_version_id: DATASET_ID,
        snapshot_id: null,
      },
    },
    {
      type: "insight",
      attrs: {
        block_id: "44444444-4444-4444-8444-444444444444",
        insight_id: INSIGHT_ID,
        type: "observation",
        classification: "supporting",
        body: [{ type: "paragraph", content: [{ type: "text", text: "Observed (fixture)" }] }],
        context: RESOLVED_CONTEXT,
        authored_at: "2026-11-08T00:00:00Z",
        modified_at: "2026-11-08T00:00:00Z",
        hypothesis_id: HYPOTHESIS_ID,
      },
    },
  ];
}

function editorWith(blocks: CanonicalBlock[], options: { element?: HTMLElement } = {}): Editor {
  const editor = new Editor({
    extensions: EDITOR_EXTENSIONS,
    content: { type: "doc", content: blocks },
    ...(options.element ? { element: options.element } : {}),
  });
  return editor;
}

function blockIds(editor: Editor): string[] {
  return (editor.getJSON().content ?? []).map((node) => node.attrs?.block_id as string);
}

function expectValidSnapshot(editor: Editor) {
  // Throws CanonicalDocumentError when the editor state is not canonical.
  const snapshot = tiptapToCanonicalDocument(editor.getJSON());
  expect(snapshot.type).toBe("doc");
  return snapshot;
}

describe("pure planners", () => {
  it("finds every dependent block of a hypothesis target", () => {
    const content = linkedFixtureBlocks();
    const dependents = findDependentBlocks(content, "22222222-2222-4222-8222-222222222222");
    expect(dependents.map((d) => d.blockType).sort()).toEqual(["evidence", "insight"]);
    expect(dependents.map((d) => d.reason)).toContain("Evidence links this hypothesis");
  });

  it("finds evidence targeting an insight or a chart block", () => {
    const content = linkedFixtureBlocks();
    expect(findDependentBlocks(content, "44444444-4444-4444-8444-444444444444")).toHaveLength(0); // insight not evidence-targeted here
    const chartDependents = findDependentBlocks(content, CHART_BLOCK_ID);
    expect(chartDependents).toHaveLength(1);
    expect(chartDependents[0].reason).toBe("Evidence targets this chart block");
  });

  it("reports no dependents for structural blocks", () => {
    const content = linkedFixtureBlocks();
    expect(findDependentBlocks(content, "11111111-1111-4111-8111-111111111111")).toEqual([]);
    expect(findDependentBlocks(content, "missing-id")).toEqual([]);
  });

  it("duplicate allocates new block and entity ids and keeps outside references", () => {
    const content = linkedFixtureBlocks();
    const ids: string[] = [];
    const allocate = () => {
      ids.push(newBlockId());
      return ids[ids.length - 1];
    };
    const evidenceCopy = duplicateBlock(content[2], allocate);
    expect(evidenceCopy.type).toBe("evidence");
    expect(evidenceCopy.attrs.block_id).not.toBe(content[2].attrs.block_id);
    expect(evidenceCopy.attrs.evidence_id).not.toBe(EVIDENCE_ID);
    // The duplicated single evidence block still links to its existing
    // hypothesis and its existing chart target (EDITOR_SPECIFICATION).
    expect(evidenceCopy.attrs.hypothesis_id).toBe(HYPOTHESIS_ID);
    expect(evidenceCopy.attrs.target_id).toBe(CHART_BLOCK_ID);
    // And the copy validates in the original document context.
    const withCopy = [...content, evidenceCopy];
    const graph = buildLinkGraph(withCopy);
    expect(graph.hypothesisIds.has(evidenceCopy.attrs.hypothesis_id)).toBe(true);

    const insightCopy = duplicateBlock(content[4], allocate);
    expect(insightCopy.attrs.insight_id).not.toBe(INSIGHT_ID);
    expect(insightCopy.attrs.hypothesis_id).toBe(HYPOTHESIS_ID);
    // The pinned ResolvedContext travels with the copy unchanged.
    expect(insightCopy.attrs.context).toEqual(RESOLVED_CONTEXT);
  });
});

describe("editor operations serialize valid canonical schema", () => {
  it("inserts every insertable P0 block type with a valid schema result", () => {
    const editor = editorWith(linkedFixtureBlocks());
    editor.commands.setTextSelection(1); // inside the heading
    for (const type of [
      "paragraph", "heading", "bullet_list", "ordered_list", "dataTable", "risk", "divider",
    ] as const) {
      expect(insertBlock(editor, type, { headingLevel: 2 })).toBe(true);
    }
    const snapshot = expectValidSnapshot(editor);
    const types = snapshot.content.map((block) => block.type);
    expect(types).toContain("dataTable");
    expect(types).toContain("risk");
    expect(types).toContain("divider");
    // Each inserted block carries a fresh, unique stable id.
    const ids = snapshot.content.map((block) => block.attrs.block_id);
    expect(new Set(ids).size).toBe(ids.length);
    editor.destroy();
  });

  it("focuses the inserted text block (selection inside the new node)", () => {
    const editor = editorWith(linkedFixtureBlocks());
    editor.commands.setTextSelection(1);
    insertBlock(editor, "paragraph");
    // The fixture has no paragraph before the insert, so a cursor inside a
    // top-level paragraph proves focus landed in the new block.
    expect(editor.state.selection.$from.node(1)?.type.name).toBe("paragraph");
    insertBlock(editor, "bullet_list");
    // Inside a list the cursor sits in the first item's paragraph.
    expect(editor.state.selection.$from.node(1)?.type.name).toBe("bulletList");
    expect(editor.state.selection.$from.node(3)?.type.name).toBe("paragraph");
    editor.destroy();
  });

  it("reorders blocks up and down preserving ids", () => {
    const editor = editorWith(linkedFixtureBlocks());
    const before = blockIds(editor);
    expect(moveTopLevelBlock(editor, 2, -1)).toBe(true);
    expect(blockIds(editor)[1]).toBe(before[2]);
    expect(blockIds(editor)[2]).toBe(before[1]);
    expectValidSnapshot(editor);
    expect(moveTopLevelBlock(editor, 1, 1)).toBe(true);
    expect(blockIds(editor)).toEqual(before);
    // Edges refuse without state corruption.
    expect(moveTopLevelBlock(editor, 0, -1)).toBe(false);
    expect(moveTopLevelBlock(editor, 4, 1)).toBe(false);
    expectValidSnapshot(editor);
    editor.destroy();
  });

  it("duplicate command inserts a canonical copy right after the original", () => {
    const editor = editorWith(linkedFixtureBlocks());
    editor.commands.setNodeSelection(editor.state.doc.child(3) ? positionOf(editor, 3) : 0);
    expect(duplicateTopLevelBlock(editor, 3)).toBe(true);
    const snapshot = expectValidSnapshot(editor);
    expect(snapshot.content[3].type).toBe("liveChart");
    expect(snapshot.content[4].type).toBe("liveChart");
    expect(snapshot.content[4].attrs.block_id).not.toBe(CHART_BLOCK_ID);
    expect(snapshot.content[4].attrs.chart_definition_version_id).toBe(CHART_DEF_ID);
    expectValidSnapshot(editor);
    editor.destroy();
  });

  it("deletes a plain block directly and keeps the schema valid", () => {
    const editor = editorWith(linkedFixtureBlocks());
    const before = blockIds(editor);
    expect(removeTopLevelBlocks(editor, [0])).toBe(true);
    expect(blockIds(editor)).toEqual(before.slice(1));
    expectValidSnapshot(editor);
    editor.destroy();
  });

  it("deletes a linked target together with its dependents — no dangling links remain", () => {
    const editor = editorWith(linkedFixtureBlocks());
    const snapshot = canonicalSnapshot(editor);
    const dependents = findDependentBlocks(snapshot.content, "22222222-2222-4222-8222-222222222222");
    expect(dependents).toHaveLength(2); // evidence + insight
    const idToIndex = new Map(snapshot.content.map((block, index) => [block.attrs.block_id, index]));
    const indices = [1, ...dependents.map((d) => idToIndex.get(d.blockId) as number)];
    expect(removeTopLevelBlocks(editor, indices)).toBe(true);
    const after = expectValidSnapshot(editor);
    const remaining = after.content.map((block) => block.type);
    expect(remaining).toEqual(["heading", "liveChart"]);
    // The evidence link is explicitly updated: it was removed WITH its target.
    const graph = buildLinkGraph(after.content);
    expect(graph.evidenceIds.has(EVIDENCE_ID)).toBe(false);
    expect(graph.hypothesisIds.has(HYPOTHESIS_ID)).toBe(false);
    editor.destroy();
  });

  it("undo restores the previous state (one step per operation)", () => {
    const editor = editorWith(linkedFixtureBlocks());
    const before = editor.getJSON();
    expect(removeTopLevelBlocks(editor, [0])).toBe(true);
    expect(editor.state.doc.childCount).toBe(4);
    editor.commands.undo();
    expect(editor.getJSON()).toEqual(before);
    expectValidSnapshot(editor);
    editor.destroy();
  });
});

describe("keyboard shortcuts", () => {
  it("moves the current block with Mod-Alt-ArrowUp/Down", () => {
    const editor = editorWith(linkedFixtureBlocks());
    // Put the selection on the second block (the hypothesis card is atomic;
    // a NodeSelection mirrors selecting the card in the paper).
    editor.commands.setNodeSelection(positionOf(editor, 1));
    expect(pressShortcut(editor, "Mod-Alt-ArrowUp")).toBe(true);
    expect(blockIds(editor)[0]).toBe("22222222-2222-4222-8222-222222222222");
    expectValidSnapshot(editor);
    expect(pressShortcut(editor, "Mod-Alt-ArrowDown")).toBe(true);
    expect(blockIds(editor)[1]).toBe("22222222-2222-4222-8222-222222222222");
    editor.destroy();
  });

  it("duplicates with Mod-Shift-d", () => {
    const editor = editorWith(linkedFixtureBlocks());
    editor.commands.setNodeSelection(positionOf(editor, 1));
    expect(pressShortcut(editor, "Mod-Shift-d")).toBe(true);
    const snapshot = expectValidSnapshot(editor);
    expect(snapshot.content.filter((b) => b.type === "hypothesis")).toHaveLength(2);
    const hypothesisIds = snapshot.content
      .filter((b) => b.type === "hypothesis")
      .map((b) => (b.type === "hypothesis" ? b.attrs.hypothesis_id : ""));
    expect(new Set(hypothesisIds).size).toBe(2);
    editor.destroy();
  });

  it("routes a keyboard delete of a linked target through the confirmation bridge", () => {
    const editor = editorWith(linkedFixtureBlocks());
    const requestSpy = vi.fn(() => true);
    editor.storage.editorUiBridge.requestBlockDelete = requestSpy;
    editor.commands.setNodeSelection(positionOf(editor, 1)); // hypothesis with dependents
    // The shortcut must NOT delete: it requests the confirmation dialog.
    expect(pressShortcut(editor, "Mod-Shift-Backspace")).toBe(false);
    expect(requestSpy).toHaveBeenCalledWith(1);
    expect(editor.state.doc.childCount).toBe(5);
    expectValidSnapshot(editor);
    editor.destroy();
  });

  it("deletes an unlinked block directly via Mod-Shift-Backspace", () => {
    const editor = editorWith(linkedFixtureBlocks());
    editor.commands.setNodeSelection(positionOf(editor, 0)); // heading, no dependents
    expect(pressShortcut(editor, "Mod-Shift-Backspace")).toBe(true);
    expect(editor.state.doc.childCount).toBe(4);
    expectValidSnapshot(editor);
    editor.destroy();
  });
});

describe("stable ids", () => {
  it("keeps block ids through reorder, edit and undo (remap never happens)", () => {
    const editor = editorWith(linkedFixtureBlocks());
    const original = blockIds(editor);
    moveTopLevelBlock(editor, 4, -1);
    moveTopLevelBlock(editor, 3, 1);
    const afterMoves = blockIds(editor);
    for (const id of original) {
      expect(afterMoves).toContain(id);
    }
    // Typing does not remap ids either.
    editor.commands.setTextSelection(2);
    editor.commands.insertContent("x");
    expect(blockIds(editor)).toEqual(blockIds(editor));
    const idsAfterTyping = blockIds(editor);
    for (const id of original) {
      expect(idsAfterTyping).toContain(id);
    }
    editor.commands.undo();
    expect(blockIds(editor)).toEqual(afterMoves);
    editor.destroy();
  });

  it("allocates ids for Tiptap-normalized top-level nodes (empty doc, Enter split)", async () => {
    const editor = new Editor({ extensions: EDITOR_EXTENSIONS, content: "" });
    // The create event (and its fill pass) runs in a post-mount macrotask.
    await new Promise((resolve) => setTimeout(resolve, 0));
    // Empty document normalizes to one empty paragraph — the plugin assigns
    // a stable id, so the state serializes canonically.
    expectValidSnapshot(editor);
    expect(editor.getJSON().content?.[0]?.attrs?.block_id).toEqual(expect.any(String));
    editor.destroy();

    const editor2 = editorWith(linkedFixtureBlocks());
    editor2.commands.setTextSelection(2);
    // Real keydown path (the keyboardShortcut command helper replays steps
    // without plugin effects — a documented jsdom limitation, like the
    // ADR-018 undo granularity note).
    expect(pressShortcut(editor2, "Enter")).toBe(true);
    expect(editor2.state.doc.childCount).toBe(6);
    const snapshot = expectValidSnapshot(editor2);
    const ids = snapshot.content.map((block) => block.attrs.block_id);
    expect(new Set(ids).size).toBe(ids.length);
    editor2.destroy();
  });
});

describe("currentTopLevelIndex", () => {
  it("resolves the top-level block under text and node selections", () => {
    const editor = editorWith(linkedFixtureBlocks());
    editor.commands.setTextSelection(2);
    expect(currentTopLevelIndex(editor)).toBe(0);
    editor.commands.setNodeSelection(positionOf(editor, 2));
    expect(currentTopLevelIndex(editor)).toBe(2);
    editor.destroy();
  });
});

function positionOf(editor: Editor, index: number): number {
  let pos = 0;
  for (let i = 0; i < index; i += 1) {
    pos += editor.state.doc.child(i).nodeSize;
  }
  return pos;
}

/**
 * Real keymap path: dispatch a synthetic keydown through ProseMirror's
 * handleKeyDown (the same path a physical keypress takes, so the shortcut's
 * own transaction — including its selection — applies verbatim). Tiptap
 * resolves `Mod` to Ctrl in non-mac environments (jsdom), matching its
 * keymap normalization.
 */
function pressShortcut(editor: Editor, keyName: string): boolean {
  const parts = keyName.split("-");
  const key = parts[parts.length - 1];
  const event = new KeyboardEvent("keydown", {
    key: key === "Space" ? " " : key,
    altKey: parts.includes("Alt"),
    ctrlKey: parts.includes("Mod") || parts.includes("Ctrl"),
    metaKey: parts.includes("Meta"),
    shiftKey: parts.includes("Shift"),
    bubbles: true,
    cancelable: true,
  });
  return editor.view.someProp("handleKeyDown", (handler) => handler(editor.view, event)) ?? false;
}
