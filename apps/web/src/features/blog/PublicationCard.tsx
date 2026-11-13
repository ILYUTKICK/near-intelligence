import Link from "next/link";

import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { publicationHref, type Publication } from "./publications";

export function PublicationCard({ publication }: { publication: Publication }) {
  return (
    <article className="paper-panel overflow-hidden lg:grid lg:grid-cols-[minmax(0,1.45fr)_minmax(18rem,1fr)]">
      <div className="p-7 lg:p-10">
        <div className="flex flex-wrap items-center gap-3 text-metadata text-text-secondary">
          <span className="rounded-full bg-sage px-3 py-1 font-medium text-accent">{publication.format}</span>
          <span>{publication.topic}</span><span aria-hidden="true">·</span><span>{publication.releaseLabel}</span>
        </div>
        <h3 className="mt-6 max-w-[20ch] font-serif text-title leading-title lg:text-[2.9rem] lg:leading-[1.08]">
          <Link href={publicationHref(publication)} className="rounded-control hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus">{publication.title}</Link>
        </h3>
        <p className="mt-4 max-w-[54ch] text-body leading-body text-text-secondary">{publication.summary}</p>
        <p className="mt-5 max-w-[60ch] text-metadata leading-metadata text-text-secondary">{publication.evidenceLabel}</p>
        <Button asChild className="mt-7"><Link href={publicationHref(publication)}>Read the research <ProductIcon name="arrow" /></Link></Button>
      </div>
      <div className="flex flex-col justify-between border-t border-border bg-sage/50 p-7 lg:border-l lg:border-t-0 lg:p-10">
        <div><p className="eyebrow">The question</p><p className="mt-5 max-w-[14ch] font-serif text-title leading-title text-accent">{publication.question}</p></div>
        <ul className="mt-8 space-y-4 text-ui text-text-secondary" aria-label="Inside the research">
          {publication.highlights.map((highlight) => <li key={highlight} className="flex items-center gap-3 border-t border-border pt-4"><ProductIcon name="document" />{highlight}</li>)}
        </ul>
      </div>
    </article>
  );
}
