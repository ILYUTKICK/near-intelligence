"use client";

import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Dropdown menu per DESIGN_SYSTEM.md (block handle/menu, nav account menu).
 * Radix provides the keyboard model (Enter/Space/ArrowDown open, arrows
 * navigate, Home/End jump, Escape closes, focus returns); items meet the
 * 44px touch target and keep a hover state behind (hover:hover).
 */
export const DropdownMenu = DropdownMenuPrimitive.Root;
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

export function DropdownMenuContent({
  className,
  sideOffset = 4,
  children,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.Content>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-48 p-1",
          "rounded-control border-2 border-panel-border bg-surface",
          "shadow-[var(--shadow-overlay)]",
          className,
        )}
        {...props}
      >
        {children}
      </DropdownMenuPrimitive.Content>
    </DropdownMenuPrimitive.Portal>
  );
}

export function DropdownMenuItem({
  className,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.Item>) {
  return (
    <DropdownMenuPrimitive.Item
      className={cn(
        "flex min-h-11 cursor-pointer items-center rounded-control px-3",
        "text-ui leading-ui text-text select-none",
        "focus:bg-surface-muted focus:outline-none",
        "hover:bg-surface-muted data-[highlighted]:bg-surface-muted",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-60",
        className,
      )}
      {...props}
    >
      {props.children}
    </DropdownMenuPrimitive.Item>
  );
}

export function DropdownMenuSeparator({
  className,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.Separator>) {
  return (
    <DropdownMenuPrimitive.Separator
      className={cn("-mx-1 my-1 h-px bg-border", className)}
      {...props}
    />
  );
}
