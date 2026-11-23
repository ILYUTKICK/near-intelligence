"use client";

import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

import { ChartBlock } from "@/features/editor/prototype/ChartNode";
import { InsightCard } from "@/features/editor/prototype/InsightCard";

/**
 * NI-038 prototype route: isolated Tiptap integration probe. Synthetic
 * fixtures only; the serialization round-trip test is the acceptance gate.
 */
export default function EditorPrototypePage() {
  const editor = useEditor({
    extensions: [StarterKit, ChartBlock, InsightCard],
    content: `<p>Prototype paragraph before the chart.</p>`,
  });

  return (
    <div className="max-w-(--width-prose)">
      <h1>Editor prototype</h1>
      <p className="text-body leading-body text-text-secondary mt-2">
        NI-038 isolation probe: type below, insert the synthetic chart/insight nodes, and check
        that typing/undo survive node updates. Data is synthetic.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => editor?.commands.insertChartBlock({ chartLabel: "Synthetic chart", seriesLabel: "Series A", points: 30 })}
          className="rounded-control border border-control-border px-3 py-2 font-ui text-ui leading-ui text-text hover:bg-surface-muted"
        >
          Insert chart block
        </button>
        <button
          type="button"
          onClick={() => editor?.commands.insertInsightCard({ insightTitle: "Synthetic insight", body: "Prototype body." })}
          className="rounded-control border border-control-border px-3 py-2 font-ui text-ui leading-ui text-text hover:bg-surface-muted"
        >
          Insert insight card
        </button>
      </div>
      <div className="mt-6 rounded-surface border-2 border-panel-border bg-surface p-4 prose-editor" data-testid="editor-root">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
