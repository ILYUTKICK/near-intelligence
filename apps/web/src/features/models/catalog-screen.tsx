import Link from "next/link";

import { PageIntro } from "@/components/layout/PageIntro";
import { ModelAvailability } from "@/features/models/ModelAvailability";
import { ModelRunList } from "@/features/models/ModelRunList";
import { fetchModelRunCatalog } from "@/features/models/models-api";


/** One honestly reported URL value the page did not forward. */
interface DroppedParam {
  param: string;
  reason: string;
}

type SearchValues = Record<string, string | string[] | undefined>;

const CURSOR_PATTERN = /^[A-Za-z0-9_-]{1,64}={0,2}$/;

/**
 * The public model catalog at /models (NI-054 contract point 1; NI-097
 * presentation): the catalog of published model runs. The pagination cursor
 * is the only URL parameter — anything else is dropped with an honest note
 * and never forwarded. The empty catalog is the honest "no published model
 * yet" state; a placeholder result is never rendered in its place.
 */
export async function ModelCatalogScreen({
  routePrefix = "",
  searchParams,
}: {
  routePrefix?: "" | "/workspace";
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
  const itemCount = result.ok ? result.data.items.length : 0;

  return (
    <div className="page-container">
      <PageIntro
        eyebrow="Econometric evidence"
        title="Models"
        description="What the data can tell us about NEAR’s economics. Published results, with the methods and limits behind them."
      />

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
          <ModelAvailability
            title="No published model yet"
            description="No model run has completed the publication process. Coefficients and intervals become available when a verified run is published."
          />
        ) : (
          <>
            <div className="mt-10 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h2 className="text-heading">Published models</h2>
              <p className="text-ui leading-ui text-text-secondary">
                {itemCount} {itemCount === 1 ? "model" : "models"}
              </p>
            </div>
            <ModelRunList items={result.data.items} basePath={`${routePrefix}/models`} />
            {result.data.next_cursor ? (
              <p className="mt-6 max-w-prose">
                <Link
                  href={catalogHref(routePrefix, result.data.next_cursor)}
                  className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  Next page
                </Link>
              </p>
            ) : null}
            <section aria-labelledby="inside-each-model-heading" className="mt-14 max-w-prose">
              <h2 id="inside-each-model-heading" className="font-serif text-heading leading-heading font-semibold text-text">
                Inside each model
              </h2>
              <dl className="mt-4 space-y-3">
                <div>
                  <dt className="text-ui leading-ui font-medium text-text">The finding</dt>
                  <dd className="text-ui leading-ui text-text-secondary">
                    The estimated relationship, its uncertainty and what it means.
                  </dd>
                </div>
                <div>
                  <dt className="text-ui leading-ui font-medium text-text">The checks</dt>
                  <dd className="text-ui leading-ui text-text-secondary">
                    Sample, diagnostics and sensitivity to the declared assumptions.
                  </dd>
                </div>
                <div>
                  <dt className="text-ui leading-ui font-medium text-text">The record</dt>
                  <dd className="text-ui leading-ui text-text-secondary">
                    Specification, sources and the frozen reproduction bundle.
                  </dd>
                </div>
              </dl>
            </section>
          </>
        )
      ) : (
        <div role="alert" className="paper-panel mt-8 p-8">
          <h2>The model catalog could not be loaded</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            {result.status === 503
              ? "The model API is unavailable right now. Nothing is shown rather than stale or fabricated runs."
              : "The catalog request failed. Nothing is shown rather than partial or fabricated runs."}
            {result.message !== null ? ` The API reported: ${result.message}` : ""}
          </p>
          <Link
            href={catalogHref(routePrefix, cursor)}
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
function catalogHref(routePrefix: string, cursor: string | null): string {
  return cursor !== null ? `${routePrefix}/models?cursor=${encodeURIComponent(cursor)}` : `${routePrefix}/models`;
}
