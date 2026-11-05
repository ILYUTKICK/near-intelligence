"use client";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Buttons per DESIGN_SYSTEM.md component contract: primary/secondary/quiet/
 * destructive, default/hover/focus/disabled/pending states, 44px touch
 * target, focus ring from the token (2px + offset).
 *
 * Pending controls set aria-busy and drop pointer events so a second submit
 * cannot fire while the first request is in flight. Disabled controls still
 * need an explanatory text next to them (nearby text, not a tooltip) — that
 * is the caller's responsibility and is documented in DESIGN_SYSTEM.md.
 */
const buttonVariants = cva(
  cn(
    "inline-flex items-center justify-center gap-2 rounded-control border",
    "font-ui text-ui leading-ui font-medium select-none",
    "h-11 min-w-11 px-4",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
    "disabled:pointer-events-none disabled:opacity-60",
    "aria-busy:pointer-events-none aria-busy:opacity-80",
    "transition-colors duration-(--transition-fast) motion-reduce:transition-none",
  ),
  {
    variants: {
      variant: {
        primary: "border-transparent bg-accent text-on-accent hover:bg-accent-hover",
        secondary:
          "border-control-border bg-surface text-text hover:bg-surface-muted",
        quiet: "border-transparent bg-transparent text-text hover:bg-surface-muted",
        destructive: "border-transparent bg-danger text-on-accent hover:opacity-90",
      },
      block: {
        true: "w-full",
      },
    },
    defaultVariants: {
      variant: "primary",
    },
  },
);

export interface ButtonProps
  extends ComponentProps<"button">,
    VariantProps<typeof buttonVariants> {
  /** Renders the slot child instead of a button (e.g. a next/link). */
  asChild?: boolean;
  /** Marks an in-flight action: blocks duplicate submits, announces via aria-busy. */
  pending?: boolean;
}

export function Button({
  className,
  variant,
  block,
  asChild = false,
  pending = false,
  disabled,
  type,
  children,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      data-variant={variant}
      className={cn(buttonVariants({ variant, block }), className)}
      aria-busy={pending || undefined}
      disabled={disabled || pending}
      type={asChild ? undefined : (type ?? "button")}
      {...props}
    >
      {pending ? (
        <span
          aria-hidden="true"
          className="animate-spin rounded-full border-2 border-current border-t-transparent size-4 motion-reduce:animate-none"
        />
      ) : null}
      {children}
    </Component>
  );
}

export { buttonVariants };
