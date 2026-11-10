import type { Metadata } from "next";
import Link from "next/link";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { fetchChartCatalog } from "@/features/charts/library/catalog-api";
import {
  EXPLORER_CATEGORIES,
  explorerForRegistryCategory,
} from "@/features/charts/library/explorer-categories";
import { dropUnknownParams } from "@/features/charts/library/search-values";

export const metadata: Metadata = { title: "Data explorer — NEAR Intelligence" };

/** The API's maximum page size; the overview counts one bounded catalog page. */
const CATALOG_OVERVIEW_LIMIT = 100;

type SearchValues = Record<string, string | string[] | undefined>;

/**
 * Public data explorer overview (NI-015) at /data: the five explorer
 * categories of INFORMATION_ARCHITECTURE.md (the workspace Data Explorer
 * grouping), each answering with its real registered charts or an honest
 * explanation — never a placeholder.
 *
 * The per-category availability lines are derived LIVE from one bounded
 * catalog request grouped through the recorded explorer mapping
 * (explorer-categories.ts), so the overview cannot claim an availability the
 * catalog does not carry. Anonymous exploration resolves charts through
 * exactly the same shared chart/query implementation as the signed-in
 * workspace: the same validated selection URLs (selection-url.ts), the same
 * catalog API and the same renderer — identical selections give identical
 * pinned values.
 */
export default async function DataExplorerPage({
  searchParams,
}: {
  searchParams: Promise<SearchValues>;
}) {
  const values = await searchParams;
  // The overview URL carries no parameters at all; anything present is
  // dropped with an honest note and never forwarded.
  const dropped = dropUnknownParams(values, []);

  const result = await fetchChartCatalog({ limit: CATALOG_OVERVIEW_LIMIT });

  // Live grouping of the fetched catalog page through the explorer mapping.
  const counts = new Map<string, { available: number; unavailable: number }>();
  let unmappedCount = 0;
  if (result.ok) {
    for (const item of result.data.items) {
      const explorer = explorerForRegistryCategory(item.category);
      if (explorer === null) {
        unmappedCount += 1;
        continue;
      }
      const entry = counts.get(explorer.slug) ?? { available: 0, unavailable: 0 };
      if (item.data_status === "available") {
        entry.available += 1;
      } else {
        entry.unavailable += 1;
      }
      counts.set(explorer.slug, entry);
    }
  }

  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <Breadcrumbs items={[{ label: "Overview", href: "/" }, { label: "Data" }]} />
      <h1 className="mt-4">Data explorer</h1>
      <p className="text-body leading-body text-text-secondary mt-2 max-w-prose">
        Anonymous exploration of the registered analytical charts, organized by the five
        explorer categories. This public explorer uses exactly the same shared chart and
        query implementation as the signed-in workspace and the chart library: the same
        validated selection URLs, the same catalog API and the same renderer — an identical
        selection resolves to identical pinned values. Every category lists its real
        registered charts or states why nothing is available; a missing value is never
        shown as zero.
      </p>

      {dropped.length > 0 ? (
        <div role="status" className="mt-4 rounded-surface border border-border bg-surface-muted p-4 max-w-prose">
          <p className="font-ui text-ui leading-ui font-medium">
            Some URL parameters were not used — this page carries no parameters.
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
        <>
          <ul className="mt-8 flex flex-col gap-4 max-w-prose">
            {EXPLORER_CATEGORIES.map((category) => {
              const entry = counts.get(category.slug);
              const hasRegistryCharts = category.registryCategories.length > 0;
              return (
                <li
                  key={category.slug}
                  className="rounded-surface border border-border bg-surface p-6 flex flex-col gap-3"
                >
                  <h2 className="text-lg">
                    <Link
                      href={`/data/${category.slug}`}
                      className="hover:underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                    >
                      {category.label}
                    </Link>
                  </h2>
                  <p className="text-body leading-body text-text-secondary">{category.question}</p>
                  {!hasRegistryCharts ? (
                    <p className="text-ui leading-ui text-text-secondary">
                      {category.emptyExplanation.heading} — {category.emptyExplanation.body}
                    </p>
                  ) : entry === undefined ? (
                    <p className="text-ui leading-ui text-text-secondary">
                      No chart is registered in the mapped registry categories yet — stated,
                      never filled with placeholders.
                    </p>
                  ) : (
                    <p className="text-ui leading-ui text-text-secondary">
                      {entry.available === 0
                        ? "No available chart right now"
                        : `${entry.available} available chart${entry.available === 1 ? "" : "s"}`}
                      {entry.unavailable > 0
                        ? `; ${entry.unavailable} registered chart${entry.unavailable === 1 ? " is" : "s are"} unavailable and ${
                            entry.unavailable === 1 ? "stays" : "stay"
                          } listed with the recorded reason`
                        : ""}
                      .
                    </p>
                  )}
                  <div>
                    {/* The accessible name must contain the visible text
                        ("Open category") — axe label-content-name-mismatch
                        (NI-064 desktop QA) — so speech-input users can say
                        what they see. */}
                    <Link
                      href={`/data/${category.slug}`}
                      aria-label={`Open category: ${category.label}`}
                      className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                    >
                      Open category
                    </Link>
                  </div>
                </li>
              );
            })}
          </ul>

          {result.data.next_cursor !== null ? (
            <p role="status" className="mt-4 text-ui leading-ui text-text-secondary max-w-prose">
              The availability lines reflect the first {CATALOG_OVERVIEW_LIMIT} catalog entries;
              a category page always lists its full registered set.
            </p>
          ) : null}

          {unmappedCount > 0 ? (
            <p className="mt-4 text-ui leading-ui text-text-secondary max-w-prose">
              Charts registered in the model category are not part of these five analytical
              categories; they are cataloged in the{" "}
              <Link
                href="/charts?category=model"
                className="text-accent underline underline-offset-2 hover:text-accent-hover"
              >
                chart library
              </Link>{" "}
              and resolve once a published model artifact exists.
            </p>
          ) : null}
        </>
      ) : (
        <div role="alert" className="mt-8 rounded-surface border border-border bg-surface-muted p-6 max-w-prose">
          <h2>The catalog could not be loaded</h2>
          <p className="text-body leading-body text-text-secondary mt-2">
            {result.status === 503
              ? "The chart API is unavailable right now, so no availability is claimed. Nothing is shown rather than stale or fabricated entries."
              : "The catalog request failed, so no availability is claimed. Nothing is shown rather than partial or fabricated entries."}
          </p>
          <Link
            href="/data"
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Try again
          </Link>
        </div>
      )}
    </div>
  );
}
