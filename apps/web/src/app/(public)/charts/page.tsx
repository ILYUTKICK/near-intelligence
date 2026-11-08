import type { Metadata } from "next";
import Link from "next/link";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { CatalogSearch } from "@/features/charts/library/CatalogSearch";
import { fetchChartCatalog } from "@/features/charts/library/catalog-api";
import type { DroppedParam } from "@/features/charts/library/selection-url";
import {
  CATALOG_CATEGORIES,
  categoryWordings,
  updateFrequencyWordings,
  visualizationWordings,
} from "@/features/charts/library/wording";

export const metadata: Metadata = { title: "Chart library — NEAR Intelligence" };

type SearchValues = Record<string, string | string[] | undefined>;

const SEARCH_MAX_LENGTH = 200;
const CURSOR_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

/**
 * Chart library (NI-034): the public catalog of registered analytical
 * charts at /charts. The search query, category and pagination cursor are
 * URL state — the server-rendered catalog request is built only from the
 * validated values below, so the request always reflects the URL and never
 * forwards an arbitrary field. Unavailable charts stay listed with their
 * recorded reason (they are never hidden and never rendered as zero).
 */
export default async function ChartLibraryPage({
  searchParams,
}: {
  searchParams: Promise<SearchValues>;
}) {
  const values = await searchParams;
  const dropped: DroppedParam[] = [];

  // Approved catalog parameters; anything else in the URL is dropped with an
  // honest note and never forwarded (same gate as the detail selection).
  const approvedLibraryParams = ["q", "category", "cursor"];
  for (const key of Object.keys(values)) {
    if (!approvedLibraryParams.includes(key)) {
      dropped.push({
        param: key,
        reason: "unsupported URL parameter; it was not sent to the chart API",
      });
    }
  }

  let q = singleValue(values, "q", dropped);
  if (q !== null) {
    q = q.trim();
    if (q === "") {
      q = null;
    } else if (q.length > SEARCH_MAX_LENGTH) {
      dropped.push({
        param: "q",
        reason: `search queries are limited to ${SEARCH_MAX_LENGTH} characters; the query was not used`,
      });
      q = null;
    }
  }

  let category = singleValue(values, "category", dropped);
  if (category !== null && !(CATALOG_CATEGORIES as readonly string[]).includes(category)) {
    dropped.push({
      param: "category",
      reason: `category must be one of ${CATALOG_CATEGORIES.join(", ")}; it was not used`,
    });
    category = null;
  }

  let cursor = singleValue(values, "cursor", dropped);
  if (cursor !== null && !CURSOR_PATTERN.test(cursor)) {
    dropped.push({
      param: "cursor",
      reason: "the pagination cursor was not recognized; the first page is shown instead",
    });
    cursor = null;
  }

  const result = await fetchChartCatalog({
    ...(q !== null ? { q } : {}),
    ...(category !== null ? { category } : {}),
    ...(cursor !== null ? { cursor } : {}),
  });

  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <Breadcrumbs items={[{ label: "Overview", href: "/" }, { label: "Charts" }]} />
      <h1 className="mt-4">Chart library</h1>
      <p className="text-body leading-body text-text-secondary mt-2 max-w-prose">
        Every registered analytical chart with its data status. Unavailable charts stay
        listed with their recorded reason — they are never hidden and never shown as zero.
        The catalog is versioned: each chart pins an immutable definition version.
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

      <CatalogSearch initialQuery={q ?? ""} category={category} />

      <nav aria-label="Chart categories" className="mt-4">
        <ul className="flex flex-wrap gap-2">
          {[
            { label: "All charts", value: null as string | null },
            ...CATALOG_CATEGORIES.map((value) => ({ label: categoryWordings[value], value })),
          ].map((tab) => {
            const active = tab.value === category;
            const href = catalogHref(tab.value, q, null);
            return (
              <li key={tab.label}>
                <Link
                  href={href}
                  aria-current={active ? "true" : undefined}
                  className={
                    active
                      ? "inline-flex h-11 items-center rounded-control border border-accent bg-accent px-4 font-ui text-ui leading-ui text-on-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                      : "inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                  }
                >
                  {tab.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {result.ok ? (
        result.data.items.length === 0 ? (
          <div className="mt-8 rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
            <h2>Nothing to show</h2>
            <p className="text-body leading-body text-text-secondary mt-2">
              {q !== null
                ? "No registered chart matches this search. Search covers titles, descriptions and chart ids."
                : category !== null
                  ? `No chart is registered in the ${categoryWordings[category].toLowerCase()} category yet; a category without charts is stated, never filled with placeholders.`
                  : "No chart is registered yet."}
            </p>
            <Link
              href="/charts"
              className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              Clear search and filters
            </Link>
          </div>
        ) : (
          <>
            <ul className="mt-8 flex flex-col gap-4 max-w-prose">
              {result.data.items.map((item) => (
                <li key={item.chart_id} className="rounded-surface border border-border bg-surface p-6 flex flex-col gap-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                    <h2 className="text-lg">
                      <Link
                        href={`/charts/${item.chart_id}`}
                        className="hover:underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                      >
                        {item.title}
                      </Link>
                    </h2>
                    {item.data_status === "available" ? (
                      <span className="font-ui text-ui leading-ui font-medium text-accent">Available</span>
                    ) : (
                      <span className="font-ui text-ui leading-ui font-medium text-danger">
                        Unavailable — this is not zero
                      </span>
                    )}
                  </div>
                  <p className="text-body leading-body text-text-secondary">{item.description}</p>
                  {item.data_status === "unavailable" && item.unavailable_reason ? (
                    <p className="text-ui leading-ui text-text-secondary">
                      Reason: {item.unavailable_reason}
                    </p>
                  ) : null}
                  <p className="text-ui leading-ui text-text-secondary">
                    {categoryWordings[item.category] ?? item.category} ·{" "}
                    {visualizationWordings[item.visualization_type] ?? item.visualization_type} ·{" "}
                    {updateFrequencyWordings[item.update_frequency] ?? item.update_frequency} · Units:{" "}
                    {[...new Set(Object.values(item.units))].join(", ")}
                  </p>
                  <div>
                    <Link
                      href={`/charts/${item.chart_id}`}
                      aria-label={`Open chart: ${item.title}`}
                      className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                    >
                      Open chart
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
            {result.data.next_cursor ? (
              <p className="mt-6">
                <Link
                  href={catalogHref(category, q, result.data.next_cursor)}
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
          <h2>The catalog could not be loaded</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            {result.status === 503
              ? "The chart API is unavailable right now. Nothing is shown rather than stale or fabricated entries."
              : "The catalog request failed. Nothing is shown rather than partial or fabricated entries."}
          </p>
          <Link
            href={catalogHref(category, q, cursor)}
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

/** Deterministic library URL from validated values only. */
function catalogHref(category: string | null, q: string | null, cursor: string | null): string {
  const params = new URLSearchParams();
  if (q !== null) {
    params.set("q", q);
  }
  if (category !== null) {
    params.set("category", category);
  }
  if (cursor !== null) {
    params.set("cursor", cursor);
  }
  return params.size > 0 ? `/charts?${params.toString()}` : "/charts";
}
