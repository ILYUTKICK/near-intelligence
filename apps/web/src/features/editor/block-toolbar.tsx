"use client";

import { cn } from "@/lib/utils";

import { blockLabel, type CurrentBlock } from "./commands";

/**
 * Block operations toolbar (NI-039): the pointer/screen-reader alternative
 * to the keyboard shortcuts, covering every structural operation for the
 * current top-level block. Buttons keep editor focus (mousedown is
 * prevented) so the commands act on the block the user sees in the panel,
 * and reorder/duplicate/delete result announcements ride the shell's polite
 * live region (EDITOR_SPECIFICATION "Up/down reorder buttons announced
 * through polite status").
 */
export function BlockToolbar({
  currentBlock,
  blockCount,
  onMoveUp,
  onMoveDown,
  onDuplicate,
  onDelete,
}: {
  currentBlock: CurrentBlock | null;
  blockCount: number;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const label = currentBlock
    ? blockLabel(currentBlock.canonicalType)
    : "No block selected";
  const canMoveUp = currentBlock !== null && currentBlock.index > 0;
  const canMoveDown = currentBlock !== null && currentBlock.index < blockCount - 1;
  const canOperate = currentBlock !== null;

  const buttonClass = cn(
    "inline-flex min-h-11 items-center gap-2 rounded-control border border-transparent bg-transparent px-2",
    "text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
    "disabled:pointer-events-none disabled:opacity-60",
  );
  const keepFocus = (event: React.MouseEvent) => event.preventDefault();

  return (
    <div
      role="group"
      aria-label="Block operations"
      data-testid="block-toolbar"
      className="flex flex-wrap items-center gap-2"
    >
      <p className="text-ui leading-ui text-text-secondary" data-testid="current-block-label">
        <span className="font-medium text-text">{label}</span>
      </p>
      <button
        type="button"
        className={buttonClass}
        disabled={!canMoveUp}
        onMouseDown={keepFocus}
        onClick={onMoveUp}
        title="Move block up (Mod+Alt+Up)"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4">
          <path d="M8 3v10M3.5 7.5 8 3l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Move up
      </button>
      <button
        type="button"
        className={buttonClass}
        disabled={!canMoveDown}
        onMouseDown={keepFocus}
        onClick={onMoveDown}
        title="Move block down (Mod+Alt+Down)"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4">
          <path d="M8 13V3M3.5 8.5 8 13l4.5-4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Move down
      </button>
      <button
        type="button"
        className={buttonClass}
        disabled={!canOperate}
        onMouseDown={keepFocus}
        onClick={onDuplicate}
        title="Duplicate block (Mod+Shift+D)"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4">
          <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M10.5 2.5h-7a1 1 0 0 0-1 1v7" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        Duplicate
      </button>
      <button
        type="button"
        className={cn(buttonClass, "text-danger")}
        disabled={!canOperate}
        onMouseDown={keepFocus}
        onClick={onDelete}
        title="Delete block (Mod+Shift+Backspace)"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4">
          <path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5 5.3 13a1 1 0 0 0 1 .9h3.4a1 1 0 0 0 1-.9l.8-8.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Delete block
      </button>
    </div>
  );
}
