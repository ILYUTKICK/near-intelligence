import type { Metadata } from "next";
import Link from "next/link";

import { PageIntro } from "@/components/layout/PageIntro";
import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { publications } from "@/features/blog/publications";
import { PublicationCard } from "@/features/blog/PublicationCard";

export const metadata: Metadata = {
  title: "Blog — NEAR Intelligence",
  description: "Original research on NEAR and Intents, with interactive evidence, clear definitions and the limits behind every conclusion.",
};

export default function BlogPage() {
  return <div className="page-container">
    <PageIntro eyebrow="The research journal" title={<>Blog.<br /><em className="text-accent">Ideas, examined.</em></>}
      action={<p className="max-w-[44ch] text-ui leading-ui text-text-secondary lg:pb-1">Original investigations into NEAR and Intents. Explore the argument, inspect the data and see where the evidence ends.</p>} />

    <section aria-labelledby="research-articles-heading" className="mt-10 border-t border-border pt-7">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="research-articles-heading" className="eyebrow">Research articles</h2>
        <p className="text-metadata text-text-secondary">{publications.length} {publications.length === 1 ? "publication" : "publications"}</p>
      </div>
      <ul className="space-y-6" aria-label="Published research articles">
        {publications.map((publication) => <li key={publication.slug}>
          <PublicationCard publication={publication} />
        </li>)}
      </ul>
    </section>
    <aside className="mt-10 flex flex-wrap items-start justify-between gap-6 border-t border-border pt-7" aria-labelledby="explore-evidence-heading">
      <div><h2 id="explore-evidence-heading" className="font-serif text-heading">Go deeper into the evidence.</h2><p className="mt-2 max-w-[60ch] text-ui leading-ui text-text-secondary">Every research question starts with a definition. Inspect the available data or read how we work.</p></div>
      <div className="flex flex-wrap gap-3"><Button asChild variant="secondary"><Link href="/data">Explore data <ProductIcon name="arrow" /></Link></Button><Button asChild variant="quiet"><Link href="/methodology">Our methodology <ProductIcon name="arrow" /></Link></Button></div>
    </aside>
  </div>;
}
