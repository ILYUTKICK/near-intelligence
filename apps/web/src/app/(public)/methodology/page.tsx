import type { Metadata } from "next";

import { methodology } from "@/features/public-research/content";

export const metadata: Metadata = { title: "Methodology — NEAR Intelligence" };

/**
 * Public methodology route (NI-011): the shell with the two stable anchors
 * required by the IA (#sources, #reproduce). Provider tables, manifests and
 * the reproduction recipe are published here by NI-013 — the shell states
 * that honestly and carries no placeholders that could read as real content.
 */
export default function MethodologyPage() {
  return (
    <article className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <div className="max-w-(--width-prose)">
        <h1>{methodology.title}</h1>
        <p className="text-body leading-body text-text-secondary mt-4">{methodology.standfirst}</p>
      </div>
      <div className="mt-10 flex flex-col gap-8 max-w-(--width-prose)">
        {methodology.sections.map((section) => (
          <section key={section.id} id={section.id} aria-labelledby={`${section.id}-title`}>
            <h2 id={`${section.id}-title`} className="font-serif text-title leading-title">
              {section.title}
            </h2>
            <p className="text-body leading-body text-text-secondary mt-2">{section.body}</p>
          </section>
        ))}
      </div>
    </article>
  );
}
