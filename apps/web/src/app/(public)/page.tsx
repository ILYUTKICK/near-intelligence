import type { Metadata } from "next";
import Link from "next/link";

import { ProductIcon, type ProductIconName } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { PublicationCard } from "@/features/blog/PublicationCard";
import { publicationBySlug } from "@/features/blog/publications";
import { OverviewArtwork } from "@/features/public-research/OverviewArtwork";
import { thesisReleaseSlug } from "@/features/public-research/content";

export const metadata: Metadata = {
  title: "Overview — NEAR Intelligence",
  description: "Original research, interactive data and the evidence behind every conclusion. Understand NEAR and build your own thesis.",
};

const sectionHeading = "font-serif text-title leading-title lg:text-[2.75rem] lg:leading-[1.08]";
const textLink = "inline-flex min-h-11 items-center gap-2 rounded-control text-ui font-medium text-accent underline underline-offset-4 hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus";

const dataDirections: readonly { title: string; description: string; href: string; icon: ProductIconName }[] = [
  { title: "Intents activity", description: "Explore how Intents is being used across the NEAR ecosystem.", href: "/data/intents", icon: "layers" },
  { title: "Revenue & fees", description: "Follow fee generation and examine which revenue can be attributed to NEAR.", href: "/data/revenue", icon: "chart" },
  { title: "Token economics", description: "Understand token flows, supply dynamics and key design choices.", href: "/data/token-economics", icon: "leaf" },
];

const workflow = [
  { title: "Start with the thesis", body: "Read the investment case, the four hypotheses it rests on and what would weaken each one.", href: "/research#question", action: "Read the hypotheses" },
  { title: "Check the evidence", body: "Open a chart, choose a period and check its source. Compare what you find with the claims in the article.", href: "/charts", action: "Browse charts" },
  { title: "Write your assessment", body: "Save charts in your workspace, cite the evidence alongside your notes and export a saved revision.", href: "/workspace", action: "Start a research document" },
] as const;

/**
 * NI-086: the approved editorial Overview. This public introduction has no
 * data/API dependency; financial observations and model status remain in their
 * owning research/data views. All featured content comes from the curated Blog
 * registry. Legacy landing anchors now lead to the corresponding discovery
 * sections and retain explicit routes to their detailed evidence.
 */
