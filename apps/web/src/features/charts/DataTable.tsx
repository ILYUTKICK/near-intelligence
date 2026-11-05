"use client";

import { cn } from "@/lib/utils";

import type { FrameTableRow } from "./chart-frame-types";

/**
 * Equivalent accessible data table for a chart frame (CHART_SYSTEM.md:
 * "charts cannot require hover"). Scrolls inside a labeled region on small
 * screens; the page itself never overflows.
 */
export function DataTable({
  caption,
  rows,
  valueHeader = "Value",
  className,
}: {
  caption: string;
  rows: FrameTableRow[];
  valueHeader?: string;
  className?: string;
}) {
  return (
    <div
      role="region"
      aria-label={`${caption} — data table`}
      tabIndex={0}
      className={cn("max-h-64 overflow-auto rounded-control border border-border", className)}
    >
      <table className="w-full border-collapse text-left tabular-nums">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="bg-surface-muted">
            <th scope="col" className="font-ui text-ui leading-ui px-3 py-2 font-medium">
              Period
            </th>
            <th scope="col" className="font-ui text-ui leading-ui px-3 py-2 font-medium">
              {valueHeader}
            </th>
            <th scope="col" className="font-ui text-ui leading-ui px-3 py-2 font-medium">
              Note
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={3} className="text-ui leading-ui text-text-secondary px-3 py-2">
                No rows — the empty state above is authoritative; this is not zero.
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.period} className="border-t border-border">
                <td className="text-ui leading-ui px-3 py-2">{row.period}</td>
                <td className="text-ui leading-ui px-3 py-2 font-medium">{row.value}</td>
                <td className="text-ui leading-ui text-text-secondary px-3 py-2">
                  {row.note ?? "—"}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
