import type { Metadata } from "next";

import { PageIntro } from "@/components/layout/PageIntro";
import { ClaimCard } from "@/features/public-research/ClaimCard";
import { DuplicateReleaseAction } from "@/features/public-research/DuplicateReleaseAction";
import { MechanismFlow } from "@/features/public-research/MechanismFlow";
import { RecordedPurchases } from "@/features/public-research/RecordedPurchases";
import { SupplyScaleFigure, UsdWindowsFigure } from "@/features/public-research/ResearchFigures";
import {
  claimRegistry,
  thesis,
  thesisReleaseSlug,
  thesisToc,
  type ClaimEvidenceLink,
  type ThesisClaim,
} from "@/features/public-research/content";

export const metadata: Metadata = { title: "Research — NEAR Intelligence" };

/**
 * Public research route (NI-014): the complete original conditional thesis on
 * the stable anchors required by the IA (/research#h1 … #h4) plus the fifteen
 * section anchors. Sections carry explicit status and rationale, the claim
 * registry CL-001–CL-009 binds every quantity to a recorded source, contrary
 * findings sit next to supporting ones, and the model section carries the
 * honest NI-070 release status: no fitted values anywhere, the real-archive
 * fit run pending operator execution, and the model catalog honestly empty.
 * The content carries no private editor metadata and no live data fetching;
 * internal links stay on implemented routes and verified methodology anchors.
 *
 * NI-078 presentation (resolving NI-076 D1/D2 without changing the thesis):
 * a compact H1–H4 assessment sits beside the opening evidence with real
 * anchor links into the unchanged full sections, and the two missing
 * recorded-evidence figures (CL-004 USD windows, CL-007 supply-scale) render
 * in their owning sections through the shared claim-registry figure
 * components. All fifteen sections, definitions and limitations are intact.
 */

const sectionClasses = "mt-12 max-w-(--width-prose)";
const h2Classes = "font-serif text-title leading-title";
const bodyClasses = "text-body leading-body text-text-secondary mt-2";
const listClasses =
  "text-body leading-body text-text-secondary mt-3 max-w-(--width-prose) list-disc pl-5 flex flex-col gap-2";
const linkClasses =
  "text-accent underline underline-offset-2 hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
const noteClasses = "text-ui leading-ui text-text-secondary mt-3";

const claimById: Map<string, ThesisClaim> = new Map(claimRegistry.map((claim) => [claim.id, claim]));

function getClaim(id: string): ThesisClaim {
  const claim = claimById.get(id);
  if (!claim) {
    throw new Error(`Thesis content references an unknown claim id: ${id}`);
  }
  return claim;
}

function EvidenceLinks({ links, label }: { readonly links: readonly ClaimEvidenceLink[]; readonly label: string }) {
  return (
    <ul aria-label={label} className="text-ui leading-ui text-text-secondary mt-3 list-disc pl-5 flex flex-col gap-1">
      {links.map((link) => (
        <li key={link.href}>
          <a href={link.href} className={linkClasses}>
            {link.label}
          </a>
        </li>
      ))}
    </ul>
  );
}

/**
 * NI-076 D1 — compact H1–H4 assessment beside the opening evidence. Statuses
 * restate `hypothesis.status` from the thesis verbatim; each card links to
 * the unchanged full section (real anchors, keyboard reachable). No new
 * claims, no API dependency; the block is server-rendered.
 */
