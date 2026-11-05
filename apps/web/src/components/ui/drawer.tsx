"use client";

import { Drawer as DrawerPrimitive } from "vaul";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Drawer per DESIGN_SYSTEM.md responsive rules: the app sidebar becomes a
 * focus-trapped drawer on phones with safe-area padding. Vaul supplies the
 * focus trap, Escape close and drag interaction; motion stays in the
 * restrained 120–180ms band and honors prefers-reduced-motion.
 */
export const Drawer = DrawerPrimitive.Root;
export const DrawerTrigger = DrawerPrimitive.Trigger;
export const DrawerClose = DrawerPrimitive.Close;
export const DrawerTitle = DrawerPrimitive.Title;
export const DrawerDescription = DrawerPrimitive.Description;

export function DrawerContent({
  className,
  children,
  ...props
}: ComponentProps<typeof DrawerPrimitive.Content>) {
  return (
    <DrawerPrimitive.Portal>
      <DrawerPrimitive.Overlay className="fixed inset-0 z-40 bg-(--color-text)/40" />
      <DrawerPrimitive.Content
        className={cn(
          "fixed inset-x-0 bottom-0 z-50 max-h-[85dvh]",
          "rounded-t-dialog border-t border-border bg-surface p-6 outline-none",
          "pb-[max(var(--space-6),env(safe-area-inset-bottom))]",
          className,
        )}
        {...props}
      >
        {/* Default accessible name; callers render content without adding another title. */}
        <DrawerPrimitive.Title className="sr-only">Menu</DrawerPrimitive.Title>
        {children}
      </DrawerPrimitive.Content>
    </DrawerPrimitive.Portal>
  );
}
