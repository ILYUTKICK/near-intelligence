import Link from "next/link";

import { EmptyState, StaleNotice, UnavailableState } from "@/components/data-state/DataState";
import { QualityBadge } from "@/components/data-state/QualityBadge";
import type { DataMetadata } from "@/components/data-state/quality";
import { MechanismFlow } from "@/features/public-research/MechanismFlow";
import { ClaimCard } from "@/features/public-research/ClaimCard";
import {
  landingDatasetHref,
  landingDefinitionHref,
  landingSelectionWindow,
} from "@/features/public-research/landing-metrics";
import { fetchLandingMetrics, type LandingMetricState } from "@/features/public-research/landing-metrics";
import { getLandingClaim, landingFindings } from "@/features/public-research/landing-findings";
import { landing, releaseStatus } from "@/features/public-research/content";

/**
 * Landing (NI-012): an evidence-bearing introduction. The shell and editorial
 * copy come from NI-011; the metric strip is fetched server-side from the
 * NI-032 delivery APIs (latest approved dataset semantics), the for/against
 * findings reuse the NI-014 claim registry through the shared ClaimCard, and
 * every quantitative value links its definition/dataset references. The
 * NI-070 release-status section states the honest model-research state: no
 * fitted values anywhere, the real-archive fit run pending operator execution,
 * and the public model catalog honestly empty until a reviewed run is
 * published.
 *
 * force-dynamic: approved-dataset resolution is a live read through the API's
 * own 60s latest-pointer cache; a statically prerendered landing could show
 * unavailability while approved data exists. All failure modes render as
 * typed fallback states — never zeros, never placeholder values.
 */
export const dynamic = "force-dynamic";

const linkClasses =
  "inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
const textLinkClasses =
  "text-accent underline underline-offset-2 hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
const sectionClasses = "mt-12";
const cardWrapperClasses =
  "mt-4 rounded-surface border border-border bg-surface p-4";
const metaLabelClasses = "font-medium text-text";

function DefinitionDatasetLinks() {
  return (
    <p className="text-ui leading-ui text-text-secondary mt-3 flex flex-wrap gap-x-4 gap-y-1">
      <a href={landingDefinitionHref} className={textLinkClasses}>
        Definition and availability vocabulary
      </a>
      <a href={landingDatasetHref} className={textLinkClasses}>
        Dataset staging and provenance
      </a>
    </p>
  );
}

function ArchiveDateLine({ asOf }: { readonly asOf: string | null }) {
  return (
    <p className="text-ui leading-ui text-text-secondary mt-1">
      <span className={metaLabelClasses}>Data as of: </span>
      {asOf !== null ? (
        <>
          <span className="text-text">{asOf}</span> (recorded archive timestamp, UTC)
        </>
      ) : (
        "no archive timestamp is recorded for this dataset"
      )}
      {/* No live badge: the saved evidence carries no recorded freshness
          guarantee, so only the "as of" archive date is shown (NI-012). */}
    </p>
  );
}

function DatasetLine({
  datasetKey,
  datasetVersion,
  datasetStatus,
  start,
  end,
}: {
  readonly datasetKey: string;
  readonly datasetVersion: number;
  readonly datasetStatus: string;
  readonly start: string;
  readonly end: string;
}) {
  return (
    <p className="text-ui leading-ui text-text-secondary mt-1">
      <span className={metaLabelClasses}>Dataset: </span>
      {datasetKey} v{datasetVersion} ({datasetStatus}), covering {start} through {end} (UTC,
      end exclusive)
    </p>
  );
}

function ObservationCard({ state }: { readonly state: Extract<LandingMetricState, { kind: "observation" }> }) {
  const stale =
    state.latest.quality.status === "stale" || state.dataset.quality.status === "stale";
  const metadata: DataMetadata = {
    units: state.latest.unit,
    period: `${state.latest.start} … ${state.latest.end} (UTC half-open period)`,
    asOf: state.asOf ?? undefined,
    limitation: state.metric.limitations[0],
  };
  return (
    <article aria-labelledby={`${state.metricId}-metric-heading`} className={cardWrapperClasses}>
      <h3 id={`${state.metricId}-metric-heading`} className="text-heading leading-heading">
        {state.metric.title}
      </h3>
      <p className="font-ui text-ui leading-ui text-text-secondary mt-1">
        <span className="font-medium text-text">{state.metric.metric_id}</span> v
        {state.metric.version} — availability {state.metric.availability}
      </p>

      {stale ? (
        <div className="mt-3">
          <StaleNotice quality={state.latest.quality} metadata={metadata} />
        </div>
      ) : null}

      <p className="text-ui leading-ui text-text-secondary mt-3">
        Latest approved observation in {landingSelectionWindow.scope}:
      </p>
      <p className="text-title leading-title text-text mt-1 [overflow-wrap:anywhere]">
        {state.latest.value} <span className="text-body leading-body">{state.latest.unit}</span>
      </p>

      <dl className="text-ui leading-ui text-text-secondary mt-3 grid grid-cols-1 gap-x-3 gap-y-1 sm:grid-cols-[max-content_minmax(0,1fr)]">
        <div className="contents">
          <dt className={metaLabelClasses}>Observation period</dt>
          <dd>
            {state.latest.start} … {state.latest.end} (UTC half-open period)
          </dd>
        </div>
        <div className="contents">
          <dt className={metaLabelClasses}>Coverage of the selection</dt>
          <dd>
            {state.observationCount} of {state.totalPeriods} periods hold a value; the rest are
            explicit gaps, never zeros
          </dd>
        </div>
      </dl>

      <div className="mt-3">
        <QualityBadge quality={state.latest.quality} />
      </div>

      <ArchiveDateLine asOf={state.asOf} />
      <DatasetLine
        datasetKey={state.dataset.dataset_key}
        datasetVersion={state.dataset.version}
        datasetStatus={state.dataset.status}
        start={state.dataset.start}
        end={state.dataset.end}
      />
      <DefinitionDatasetLinks />
    </article>
  );
}

