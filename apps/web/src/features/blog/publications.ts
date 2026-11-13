import { thesis, thesisReleaseSlug } from "@/features/public-research/content";

export interface PublicationSection {
  id: string;
  title: string;
  paragraphs: readonly string[];
  sources?: readonly { label: string; href: string }[];
}

interface PublicationMetadata {
  slug: string;
  title: string;
  summary: string;
  topic: string;
  format: string;
  releaseLabel: string;
  evidenceLabel: string;
  question: string;
  highlights: readonly string[];
  /** Only verified editorial dates/authorship belong here, never retrieval times. */
  publishedAt?: string;
  updatedAt?: string;
  author?: string;
  relatedSlugs?: readonly string[];
}

export type Publication = PublicationMetadata & (
  | { kind: "original-research" }
  | { kind: "article"; sections: readonly PublicationSection[] }
);

/** Curated public content only. Never enumerate private documents or demo releases. */
export const publications: readonly Publication[] = [{
  slug: thesisReleaseSlug,
  kind: "original-research",
  title: `${thesis.title} ${thesis.emphasis}`,
  summary: "Does growing Intents activity translate into lasting value for NEAR? Follow the evidence from adoption and fees to observed purchases, treasury flows and token supply.",
  topic: "NEAR Intents",
  format: "Full research",
  releaseLabel: "November 2026 research release",
  evidenceLabel: "Original cohort: 6 August–3 November 2026 UTC. Longer provider history is explored separately in the article.",
  question: "Does adoption reach the token?",
  highlights: ["How the economic mechanism works", "Interactive charts and exact data", "Supporting evidence and open questions"],
}];

export function publicationBySlug(slug: string): Publication | undefined {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) return undefined;
  return publications.find((publication) => publication.slug === slug);
}

export function publicationHref(publication: Publication): string {
  return publication.kind === "original-research" ? "/research" : `/blog/${publication.slug}`;
}

export function relatedPublications(publication: Publication): Publication[] {
  return (publication.relatedSlugs ?? []).flatMap((slug) => {
    const related = publicationBySlug(slug);
    return related && related.slug !== publication.slug ? [related] : [];
  });
}
