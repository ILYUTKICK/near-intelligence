import { Node, mergeAttributes } from "@tiptap/core";
import {
  NodeViewWrapper,
  ReactNodeViewRenderer,
  type NodeViewProps,
} from "@tiptap/react";

import { blockIdAttr, jsonAttr, stringAttr } from "../attributes";
import { emitOpenBlockProperties } from "../ui-bridge";
import { shortId } from "./display";

/**
 * Canonical `liveChart` block (P0, EDITOR_SPECIFICATION): chart reference +
 * mode + selection + observed dataset pin. The block is atomic — it is
 * selected, moved, duplicated and deleted as one unit, and its context pins
 * travel with it. Interactive chart rendering inside the editor and the
 * chart properties flow arrive with NI-042; until then the node view
 * shows the persisted context honestly instead of a placeholder chart.
 */
export const LiveChart = Node.create({
  name: "liveChart",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
      chart_definition_version_id: stringAttr("chart_definition_version_id"),
      mode: stringAttr("mode"),
      selection: jsonAttr("selection"),
      observed_dataset_version_id: stringAttr("observed_dataset_version_id"),
      snapshot_id: stringAttr("snapshot_id"),
    };
  },

  parseHTML() {
    return [{ tag: "div[data-live-chart]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes({ "data-live-chart": "" }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(LiveChartBlockView);
  },
});

function LiveChartBlockView({ node, editor, getPos }: NodeViewProps) {
  const attrs = node.attrs as {
    block_id: string | null;
    chart_definition_version_id: string | null;
    mode: string | null;
    selection: { start?: string; end?: string; filters?: Record<string, string> } | null;
    observed_dataset_version_id: string | null;
    snapshot_id: string | null;
  };
  const selection = attrs.selection ?? {};
  return (
    <NodeViewWrapper
      data-live-chart-block
      className="my-4 rounded-surface border border-control-border bg-surface p-4"
      aria-label="Live chart block"
    >
      <div contentEditable={false} className="not-prose">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-ui text-ui leading-ui font-medium text-text">Live chart</p>
          <span className="rounded-control border border-control-border px-1.5 py-0.5 text-metadata leading-metadata text-text-secondary">
            {attrs.mode === "snapshot" ? "snapshot mode" : "live mode"}
          </span>
        </div>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-metadata leading-metadata text-text-secondary">
          <dt>Chart definition version</dt>
          <dd className="break-all">{shortId(attrs.chart_definition_version_id)}</dd>
          <dt>Selection window</dt>
          <dd>
            {selection.start ?? "?"} – {selection.end ?? "?"} (UTC, half-open)
          </dd>
          <dt>Inspected filters</dt>
          <dd className="break-words">{Object.entries(selection.filters ?? {}).map(([key, value]) => `${key}: ${value}`).join("; ") || "None"}</dd>
          <dt>Observed dataset version</dt>
          <dd className="break-all">{shortId(attrs.observed_dataset_version_id)}</dd>
          {attrs.snapshot_id ? (
            <>
              <dt>Snapshot</dt>
              <dd className="break-all">{shortId(attrs.snapshot_id)}</dd>
            </>
          ) : null}
        </dl>
        <p className="mt-2 text-metadata leading-metadata text-text-secondary">
          The interactive chart (hover, table, range controls) renders here with NI-042.
          The block&apos;s context pins and its structural operations are active now.
        </p>
        <button
          type="button"
          className="mt-2 min-h-11 rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          onClick={() => {
            const pos = typeof getPos === "function" ? getPos() : undefined;
            if (typeof pos === "number") {
              editor.commands.setNodeSelection(pos);
            }
            emitOpenBlockProperties(editor, attrs.block_id);
          }}
        >
          Edit properties
        </button>
      </div>
    </NodeViewWrapper>
  );
}
