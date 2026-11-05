"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { QualityBadge } from "./QualityBadge";
import { Skeleton } from "./Skeleton";
import type { DataMetadata, DataQuality } from "./quality";
import { qualityPresentation } from "./quality";

import { cn } from "@/lib/utils";

/**
 * Shared async/data state panels (NI-009). Core rules from MVP scope and
 * DESIGN_SYSTEM.md:
 * - "Missing is not zero; unavailable is not fake data."
 * - An empty result never renders a zero value.
 * - Partial/stale/bounded states retain units, dates and limitations.
 * - Status is never conveyed by color alone (icon + text everywhere).
 */

function StatePanel({
  tone,
  icon,
  title,
  children,
  actions,
  className,
}: {
  tone: "neutral" | "warning" | "critical";
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  const toneText = tone === "warning" ? "text-warning" : tone === "critical" ? "text-danger" : "text-text-secondary";
  return (
    <div
      role={tone === "critical" ? "alert" : "status"}
      className={cn(
        "flex flex-col gap-2 rounded-surface border border-border bg-surface-muted p-6",
        className,
      )}
    >
      <p className={cn("flex items-center gap-2 font-ui text-ui leading-ui font-medium", toneText)}>
        <span aria-hidden="true" className="inline-flex">
          {icon}
        </span>
        {title}
      </p>
      {children ? (
        <div className="text-body leading-body text-text-secondary">{children}</div>
      ) : null}
      {actions ? <div className="mt-1">{actions}</div> : null}
    </div>
  );
}

function MetadataList({ metadata }: { metadata?: DataMetadata }) {
  if (!metadata) {
    return null;
  }
  const rows = [
    metadata.units ? { key: "Units", value: metadata.units } : null,
    metadata.period ? { key: "Period", value: metadata.period } : null,
    metadata.asOf ? { key: "Last observed", value: metadata.asOf } : null,
    metadata.limitation ? { key: "Limitation", value: metadata.limitation } : null,
  ].filter((row): row is { key: string; value: string } => row !== null);
  if (rows.length === 0) {
    return null;
  }
  return (
    <dl className="text-ui leading-ui text-text-secondary mt-1 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1">
      {rows.map((row) => (
        <div key={row.key} className="contents">
          <dt className="font-medium">{row.key}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Explicit empty state. Callers must render this for empty results — an
 * empty array is "nothing matched", never the number zero.
 */
export function EmptyState({
  metadata,
  className,
}: {
  metadata?: DataMetadata;
  className?: string;
}) {
  return (
    <StatePanel tone="neutral" icon={<SlashIcon />} title="No data for this selection" className={className}>
      <p>
        The selection matched no observations. An empty result is not zero — no value is
        shown and none should be inferred.
      </p>
      <MetadataList metadata={metadata} />
    </StatePanel>
  );
}

const SlashIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4">
    <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M4.2 11.8 11.8 4.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

/**
 * Missing/unavailable data state driven by the canonical DataQuality
 * contract: shows the quality reasons verbatim plus retained metadata.
 */
export function UnavailableState({
  quality,
  metadata,
  className,
}: {
  quality: DataQuality;
  metadata?: DataMetadata;
  className?: string;
}) {
  const presentation = qualityPresentation[quality.status];
  return (
    <StatePanel tone={presentation.tone === "critical" ? "critical" : "neutral"} icon={<SlashIcon />} title={`${presentation.label} — this is not zero`} className={className}>
      <p>{presentation.description}</p>
      {quality.reasons.length > 0 ? (
        <ul className="list-disc pl-5">
          {quality.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <div className="mt-1">
        <QualityBadge quality={quality} />
      </div>
      <MetadataList metadata={metadata} />
    </StatePanel>
  );
}

/** Error state with a retry action; retry honors Button pending. */
export function ErrorPanel({
  message,
  onRetry,
  retryPending = false,
  className,
}: {
  message: string;
  onRetry?: () => void;
  retryPending?: boolean;
  className?: string;
}) {
  return (
    <StatePanel
      tone="critical"
      icon={<AlertIcon />}
      title="Data failed to load"
      className={className}
      actions={
        onRetry ? (
          <Button variant="secondary" onClick={onRetry} pending={retryPending}>
            Retry
          </Button>
        ) : null
      }
    >
      <p>{message}</p>
    </StatePanel>
  );
}

const AlertIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4">
    <path
      d="M8 2.6 14.4 13H1.6L8 2.6Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
    <path d="M8 6.5v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <circle cx="8" cy="11.4" r="0.9" fill="currentColor" />
  </svg>
);

/**
 * Stale-data notice rendered alongside retained values: the data stays
 * visible, the staleness is explicit and metadata is retained.
 */
export function StaleNotice({
  quality,
  metadata,
  className,
}: {
  quality: DataQuality;
  metadata?: DataMetadata;
  className?: string;
}) {
  const target =
    quality.freshness_target_seconds !== null
      ? ` (freshness target ${Math.round(quality.freshness_target_seconds / 60)} min)`
      : "";
  return (
    <div role="status" className={cn("rounded-control border border-warning bg-surface p-4", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <QualityBadge quality={quality} />
        <p className="text-ui leading-ui text-warning font-medium">
          Showing the last verified values{target}
        </p>
      </div>
      <MetadataList metadata={metadata} />
    </div>
  );
}

/** Loading placeholder block with an accessible loading status. */
export function LoadingPanel({
  label = "Loading data",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div role="status" aria-label={label} className={cn("flex flex-col gap-2", className)}>
      <Skeleton className="h-6 w-1/3" />
      <Skeleton className="h-40 w-full" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
