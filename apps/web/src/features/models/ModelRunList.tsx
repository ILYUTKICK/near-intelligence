import Link from "next/link";

import type { ModelRunSummary } from "@/features/models/models-schema";
import {
  fittedSampleSpan,
  presentSummary,
} from "@/features/models/presentation";

/**
 * The catalog cards of published model runs (NI-054 contract point 1,
 * NI-097 presentation): one wide readable card per published run. The
 * recorded technical identity (spec id · version) stays as secondary text;
 * run ids, commits, tolerances and the full publication timestamp live on
 * the result page. Pure presentation: the page validates the payload first,
 * so a card never renders an unvalidated field.
 */
export function ModelRunList({ items, basePath = "/models" }: { items: ModelRunSummary[]; basePath?: string }) {
  return (
    <ul className="mt-6 grid gap-5">
      {items.map((item) => {
        const presentation = presentSummary(item);
        const href = `${basePath}/${encodeURIComponent(item.run_id)}`;
        return (
          <li key={item.run_id} className="paper-panel flex min-w-0 flex-col gap-4 p-6 lg:p-8">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <p className="eyebrow">{presentation.categoryLabel}</p>
              <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-metadata font-medium text-text-secondary">
                {presentation.statusLabel}
              </span>
            </div>
            <h2 className="font-serif text-heading leading-heading font-semibold text-text">
              <Link
                href={href}
                className="hover:underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
              >
                {presentation.cardTitle}
              </Link>
            </h2>
            <p className="max-w-prose text-body leading-body text-text">
              {presentation.question}
            </p>
            <p className="max-w-prose text-ui leading-ui text-text-secondary">
              {item.gate_verdict === "READY_WITH_LIMITS"
                ? "This model describes the recorded relationship; read its recorded limits before using the result."
                : "The published result carries the methods and limits behind it."}
            </p>
            <dl className="mt-1 grid gap-4 border-t border-border pt-4 sm:grid-cols-3">
              <div>
                <dt className="text-metadata leading-metadata text-text-secondary">Input window · UTC</dt>
                <dd className="mt-0.5 text-ui leading-ui font-medium text-text">
                  {fittedSampleSpan(item)}
                </dd>
              </div>
              <div>
                <dt className="text-metadata leading-metadata text-text-secondary">Fitted sample</dt>
                <dd className="mt-0.5 text-ui leading-ui font-medium text-text">
                  {item.sample.nobs} observations
                </dd>
              </div>
              {presentation.methodLabel ? (
                <div>
                  <dt className="text-metadata leading-metadata text-text-secondary">Method</dt>
                  <dd className="mt-0.5 text-ui leading-ui font-medium text-text">
                    {presentation.methodLabel}
                  </dd>
                </div>
              ) : null}
            </dl>
            <p className="text-metadata leading-metadata text-text-secondary">
              {item.model_id} · version {item.model_version}
            </p>
            <div>
              <Link
                href={href}
                className="inline-flex h-11 items-center gap-2 rounded-control border border-control-border bg-surface px-5 font-ui text-ui font-medium text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
              >
                View results
                <span aria-hidden="true">↗</span>
              </Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
