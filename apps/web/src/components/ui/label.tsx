"use client";

import * as LabelPrimitive from "@radix-ui/react-label";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Persistent form label (DESIGN_SYSTEM.md: "controls labeled"; a tooltip
 * alone is never sufficient). Pair with Input/Select via htmlFor + id.
 */
export function Label({ className, ...props }: ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn(
        "font-ui text-ui leading-ui text-text select-none",
        "peer-disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}
