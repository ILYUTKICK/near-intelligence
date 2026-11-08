import type { Metadata } from "next";
import Link from "next/link";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { ModelRunList } from "@/features/models/ModelRunList";
import { fetchModelRunCatalog } from "@/features/models/models-api";

export const metadata: Metadata = { title: "Models — NEAR Intelligence" };

/** One honestly reported URL value the page did not forward. */
interface DroppedParam {
  param: string;
  reason: string;
}

type SearchValues = Record<string, string | string[] | undefined>;

const CURSOR_PATTERN = /^[A-Za-z0-9_-]{1,64}={0,2}$/;

/**
 * The public model catalog at /models (NI-054 handoff, contract point 1):
 * the catalog of published model runs. The pagination cursor is the only
 * URL parameter — anything else is dropped with an honest note and never
 * forwarded. The empty catalog is the honest "no published model yet"
 * state; a placeholder result is never rendered in its place.
 */
export default async function ModelsPage({
  searchParams,
}: {
  searchParams: Promise<SearchValues>;
}) {
  const values = await searchParams;
  const dropped: DroppedParam[] = [];

  // The cursor is the only approved catalog parameter; anything else in the
  // URL is dropped with an honest note and never forwarded.
  for (const key of Object.keys(values)) {
    if (key !== "cursor") {
      dropped.push({
        param: key,
        reason: "unsupported URL parameter; it was not sent to the model API",
      });
    }
  }

  let cursor = singleValue(values, "cursor", dropped);
  if (cursor !== null && !CURSOR_PATTERN.test(cursor)) {
    dropped.push({
      param: "cursor",
      reason: "the pagination cursor was not recognized; the first page is shown instead",
    });
    cursor = null;
  }

  const result = await fetchModelRunCatalog(cursor !== null ? { cursor } : {});

  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <Breadcrumbs items={[{ label: "Overview", href: "/" }, { label: "Models" }]} />
      <h1 className="mt-4">Econometric models</h1>
      <p className="text-body leading-body text-text-secondary mt-2 max-w-prose">
        Published model runs only. A run appears here exactly when the operator publication
        gate verified its bundle and the recorded review approved it; unpublished, failed or
        gate-rejected runs do not exist on these pages and are indistinguishable from absent
        ones. Every recorded value is shown as served.
      </p>

      {dropped.length > 0 ? (
        <div role="status" className="mt-4 rounded-surface border border-border bg-surface-muted p-4 max-w-prose">
          <p className="font-ui text-ui leading-ui font-medium">
            Some URL parameters were not used — the catalog request carries only supported fields.
          </p>
          <ul className="mt-2 list-disc pl-5 text-ui leading-ui text-text-secondary">
            {dropped.map((item, index) => (
              <li key={`${item.param}-${index}`}>
                <span className="font-medium">{item.param}</span>: {item.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {result.ok ? (
        result.data.items.length === 0 ? (
          <div className="mt-8 rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
            <h2>No published model yet</h2>
            <p className="text-body leading-body text-text-secondary mt-2">
              No model run has been published through the verification and review flow yet.
              This page states that honestly — it is not a placeholder result, and no
              coefficient or statistic is invented for display. Publication is an operator
              flow, never a browser action.
            </p>
            <Link
              href="/methodology#reproduce"
              className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              How models are verified and reproduced
            </Link>
          </div>
        ) : (
          <>
            <ModelRunList items={result.data.items} />
            {result.data.next_cursor ? (
              <p className="mt-6 max-w-prose">
                <Link
                  href={catalogHref(result.data.next_cursor)}
                  className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  Next page
                </Link>
              </p>
            ) : null}
          </>
        )
      ) : (
        <div role="alert" className="mt-8 rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
          <h2>The model catalog could not be loaded</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            {result.status === 503
              ? "The model API is unavailable right now. Nothing is shown rather than stale or fabricated runs."
              : "The catalog request failed. Nothing is shown rather than partial or fabricated runs."}
            {result.message !== null ? ` The API reported: ${result.message}` : ""}
          </p>
          <Link
            href={catalogHref(cursor)}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Try again
          </Link>
        </div>
      )}
    </div>
  );
}

function singleValue(values: SearchValues, key: string, dropped: DroppedParam[]): string | null {
  const raw = values[key];
  if (raw === undefined) {
    return null;
  }
  if (Array.isArray(raw)) {
    dropped.push({
      param: key,
      reason: `the URL carries ${raw.length} conflicting values for this parameter; none was used`,
    });
    return null;
  }
  return raw;
}

/** Deterministic catalog URL from validated values only. */
function catalogHref(cursor: string | null): string {
  return cursor !== null ? `/models?cursor=${encodeURIComponent(cursor)}` : "/models";
}
