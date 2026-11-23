import Link from "next/link";

import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { publicationHref, type Publication } from "./publications";

/** The cover uses registered publication metadata; it never implies another article. */
export function PublicationCard({ publication }: { publication: Publication }) {
  return <article className="paper-panel overflow-hidden lg:grid lg:grid-cols-[minmax(16rem,.7fr)_minmax(0,1.3fr)]">
    <div className="flex flex-col justify-between gap-8 border-b-2 border-panel-border bg-action p-7 text-text lg:border-r-2 lg:border-b-0 lg:p-9">
      <div><p className="text-metadata font-semibold">Research journal</p><p className="mt-6 max-w-[12ch] font-display text-title leading-title font-bold">{publication.topic}</p></div>
      <div><p className="max-w-[22ch] text-heading leading-heading font-display font-bold">{publication.question}</p><span className="comic-tag mt-6 bg-surface">{publication.releaseLabel}</span></div>
    </div>
    <div className="p-7 lg:p-9">
      <div className="flex flex-wrap items-center gap-3 text-metadata text-text-secondary"><span className="comic-tag bg-yellow">{publication.format}</span><span>{publication.evidenceLabel}</span></div>
      <h3 className="mt-6 max-w-[24ch] font-display text-title leading-title font-bold">
        <Link href={publicationHref(publication)} className="rounded-control hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus">{publication.title}</Link>
      </h3>
      <p className="mt-4 max-w-[54ch] text-body leading-body text-text-secondary">{publication.summary}</p>
      <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-ui text-text-secondary" aria-label="Inside the research">
        {publication.highlights.map((highlight) => <li key={highlight} className="flex items-center gap-2"><ProductIcon name="document" />{highlight}</li>)}
      </ul>
      <Button asChild className="mt-7"><Link href={publicationHref(publication)}>Read the research</Link></Button>
    </div>
  </article>;
}
