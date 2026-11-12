"use client";

import type { Editor, JSONContent } from "@tiptap/core";

import {
  MAX_DATATABLE_CELLS,
  MAX_DATATABLE_COLUMNS,
  type CanonicalCell,
  type CanonicalTableColumn,
} from "./canonical";
import { blockLabel, type CurrentBlock } from "./commands";
import { RichFragmentView } from "./blocks/rich-fragment";
import { fieldPair, formatTimestamp, shortId } from "./blocks/display";
import { assessmentLabel } from "./hypotheses/assessment";
import { cn } from "@/lib/utils";

/**
 * Context tools pane (NI-039, UI_SCREEN_SPECIFICATIONS "right contextual
 * panel switches Add Block/Chart Library/Properties/Sources/Insight/Model").
 * NI-039 delivers the Properties surface: the details of the selected block
 * — for annotation cards the full NI-046 contract fields (ResolvedContext
 * display for pinned chart contexts) and the authored data table editor.
 * Chart Library/Insight/Model panels arrive with NI-041/NI-047 and are not
 * rendered as dead placeholders.
 */

const PANEL_DDL_CLASS = "text-metadata leading-metadata text-text-secondary";

function InfoList({ children }: { children: React.ReactNode }) {
  return (
    <dl className="grid gap-y-0.5 text-metadata text-text-secondary [&_dt]:mt-2 [&_dt]:font-medium [&_dd]:min-w-0 [&_dd]:break-normal [&_dd]:[overflow-wrap:anywhere]">
      {children}
    </dl>
  );
}

function FieldNote({ children }: { children: React.ReactNode }) {
  return <p className={cn("mt-2", PANEL_DDL_CLASS)}>{children}</p>;
}

// --------------------------------------------------------------------------- //
// Authored data table editor
// --------------------------------------------------------------------------- //

const COLUMN_TYPES = ["string", "number", "date"] as const;

interface TablePatch {
  columns: CanonicalTableColumn[];
  rows: CanonicalCell[][];
}

function uniqueColumnKey(existing: Array<{ key: string }>): string {
  let index = existing.length + 1;
  let key = `column_${index}`;
  const keys = new Set(existing.map((column) => column.key));
  while (keys.has(key)) {
    index += 1;
    key = `column_${index}`;
  }
  return key;
}

