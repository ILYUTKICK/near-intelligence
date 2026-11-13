"use client";

import { cn } from "@/lib/utils";

import type { TableModel } from "./option-builder";

/**
 * Accessible exact-value table for a rendered chart (NI-033).
 *
 * CHART_SYSTEM.md: "charts cannot require hover" — every plotted value is
 * readable here as the exact decimal string delivered by the API (grouped
 * for display, never float-rounded), with bounds labeled and missing points
 * shown as gaps with their reasons, never as zero. Scrolls inside a labeled
 * region on small screens; the page itself never overflows.
 */
export function SeriesTable({
  model,
  title,
  instanceLabel,
  className,
}: {
  model: TableModel;
  /** Chart title used in the accessible name/caption. */
  title: string;
  /** Human context distinguishing repeated charts, e.g. "research block 10". */
  instanceLabel?: string;
  className?: string;
}) {
  const hasNotes = model.rows.some((row) =>
    row.cells.some((cell) => cell.kind === "missing" || cell.bound !== null),
  );
  return (
    <div
      role="region"
      aria-label={`${title} — exact data table${instanceLabel ? ` — ${instanceLabel}` : ""}`}
      tabIndex={0}
      className={cn("max-h-64 overflow-auto rounded-control border border-border", className)}
    >
      <table className="w-full border-collapse text-left tabular-nums">
        <caption className="sr-only">{`${title} — equivalent data with exact values${instanceLabel ? ` — ${instanceLabel}` : ""}`}</caption>
        <thead>
          <tr className="bg-surface-muted">
            <th scope="col" className="font-ui text-ui leading-ui px-3 py-2 font-medium">
              Date (UTC)
            </th>
            {model.columns.map((column) => (
              <th key={column.label} scope="col" className="font-ui text-ui leading-ui px-3 py-2 font-medium">
                {column.label} ({column.unit})
              </th>
            ))}
            {hasNotes ? (
              <th scope="col" className="font-ui text-ui leading-ui px-3 py-2 font-medium">
                Notes
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {model.rows.length === 0 ? (
            <tr>
              <td
                colSpan={1 + model.columns.length + (hasNotes ? 1 : 0)}
                className="text-ui leading-ui text-text-secondary px-3 py-2"
              >
                No rows — the empty state above is authoritative; this is not zero.
              </td>
            </tr>
          ) : (
            model.rows.map((row) => {
              const notes = row.cells
                .flatMap((cell, columnIndex) => {
                  const label = model.columns[columnIndex]?.label ?? `series ${columnIndex + 1}`;
                  if (cell.kind === "missing") {
                    return [`${label}: ${cell.reason}`];
                  }
                  return cell.bound !== null ? [`${label}: ${cell.bound}`] : [];
                })
                .join("; ");
              return (
                <tr key={row.date} className="border-t border-border">
                  <td className="text-ui leading-ui px-3 py-2">{row.date}</td>
                  {row.cells.map((cell, columnIndex) => (
                    <td key={columnIndex} className="text-ui leading-ui px-3 py-2 font-medium">
                      {cell.kind === "value" ? cell.display : "not observed"}
                    </td>
                  ))}
                  {hasNotes ? (
                    <td className="text-ui leading-ui text-text-secondary px-3 py-2">{notes || "—"}</td>
                  ) : null}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
