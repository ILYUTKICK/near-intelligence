import { Node, mergeAttributes } from "@tiptap/core";
import {
  NodeViewWrapper,
  ReactNodeViewRenderer,
  type NodeViewProps,
} from "@tiptap/react";
import { useState } from "react";

/**
 * NI-038 prototype: atomic chart block node. The whole node is selected/
 * deleted as one unit (atom: true); its controls live inside the node view
 * and must not swallow editor keyboard behavior. Synthetic data only — no
 * real metrics bind until NI-032/NI-033.
 */

interface ChartAttrs {
  chartLabel: string;
  seriesLabel: string;
  points: number;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    chartBlock: {
      insertChartBlock: (attrs: ChartAttrs) => ReturnType;
    };
  }
}

function ChartNodeView({ node, deleteNode }: NodeViewProps) {
  const attrs = node.attrs as ChartAttrs;
  const [note, setNote] = useState("");

  return (
    <NodeViewWrapper
      className="my-4 rounded-surface border border-control-border bg-surface p-4"
      data-chart-block
    >
      {/* contenteditable=false keeps typing outside; buttons stay keyboard-reachable */}
      <div contentEditable={false} className="not-prose">
        <p className="font-ui text-ui leading-ui font-medium text-text">
          {attrs.chartLabel}
        </p>
        <p className="text-metadata leading-metadata text-text-secondary">
          {attrs.seriesLabel} · {attrs.points} points (synthetic fixture)
        </p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            data-chart-action="annotate"
            className="rounded-control border border-control-border px-2 py-1 font-ui text-ui leading-ui text-text hover:bg-surface-muted"
            onClick={() => setNote("annotated")}
          >
            Annotate
          </button>
          <button
            type="button"
            data-chart-action="remove"
            className="rounded-control border border-control-border px-2 py-1 font-ui text-ui leading-ui text-danger hover:bg-surface-muted"
            onClick={() => deleteNode()}
          >
            Remove block
          </button>
        </div>
        {note ? (
          <p className="text-metadata leading-metadata text-text-secondary mt-1">{note}</p>
        ) : null}
      </div>
      {/* Hidden editable slot: proves editor focus survives nested controls. */}
      <input
        aria-label="Chart note (prototype)"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        className="sr-only"
      />
    </NodeViewWrapper>
  );
}

export const ChartBlock = Node.create({
  name: "chartBlock",
  group: "block",
  atom: true,
  draggable: true,

  addAttributes() {
    return {
      chartLabel: { default: "Chart" },
      seriesLabel: { default: "Series" },
      points: { default: 0 },
    };
  },

  addCommands() {
    return {
      insertChartBlock:
        (attrs: ChartAttrs) =>
        ({ commands }) => {
          return commands.insertContent({ type: this.name, attrs });
        },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'div[data-chart-block]',
        getAttrs: (element) => ({
          chartLabel: element.getAttribute("data-chart-label") ?? "Chart",
          seriesLabel: element.getAttribute("data-series-label") ?? "Series",
          points: Number(element.getAttribute("data-points") ?? 0),
        }),
      },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    return ["div", mergeAttributes({
      "data-chart-block": "",
      "data-chart-label": node.attrs.chartLabel,
      "data-series-label": node.attrs.seriesLabel,
      "data-points": String(node.attrs.points),
    }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(ChartNodeView);
  },
});