export function TableProperties({
  columns,
  rows,
  datasetVersionId,
  onChange,
}: {
  columns: CanonicalTableColumn[];
  rows: CanonicalCell[][] | null;
  datasetVersionId: string | null;
  onChange: (patch: TablePatch) => void;
}) {
  if (rows === null) {
    return (
      <div>
        <InfoList>
          {fieldPair("Kind", "Dataset projection", "tkind")}
          {fieldPair("Dataset version", shortId(datasetVersionId), "tds")}
        </InfoList>
        <FieldNote>
          Dataset projections render from the pinned dataset version with the
          data tasks; the projection itself is never edited here.
        </FieldNote>
      </div>
    );
  }

  const cells = rows.length * columns.length;
  const canAddColumn = columns.length < MAX_DATATABLE_COLUMNS && cells + rows.length <= MAX_DATATABLE_CELLS;
  const canAddRow = cells + columns.length <= MAX_DATATABLE_CELLS;
  const inputClass =
    "min-h-11 w-full rounded-control border border-control-border bg-surface px-2 py-1 font-ui text-ui leading-ui text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
  const buttonClass =
    "inline-flex min-h-11 items-center rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:pointer-events-none disabled:opacity-60";

  return (
    <div data-testid="table-properties">
      <p className={PANEL_DDL_CLASS}>
        Authored table · {columns.length} column{columns.length === 1 ? "" : "s"} × {rows.length} row{rows.length === 1 ? "" : "s"} = {cells} of {MAX_DATATABLE_CELLS} allowed cells
      </p>
      <table className="mt-2 w-full border-collapse">
        <caption className="sr-only">Authored table cells</caption>
        <thead>
          <tr>
            {columns.map((column, columnIndex) => (
              <th key={column.key} scope="col" className="border border-border p-1 align-top">
                <label className="sr-only" htmlFor={`table-column-label-${columnIndex}`}>
                  Column {columnIndex + 1} label
                </label>
                <input
                  id={`table-column-label-${columnIndex}`}
                  value={column.label}
                  maxLength={200}
                  onChange={(event) =>
                    onChange({
                      columns: columns.map((entry, index) =>
                        index === columnIndex ? { ...entry, label: event.target.value } : entry,
                      ),
                      rows,
                    })
                  }
                  className={inputClass}
                />
                <label className="sr-only" htmlFor={`table-column-type-${columnIndex}`}>
                  Column {columnIndex + 1} type
                </label>
                <select
                  id={`table-column-type-${columnIndex}`}
                  value={column.type}
                  onChange={(event) =>
                    onChange({
                      columns: columns.map((entry, index) =>
                        index === columnIndex
                          ? { ...entry, type: event.target.value as CanonicalTableColumn["type"] }
                          : entry,
                      ),
                      rows,
                    })
                  }
                  className={cn(inputClass, "mt-1")}
                >
                  {COLUMN_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </th>
            ))}
            <th scope="col" className="sr-only">
              Column actions
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="border border-border p-1">
                  <label className="sr-only" htmlFor={`table-cell-${rowIndex}-${cellIndex}`}>
                    Row {rowIndex + 1}, column {columns[cellIndex]?.label ?? cellIndex + 1}
                  </label>
                  <input
                    id={`table-cell-${rowIndex}-${cellIndex}`}
                    value={cell === null ? "" : String(cell)}
                    maxLength={500}
                    onChange={(event) =>
                      onChange({
                        columns,
                        rows: rows.map((currentRow, currentRowIndex) =>
                          currentRowIndex === rowIndex
                            ? currentRow.map((currentCell, currentCellIndex) =>
                                currentCellIndex === cellIndex ? event.target.value : currentCell,
                              )
                            : currentRow,
                        ),
                      })
                    }
                    className={inputClass}
                  />
                </td>
              ))}
              <td className="border border-border p-1 text-center">
                <button
                  type="button"
                  aria-label={`Remove row ${rowIndex + 1}`}
                  className={cn(buttonClass, "h-11 w-11 justify-center px-0")}
                  onClick={() =>
                    onChange({
                      columns,
                      rows: rows.filter((_, index) => index !== rowIndex),
                    })
                  }
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          className={buttonClass}
          disabled={!canAddColumn}
          onClick={() =>
            onChange({
              columns: [
                ...columns,
                { key: uniqueColumnKey(columns), label: `Column ${columns.length + 1}`, type: "string" },
              ],
              rows: rows.map((row) => [...row, ""]),
            })
          }
        >
          Add column
        </button>
        <button
          type="button"
          className={buttonClass}
          disabled={!canAddRow}
          onClick={() =>
            onChange({
              columns,
              rows: [...rows, columns.map(() => "")],
            })
          }
        >
          Add row
        </button>
        <button
          type="button"
          className={buttonClass}
          disabled={columns.length <= 1}
          onClick={() =>
            onChange({
              columns: columns.slice(0, -1),
              rows: rows.map((row) => row.slice(0, -1)),
            })
          }
        >
          Remove last column
        </button>
      </div>
      <FieldNote>
        Cells are stored exactly as typed (strings keep decimal precision; the
        500-character and 1k-cell limits match the canonical schema). Column
        types describe the intended reading of the column.
      </FieldNote>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Pane
// --------------------------------------------------------------------------- */

const LATER_TASKS_NOTE: Record<string, string> = {
  liveChart:
    "Use the chart controls in the paper to inspect sources, apply a range or filter, and explicitly refresh its observed dataset. These changes are document edits.",
  insight:
    "Use Edit insight on the saved block to revise its note. The evidence context stays pinned.",
  hypothesis:
    "Use Edit hypothesis on the saved block to update the statement or author assessment. Linked evidence keeps the same hypothesis ID.",
  evidence:
    "Use Edit evidence link on the saved block to revise its target, classification or explanation.",
  risk: "Risk body rich-text editing arrives with the annotation tasks; the title is edited on the card itself.",
  dataTable: "Cells are edited below; the block serializes through the canonical schema.",
};

