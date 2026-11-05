import { cn } from "@/lib/utils";

/**
 * Loading placeholder. Decorative only (aria-hidden) — the container must
 * provide an accessible loading status (see SaveStatus/StatePanel copy).
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-control bg-surface-muted motion-reduce:animate-none", className)}
    />
  );
}
