"use client";

import type { DataQuality } from "./quality";
import { boundLabel, qualityPresentation } from "./quality";

import { cn } from "@/lib/utils";

const toneClasses = {
  neutral: "bg-surface-muted text-text border-border",
  positive: "bg-sage text-text border-transparent",
  warning: "bg-surface text-warning border-warning",
  critical: "bg-surface text-danger border-danger",
  info: "bg-info-surface text-chart-2 border-transparent",
} as const;

/** Status glyphs — status is never conveyed by color alone. */
function StatusIcon({ status }: { status: DataQuality["status"] }) {
  const common = { "aria-hidden": true, viewBox: "0 0 16 16", className: "size-3.5 shrink-0" };
  switch (status) {
    case "ok":
      return (
        <svg {...common}>
          <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "missing":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M4.2 11.8 11.8 4.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    case "unavailable":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M5.5 8h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    case "stale":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 5v3.2l2.2 1.3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    case "revised":
      return (
        <svg {...common}>
          <path d="M3 6.5a5.2 5.2 0 0 1 9-1.6M13 9.5a5.2 5.2 0 0 1-9 1.6" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M12 2v3h-3M4 14v-3h3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "partial":
      return (
        <svg {...common}>
          <path d="M8 2.8a5.2 5.2 0 1 0 5.2 5.2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx="8" cy="8" r="1.6" fill="currentColor" />
        </svg>
      );
  }
}

/**
 * Quality badge per DESIGN_SYSTEM.md: visible text label plus glyph, so the
 * state never relies on color alone. Shows the bound kind for bounded
 * values (estimate / lower bound / upper bound) and partial coverage.
 */
export function QualityBadge({
  quality,
  className,
}: {
  quality: DataQuality;
  className?: string;
}) {
  const presentation = qualityPresentation[quality.status];
  const bound = boundLabel(quality.bound_kind);
  const coverage =
    quality.status === "partial" && quality.coverage.expected > 0
      ? `${quality.coverage.observed}/${quality.coverage.expected}`
      : null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
        "text-metadata font-medium",
        toneClasses[presentation.tone],
        className,
      )}
      title={`${presentation.label}: ${presentation.description}`}
    >
      <StatusIcon status={quality.status} />
      <span>
        {presentation.label}
        {bound ? ` · ${bound}` : ""}
        {coverage ? ` · ${coverage}` : ""}
      </span>
    </span>
  );
}
