import { Node, mergeAttributes } from "@tiptap/core";
import {
  NodeViewWrapper,
  ReactNodeViewRenderer,
  type NodeViewProps,
} from "@tiptap/react";

/**
 * NI-038 prototype: one insight card node (inline-ish block with editable
 * title inside the node view — the nested-editing probe for the prototype).
 */

interface InsightAttrs {
  insightTitle: string;
  body: string;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    insightCard: {
      insertInsightCard: (attrs: InsightAttrs) => ReturnType;
    };
  }
}

function InsightCardView({
  node,
  updateAttributes,
  editor,
}: NodeViewProps) {
  const attrs = node.attrs as InsightAttrs;

  return (
    <NodeViewWrapper
      className="my-4 rounded-surface border border-border bg-surface-muted p-4"
      data-insight-card
    >
      <div contentEditable={false} className="not-prose">
        <p className="text-metadata leading-metadata text-text-secondary font-medium uppercase tracking-wide">
          Insight (prototype)
        </p>
      </div>
      {/* Editable title INSIDE the node view — the nested-editing probe:
          typing here must not corrupt the editor selection state. */}
      <input
        aria-label="Insight title"
        value={attrs.insightTitle}
        onChange={(event) => updateAttributes({ insightTitle: event.target.value })}
        className="w-full rounded-control border border-control-border bg-surface px-2 py-1 font-ui text-ui leading-ui text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      />
      <button
        type="button"
        contentEditable={false}
        data-insight-action="editor-undo"
        className="mt-2 rounded-control border border-control-border px-2 py-1 font-ui text-ui leading-ui text-text hover:bg-surface-muted"
        onClick={() => editor.commands.undo()}
      >
        Undo (editor)
      </button>
      <p className="text-body leading-body text-text-secondary mt-2">{attrs.body}</p>
    </NodeViewWrapper>
  );
}

export const InsightCard = Node.create({
  name: "insightCard",
  group: "block",
  atom: true,

  addAttributes() {
    return {
      insightTitle: { default: "Untitled insight" },
      body: { default: "Prototype insight body." },
    };
  },

  addCommands() {
    return {
      insertInsightCard:
        (attrs: InsightAttrs) =>
        ({ commands }) => {
          return commands.insertContent({ type: this.name, attrs });
        },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'div[data-insight-card]',
        getAttrs: (element) => ({
          insightTitle: element.getAttribute("data-insight-title") ?? "Untitled insight",
          body: element.getAttribute("data-body") ?? "Prototype insight body.",
        }),
      },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    return ["div", mergeAttributes({
      "data-insight-card": "",
      "data-insight-title": node.attrs.insightTitle,
      "data-body": node.attrs.body,
    }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(InsightCardView);
  },
});
