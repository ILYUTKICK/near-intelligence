/**
 * NI-038 prototype acceptance: node schema serialization/reload round trip
 * and typing/undo survival across React node updates. Synthetic content
 * only. Real IME/paste/selection browser checks are recorded as operator-
 * manual steps (jsdom cannot emulate IME composition).
 */
import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ChartBlock } from "@/features/editor/prototype/ChartNode";
import { InsightCard } from "@/features/editor/prototype/InsightCard";

const extensions = [StarterKit, ChartBlock, InsightCard];

let editor: Editor;

beforeEach(() => {
  editor = new Editor({ extensions, content: "<p>Anchor paragraph.</p>" });
});

afterEach(() => {
  editor.destroy();
});

describe("Prototype serialization round trip", () => {
  it("inserts chart and insight nodes; JSON survives reload identically", () => {
    editor.commands.insertChartBlock({
      chartLabel: "Synthetic chart",
      seriesLabel: "Series A",
      points: 30,
    });
    editor.commands.insertInsightCard({
      insightTitle: "Synthetic insight",
      body: "Prototype body.",
    });

    const jsonAfterInsert = editor.getJSON();

    // Reload: canonical storage path is JSON (NI-036 document content) —
    // a fresh editor instance parses the serialized JSON...
    const reloaded = new Editor({ extensions, content: jsonAfterInsert });
    const jsonAfterReload = reloaded.getJSON();
    reloaded.destroy();

    // ...and the canonical JSON is identical — schema round trip holds.
    expect(jsonAfterReload).toEqual(jsonAfterInsert);
    const types = (jsonAfterInsert.content as Array<{ type: string }>).map((n) => n.type);
    expect(types).toContain("chartBlock");
    expect(types).toContain("insightCard");
    // Attributes survive the round trip.
    const chartNode = (jsonAfterInsert.content as Array<{ type: string; attrs?: Record<string, unknown> }>).find(
      (n) => n.type === "chartBlock",
    );
    expect(chartNode?.attrs?.chartLabel).toBe("Synthetic chart");
    expect(chartNode?.attrs?.points).toBe(30);
  });

  it("keeps typing and undo intact after React node updates", () => {
    editor.commands.insertChartBlock({
      chartLabel: "Chart",
      seriesLabel: "S",
      points: 1,
    });
    // Typing after a node insert lands in a new paragraph (atomic node
    // boundary): undo twice returns to the anchor state.
    editor.commands.insertContent("<p>typed after node</p>");
    expect(editor.getHTML()).toContain("typed after node");

    // Undo works across the React node update boundary. Adjacent inserts may
    // group into one history step, so the only stable assertion is: the typed
    // text is gone after undo, and the document is a valid parseable state.
    editor.commands.undo();
    expect(editor.getHTML()).not.toContain("typed after node");
    const reparse = new Editor({ extensions, content: editor.getJSON() });
    expect(reparse.getJSON()).toEqual(editor.getJSON());
    reparse.destroy();
  });

  it("empty document stays valid per the canonical schema", () => {
    const empty = new Editor({ extensions, content: "" });
    // Tiptap normalizes an empty doc to a single empty paragraph (doc schema
    // requires block content) — parsing succeeds, which is the invariant.
    expect(empty.getJSON().content).toEqual([{ type: "paragraph" }]);
    empty.destroy();
  });
});
