"use client";

import * as SelectPrimitive from "@radix-ui/react-select";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Select per DESIGN_SYSTEM.md control contract. Radix provides the keyboard
 * model (Enter/Space/ArrowDown open, arrows navigate, Escape closes, focus
 * returns to the trigger); this wrapper applies the token styling, a 44px
 * trigger and item targets, and a persistent label via the caller's Label.
 */
export const Select = SelectPrimitive.Root;
export const SelectValue = SelectPrimitive.Value;
export const SelectGroup = SelectPrimitive.Group;

export function SelectTrigger({
  className,
  children,
  ...props
}: ComponentProps<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        "flex h-11 w-full items-center justify-between gap-2 rounded-control border-2",
        "border-control-border bg-surface px-3",
        "font-ui text-ui leading-ui text-text",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
        "aria-invalid:border-danger",
        "disabled:pointer-events-none disabled:opacity-60",
        "data-[placeholder]:text-text-secondary",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          className="size-4 shrink-0 text-text-secondary"
        >
          <path
            d="M4 6l4 4 4-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

export function SelectContent({
  className,
  children,
  ...props
}: ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        position="popper"
        sideOffset={4}
        className={cn(
          "z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden",
          "rounded-control border-2 border-panel-border bg-surface",
          "shadow-[var(--shadow-overlay)]",
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Viewport className="p-1">{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

export function SelectItem({
  className,
  children,
  ...props
}: ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "flex min-h-11 cursor-pointer items-center rounded-control px-3",
        "text-ui leading-ui text-text select-none",
        "focus:bg-surface-muted focus:outline-none",
        "data-[state=checked]:font-medium",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-60",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  );
}
