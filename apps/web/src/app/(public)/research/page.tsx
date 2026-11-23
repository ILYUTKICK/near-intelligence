import type { Metadata } from "next";
import Link from "next/link";

import { AcquisitionComparison } from "@/features/public-research/AcquisitionComparison";
import { ClaimCard } from "@/features/public-research/ClaimCard";
import { DuplicateReleaseAction } from "@/features/public-research/DuplicateReleaseAction";
import { MechanismFlow } from "@/features/public-research/MechanismFlow";
import { InteractiveHistory } from "@/features/public-research/InteractiveHistory";
import { scopePeriodLabel, SupplyScaleFigure } from "@/features/public-research/ResearchFigures";
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
 * NI-087 puts the thesis, recorded window comparison and H1–H4 verdicts
 * before the full assessment. The article retains the stable source anchors.
 */

const sectionClasses = "mt-12 min-w-0 scroll-mt-8 border-t border-border pt-7";
const h2Classes = "max-w-[28ch] font-serif text-title leading-title";
const bodyClasses = "mt-3 max-w-[62ch] font-sans text-[1.25rem] leading-[1.5]";
const listClasses = `${bodyClasses} list-disc space-y-2 pl-5`;
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

const purchaseClaim = getClaim("CL-002");
const valuationClaim = getClaim("CL-004");
const acquisitionWindows = purchaseClaim.quantities
  .filter((quantity) => quantity.unit === "NEAR acquired")
  .map((quantity) => {
    const estimate = valuationClaim.quantities.find(
      (entry) => entry.scope === quantity.scope && entry.unit === "USD (approximate acquisition value)",
    );
    if (!estimate) throw new Error(`Missing recorded USD valuation for ${quantity.scope}`);
    return { label: scopePeriodLabel(quantity.scope), near: quantity.value, usd: estimate.value };
  });