function HypothesisAssessment() {
  const { question } = thesis;
  return (
    <section
      id="hypothesis-assessment"
      aria-labelledby="hypothesis-assessment-heading"
      className={sectionClasses}
    >
      <h2 id="hypothesis-assessment-heading" className={h2Classes}>
        Hypothesis assessment at a glance
      </h2>
      <p className={bodyClasses}>
        The four canonical hypotheses currently carry these recorded assessments. Each card links
        to the full statement below — question, rationale, weakening condition and cited claims.
      </p>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2" aria-label="H1–H4 current assessment">
        {question.hypotheses.map((hypothesis) => (
          <li key={hypothesis.id} className="rounded-surface border border-border bg-surface p-4">
            <p className="font-ui text-ui leading-ui text-text-secondary">
              <span className="font-medium text-text">{hypothesis.code}</span> —{" "}
              <span className="font-medium text-text">{hypothesis.status}</span>
            </p>
            <p className="text-heading leading-heading mt-1">{hypothesis.title}</p>
            <a href={`#${hypothesis.id}`} className={`${linkClasses} mt-2 inline-block`}>
              Read the full {hypothesis.code} assessment
            </a>
          </li>
        ))}
      </ul>
      <p className={noteClasses}>
        The complete thesis follows with all fifteen sections, definitions and limitations:{" "}
        <a href="#executive-summary" className={linkClasses}>
          continue to the executive summary
        </a>
        .
      </p>
    </section>
  );
}