export default function HomePage() {
  const featured = publicationBySlug(thesisReleaseSlug);
  if (!featured) throw new Error("The featured public research must be registered.");

  return <div className="page-container">
    <section aria-labelledby="overview-heading" className="grid items-center gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-12">
      <div>
        <p className="eyebrow">Independent research · NEAR ecosystem</p>
        <h1 id="overview-heading" className="mt-6 font-serif text-[clamp(3rem,4.5vw,4.25rem)] leading-[1.02] tracking-[-0.045em]">
          Understand NEAR.<br /><em className="text-accent">Build your own thesis.</em>
        </h1>
        <p className="mt-6 max-w-[39ch] text-body leading-body text-text-secondary lg:text-[1.25rem] lg:leading-[1.5]">Original research, interactive data and the evidence behind every conclusion.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild><Link href="/blog">Read the research <ProductIcon name="arrow" /></Link></Button>
          <Button asChild variant="secondary"><Link href="/data">Explore data</Link></Button>
          <Link href="#how-it-works" className={textLink}>How it works</Link>
        </div>
      </div>
      <OverviewArtwork />
    </section>

    <section id="findings" aria-labelledby="featured-research-heading" className="mt-14 border-t border-border pt-9 lg:mt-16">
      <div className="mb-7 flex flex-wrap items-center justify-between gap-3">
        <h2 id="featured-research-heading" className={sectionHeading}>The research, in focus.</h2>
        <Link href="/blog" className={textLink}>Visit the Blog <ProductIcon name="arrow" /></Link>
      </div>
      <PublicationCard publication={featured} />
    </section>

    <section id="evidence" aria-labelledby="evidence-heading" className="mt-14 border-t border-border pt-9 lg:mt-16">
      <h2 id="evidence-heading" className={sectionHeading}>Explore the evidence.</h2>
      <p className="mt-3 text-body leading-body text-text-secondary">Follow the activity, fees and token flows behind the research.</p>
      <ul aria-label="Data exploration directions" className="mt-7 grid gap-4 lg:grid-cols-3">
        {dataDirections.map((direction) => <li key={direction.href} className="rounded-surface border border-border p-6 lg:p-7">
          <ProductIcon name={direction.icon} className="size-8 text-accent" />
          <h3 className="mt-5 font-serif text-heading leading-heading">{direction.title}</h3>
          <p className="mt-3 max-w-[36ch] text-ui leading-ui text-text-secondary">{direction.description}</p>
          <Link href={direction.href} className={`${textLink} mt-3`} aria-label={`Explore data: ${direction.title}`}>Explore data <ProductIcon name="arrow" /></Link>
        </li>)}
      </ul>
      <p className="mt-4 text-metadata leading-metadata text-text-secondary">Historical datasets · coverage varies by source</p>
    </section>

    <section id="how-it-works" aria-labelledby="workflow-heading" className="mt-12 scroll-mt-8 border-t border-border pt-9 lg:mt-14">
      <h2 id="workflow-heading" className={sectionHeading}>How it works</h2>
      <ol className="mt-8 grid gap-7 lg:grid-cols-3 lg:gap-0">
        {workflow.map((step, index) => <li key={step.title} className="lg:px-7 lg:first:pl-0 lg:last:pr-0 lg:not-first:border-l lg:not-first:border-border">
          <span className="inline-flex size-8 items-center justify-center rounded-control bg-sage font-serif text-ui font-semibold text-accent">0{index + 1}</span>
          <h3 className="mt-4 font-serif text-heading leading-heading">{step.title}</h3>
          <p className="mt-3 max-w-[34ch] text-ui leading-ui text-text-secondary">{step.body}</p>
          <Link href={step.href} className={`${textLink} mt-2`}>{step.action} <ProductIcon name="arrow" /></Link>
        </li>)}
      </ol>
      <p id="mechanism" className="mt-5 text-metadata text-text-secondary">Trace the mechanism in the <Link href="/research#mechanism" className="text-accent underline underline-offset-4">full research</Link>.</p>
    </section>

    <section id="release-status" aria-labelledby="methodology-heading" className="mt-12 flex flex-wrap items-center justify-between gap-5 border-y border-border py-8 lg:mt-14">
      <div>
        <h2 id="methodology-heading" className="font-serif text-heading leading-heading lg:text-[2rem]">Sources first. Assumptions visible.</h2>
        <p className="mt-2 text-ui leading-ui text-text-secondary">Every conclusion has a scope. Every number has a source.</p>
      </div>
      <div className="flex flex-wrap items-center gap-x-6">
        <Link href="/methodology" className={textLink}>Our methodology <ProductIcon name="arrow" /></Link>
        <Link href="/research#econometrics" className="inline-flex min-h-11 items-center text-metadata text-accent underline underline-offset-4">Research status</Link>
      </div>
    </section>

    <section aria-labelledby="workspace-heading" className="mt-6 rounded-surface bg-accent px-7 py-10 text-center text-on-accent lg:py-12">
      <h2 id="workspace-heading" className="font-serif text-title leading-title text-on-accent lg:text-[2.75rem] lg:leading-[1.08]">Make the research your own.</h2>
      <p className="mt-3 text-ui leading-ui">Save charts, add notes and build a thesis you can trace.</p>
      <Button asChild className="mt-6 border-transparent bg-surface text-accent hover:bg-sage focus-visible:outline-on-accent"><Link href="/workspace">Open workspace <ProductIcon name="arrow" /></Link></Button>
    </section>
  </div>;
}
