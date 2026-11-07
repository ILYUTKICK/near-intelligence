import { Node, mergeAttributes } from "@tiptap/core";
import {
  NodeViewWrapper,
  ReactNodeViewRenderer,
  type NodeViewProps,
} from "@tiptap/react";

import { blockIdAttr, jsonAttr, stringAttr } from "../attributes";
import { shortId } from "./display";

import type { CanonicalCell, CanonicalTableColumn } from "../canonical";

/**
 * Canonical `dataTable` block (P0): a small authored table (max 1k cells) or
 * an approved dataset reference. The block is atomic; cells are authored as
 * strings in the properties panel so no float parsing ever touches authored
 * values (financial precision stays exact). The paper view renders the first
 * rows honestly and names the full count.
 */
export const DataTable = Node.create({
  name: "dataTable",
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      block_id: blockIdAttr(),
      columns: jsonAttr("columns"),
      rows: jsonAttr("rows"),
      dataset_version_id: stringAttr("dataset_version_id"),
    };
  },

  parseHTML() {
    return [{ tag: "div[data-data-table]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes({ "data-data-table": "" }, HTMLAttributes)];
  },

  addNodeView() {
    return ReactNodeViewRenderer(DataTableBlockView);
  },
});

const DISPLAY_ROW_LIMIT = 10;

function cellText(cell: CanonicalCell): string {
  if (cell === null) {
    return "";
  }
  if (typeof cell === "boolean") {
    return cell ? "true" : "false";
  }
  return String(cell);
}

export function DataTableBlockView({ node, editor, getPos }: NodeViewProps) {
  const attrs = node.attrs as {
    block_id: string | null;
    columns: CanonicalTableColumn[] | null;
    rows: CanonicalCell[][] | null;
    dataset_version_id: string | null;
  };
  const columns = attrs.columns ?? [];
  const rows = attrs.rows ?? null;

  return (
    <NodeViewWrapper
      data-data-table-block
      className="my-4 overflow-x-auto rounded-surface border border-control-border bg-surface p-4"
      aria-label="Data table block"
    >
      <div contentEditable={false} className="not-prose">
        {rows !== null ? (
          <>
            <table className="w-full border-collapse text-body leading-body text-text">
              <caption className="sr-only">Authored data table</caption>
              <thead>
                <tr>
                  {columns.map((column) => (
                    <th
                      key={column.key}
                      scope="col"
                      className="border border-border bg-surface-muted px-2 py-1 text-left font-ui text-ui leading-ui font-medium"
                    >
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, DISPLAY_ROW_LIMIT).map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="border border-border px-2 py-1">
                        {cellText(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > DISPLAY_ROW_LIMIT ? (
              <p className="mt-1 text-metadata leading-metadata text-text-secondary">
                Showing the first {DISPLAY_ROW_LIMIT} of {rows.length} rows — the full table stays
                in the block and exports completely.
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-body leading-body text-text-secondary">
            Dataset projection of <span className="break-all">{shortId(attrs.dataset_version_id)}</span>
            {" "}— the projection renders from the pinned dataset version with the data tasks; the
            block's structural operations are active now.
          </p>
        )}
        <button
          type="button"
          className="mt-2 min-h-11 rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          onClick={() => {
            const pos = typeof getPos === "function" ? getPos() : undefined;
            if (typeof pos === "number") {
              editor.commands.setNodeSelection(pos);
            }
            editor.storage.editorUiBridge.openBlockProperties(attrs.block_id);
          }}
        >
          Edit properties
        </button>
      </div>
    </NodeViewWrapper>
  );
}
