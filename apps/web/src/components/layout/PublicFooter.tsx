import Link from "next/link";

import { editorialAnchors, publicNav } from "@/lib/navigation";

/**
 * Public footer: honest product framing only — no live statistics, no
 * counters, no unfinished-feature links. Data is historical; the note says
 * so explicitly.
 */
export function PublicFooter() {
  return (
    <footer className="border-t border-border bg-surface mt-12">
      <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-8">
        <div className="flex flex-col gap-6 md:flex-row md:justify-between">
          <div className="max-w-(--width-prose)">
            <p className="font-serif text-heading leading-heading text-text">NEAR Intelligence</p>
            <p className="text-ui leading-ui text-text-secondary mt-2">
              Evidence-first NEAR investment research. Published values are historical and
              carry their own source, definition version and limitations — the site never
              presents a missing value as zero.
            </p>
          </div>
          <nav aria-label="Footer" className="text-ui leading-ui">
            <ul className="flex flex-col gap-2">
              {publicNav.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="text-text-secondary hover:text-text underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
              <li>
                <Link href={editorialAnchors.sources} className="text-text-secondary hover:text-text underline-offset-2 hover:underline">
                  Data sources
                </Link>
              </li>
              <li>
                <Link href={editorialAnchors.reproduce} className="text-text-secondary hover:text-text underline-offset-2 hover:underline">
                  Reproduction
                </Link>
              </li>
            </ul>
          </nav>
        </div>
      </div>
    </footer>
  );
}
