import Link from "next/link";

import { editorialAnchors } from "@/lib/navigation";

/**
 * Public footer: honest product framing only — no live statistics, no
 * counters, no unfinished-feature links. Data is historical; the note says
 * so explicitly.
 */
export function PublicFooter() {
  return (
    <footer className="mt-6 border-t border-border">
      <div className="mx-auto flex w-full max-w-(--width-content-max) flex-wrap items-center justify-between gap-4 px-(--page-gutter) py-7 text-metadata text-text-secondary">
        <p>NEAR Intelligence · Independent, evidence-first research.</p>
        <nav aria-label="Footer" className="flex flex-wrap gap-5">
          <Link href={editorialAnchors.sources} className="hover:underline">Sources &amp; definitions</Link>
          <Link href={editorialAnchors.reproduce} className="hover:underline">Reproduction</Link>
          <Link href="/research" className="hover:underline">Read the thesis</Link>
        </nav>
      </div>
    </footer>
  );
}
