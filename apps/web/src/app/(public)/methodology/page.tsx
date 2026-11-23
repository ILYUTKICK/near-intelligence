import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { ProductIcon, type ProductIconName } from "@/components/layout/ProductIcon";

export const metadata: Metadata = {
  title: "Methodology — NEAR Intelligence",
  description: "Where our evidence comes from, what the metrics mean, and how to inspect the same data behind a claim.",
};

const chapters = [
  { id: "sources", label: "Sources" },
  { id: "definitions", label: "Metric definitions" },
  { id: "collection", label: "From data to evidence" },
  { id: "verify", label: "Inspect a number" },
  { id: "readiness", label: "Limits & interpretation" },
  { id: "reproduce", label: "Reproducibility" },
] as const;

const sourceFamilies: Array<{ icon: ProductIconName; name: string; providers: string; body: string; limitation: string }> = [
  {
    icon: "globe", name: "On-chain records", providers: "NEAR public BigQuery tables · NEAR RPC",
    body: "Saved transaction and execution records underpin the observed conversion and treasury-payout cohort. Block data provides recorded supply boundaries.",
    limitation: "The conversion and payout study covers 6 August–3 November 2026 UTC and a selected treasury-linked cohort, not all market activity.",
  },
  {
    icon: "chart", name: "Reported fees & volume", providers: "DefiLlama · NEAR Revenue Dashboard · Dune",
    body: "Daily fee and volume series are retained with their provider's definition and observation dates. Source disagreements remain visible rather than being averaged away.",
    limitation: "These sources share Dune lineage. Agreement is not independent confirmation, and provider-reported gross fees are not attributable protocol revenue.",
  },
  {
    icon: "book", name: "Prices & supporting context", providers: "CoinGecko · NEAR materials · Indexed chain history",
    body: "Historical price observations support an estimated dollar valuation. Governance materials and indexed records provide additional, separately qualified context.",
    limitation: "A daily price is not a swap execution price. An index's observed history is not proof of every action, and a policy statement is not a guaranteed outcome.",
  },
];

const keyMetrics = [
  {
    title: "Observed NEAR purchases", unit: "NEAR acquired",
    counts: "Successful conversions of other assets into wrap.near within the observed treasury-linked cohort.",
    limits: "Not whole-market demand or proof that earned fees funded the purchases.",
  },
  {
    title: "Treasury payouts", unit: "NEAR transferred",
    counts: "Matched native transfers from intents.near to the three selected wallets, excluding internal treasury hops.",
    limits: "Cash flows, not revenue, profit or an independently additive measure of token demand.",
  },
  {
    title: "Provider-reported gross fees", unit: "USD reported",
    counts: "The provider's gross protocol and distribution fee measure, retained under its stated methodology.",
    limits: "Not revenue retained by NEAR. Definitions and historical values can differ or be revised by the provider.",
  },
];

const preparation = [
  { title: "Preserve the source", body: "Keep the saved input, its source, observation period and content hash. Recorded evidence stays tied to its original dates." },
  { title: "Validate the records", body: "Check identities, duplicates, successful execution, units and calendar coverage. Missing or conflicting records carry an explicit reason." },
  { title: "Apply one definition", body: "Calculate each metric with a registered formula and exact token arithmetic. A changed definition receives a new version." },
  { title: "Publish a fixed version", body: "Only validated datasets are approved. Charts identify the resolved version; saved research revisions and exports retain the evidence they pinned." },
];

const verification = [
  { title: "Read the definition", body: "Open Sources & definitions on a chart. Check what is counted, the unit, the source and the limits of the measure." },
  { title: "Check the selected evidence", body: "Confirm the dates, filters and dataset version. A historical range remains historical even when retrieved today." },
  { title: "Inspect the exact values", body: "Use the equivalent data table, available without hovering. Missing values remain gaps, and estimates or bounds retain their labels." },
  { title: "Keep the same context", body: "Save the inspected selection to research. Its acknowledged revision and exported figures retain that dataset and calculation context." },
];

const linkClass = "text-link underline underline-offset-4 hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus";
const bodyClass = "mt-4 max-w-(--width-prose) text-body leading-body text-text-secondary";
const sectionClass = "scroll-mt-28 border-t border-border pt-8";

function SectionHeading({ number, title, children }: { number: string; title: string; children: ReactNode }) {
  return <header>
    <p className="eyebrow">{number}</p>
    <h2 className="mt-3 text-title text-pretty">{title}</h2>
    <p className={bodyClass}>{children}</p>
  </header>;
}

