"use client";

import { useId } from "react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Text input per DESIGN_SYSTEM.md: 1px control boundary from the token,
 * 16px font (prevents iOS focus zoom), 44px target height, persistent
 * label by the caller via Label+htmlFor, error state keeps the typed value
 * and announces itself (aria-invalid + role=alert message).
 */
export interface InputProps extends ComponentProps<"input"> {
  /** Error message rendered below the input; keeps value and announces once. */
  error?: string;
}

export function Input({ className, error, id, ...props }: InputProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const errorId = `${inputId}-error`;
  return (
    <div className="w-full">
      <input
        id={inputId}
        className={cn(
          "h-11 w-full rounded-control border bg-surface px-3",
          "text-base text-text placeholder:text-text-secondary",
          "border-control-border",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
          "aria-invalid:border-danger aria-invalid:outline-danger",
          "disabled:pointer-events-none disabled:opacity-60",
          className,
        )}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : props["aria-describedby"]}
        {...props}
      />
      {error ? (
        <p id={errorId} role="alert" className="text-ui leading-ui text-danger mt-2">
          {error}
        </p>
      ) : null}
    </div>
  );
}
