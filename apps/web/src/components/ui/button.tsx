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
    // Pending blocks duplicate submits via aria-busy without dimming: opacity
    // < 1 blends the button colors with whatever is behind it and the blended
    // pair fails the WCAG contrast rule while the request is in flight (axe
    // caught exactly that on workspace home in CI). Contrast must hold in
    // every reachable state, pending included.
    "aria-busy:pointer-events-none",
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
  // Radix Slot requires exactly ONE child: the slotted element is cloned with
  // the merged props, so a spinner sibling (or a null placeholder next to the
  // child) crashes with React's Children.only error (NI-024 regression,
  // regression-tested in tests/ui/form.test.tsx). Slotted links announce the
  // pending state through aria-busy on the anchor instead of a spinner.
  if (asChild) {
    return (
      <Slot
        data-variant={variant}
        className={cn(buttonVariants({ variant, block }), className)}
        aria-busy={pending || undefined}
        {...props}
      >
        {children}
      </Slot>
    );
  }
  return (
    <button
      data-variant={variant}
      className={cn(buttonVariants({ variant, block }), className)}
      aria-busy={pending || undefined}
      disabled={disabled || pending}
      type={type ?? "button"}
      {...props}
    >
      {pending ? (
        <span
          aria-hidden="true"
          className="animate-spin rounded-full border-2 border-current border-t-transparent size-4 motion-reduce:animate-none"
        />
      ) : null}
      {children}
    </button>
  );
}

export { buttonVariants };