function ThesisBody() {
  const {
    executiveSummary,
    question,
    ecosystem,
    intentsMechanism,
    adoption,
    revenueGeneration,
    revenueCapture,
    tokenEconomics,
    econometrics,
    alternativeExplanations,
    risks,
    scenarios,
    assessment,
    limitations,
    sourcesReproducibility,
  } = thesis;

  return (
    <div className="min-w-0">
      <RecordedPurchases />
      <p className="mt-4 rounded-surface bg-sage px-5 py-4 text-ui text-text">
        {thesis.evidenceStatus}
      </p>

      {/* NI-076 D1: compact overview of the four canonical hypotheses. */}
      <HypothesisAssessment />
      {/* NI-045 duplication CTA: rendered only when a published release
          exists for the thesis slug; otherwise it renders nothing. */}
      <DuplicateReleaseAction slug={thesisReleaseSlug} nextPath="/research" />

      <MechanismFlow />

      {/* 1. Executive summary */}
      <section id={executiveSummary.id} aria-labelledby={`${executiveSummary.id}-heading`} className={sectionClasses}>
        <h2 id={`${executiveSummary.id}-heading`} className={h2Classes}>
          {executiveSummary.title}
        </h2>
        <p className="text-body leading-body text-text mt-3">{executiveSummary.lead}</p>
        {executiveSummary.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
      </section>

      {/* 2. Research question and canonical hypotheses (anchors #h1–#h4) */}
      <section id={question.id} aria-labelledby={`${question.id}-heading`} className={sectionClasses}>
        <h2 id={`${question.id}-heading`} className={h2Classes}>
          {question.title}
        </h2>
        <p className={bodyClasses}>{question.intro}</p>
        <p className={bodyClasses}>{question.hypothesesIntro}</p>
        <div className="mt-4 flex flex-col gap-6">
          {question.hypotheses.map((hypothesis) => (
            <article
              key={hypothesis.id}
              id={hypothesis.id}
              aria-labelledby={`${hypothesis.id}-heading`}
              className="rounded-surface border border-border bg-surface p-4"
            >
              <p className="font-ui text-ui leading-ui text-text-secondary">
                <span className="font-medium text-text">{hypothesis.code}</span> —{" "}
                <span className="font-medium text-text">{hypothesis.status}</span>
              </p>
              <h3 id={`${hypothesis.id}-heading`} className="text-heading leading-heading mt-1">
                {hypothesis.title}
              </h3>
              <p className="text-body leading-body text-text mt-2">{hypothesis.question}</p>
              <p className={bodyClasses}>
                <span className="font-medium text-text">Rationale: </span>
                {hypothesis.rationale}
              </p>
              <p className={bodyClasses}>
                <span className="font-medium text-text">Weakening condition: </span>
                {hypothesis.weakening}
              </p>
              <p className={noteClasses}>
                Recorded claims cited: {hypothesis.claimIds.map((id) => getClaim(id).id).join(", ")}
              </p>
              <EvidenceLinks links={hypothesis.evidence} label={`${hypothesis.code} evidence links`} />
            </article>
          ))}
        </div>
      </section>

      {/* 3. Ecosystem overview */}
      <section id={ecosystem.id} aria-labelledby={`${ecosystem.id}-heading`} className={sectionClasses}>
        <h2 id={`${ecosystem.id}-heading`} className={h2Classes}>
          {ecosystem.title}
        </h2>
        {ecosystem.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
        <p className={noteClasses}>{ecosystem.externalNote}</p>
        <EvidenceLinks links={ecosystem.links} label="Ecosystem external references" />
      </section>

      {/* 4. Cross-chain execution and Intents */}
      <section id={intentsMechanism.id} aria-labelledby={`${intentsMechanism.id}-heading`} className={sectionClasses}>
        <h2 id={`${intentsMechanism.id}-heading`} className={h2Classes}>
          {intentsMechanism.title}
        </h2>
        {intentsMechanism.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
        <EvidenceLinks links={intentsMechanism.links} label="Intents mechanism references" />
      </section>

      {/* 5. Adoption and network activity */}
      <section id={adoption.id} aria-labelledby={`${adoption.id}-heading`} className={sectionClasses}>
        <h2 id={`${adoption.id}-heading`} className={h2Classes}>
          {adoption.title}
        </h2>
        {adoption.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
        <EvidenceLinks links={adoption.links} label="Adoption definitions references" />
      </section>

      {/* 6. Revenue generation */}
      <section id={revenueGeneration.id} aria-labelledby={`${revenueGeneration.id}-heading`} className={sectionClasses}>
        <h2 id={`${revenueGeneration.id}-heading`} className={h2Classes}>
          {revenueGeneration.title}
        </h2>
        {revenueGeneration.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
        <EvidenceLinks links={revenueGeneration.links} label="Revenue generation references" />
      </section>

      {/* 7. Revenue capture and observed findings — claims CL-001–CL-006 */}
      <section id={revenueCapture.id} aria-labelledby={`${revenueCapture.id}-heading`} className={sectionClasses}>
        <h2 id={`${revenueCapture.id}-heading`} className={h2Classes}>
          {revenueCapture.title}
        </h2>
        <p className={bodyClasses}>{revenueCapture.intro}</p>
        {/* NI-076 D2: the approximate USD windows (CL-004) beside their claim. */}
        <div className="mt-6 max-w-none">
          <UsdWindowsFigure />
        </div>
        <ol aria-label="Claim registry: revenue capture" className="mt-6 flex flex-col gap-6 list-none pl-0">
          {revenueCapture.claimIds.map((id) => (
            <li key={id}>
              <ClaimCard claim={getClaim(id)} />
            </li>
          ))}
        </ol>
        <p className={bodyClasses}>{revenueCapture.closing}</p>
      </section>

      {/* 8. Token economics — claims CL-007–CL-009 */}
      <section id={tokenEconomics.id} aria-labelledby={`${tokenEconomics.id}-heading`} className={sectionClasses}>
        <h2 id={`${tokenEconomics.id}-heading`} className={h2Classes}>
          {tokenEconomics.title}
        </h2>
        <p className={bodyClasses}>{tokenEconomics.intro}</p>
        {/* NI-076 D2: purchases versus net supply growth on one NEAR scale (CL-007). */}
        <div className="mt-6 max-w-none">
          <SupplyScaleFigure />
        </div>
        <ol aria-label="Claim registry: token economics" className="mt-6 flex flex-col gap-6 list-none pl-0">
          {tokenEconomics.claimIds.map((id) => (
            <li key={id}>
              <ClaimCard claim={getClaim(id)} />
            </li>
          ))}
        </ol>
      </section>

      {/* 9. Econometric evidence — NI-070 release status (no fitted values) */}
      <section id={econometrics.id} aria-labelledby={`${econometrics.id}-heading`} className={sectionClasses}>
        <h2 id={`${econometrics.id}-heading`} className={h2Classes}>
          {econometrics.title}
        </h2>
        <p className="rounded-surface border border-border bg-sage p-4 text-body leading-body text-text mt-3">
          {econometrics.releaseStatus}
        </p>
        {econometrics.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
        <EvidenceLinks links={econometrics.links} label="Econometrics references" />
      </section>

      {/* 10. Alternative explanations */}
      <section
        id={alternativeExplanations.id}
        aria-labelledby={`${alternativeExplanations.id}-heading`}
        className={sectionClasses}
      >
        <h2 id={`${alternativeExplanations.id}-heading`} className={h2Classes}>
          {alternativeExplanations.title}
        </h2>
        <ul className={listClasses}>
          {alternativeExplanations.items.map((item) => (
            <li key={item.slice(0, 64)}>{item}</li>
          ))}
        </ul>
      </section>

      {/* 11. Risks and counterarguments */}
      <section id={risks.id} aria-labelledby={`${risks.id}-heading`} className={sectionClasses}>
        <h2 id={`${risks.id}-heading`} className={h2Classes}>
          {risks.title}
        </h2>
        <ul className={listClasses}>
          {risks.items.map((item) => (
            <li key={item.slice(0, 64)}>{item}</li>
          ))}
        </ul>
      </section>

      {/* 12. Long-term scenarios */}
      <section id={scenarios.id} aria-labelledby={`${scenarios.id}-heading`} className={sectionClasses}>
        <h2 id={`${scenarios.id}-heading`} className={h2Classes}>
          {scenarios.title}
        </h2>
        <p className={bodyClasses}>{scenarios.intro}</p>
        <ol className="mt-4 flex flex-col gap-3 max-w-(--width-prose)">
          {scenarios.cases.map((scenario) => (
            <li key={scenario.id} className="rounded-surface border border-border bg-surface p-4">
              <p className="font-ui text-ui leading-ui text-text font-medium">{scenario.title}</p>
              <p className="text-body leading-body text-text-secondary mt-1">{scenario.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* 13. Final assessment */}
      <section id={assessment.id} aria-labelledby={`${assessment.id}-heading`} className={sectionClasses}>
        <h2 id={`${assessment.id}-heading`} className={h2Classes}>
          {assessment.title}
        </h2>
        {assessment.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
      </section>

      {/* 14. Limitations */}
      <section id={limitations.id} aria-labelledby={`${limitations.id}-heading`} className={sectionClasses}>
        <h2 id={`${limitations.id}-heading`} className={h2Classes}>
          {limitations.title}
        </h2>
        <ul className={listClasses}>
          {limitations.items.map((item) => (
            <li key={item.slice(0, 64)}>{item}</li>
          ))}
        </ul>
        <p className={bodyClasses}>{limitations.staleness}</p>
      </section>

      {/* 15. Sources and reproducibility */}
      <section
        id={sourcesReproducibility.id}
        aria-labelledby={`${sourcesReproducibility.id}-heading`}
        className={sectionClasses}
      >
        <h2 id={`${sourcesReproducibility.id}-heading`} className={h2Classes}>
          {sourcesReproducibility.title}
        </h2>
        {sourcesReproducibility.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
        <p className={bodyClasses}>{sourcesReproducibility.datasetNote}</p>
        <EvidenceLinks links={sourcesReproducibility.links} label="Sources and reproduction references" />
      </section>
    </div>
  );
}

export default function ResearchPage() {
  return (
    <article className="page-container">
      <PageIntro
        eyebrow="The original research · November 2026"
        title={<>{thesis.title}<br /><em className="text-accent">{thesis.emphasis}</em></>}
        action={<p className="max-w-[45ch] text-ui text-text-secondary lg:pb-1">{thesis.standfirst}</p>}
      />
      <div className="mt-9 grid items-start gap-8 lg:grid-cols-[12.75rem_minmax(0,1fr)]">
        <nav aria-label={thesis.tocLabel} className="lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:overflow-y-auto lg:px-1">
          <p aria-hidden="true" className="eyebrow mb-3">In this research</p>
          <ol className="list-decimal space-y-0.5 pl-5 text-metadata text-text-secondary marker:font-medium marker:tabular-nums">
            {thesisToc.map((entry) => (
              <li key={entry.id} className="pl-1">
                <a href={`#${entry.id}`} className="inline-flex rounded-control px-1 py-1 text-text-secondary hover:text-accent hover:underline">
                  {entry.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <ThesisBody />
      </div>
    </article>
  );
}
