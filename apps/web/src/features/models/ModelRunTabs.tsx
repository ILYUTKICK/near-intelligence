"use client";

import { useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Keyboard-accessible section tabs for the published model result
 * (NI-097): Result / Diagnostics / Specification / Reproduction, styled
 * after the approved mockup. WAI-ARIA tabs pattern: roving focus with
 * Arrow/Home/End, automatic activation, one visible panel.
 */
export function ModelRunTabs({
  tabs,
}: {
  tabs: Array<{ id: string; label: string; content: ReactNode }>;
}) {
  const [activeId, setActiveId] = useState(tabs[0]?.id ?? "");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function focusAndSelect(index: number): void {
    const tab = tabs[index];
    if (!tab) {
      return;
    }
    setActiveId(tab.id);
    tabRefs.current[index]?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent, index: number): void {
    let next: number | undefined;
    if (event.key === "ArrowRight") {
      next = (index + 1) % tabs.length;
    } else if (event.key === "ArrowLeft") {
      next = (index + tabs.length - 1) % tabs.length;
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = tabs.length - 1;
    }
    if (next !== undefined) {
      event.preventDefault();
      focusAndSelect(next);
    }
  }

  return (
    <div>
      <div
        role="tablist"
        aria-label="Published result sections"
        className="flex flex-wrap gap-1 border-b border-border"
      >
        {tabs.map((tab, index) => {
          const selected = tab.id === activeId;
          return (
            <button
              key={tab.id}
              ref={(node) => {
                tabRefs.current[index] = node;
              }}
              role="tab"
              id={`model-tab-${tab.id}`}
              aria-selected={selected}
              aria-controls={`model-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActiveId(tab.id)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={cn(
                "rounded-t-control px-4 py-2.5 font-ui text-ui leading-ui font-medium transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                selected
                  ? "border border-border border-b-transparent bg-surface text-text"
                  : "text-text-secondary hover:bg-surface-muted hover:text-text",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`model-panel-${tab.id}`}
          aria-labelledby={`model-tab-${tab.id}`}
          hidden={tab.id !== activeId}
          className="pt-6"
        >
          {tab.content}
        </div>
      ))}
    </div>
  );
}
