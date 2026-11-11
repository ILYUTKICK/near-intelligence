import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { ModelRunDetail } from "@/features/models/ModelRunDetail";
import {
  fetchModelDefinition,
  fetchModelReadiness,
  fetchModelRunDetail,
} from "@/features/models/models-api";

export const metadata: Metadata = { title: "Model run — NEAR Intelligence" };

/**
 * The published run detail at /models/{run_id} (NI-054 handoff, contract
 * point 2). The run is fetched server-side and validated against the
 * render-boundary schemas before any rendering; a 404 or a validation
 * failure of the identity lands on the generic not-found boundary with no
 * existence leak (an unpublished run is indistinguishable from an absent
 * one). The public definition and the recorded readiness verdict are
 * fetched alongside (contract point 4); either can fail alone with an
 * honest note while the run itself still renders.
 */
export default async function ModelRunPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;

  const result = await fetchModelRunDetail(runId);
  if (!result.ok) {
    // 404 (absent/unpublished) and 422 (malformed identity) share one
    // generic boundary; nothing distinguishes them.
    if (result.status === 404 || result.status === 422) {
      notFound();
    }
    return (
      <div className="page-container">
        <div role="alert" className="paper-panel p-8">
          <h1 className="text-page">Model run unavailable</h1>
          <p className="text-body leading-body text-text-secondary mt-2">
            The model run could not be loaded right now. Nothing is shown rather than partial
            or fabricated content.
            {result.message !== null ? ` The API reported: ${result.message}` : ""}
          </p>
          <Link
            href={`/models/${encodeURIComponent(runId)}`}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Try again
          </Link>
        </div>
      </div>
    );
  }
  const run = result.data;

  // The specification record and the recorded gate verdict are independent
  // GETs; each may fail alone with an honest in-panel note.
  const [definitionResult, readinessResult] = await Promise.all([
    fetchModelDefinition(run.model_id),
    fetchModelReadiness(run.model_id),
  ]);

  return (
    <div className="page-container">
      <Breadcrumbs
        items={[{ label: "Overview", href: "/" }, { label: "Models", href: "/models" }, { label: `Model run ${run.model_id} v${run.model_version}` }]}
      />
      <ModelRunDetail
        run={run}
        definition={definitionResult.ok ? definitionResult.data : null}
        readiness={readinessResult.ok ? readinessResult.data : null}
      />
      <p className="mt-10 max-w-prose">
        <Link
          href="/models"
          className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          All published model runs
        </Link>
      </p>
    </div>
  );
}
