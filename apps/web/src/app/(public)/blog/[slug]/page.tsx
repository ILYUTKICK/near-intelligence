import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";

import { PublicationArticle } from "@/features/blog/PublicationArticle";
import { publicationBySlug } from "@/features/blog/publications";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const publication = publicationBySlug((await params).slug);
  return publication ? { title: `${publication.title} — NEAR Intelligence`, description: publication.summary }
    : { title: "Article not found — NEAR Intelligence" };
}

export default async function BlogArticlePage({ params }: Props) {
  const publication = publicationBySlug((await params).slug);
  if (!publication) notFound();
  // Keep the original full thesis and every existing fragment at its canonical URL.
  if (publication.kind === "original-research") permanentRedirect("/research");
  return <PublicationArticle publication={publication} />;
}