/** Reader-facing article; canonical evidence lives in the existing registers. */
export default function MethodologyPage() {
  return <article className="page-container pb-10">
    <header className="border-b border-border pb-10 lg:pb-12">
      <p className="eyebrow">Our methodology</p>
      <h1 className="mt-4 max-w-[19ch] text-page text-pretty">How we turn data<br className="hidden sm:block" /> <em className="text-accent">into evidence.</em></h1>
      <p className="mt-5 max-w-[60ch] text-lg leading-relaxed text-text-secondary">A number is useful when you can trace it. Here is where our data comes from, how we define it, and what the evidence can actually support.</p>
      <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3 text-ui">
        <Link className={linkClass} href="/charts">Inspect the chart library</Link>
        <p className="text-text-secondary">Sources, definitions and limitations stay with every chart.</p>
      </div>
    </header>

    <div className="mt-10 grid items-start gap-12 lg:grid-cols-[180px_minmax(0,1fr)] lg:gap-16">
      <nav aria-label="On this page" className="lg:sticky lg:top-8">
        <p className="eyebrow">On this page</p>
        <ol className="mt-4 flex flex-wrap gap-x-5 gap-y-3 lg:flex-col lg:gap-0">
          {chapters.map((chapter, index) => <li key={chapter.id}>
            <a className="flex min-h-11 items-center gap-3 text-ui text-text-secondary hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus" href={`#${chapter.id}`}>
              <span aria-hidden="true" className="text-metadata tabular-nums">{String(index + 1).padStart(2, "0")}</span>{chapter.label}
            </a>
          </li>)}
        </ol>
      </nav>

      <div className="min-w-0 space-y-16 lg:space-y-20">
        <section id="sources" className="scroll-mt-28" aria-label="Sources">
          <SectionHeading number="01 / Sources" title="Start with the source.">We distinguish records observed on-chain from values reported by a provider and estimates derived from them. Each needs its own context.</SectionHeading>
          <div className="mt-7 divide-y divide-border">
            {sourceFamilies.map((source) => <div key={source.name} className="grid gap-3 py-6 sm:grid-cols-[32px_minmax(0,1fr)] sm:gap-5">
              <ProductIcon name={source.icon} className="mt-1 size-6 text-accent" />
              <div>
                <h3 className="text-heading">{source.name}</h3>
                <p className="mt-1 text-metadata font-medium text-accent">{source.providers}</p>
                <p className="mt-3 text-body leading-body text-text-secondary">{source.body}</p>
                <p className="mt-2 text-ui leading-relaxed text-text-secondary"><span className="font-medium text-text">Keep in mind.</span> {source.limitation}</p>
              </div>
            </div>)}
          </div>
          <p className="mt-3 text-ui leading-relaxed text-text-secondary">Coverage, access and reuse rights vary by source. Historical observations keep their dates; a fresh retrieval does not make an old observation fresh.</p>
        </section>

        <section id="definitions" className={sectionClass} aria-label="Metric definitions">
          <SectionHeading number="02 / Definitions" title="Different numbers. Different meanings.">Activity, fees, purchases and supply answer different questions. We define a metric once and keep its meaning attached to every view.</SectionHeading>
          <div className="mt-7 overflow-x-auto" role="region" aria-label="Key metric comparison" tabIndex={0}>
            <table className="w-full min-w-[580px] border-collapse text-left text-ui leading-relaxed">
              <caption className="sr-only">What the three key metrics measure and what they do not establish</caption>
              <thead><tr className="border-b border-border text-metadata text-text-secondary"><th scope="col" className="w-[25%] pb-3 pr-5 font-medium">Measure</th><th scope="col" className="w-[40%] pb-3 pr-5 font-medium">What we count</th><th scope="col" className="pb-3 font-medium">What it does not establish</th></tr></thead>
              <tbody>{keyMetrics.map((metric) => <tr key={metric.title} className="border-b border-border align-top"><th scope="row" className="py-5 pr-5 font-medium text-text">{metric.title}<span className="mt-1 block text-metadata font-normal text-text-secondary">{metric.unit}</span></th><td className="py-5 pr-5 text-text-secondary">{metric.counts}</td><td className="py-5 text-text-secondary">{metric.limits}</td></tr>)}</tbody>
            </table>
          </div>
          <p className="mt-6 max-w-(--width-prose) font-serif text-heading text-accent">Treasury purchases do not reduce total supply — burns do.</p>
          <p className={bodyClass}>Token amounts retain exact arithmetic. Dollar valuations based on daily prices are estimates. Missing observations remain gaps, never zeros; flows and prices are never silently filled forward.</p>
        </section>

        <section id="collection" className={sectionClass} aria-label="From data to evidence">
          <SectionHeading number="03 / Preparation" title="A traceable path to every chart.">Validation comes before publication. The source, calculation and dataset version remain linked as a number moves into a chart or a research document.</SectionHeading>
          <ol className="mt-8">{preparation.map((step, index) => <li key={step.title} className="relative grid grid-cols-[32px_minmax(0,1fr)] gap-5 pb-7 last:pb-0">
            {index < preparation.length - 1 ? <span aria-hidden="true" className="absolute top-8 bottom-0 left-[15px] w-px bg-border" /> : null}
            <span aria-hidden="true" className="relative z-1 grid size-8 place-items-center rounded-full bg-sage text-ui font-medium text-accent">{index + 1}</span><div><h3 className="text-ui font-semibold text-text">{step.title}</h3><p className="mt-1 max-w-(--width-prose) text-body leading-body text-text-secondary">{step.body}</p></div>
          </li>)}</ol>
          <div className="mt-8 border-l-2 border-accent pl-5">
            <p className="text-ui font-medium text-text">For example: observed NEAR purchases</p>
            <p className="mt-2 text-body leading-body text-text-secondary">Saved successful conversions in the treasury-linked cohort → deduplicated events and exact NEAR amounts → the versioned purchase metric → an approved dataset and its chart. The 90-day window is 2026-08-06 ≤ UTC date &lt; 2026-11-04.</p>
          </div>
        </section>

        <section id="verify" className={sectionClass} aria-label="Inspect a number">
          <SectionHeading number="04 / Verification" title="Inspect the evidence behind a number.">Follow a number from its definition to its saved context before using it in your thesis.</SectionHeading>
          <ol className="mt-7 grid gap-x-8 gap-y-7 sm:grid-cols-2">{verification.map((step, index) => <li key={step.title}><p className="text-metadata font-medium text-accent">0{index + 1}</p><h3 className="mt-2 text-ui font-semibold text-text">{step.title}</h3><p className="mt-2 text-body leading-body text-text-secondary">{step.body}</p></li>)}</ol>
          <Link className={`${linkClass} mt-6 inline-flex min-h-11 items-center gap-2 text-ui font-medium`} href="/charts">Open a chart and inspect its source</Link>
        </section>

        <section id="readiness" className={sectionClass} aria-label="Limits and interpretation">
          <SectionHeading number="05 / Interpretation" title="Know where the evidence stops.">A measured relationship is not a causal explanation. Coverage, accounting scope and the way a provider constructs its data limit the conclusions we can draw.</SectionHeading>
          <ul className="mt-7 divide-y divide-border">
            <li className="py-5 first:pt-0"><h3 className="text-ui font-semibold text-text">A cohort is not the whole market.</h3><p className="mt-2 text-body leading-body text-text-secondary">Observed purchases cover treasury-linked collector accounts only. Short attribution cohorts stay descriptive; the 90-day window cannot establish a long-term stable mechanism.</p></li>
            <li className="py-5"><h3 className="text-ui font-semibold text-text">A bound is not an exact total.</h3><p className="mt-2 text-body leading-body text-text-secondary">Gross issuance and burn remain conservative lower bounds: the mint-header audit verified 6 of 297 headers. The unverified remainder is never assumed zero.</p></li>
            <li className="py-5"><h3 className="text-ui font-semibold text-text">Correlation is not causation.</h3><p className="mt-2 text-body leading-body text-text-secondary">Fees and volume can be mechanically related. Shared sources, market trends and accounting choices remain limitations even when a statistical model reports a strong association.</p></li>
          </ul>
          <div className="mt-3 bg-sage px-5 py-5">
            <p className="text-ui font-semibold text-text">Current model evidence</p>
            <p className="mt-2 text-body leading-body text-text">No reviewed fitted result is published here. The current data-readiness decision admits a fee-versus-volume proxy only with limits; it does not establish attributable protocol revenue or token value capture.</p>
            <Link href="/models" className={`${linkClass} mt-3 inline-flex min-h-11 items-center text-ui font-medium`}>View published model evidence</Link>
          </div>
        </section>

        <section id="reproduce" className={sectionClass} aria-label="Reproducibility">
          <SectionHeading number="06 / Reproducibility" title="The same evidence, again.">A reproducible result needs more than a screenshot. Its inputs, definitions, selections and calculation environment must be identifiable.</SectionHeading>
          <ul className="mt-7 grid gap-x-8 gap-y-5 sm:grid-cols-2">{[
            ["Source & input identity", "Where the observations came from, their actual period and the content hashes of the retained inputs."],
            ["Definition & selection", "The metric and chart versions, units, dates and filters used for the figure."],
            ["Dataset & calculation", "The approved immutable dataset, formula version and recorded transformation path."],
            ["A fixed research revision", "The saved context behind an exported figure, rather than a chart that silently refreshes later."],
          ].map(([title, body]) => <li key={title}><h3 className="text-ui font-semibold text-text">{title}</h3><p className="mt-1 text-body leading-body text-text-secondary">{body}</p></li>)}</ul>
          <p className={bodyClass}>Raw archive access remains restricted by the source and sharing permissions. No raw-data downloads are offered here. Published metric, chart and model views expose their permitted evidence and limitations.</p>
          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border pt-6 text-ui font-medium"><Link href="/research" className={linkClass}>Read the research</Link><Link href="/charts" className={linkClass}>Explore the evidence</Link></div>
        </section>
      </div>
    </div>
  </article>;
}
