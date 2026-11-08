"use client";

import { cn } from "@/lib/utils";

import type { OutlineEntry } from "./outline";

/**
 * Outline pane (NI-039): the heading structure of the paper, anchored to the
 * headings' stable block_ids (EDITOR_SPECIFICATION "Outline follows heading
 * IDs"). Activating an entry selects and focuses that heading in the editor.
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
          No headings yet. Add a heading block to build the outline.
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
                {entry.text || "(empty heading)"}
              </span>
              <span className="sr-only">, level {entry.level}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
