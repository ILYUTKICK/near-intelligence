import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function ArticleNotFound() {
  return <div className="page-container"><div className="paper-panel max-w-(--width-prose) p-7 lg:p-10">
    <p className="eyebrow">Blog</p><h1 className="mt-3 font-serif text-title">Article not found</h1>
    <p className="mt-3 text-body leading-body text-text-secondary">This research article is unavailable. Browse the journal to find a published article.</p>
    <Button asChild className="mt-6"><Link href="/blog">Back to Blog</Link></Button>
  </div></div>;
}
