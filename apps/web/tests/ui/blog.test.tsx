import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import BlogPage from "@/app/(public)/blog/page";
import BlogArticlePage, { generateMetadata } from "@/app/(public)/blog/[slug]/page";
import ArticleNotFound from "@/app/(public)/blog/not-found";
import { PublicHeader } from "@/components/layout/PublicHeader";
import { PublicationArticle } from "@/features/blog/PublicationArticle";
import { PublicationCard } from "@/features/blog/PublicationCard";
import { publicationBySlug, publicationHref, publications, type Publication } from "@/features/blog/publications";
import { thesisReleaseSlug } from "@/features/public-research/content";

const pathname = vi.hoisted(() => ({ current: "/blog" }));
vi.mock("next/navigation", () => ({
  usePathname: () => pathname.current,
  notFound: () => { throw new Error("NEXT_NOT_FOUND"); },
  permanentRedirect: (path: string) => { throw new Error(`NEXT_REDIRECT_308:${path}`); },
}));
afterEach(() => { pathname.current = "/blog"; });

/** Test-only authored article; never registered or exposed by runtime routes. */
const future: Extract<Publication, { kind: "article" }> = {
  kind: "article", slug: "synthetic-publication-fixture", title: "Synthetic research article (fixture)",
  summary: "Synthetic summary for the shared publication template.", topic: "Synthetic topic",
  format: "Research note", releaseLabel: "Synthetic release (fixture)", evidenceLabel: "Synthetic evidence only — not production data.",
  question: "A separate synthetic research question?", highlights: ["Synthetic finding scope"],
  sections: [{ id: "synthetic-section", title: "Synthetic section", paragraphs: ["<script>unsafe()</script> is literal source text, not markup."],
    sources: [{ label: "Synthetic source citation", href: "https://example.test/source" }] }],
  relatedSlugs: [thesisReleaseSlug, "unknown-not-published"],
};

describe("Blog publication catalog", () => {
  it("lists exactly the existing complete research with a working canonical link and honest metadata", () => {
    render(<BlogPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Blog");
    const list = screen.getByRole("list", { name: "Published research articles" });
    expect(within(list).getAllByRole("article")).toHaveLength(1);
    expect(within(list).getByRole("link", { name: "Read the research" })).toHaveAttribute("href", "/research");
    expect(within(list).getByText("November 2026 research release")).toBeInTheDocument();
    expect(list).toHaveTextContent("6 August–3 November 2026 UTC");
    expect(list).not.toHaveTextContent(/Published 10 November|Coming soon|Buy now|Synthetic/);
    expect(list.querySelector("time")).toBeNull();
  });

  it("supports another article without copying the route or its original research question", () => {
    render(<><PublicationCard publication={future} /><PublicationArticle publication={future} /></>);
    expect(screen.getByRole("link", { name: "Read the research" })).toHaveAttribute("href", "/blog/synthetic-publication-fixture");
    expect(screen.getByText(future.question)).toBeInTheDocument();
    expect(screen.queryByText("Does adoption reach the token?")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Synthetic section" })).toHaveAttribute("id", "synthetic-section-heading");
    expect(screen.getByText(future.sections[0].paragraphs[0])).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByRole("link", { name: "Synthetic source citation" })).toHaveAttribute("href", "https://example.test/source");
    expect(screen.getByRole("complementary", { name: "Related research" })).not.toHaveTextContent("unknown-not-published");
    expect(publicationBySlug(future.slug)).toBeUndefined();
  });

  it("has unique slugs and no synthetic publication in the runtime registry", () => {
    expect(publications).toHaveLength(1);
    expect(new Set(publications.map((publication) => publication.slug)).size).toBe(publications.length);
    expect(publicationBySlug(thesisReleaseSlug)).toBe(publications[0]);
    expect(publicationHref(publications[0])).toBe("/research");
    for (const slug of ["__proto__", "../workspace", "not-published", future.slug]) expect(publicationBySlug(slug)).toBeUndefined();
  });

  it("keeps the original article URL canonical and rejects unknown article slugs", async () => {
    await expect(BlogArticlePage({ params: Promise.resolve({ slug: thesisReleaseSlug }) })).rejects.toThrow("NEXT_REDIRECT_308:/research");
    await expect(BlogArticlePage({ params: Promise.resolve({ slug: "not-published" }) })).rejects.toThrow("NEXT_NOT_FOUND");
    const metadata = await generateMetadata({ params: Promise.resolve({ slug: thesisReleaseSlug }) });
    expect(metadata.description).toBe(publications[0].summary);
    expect(metadata.alternates).toBeUndefined();
    render(<ArticleNotFound />);
    expect(screen.getByRole("heading", { name: "Article not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Blog" })).toHaveAttribute("href", "/blog");
  });

  it.each(["/blog", "/blog/future-real-article", "/research"])("keeps Blog active on %s", (route) => {
    pathname.current = route;
    render(<PublicHeader />);
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(within(nav).getByRole("link", { name: "Blog" })).toHaveAttribute("aria-current", "page");
    expect(nav.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  });

  it("offers a keyboard-reachable article action and accessible catalog", async () => {
    const { container } = render(<BlogPage />);
    const action = screen.getByRole("link", { name: "Read the research" });
    action.focus();
    expect(action).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("link", { name: "Explore data" })).toHaveFocus();
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});
