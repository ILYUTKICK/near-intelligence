import Link from "next/link";

import { gateVerdictWording } from "@/features/models/recorded";
import type { ModelRunSummary } from "@/features/models/models-schema";

/**
 * The catalog cards of published model runs (NI-054 handoff, contract
 * point 1). Pure presentation: the page validates the payload first, so a
 * card never renders an unvalidated field. Every recorded value is shown as
 * served — the empty catalog case is handled by the page as the honest
 * "no published model yet" state, never as placeholder content here.
 */
export function ModelRunList({ items }: { items: ModelRunSummary[] }) {
  return (
    <ul className="mt-8 flex flex-col gap-4 max-w-prose">
      {items.map((item) => (
        <li
          key={item.run_id}
          className="rounded-surface border border-border bg-surface p-6 flex flex-col gap-3"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="text-lg">
              <Link
                href={`/models/${encodeURIComponent(item.run_id)}`}
                className="hover:underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
              >
                Model run {item.model_id} v{item.model_version}
              </Link>
            </h2>
            <span className="font-ui text-ui leading-ui font-medium text-text-secondary">
              {gateVerdictWording(item.gate_verdict)}
            </span>
          </div>
          <dl className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-4 gap-y-1 text-ui leading-ui">
            <dt className="text-text-secondary">Run id</dt>
            <dd className="font-mono break-all">{item.run_id}</dd>
            <dt className="text-text-secondary">Sample</dt>
            <dd>
              {`${item.sample.start} to ${item.sample.end_exclusive} (end exclusive) · ${item.sample.nobs} observations`}
            </dd>
            <dt className="text-text-secondary">Reproduction tolerances</dt>
            <dd>
              {`rtol ${item.tolerances.coefficient_rtol} / atol ${item.tolerances.coefficient_atol} (recorded)`}
            </dd>
            <dt className="text-text-secondary">Published</dt>
            <dd>{`${item.published_at} by ${item.published_by}`}</dd>
            <dt className="text-text-secondary">Code commit</dt>
            <dd className="font-mono break-all">{item.code_commit}</dd>
          </dl>
          <div>
            <Link
              href={`/models/${encodeURIComponent(item.run_id)}`}
              aria-label={`Open model run: ${item.model_id} v${item.model_version}`}
              className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              Open run
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}
