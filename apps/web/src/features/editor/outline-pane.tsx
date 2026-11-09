"use client";

import { cn } from "@/lib/utils";

import type { OutlineEntry } from "./outline";

/**
 * The outline selects headings and hypotheses by their stable block IDs.
 * The same component renders in the desktop aside, the tablet collapsible
 * section and the mobile drawer.
 */
export function OutlinePane({
  entries,
  activeBlockId,
  onNavigate,
  className,
}: {
  entries: readonly OutlineEntry[];
  activeBlockId: string | null;
  onNavigate: (blockId: string) => void;
  className?: string;
}) {
  if (entries.length === 0) {
    return (
      <nav aria-label="Document outline" className={cn("px-1", className)}>
        <p className="text-metadata leading-metadata text-text-secondary px-2 py-1">
          Add a heading or hypothesis to build the outline.
        </p>
      </nav>
    );
  }
  return (
    <nav aria-label="Document outline" className={cn("px-1", className)}>
      <ul className="flex flex-col">
        {entries.map((entry) => (
          <li key={entry.blockId}>
            <button
              type="button"
              data-hypothesis-id={entry.hypothesisId}
              aria-current={entry.blockId === activeBlockId ? "true" : undefined}
              onClick={() => onNavigate(entry.blockId)}
              style={{ paddingInlineStart: `${(entry.level - 1) * 16 + 8}px` }}
              className={cn(
                "flex min-h-11 w-full items-center rounded-control px-2 text-left text-ui leading-ui",
                "hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                entry.blockId === activeBlockId ? "bg-surface-muted font-medium text-text" : "text-text-secondary",
              )}
            >
              <span className="truncate">
                {entry.hypothesisId ? `Hypothesis · ${entry.text}` : entry.text || "(empty heading)"}
              </span>
              {!entry.hypothesisId ? <span className="sr-only">, level {entry.level}</span> : null}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