const readingLinks = [
  ["executive-summary", "Investment thesis"],
  ["purchase-windows", "Purchases over time"],
  ["hypothesis-assessment", "Hypotheses and verdicts"],
  ["revenue-capture", "From fees to treasury"],
  ["token-economics", "Purchases and supply"],
  ["interactive-history", "Explore the data"],
  ["assessment", "Final assessment"],
  ["sources-reproducibility", "Sources and notes"],
] as const;

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
      <ul className="mt-4 divide-y divide-border border-y border-border" aria-label="H1–H4 current assessment">
        {question.hypotheses.map((hypothesis) => (
          <li key={hypothesis.id}>
            <a href={`#${hypothesis.id}`} className="grid grid-cols-[2.25rem_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1 py-3 hover:bg-surface-muted/60">
              <span className="text-ui font-semibold text-accent">{hypothesis.code}</span>{" "}
              <span className="font-serif text-xl font-medium">{hypothesis.title}</span>{" "}
              <span className="col-start-2 text-ui text-text-secondary">{hypothesis.status}</span>
            </a>
          </li>
        ))}
      </ul>
      <p className={noteClasses}>
        <a href="#question" className={linkClasses}>Read the research question and test criteria</a>
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
      {/* 1. Executive summary */}
      <section id={executiveSummary.id} aria-labelledby={`${executiveSummary.id}-heading`} className="min-w-0 scroll-mt-8">
        <h2 id={`${executiveSummary.id}-heading`} className={h2Classes}>
          {executiveSummary.title}
        </h2>
        <p className={bodyClasses}><strong>The thesis.</strong> {executiveSummary.lead}</p>
        {executiveSummary.paragraphs.map((paragraph) => (
          <p key={paragraph.slice(0, 64)} className={bodyClasses}>
            {paragraph}
          </p>
        ))}
      </section>

      <section id="purchase-windows" aria-labelledby="purchase-windows-heading" className="mt-6 scroll-mt-8">
        <h2 id="purchase-windows-heading" className={h2Classes}>Fewer tokens in each 30-day window</h2>
        <p className={bodyClasses}>
          The cohort acquired less NEAR in each window. Higher daily prices offset much of the drop
          in token quantity when we valued the final window in dollars.
        </p>
        <AcquisitionComparison
          windows={acquisitionWindows}
          nearDecline={purchaseClaim.quantities[3].value}
          usdDecline={valuationClaim.quantities[3].value}
          closingDecline={valuationClaim.quantities[4].value}
        />
      </section>

      <HypothesisAssessment />

      {/* 2. Research question and canonical hypotheses (anchors #h1–#h4) */}
      <section id={question.id} aria-labelledby={`${question.id}-heading`} className={sectionClasses}>
        <h2 id={`${question.id}-heading`} className={h2Classes}>
          {question.title}
        </h2>
        <p className={bodyClasses}>{question.intro}</p>
        <div className="mt-6 divide-y divide-border border-y border-border">
          {question.hypotheses.map((hypothesis) => (
            <article
              key={hypothesis.id}
              id={hypothesis.id}
              aria-labelledby={`${hypothesis.id}-heading`}
              className="scroll-mt-8 py-5"
            >
              <p className="font-ui text-ui leading-ui text-text-secondary">
                <span className="font-medium text-text">{hypothesis.code}</span> —{" "}
                <span className="font-medium text-text">{hypothesis.status}</span>
              </p>
              <h3 id={`${hypothesis.id}-heading`} className="text-heading leading-heading mt-1">
                {hypothesis.title}
              </h3>
              <p className={bodyClasses}>{hypothesis.question}</p>
              <p className={bodyClasses}>
                {hypothesis.rationale}
              </p>
              <p className={bodyClasses}>
                <strong>What would weaken it.</strong>{" "}
                {hypothesis.weakening}
              </p>
              <ul aria-label={`${hypothesis.code} recorded claims`} className="mt-3 flex flex-wrap gap-3 text-ui">
                {hypothesis.claimIds.map((id) => (
                  <li key={id}><a href={`#${id}-heading`} className={linkClasses}>{id}</a></li>
                ))}
              </ul>
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
        <MechanismFlow />
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

      <InteractiveHistory />

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
        <p className={bodyClasses}>{revenueCapture.closing}</p>
        <p className={noteClasses}>
          <a href="#thesis-usd-windows" className={linkClasses}>Compare NEAR and estimated USD across the three windows</a>
        </p>
        <ol aria-label="Claim registry: revenue capture" className="mt-6 list-none divide-y divide-border border-y border-border pl-0">
          {revenueCapture.claimIds.map((id) => (
            <li key={id}>
              <ClaimCard claim={getClaim(id)} />
            </li>
          ))}
        </ol>
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
        <ol aria-label="Claim registry: token economics" className="mt-6 list-none divide-y divide-border border-y border-border pl-0">
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
        <p className={bodyClasses}>
          The available data support an exploratory comparison of volume and gross fees.
          The dataset still lacks comparable daily protocol revenue, and the archive fit is pending.
        </p>
        <details className="mt-3 border-y border-border py-2">
          <summary className="w-fit cursor-pointer py-1 text-ui font-medium text-accent">Model design and release status</summary>
          <p className={bodyClasses}>{econometrics.releaseStatus}</p>
          {econometrics.paragraphs.map((paragraph) => (
            <p key={paragraph.slice(0, 64)} className={bodyClasses}>{paragraph}</p>
          ))}
        </details>
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
            <li key={scenario.id} className="rounded-surface border-2 border-panel-border bg-surface p-4">
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
        <DuplicateReleaseAction slug={thesisReleaseSlug} nextPath="/research" />
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
        <p className={bodyClasses}>{thesis.evidenceStatus}</p>
        <EvidenceLinks links={sourcesReproducibility.links} label="Sources and reproduction references" />
      </section>
    </div>
  );
}

export default function ResearchPage() {
  return (
    <article className="page-container pt-8 lg:pt-9" aria-labelledby="research-title">
      <header className="border-b border-border pb-6">
        <div className="flex flex-wrap items-center gap-3 text-ui">
          <Link href="/blog" className="inline-flex min-h-11 items-center font-medium text-accent hover:underline">← Back to Blog</Link>
          <span className="border-l border-border pl-3 text-text-secondary">NEAR Intents · November 2026</span>
        </div>
        <h1 id="research-title" className="mt-3 text-left text-[clamp(2.75rem,6vw,4.85rem)] leading-[.98] tracking-[-.04em]">
          {thesis.title}<br /><em className="text-accent">{thesis.emphasis}</em>
        </h1>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-5">
          <p className="max-w-[47ch] font-sans text-[clamp(1.35rem,2.6vw,1.625rem)] leading-[1.25]">{thesis.standfirst}</p>
          <p className="border-l border-border pl-4 text-ui text-text-secondary">
            Observation window<br />
            <strong className="text-text">6 Aug–3 Nov 2026 UTC</strong><br />
            Accounts linked to three treasury wallets
          </p>
        </div>
      </header>
      <div className="mt-6 grid items-start gap-8 lg:grid-cols-[11.5rem_minmax(0,53rem)] lg:gap-12">
        <aside className="lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:overflow-y-auto lg:pr-2">
          <nav aria-label="In this article">
            <p className="eyebrow mb-2">In this article</p>
            <ul className="border-l border-border text-ui">
              {readingLinks.map(([id, label]) => (
                <li key={id}><a href={`#${id}`} className="block py-2 pl-3 text-text-secondary hover:text-accent hover:underline">{label}</a></li>
              ))}
            </ul>
          </nav>
          <details className="mt-3 text-ui">
            <summary className="w-fit cursor-pointer py-2 text-accent">All sections</summary>
            <nav aria-label={thesis.tocLabel}>
              <ol className="space-y-1 border-l border-border pl-3">
                {thesisToc.map((entry) => (
                  <li key={entry.id}><a href={`#${entry.id}`} className="block py-1 text-text-secondary hover:text-accent hover:underline">{entry.title}</a></li>
                ))}
              </ol>
            </nav>
          </details>
        </aside>
        <ThesisBody />
      </div>
    </article>
  );
}
