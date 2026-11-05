"use client";

/**
 * Persistent inline save/status indicator (DESIGN_SYSTEM.md: "Inline status
 * for save/freshness is persistent; toasts only confirm brief actions").
 * Always occupies its space (no layout jump), announces polite updates via
 * aria-live, and pairs a glyph with visible text — never color alone.
 */
export function SaveStatus({
  status,
  savedAt,
}: {
  status: "idle" | "saving" | "saved" | "error";
  /** Timestamp shown with the saved state, e.g. "14:32:07 UTC". */
  savedAt?: string;
}) {
  const copy: Record<typeof status, string> = {
    idle: "All changes saved",
    saving: "Saving…",
    saved: savedAt ? `Saved at ${savedAt}` : "Saved",
    error: "Save failed — your latest edits are kept locally",
  };
  return (
    <p
      aria-live="polite"
      data-status={status}
      className={
        status === "error"
          ? "text-ui leading-ui text-danger inline-flex items-center gap-1.5 font-medium"
          : "text-ui leading-ui text-text-secondary inline-flex items-center gap-1.5"
      }
    >
      <StatusGlyph status={status} />
      {copy[status]}
    </p>
  );
}

function StatusGlyph({ status }: { status: "idle" | "saving" | "saved" | "error" }) {
  const common = { "aria-hidden": true, viewBox: "0 0 16 16", className: "size-3.5 shrink-0" };
  switch (status) {
    case "saving":
      return (
        <svg {...common} className="size-3.5 shrink-0 animate-spin motion-reduce:animate-none">
          <path d="M8 2.5a5.5 5.5 0 1 1-5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    case "saved":
    case "idle":
      return (
        <svg {...common}>
          <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "error":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 5v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx="8" cy="11" r="0.9" fill="currentColor" />
        </svg>
      );
  }
}
