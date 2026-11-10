import type { Metadata } from "next";

import { ClaimCard } from "@/features/public-research/ClaimCard";
import { MechanismFlow } from "@/features/public-research/MechanismFlow";
import {
  claimRegistry,
  thesis,
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

export default function ResearchPage() {
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
    <article className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <div className="max-w-(--width-prose)">
        <h1>{thesis.title}</h1>
        <p className="text-body leading-body text-text-secondary mt-4">{thesis.standfirst}</p>
        <p className="text-ui leading-ui text-text mt-4 rounded-surface border border-border bg-surface p-4">
          {thesis.evidenceStatus}
        </p>
      </div>

      <nav aria-label={thesis.tocLabel} className="mt-8 max-w-(--width-prose)">
        <ol className="rounded-surface border border-border bg-surface p-4 list-decimal pl-9 flex flex-col gap-1 text-ui leading-ui">
          {thesisToc.map((entry) => (
            <li key={entry.id}>
              <a href={`#${entry.id}`} className={linkClasses}>
                {entry.title}
              </a>
            </li>
          ))}
        </ol>
      </nav>

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
        <ol aria-label="Claim registry: revenue capture" className="mt-4 flex flex-col gap-6 list-none pl-0">
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
        <ol aria-label="Claim registry: token economics" className="mt-4 flex flex-col gap-6 list-none pl-0">
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
    </article>
  );
}