function NoObservationsCard({
  state,
}: {
  readonly state: Extract<LandingMetricState, { kind: "no-observations" }>;
}) {
  return (
    <article aria-labelledby={`${state.metricId}-metric-heading`} className={cardWrapperClasses}>
      <h3 id={`${state.metricId}-metric-heading`} className="text-heading leading-heading">
        {state.metricTitle}
      </h3>
      <p className="font-ui text-ui leading-ui text-text-secondary mt-1">
        No unambiguous approved value is available in {landingSelectionWindow.scope}.
      </p>
      <div className="mt-3">
        <EmptyState
          metadata={{
            units: state.unit,
            period: state.dataset
              ? `approved dataset ${state.dataset.dataset_key} v${state.dataset.version} covers ${state.dataset.start} through ${state.dataset.end} (UTC, end exclusive)`
              : undefined,
            limitation:
              "No unambiguous value can be displayed for the recorded selection window. See the source-quality reasons below. This is not zero.",
          }}
        />
      </div>
      {state.reasons.length > 0 ? (
        <ul className="text-ui leading-ui text-text-secondary mt-2 list-disc pl-5">
          {state.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <DefinitionDatasetLinks />
    </article>
  );
}

function UnavailableCard({
  state,
}: {
  readonly state: Extract<LandingMetricState, { kind: "unavailable" }>;
}) {
  return (
    <article aria-labelledby={`${state.metricId}-metric-heading`} className={cardWrapperClasses}>
      <h3 id={`${state.metricId}-metric-heading`} className="text-heading leading-heading">
        {state.metricTitle}
      </h3>
      <div className="mt-3">
        <UnavailableState
          quality={{
            status: "unavailable",
            bound_kind: null,
            reasons: [state.reason],
            coverage: { observed: 0, expected: 0 },
            freshness_target_seconds: null,
          }}
          metadata={{
            limitation:
              "No approved value is shown because the delivery API could not provide one. This is not zero.",
          }}
        />
      </div>
      <DefinitionDatasetLinks />
    </article>
  );
}

function MetricCard({ state }: { readonly state: LandingMetricState }) {
  switch (state.kind) {
    case "observation":
      return <ObservationCard state={state} />;
    case "no-observations":
      return <NoObservationsCard state={state} />;
    case "unavailable":
      return <UnavailableCard state={state} />;
  }
}

export default async function HomePage() {
  const metricStates = await fetchLandingMetrics();

  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <h1>{landing.title}</h1>
      <p className="text-body leading-body text-text-secondary max-w-(--width-prose) mt-4">
        {landing.standfirst}
      </p>
      <p className="text-body leading-body max-w-(--width-prose) mt-4">{landing.whatYouCanDo}</p>
      <ul className="mt-6 flex flex-wrap gap-2">
        {landing.links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className={linkClasses}>
              {link.label}
            </Link>
          </li>
        ))}
        <li>
          {/* Workspace CTA: /workspace is the gated shell; unauthenticated
              visitors are redirected to /login by the workspace layout. */}
          <Link href="/workspace" className={linkClasses}>
            Open the workspace
          </Link>
        </li>
      </ul>

      {/* Evidence metric strip: at most three approved delivery-API metrics. */}
      <section id="evidence" aria-labelledby="evidence-heading" className={sectionClasses}>
        <h2 id="evidence-heading" className="font-serif text-title leading-title">
          Selected approved metrics
        </h2>
        <p className="text-body leading-body text-text-secondary max-w-(--width-prose) mt-2">
          Three registry metrics carry the mechanism stages this project measures: observed
          conversions into NEAR, matched treasury payouts, and provider-reported gross fees. They
          are different metrics — purchases, payouts and fees are never added together, and gross
          fees are not protocol revenue. Values come from one approved dataset version per metric
          (latest approved, resolved by the delivery API) and render exactly as delivered.
        </p>
        <p className="text-ui leading-ui text-text-secondary max-w-(--width-prose) mt-2 rounded-surface border border-border bg-surface p-3">
          Selection: {landingSelectionWindow.scope}. A value appears only where an approved dataset
          covers it; unavailable sources show explicit states, not zeros. No live badge is shown —
          the recorded evidence carries no freshness guarantee, only archive dates.
        </p>
        <ul className="mt-4 flex flex-col gap-4 max-w-(--width-prose) list-none pl-0">
          {metricStates.map((state) => (
            <li key={state.metricId}>
              <MetricCard state={state} />
            </li>
          ))}
        </ul>
      </section>

      {/* For/against findings from the claim registry (NI-014 consumption). */}
      <section
        id={landingFindings.id}
        aria-labelledby={`${landingFindings.id}-heading`}
        className={sectionClasses}
      >
        <h2 id={`${landingFindings.id}-heading`} className="font-serif text-title leading-title">
          {landingFindings.heading}
        </h2>
        <p className="text-body leading-body text-text-secondary max-w-(--width-prose) mt-2">
          {landingFindings.intro}
        </p>
        <p className="text-ui leading-ui text-text mt-3 max-w-(--width-prose) rounded-surface border border-border bg-surface p-4">
          {landingFindings.recordedBasis}
        </p>

        <div className="mt-6 max-w-(--width-prose)">
          <h3 className="text-heading leading-heading">{landingFindings.forSide.heading}</h3>
          <p className="text-body leading-body text-text-secondary mt-1">
            {landingFindings.forSide.lead}
          </p>
          <ol aria-label="Supporting claims" className="mt-4 flex flex-col gap-6 list-none pl-0">
            {landingFindings.forSide.claimIds.map((id) => (
              <li key={id}>
                <ClaimCard claim={getLandingClaim(id)} />
              </li>
            ))}
          </ol>
          <p className="text-ui leading-ui mt-3">
            <a href={landingFindings.forSide.thesisAnchor} className={textLinkClasses}>
              {landingFindings.forSide.anchorLabel}
            </a>
          </p>
        </div>

        <div className="mt-8 max-w-(--width-prose)">
          <h3 className="text-heading leading-heading">{landingFindings.againstSide.heading}</h3>
          <p className="text-body leading-body text-text-secondary mt-1">
            {landingFindings.againstSide.lead}
          </p>
          <ol aria-label="Contrary claims" className="mt-4 flex flex-col gap-6 list-none pl-0">
            {landingFindings.againstSide.claimIds.map((id) => (
              <li key={id}>
                <ClaimCard claim={getLandingClaim(id)} />
              </li>
            ))}
          </ol>
          <p className="text-ui leading-ui text-text-secondary mt-3">
            {landingFindings.againstSide.note}
          </p>
          <p className="text-ui leading-ui mt-3">
            <a href={landingFindings.againstSide.thesisAnchor} className={textLinkClasses}>
              {landingFindings.againstSide.anchorLabel}
            </a>
          </p>
        </div>
      </section>

      <MechanismFlow />

      {/* NI-070 release status: the honest model-research state. No numbers
          beyond the recorded verdict strings; the model catalog stays empty
          until a reviewed run is published. */}
      <section
        id={releaseStatus.id}
        aria-labelledby={`${releaseStatus.id}-heading`}
        className={sectionClasses}
      >
        <h2 id={`${releaseStatus.id}-heading`} className="font-serif text-title leading-title">
          {releaseStatus.heading}
        </h2>
        {releaseStatus.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className="text-body leading-body text-text-secondary max-w-(--width-prose) mt-2">
            {paragraph}
          </p>
        ))}
        <ul aria-label="Release status links" className="mt-3 flex flex-col gap-1 max-w-(--width-prose) list-disc pl-5">
          {releaseStatus.links.map((link) => (
            <li key={link.href}>
              <a href={link.href} className={textLinkClasses}>
                {link.label}
              </a>
            </li>
          ))}
        </ul>
      </section>

      {/* Closing CTAs: the documented destinations, honestly labeled. */}
      <section aria-labelledby="continue-heading" className={sectionClasses}>
        <h2 id="continue-heading" className="font-serif text-title leading-title">
          Continue
        </h2>
        <ul className="mt-4 flex flex-wrap gap-2 list-none pl-0">
          <li>
            <Link href="/research" className={linkClasses}>
              Read the full thesis
            </Link>
          </li>
          <li>
            <Link href="/methodology" className={linkClasses}>
              Check the methodology
            </Link>
          </li>
          <li>
            <Link href="/data" className={linkClasses}>
              Open the data explorer
            </Link>
          </li>
          <li>
            <Link href="/workspace" className={linkClasses}>
              Open the workspace
            </Link>
          </li>
        </ul>
        <p className="text-ui leading-ui text-text-secondary max-w-(--width-prose) mt-3">
          The workspace requires signing in; unauthenticated visits are redirected to the login
          route. The public data explorer renders the registered charts from approved datasets,
          with explicit unavailability when a source cannot be resolved.
        </p>
      </section>
    </div>
  );
}
