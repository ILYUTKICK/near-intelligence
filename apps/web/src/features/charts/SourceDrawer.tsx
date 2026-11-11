"use client";

import type { ReactNode } from "react";

import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { DataSource } from "./chart-frame-types";

/**
 * Only http(s) URLs may become links. Anything else (javascript:, data:,
 * protocol-relative, empty) renders as inert text — the drawer defense for
 * CHART_SYSTEM.md "sanitized manifest" links, on top of the upstream
 * sanitized API projection.
 */
export function sanitizeSourceUrl(url: string): string | null {
  if (!url) {
    return null;
  }
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function SourceLink({ url, children }: { url: string; children: ReactNode }) {
  const safe = sanitizeSourceUrl(url);
  if (!safe) {
    return <span className="break-all">{url ? `${url} (link withheld)` : "—"}</span>;
  }
  return (
    <a
      href={safe}
      target="_blank"
      rel="noreferrer noopener"
      className="text-accent underline underline-offset-2 break-all hover:text-accent-hover"
    >
      {children}
    </a>
  );
}

function SourceEntry({ source }: { source: DataSource }) {
  return (
    <li className="border-border border-t py-4 first:border-t-0 first:pt-0">
      <p className="text-ui leading-ui font-medium">{source.name}</p>
      <dl className="text-ui leading-ui text-text-secondary mt-1 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1">
        <dt className="font-medium">License</dt>
        <dd>{source.license_status}</dd>
        <dt className="font-medium">Access</dt>
        <dd>{source.access_status}</dd>
        <dt className="font-medium">Verified</dt>
        <dd>{source.verified_at ?? "not yet recorded"}</dd>
        <dt className="font-medium">Update cadence</dt>
        <dd>{source.expected_update_frequency ?? "not yet recorded"}</dd>
        <dt className="font-medium">Last success</dt>
        <dd>{source.last_success_at ?? "never (no successful retrieval yet)"}</dd>
        <dt className="font-medium">Documentation</dt>
        <dd>
          <SourceLink url={source.docs_url ?? ""}>{source.docs_url ?? "—"}</SourceLink>
        </dd>
      </dl>
      {source.lineage.length > 0 ? (
        <div className="mt-2">
          <p className="text-ui leading-ui text-text-secondary font-medium">Lineage</p>
          <ol className="text-ui leading-ui text-text-secondary list-decimal pl-5">
            {source.lineage.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </li>
  );
}

/**
 * Source/definition drawer per CHART_SYSTEM.md: provider documentation,
 * license/access status, verification and retrieval timestamps, and lineage.
 * Every timestamp and bound stays visible here at any screen size — the
 * Dialog reflows instead of hiding metadata.
 */
export function SourceDrawer({
  label,
  sources,
  formulaUrl,
  manifestUrl,
  definition,
  triggerClassName,
}: {
  /** Trigger text, e.g. "Sources & definitions". */
  label: string;
  sources: DataSource[];
  formulaUrl?: string;
  manifestUrl?: string;
  /** Human-readable metric definition/version line shown above sources. */
  definition?: string;
  triggerClassName?: string;
}) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="secondary" className={triggerClassName}>
          <ProductIcon name="book" /> {label}
        </Button>
      </DialogTrigger>
      <DialogContent className="w-[min(40rem,calc(100vw-2rem))]">
        <DialogTitle>Sources and definitions</DialogTitle>
        <DialogDescription>
          Provenance for this chart: who produces the data, under which license, verified
          when, and how it reaches this product.
        </DialogDescription>
        {definition ? (
          <div className="mt-4 rounded-surface bg-sage p-4">
            <p className="text-ui leading-ui font-medium">Definition</p>
            <p className="text-ui leading-ui text-text-secondary">{definition}</p>
            {formulaUrl ? (
              <p className="text-ui leading-ui mt-1">
                <SourceLink url={formulaUrl}>Metric formula</SourceLink>
              </p>
            ) : null}
            {manifestUrl ? (
              <p className="text-ui leading-ui mt-1">
                <SourceLink url={manifestUrl}>Dataset manifest</SourceLink>
              </p>
            ) : null}
          </div>
        ) : null}
        <ul className="mt-4">
          {sources.map((source) => (
            <SourceEntry key={source.id} source={source} />
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
