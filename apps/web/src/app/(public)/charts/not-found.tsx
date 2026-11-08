import Link from "next/link";

/**
 * Honest 404 boundary for the chart routes (NI-034): an unknown chart id or
 * a pinned definition version that does not exist lands here with a real
 * 404 status and recoverable actions — never a fabricated chart.
 */
export default function ChartNotFound() {
  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <div className="rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
        <h1>Chart not found</h1>
        <p className="text-body leading-body text-text-secondary mt-2">
          This chart, or the definition version pinned in the URL, is not registered. The link
          may be outdated or mistyped — nothing is shown in place of an unregistered chart.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/charts"
            className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Open the chart library
          </Link>
          <Link
            href="/methodology#definitions"
            className="inline-flex h-11 items-center rounded-control border border-transparent px-4 font-ui text-ui leading-ui text-text underline underline-offset-2 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            How charts are defined
          </Link>
        </div>
      </div>
    </div>
  );
}
