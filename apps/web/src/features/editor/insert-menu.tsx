"use client";

import { useEffect, useRef } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { INSERTABLE_BLOCK_TYPES, type InsertableBlockType } from "./commands";

/**
 * Insert menu (NI-039): labeled P0 block types with shortcut hints
 * (UI_SCREEN_SPECIFICATIONS "Slash menu has labeled types and shortcut
 * hints"). Two surfaces share one item model:
 *
 * - `InsertMenuButton` — the toolbar dropdown (Radix keyboard model);
 * - `SlashMenu` — the positioned popover opened by typing "/" in an empty
 *   top-level text block; arrows + Enter select, Escape closes, and focus
 *   returns to the editor with the selection preserved.
 */

const INSERT_ITEMS: Array<{
  type: InsertableBlockType | "modelResult";
  label: string;
  hint: string;
}> = [
  { type: "paragraph", label: "Paragraph", hint: "Plain text" },
  { type: "heading", label: "Heading 1", hint: "Section title, level 1" },
  { type: "heading", label: "Heading 2", hint: "Section title, level 2" },
  { type: "heading", label: "Heading 3", hint: "Section title, level 3" },
  { type: "bullet_list", label: "Bullet list", hint: "Unordered list block" },
  { type: "ordered_list", label: "Ordered list", hint: "Numbered list block" },
  { type: "dataTable", label: "Data table", hint: "Small authored table (max 1k cells)" },
  { type: "risk", label: "Risk", hint: "Explicit counterargument card" },
  // NI-055: the model result is pinned server-side — the shell intercepts
  // this choice and opens the published-run chooser instead of a local draft.
  { type: "modelResult", label: "Model result", hint: "Published model run + your interpretation" },
  { type: "divider", label: "Divider", hint: "Semantic separator" },
];

export interface InsertItemChoice {
  type: InsertableBlockType | "modelResult";
  headingLevel?: number;
}

function headingLevelOf(label: string): number | undefined {
  if (label === "Heading 1") return 1;
  if (label === "Heading 2") return 2;
  if (label === "Heading 3") return 3;
  return undefined;
}

export function InsertMenuButton({
  onInsert,
  disabled,
}: {
  onInsert: (choice: InsertItemChoice) => void;
  disabled?: boolean;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled}
        className="inline-flex min-h-11 items-center gap-1.5 rounded-control border border-control-border bg-surface px-3 text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus data-[disabled]:opacity-60"
        aria-label="Insert block"
      >
        Insert block
        <svg aria-hidden="true" viewBox="0 0 12 12" className="size-3">
          <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </DropdownMenuTrigger>
      {/* The menu takes its accessible name from the trigger via Radix's
          aria-labelledby — one name, no duplicate labelling. */}
      <DropdownMenuContent>
        <p className="px-3 py-1.5 text-metadata leading-metadata text-text-secondary">
          Insert after the current block · type <kbd className="rounded-control border border-control-border px-1">/</kbd> in an empty line
        </p>
        <DropdownMenuSeparator />
        {INSERT_ITEMS.map((item) => (
          <DropdownMenuItem
            key={`${item.type}-${item.label}`}
            onSelect={() =>
              onInsert({ type: item.type, headingLevel: headingLevelOf(item.label) })
            }
          >
            <span className="flex w-full items-baseline justify-between gap-4">
              <span>{item.label}</span>
              <span className="text-metadata leading-metadata text-text-secondary">{item.hint}</span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * Positioned slash-menu popover. `position` is the document position of the
 * "/" trigger; `coordinates` come from the shell (client rect of the trigger
 * relative to the paper container).
 */
export function SlashMenu({
  onInsert,
  onClose,
  coordinates,
  boundaryWidth,
}: {
  onInsert: (choice: InsertItemChoice) => void;
  onClose: () => void;
  coordinates: { left: number; top: number } | null;
  boundaryWidth: number | null;
}) {
  const listRef = useRef<HTMLUListElement>(null);
  const activeIndexRef = useRef(0);

  useEffect(() => {
    // Move focus into the menu so arrow/Enter keys work without a pointer;
    // Escape is handled here and focus returns to the editor via the shell.
    listRef.current?.focus();
  }, []);

  const choose = (index: number) => {
    const item = INSERT_ITEMS[index];
    onInsert({ type: item.type, headingLevel: headingLevelOf(item.label) });
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndexRef.current = Math.min(activeIndexRef.current + 1, INSERT_ITEMS.length - 1);
      highlight();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndexRef.current = Math.max(activeIndexRef.current - 1, 0);
      highlight();
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(activeIndexRef.current);
    } else if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
  };

  const highlight = () => {
    const list = listRef.current;
    if (!list) {
      return;
    }
    for (const [index, node] of Array.from(list.children).entries()) {
      if (node instanceof HTMLElement) {
        node.setAttribute("aria-selected", index === activeIndexRef.current ? "true" : "false");
      }
    }
    const active = list.children[activeIndexRef.current];
    if (active instanceof HTMLElement) {
      active.scrollIntoView({ block: "nearest" });
    }
  };

  const left = coordinates ? Math.max(0, coordinates.left) : 0;
  const top = coordinates ? coordinates.top : 0;
  const width = boundaryWidth ? Math.min(288, Math.max(224, boundaryWidth)) : 256;

  return (
    <div
      role="dialog"
      aria-label="Insert block (slash menu)"
      data-testid="slash-menu"
      style={{ left, top, width }}
      className="absolute z-30 rounded-control border border-border bg-surface p-1 shadow-[var(--shadow-overlay)]"
    >
      <p className="px-3 py-1.5 text-metadata leading-metadata text-text-secondary">
        Insert after this block
      </p>
      <ul
        ref={listRef}
        role="listbox"
        aria-label="Block types"
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className="outline-none"
      >
        {INSERT_ITEMS.map((item, index) => (
          <li
            key={`${item.type}-${item.label}`}
            role="option"
            aria-selected={index === 0 ? "true" : "false"}
            id={`slash-menu-item-${index}`}
            className="flex min-h-11 cursor-pointer items-center justify-between gap-4 rounded-control px-3 text-ui leading-ui text-text hover:bg-surface-muted aria-[selected=true]:bg-surface-muted"
            onMouseDown={(event) => {
              event.preventDefault();
              activeIndexRef.current = index;
              choose(index);
            }}
          >
            <span>{item.label}</span>
            <span className="text-metadata leading-metadata text-text-secondary">{item.hint}</span>
          </li>
        ))}
      </ul>
      <p className="px-3 py-1.5 text-metadata leading-metadata text-text-secondary">
        Arrow keys move · Enter inserts · Escape closes
      </p>
    </div>
  );
}

export { INSERTABLE_BLOCK_TYPES };
