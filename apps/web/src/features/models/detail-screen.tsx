import Link from "next/link";
import { notFound } from "next/navigation";

import { ModelRunDetail } from "@/features/models/ModelRunDetail";
import {
  fetchModelDefinition,
  fetchModelReadiness,
  fetchModelRunDetail,
} from "@/features/models/models-api";
import {
  formatPublishedDay,
  presentRun,
} from "@/features/models/presentation";


/**
 * The published run detail at /models/{run_id} (NI-054 contract point 2;
 * NI-097 presentation). The run is fetched server-side and validated against
 * the render-boundary schemas before any rendering; a 404 or a validation
 * failure of the identity lands on the generic not-found boundary with no
 * existence leak (an unpublished run is indistinguishable from an absent
 * one). The public definition and the recorded readiness verdict are
 * fetched alongside (contract point 4); either can fail alone with an
 * honest note while the run itself still renders.
 */
export async function ModelDetailScreen({
  routePrefix = "",
  params,
}: {
  routePrefix?: "" | "/workspace";
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
            href={`${routePrefix}/models/${encodeURIComponent(runId)}`}
            className="mt-4 inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Try again
          </Link>
        </div>
      </div>
    );
  }
  const run = result.data;
  const presentation = presentRun(run);

  // The specification record and the recorded gate verdict are independent
  // GETs; each may fail alone with an honest in-panel note.
  const [definitionResult, readinessResult] = await Promise.all([
    fetchModelDefinition(run.model_id),
    fetchModelReadiness(run.model_id),
  ]);

  return (
    <div className="page-container">
      <p className="mt-5">
        <Link
          href={`${routePrefix}/models`}
          className="text-ui leading-ui text-text-secondary hover:text-text hover:underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          ← All models
        </Link>
      </p>
      <header className="mt-4 max-w-[70rem]">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <p className="eyebrow">{presentation.categoryLabel}</p>
          <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-metadata font-medium text-text-secondary">
            {run.gate_verdict === "READY_WITH_LIMITS" ? "Published with limits" : "Published"}
          </span>
        </div>
        <h1 className="mt-2 font-serif text-page leading-page font-semibold text-text">
          {presentation.headline}
        </h1>
        {presentation.subtitle.map((line) => (
          <p key={line} className="mt-1 text-body leading-body text-text-secondary">{line}</p>
        ))}
        <p className="mt-3 text-metadata leading-metadata text-text-secondary">
          {run.model_id} · version {run.model_version} · Published{" "}
          {formatPublishedDay(run.published_at)}
        </p>
        <dl className="mt-5 grid gap-x-8 gap-y-3 border-y border-border py-4 text-ui leading-ui sm:grid-cols-4">
          <div>
            <dt className="text-metadata leading-metadata text-text-secondary">Fitted observations</dt>
            <dd className="mt-0.5 font-medium text-text">{run.sample.nobs}</dd>
          </div>
          <div>
            <dt className="text-metadata leading-metadata text-text-secondary">Fitted sample</dt>
            <dd className="mt-0.5 font-medium text-text">{fittedSpan(run)}</dd>
          </div>
          <div>
            <dt className="text-metadata leading-metadata text-text-secondary">Method</dt>
            <dd className="mt-0.5 font-medium text-text">{methodLine(run)}</dd>
          </div>
          <div>
            <dt className="text-metadata leading-metadata text-text-secondary">Source</dt>
            <dd className="mt-0.5 font-medium text-text">{sourceLine(run)}</dd>
          </div>
        </dl>
      {presentation.variables ? (
        <dl className="mt-6 grid gap-4 max-w-[70rem] sm:grid-cols-2">
          {presentation.variables.map((variable) => (
            <div key={variable.role} className="paper-panel p-5">
              <dt>
                <p className="text-metadata leading-metadata uppercase tracking-wide text-accent font-medium">
                  {variable.role === "dependent" ? "Fee measure" : "Activity measure"}
                </p>
                <h2 className="mt-1 font-serif text-heading leading-heading font-semibold text-text">
                  {variable.heading}
                </h2>
              </dt>
              <dd className="mt-2">
                <p className="text-ui leading-ui text-text">{variable.description}</p>
                <p className="mt-1 text-ui leading-ui text-text-secondary">{variable.transform}</p>
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      <div className="mt-6 max-w-[70rem]">
        <h2 className="text-ui leading-ui font-semibold text-text">The important limit</h2>
        <p className="mt-1 max-w-prose text-ui leading-ui text-text-secondary">
          {presentation.scopeLimit}
        </p>
      </div>
      </header>
      <div className="mt-8">
        <ModelRunDetail
          run={run}
          definition={definitionResult.ok ? definitionResult.data : null}
          readiness={readinessResult.ok ? readinessResult.data : null}
        />
      </div>
    </div>
  );
}

/** "7 Aug – 3 Nov 2026" — the fitted sample (one day lost to differencing). */
function fittedSpan(run: Parameters<typeof presentRun>[0]): string {
  const end = new Date(`${run.sample.end_exclusive}T00:00:00Z`);
  end.setUTCDate(end.getUTCDate() - 1);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const startShort = formatMonthDay(run.sample.start, months);
  return `${startShort} – ${end.getUTCDate()} ${months[end.getUTCMonth()]} ${end.getUTCFullYear()}`;
}

function formatMonthDay(iso: string, months: string[]): string {
  const [, month, day] = iso.split("-").map((part) => Number(part));
  return `${day} ${months[month - 1] ?? month}`;
}

/** "OLS / HAC · 7 lags" from the recorded estimation block. */
function methodLine(run: Parameters<typeof presentRun>[0]): string {
  const estimation = run.estimation as Record<string, unknown>;
  const covariance = (estimation.covariance ?? {}) as Record<string, unknown>;
  return `${estimation.method ?? "OLS"} / ${covariance.type ?? "HAC"} · ${covariance.maxlags ?? "?"} lags`;
}

/** The recorded source dimension(s) of the bound variables. */
function sourceLine(run: Parameters<typeof presentRun>[0]): string {
  const specification = run.specification as Record<string, unknown>;
  const sources = new Set<string>();
  const dependent = specification.dependent_variable as { dimension?: string } | undefined;
  const explanatory = specification.explanatory_variables as
    Array<{ dimension?: string }> | undefined;
  if (typeof dependent?.dimension === "string") {
    sources.add(dependent.dimension);
  }
  for (const variable of explanatory ?? []) {
    if (typeof variable.dimension === "string") {
      sources.add(variable.dimension);
    }
  }
  return [...sources].join(", ") || "—";
}
