import Link from "next/link";

import { PageIntro } from "@/components/layout/PageIntro";
import { publicationHref, relatedPublications, type Publication } from "./publications";

/** Shared article presentation for later real entries; source strings stay React-escaped. */
export function PublicationArticle({ publication }: { publication: Extract<Publication, { kind: "article" }> }) {
  const related = relatedPublications(publication);
  return <article className="page-container">
    <Link href="/blog" className="mb-6 inline-flex min-h-11 items-center text-ui text-accent underline underline-offset-4">← Back to Blog</Link>
    <PageIntro eyebrow={`${publication.format} · ${publication.topic}`} title={publication.title} description={publication.summary} />
    <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-metadata text-text-secondary">
      <span>{publication.releaseLabel}</span>
      {publication.author ? <span>By {publication.author}</span> : null}
      {publication.publishedAt ? <span>Published <time dateTime={publication.publishedAt}>{publication.publishedAt}</time></span> : null}
      {publication.updatedAt ? <span>Updated <time dateTime={publication.updatedAt}>{publication.updatedAt}</time></span> : null}
    </div>
    <p className="mt-5 max-w-(--width-prose) rounded-surface bg-sage p-4 text-ui text-text-secondary">{publication.evidenceLabel}</p>
    <div className="mt-10 max-w-(--width-prose) space-y-10">
      {publication.sections.map((section) => <section key={section.id} id={section.id} aria-labelledby={`${section.id}-heading`}>
        <h2 id={`${section.id}-heading`} className="font-serif text-title leading-title">{section.title}</h2>
        {section.paragraphs.map((paragraph, index) => <p key={index} className="mt-3 text-body leading-body text-text-secondary">{paragraph}</p>)}
        {section.sources?.length ? <ul className="mt-4 list-disc space-y-2 pl-5 text-ui text-text-secondary" aria-label={`${section.title} sources`}>
          {section.sources.map((source) => <li key={source.href}><a href={source.href} className="text-accent underline underline-offset-4">{source.label}</a></li>)}
        </ul> : null}
      </section>)}
    </div>
    {related.length ? <aside className="mt-12 border-t border-border pt-6" aria-label="Related research"><h2 className="font-serif text-heading">Related research</h2><ul className="mt-3 space-y-2">{related.map((entry) => <li key={entry.slug}><Link className="text-accent underline underline-offset-4" href={publicationHref(entry)}>{entry.title}</Link></li>)}</ul></aside> : null}
    <Link href="/blog" className="mt-10 inline-flex min-h-11 items-center text-ui text-accent underline underline-offset-4">All research articles →</Link>
  </article>;
}