function plainPreview(node: JSONContent, limit = 160): string {
  const collect = (content: JSONContent[] | undefined): string =>
    (content ?? [])
      .map((run) => (run.type === "text" && typeof run.text === "string" ? run.text : ""))
      .join("");
  const text = node.type === "heading" || node.type === "paragraph"
    ? collect(node.content)
    : "";
  if (text.length > limit) {
    return `${text.slice(0, limit)}…`;
  }
  return text || "(empty)";
}

export function ContextPane({
  editor,
  currentBlock,
  onTableChange,
}: {
  editor: Editor;
  currentBlock: CurrentBlock | null;
  onTableChange: (patch: TablePatch) => void;
}) {
  if (!currentBlock) {
    return (
      <div className="px-1">
        <p className={PANEL_DDL_CLASS}>
          Select a block in the paper to see its properties.
        </p>
      </div>
    );
  }

  const nodeJson = editor.state.doc.child(currentBlock.index).toJSON();
  const attrs = (nodeJson.attrs ?? {}) as Record<string, unknown>;
  const blockId = (attrs.block_id as string | null) ?? null;
  const note = LATER_TASKS_NOTE[currentBlock.canonicalType];

  return (
    <div className="px-1" data-testid="context-pane">
      <p className="font-ui text-ui leading-ui font-medium text-text">
        {blockLabel(currentBlock.canonicalType)}
      </p>
      {blockId ? (
        <p className="mt-1 text-metadata leading-metadata text-text-secondary">
          Block id: <span className="break-all font-mono" title={blockId}>{shortId(blockId)}</span>
        </p>
      ) : null}

      <div className="mt-3">
        {currentBlock.canonicalType === "paragraph" || currentBlock.canonicalType === "heading" ? (
          <InfoList>
            {currentBlock.canonicalType === "heading"
              ? fieldPair("Level", `Heading level ${attrs.level as number}`, "hl")
              : null}
            {fieldPair("Preview", plainPreview(nodeJson), "prev")}
          </InfoList>
        ) : null}

        {currentBlock.canonicalType === "bullet_list" || currentBlock.canonicalType === "ordered_list" ? (
          <InfoList>
            {fieldPair("Items", String(nodeJson.content?.length ?? 0), "items")}
          </InfoList>
        ) : null}

        {currentBlock.canonicalType === "dataTable" ? (
          <TableProperties
            columns={(attrs.columns as CanonicalTableColumn[] | null) ?? []}
            rows={(attrs.rows as CanonicalCell[][] | null) ?? null}
            datasetVersionId={(attrs.dataset_version_id as string | null) ?? null}
            onChange={onTableChange}
          />
        ) : null}

        {currentBlock.canonicalType === "risk" ? (
          <div>
            <InfoList>
              {fieldPair("Title", (attrs.title as string | null) ?? "—", "rtitle")}
              {fieldPair(
                "Related hypothesis",
                attrs.related_hypothesis_id ? shortId(attrs.related_hypothesis_id as string) : "None",
                "rh",
              )}
            </InfoList>
            {attrs.body ? (
              <div className="mt-2 text-body leading-body text-text">
                <RichFragmentView fragment={attrs.body as never} />
              </div>
            ) : null}
          </div>
        ) : null}

        {currentBlock.canonicalType === "liveChart" ? (
          <InfoList>
            {/* NI-078 (NI-076 D5): the full technical identifiers live here in
                Properties instead of the paper; the block in the paper keeps
                its compact status row. */}
            {fieldPair("Chart definition version", (attrs.chart_definition_version_id as string | null) ?? "—", "lcv")}
            {fieldPair("Mode", (attrs.mode as string | null) === "snapshot" ? "snapshot" : "live", "lmode")}
            {fieldPair(
              "Selection window",
              (() => {
                const selection = attrs.selection as { start?: string; end?: string } | null;
                return selection ? `${selection.start ?? "?"} – ${selection.end ?? "?"} (UTC, half-open)` : "—";
              })(),
              "lsel",
            )}
            {fieldPair("Observed dataset version", (attrs.observed_dataset_version_id as string | null) ?? "—", "lod")}
            {attrs.snapshot_id
              ? fieldPair("Snapshot", shortId(attrs.snapshot_id as string), "lsnap")
              : null}
          </InfoList>
        ) : null}

        {currentBlock.canonicalType === "insight" ? (
          <div>
            <InfoList>
              {fieldPair("Type", (attrs.type as string | null) ?? "—", "itype")}
              {fieldPair("Classification", (attrs.classification as string | null) ?? "—", "icls")}
              {fieldPair("Hypothesis link", attrs.hypothesis_id ? shortId(attrs.hypothesis_id as string) : "None", "ih")}
              {fieldPair("Authored at", formatTimestamp(attrs.authored_at as string | null), "ia")}
              {fieldPair("Modified at", formatTimestamp(attrs.modified_at as string | null), "im")}
            </InfoList>
            {attrs.body ? (
              <div className="mt-2 text-body leading-body text-text">
                <RichFragmentView fragment={attrs.body as never} />
              </div>
            ) : null}
            {attrs.context ? (
              <div className="mt-2">
                <p className={PANEL_DDL_CLASS}>Pinned context (ResolvedContext)</p>
                <InfoList>
                  {(() => {
                    const context = attrs.context as Record<string, unknown>;
                    if ("chart_definition_version_id" in context) {
                      return (
                        <>
                          {fieldPair("Chart definition version", shortId(context.chart_definition_version_id as string), "cctx-c")}
                          {fieldPair("Dataset version", shortId(context.dataset_version_id as string), "cctx-d")}
                          {fieldPair("Context hash", shortId(context.context_hash as string), "cctx-h")}
                          {fieldPair("Renderer version", String(context.renderer_version), "cctx-r")}
                          {fieldPair("Resolved at", formatTimestamp(context.resolved_at as string), "cctx-t")}
                        </>
                      );
                    }
                    return (
                      <>
                        {fieldPair("Model run", shortId(context.model_run_id as string), "mctx-m")}
                        {fieldPair("Dataset version", shortId(context.dataset_version_id as string), "mctx-d")}
                        {fieldPair("Specification version", String(context.specification_version), "mctx-s")}
                      </>
                    );
                  })()}
                </InfoList>
              </div>
            ) : null}
          </div>
        ) : null}

        {currentBlock.canonicalType === "hypothesis" ? (
          <div>
            <InfoList>
              {fieldPair("Hypothesis ID", shortId(attrs.hypothesis_id as string | null), "hid")}
              {fieldPair("Author assessment", assessmentLabel(attrs.assessment as string | null), "hassess")}
              {fieldPair("Authored at", formatTimestamp(attrs.authored_at as string | null), "ha")}
              {fieldPair("Modified at", formatTimestamp(attrs.modified_at as string | null), "hm")}
            </InfoList>
            <p className="mt-2 text-body leading-body text-text">{(attrs.statement as string | null) ?? ""}</p>
          </div>
        ) : null}

        {currentBlock.canonicalType === "evidence" ? (
          <InfoList>
            {fieldPair("Classification", (attrs.classification as string | null) ?? "—", "ecls")}
            {fieldPair("Hypothesis", shortId(attrs.hypothesis_id as string | null), "eh")}
            {fieldPair("Target", `${(attrs.target_kind as string | null) ?? "—"} ${shortId(attrs.target_id as string | null)}`, "et")}
            {fieldPair("Explanation", (attrs.explanation as string | null) ?? "—", "eexpl")}
          </InfoList>
        ) : null}

        {currentBlock.canonicalType === "divider" ? (
          <FieldNote>Semantic separator; move or remove it with the block operations.</FieldNote>
        ) : null}
      </div>

      {note ? <FieldNote>{note}</FieldNote> : null}
    </div>
  );
}
