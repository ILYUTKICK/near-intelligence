import type { Metadata } from "next";

import { MechanismFlow } from "@/features/public-research/MechanismFlow";
import { research } from "@/features/public-research/content";

export const metadata: Metadata = { title: "Research — NEAR Intelligence" };

/**
 * Public research route (NI-011): the reading structure for the thesis.
 * Sections carry stable anchors (IA: /research#h1 … #h4) so citations and
 * evidence links can already reference them; the reviewed quantitative
 * content is bound to these sections by NI-014 — until then each section
 * says exactly that, with no metrics and no dead controls.
 */
export default function ResearchPage() {
  return (
    <article className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <div className="max-w-(--width-prose)">
        <h1>{research.title}</h1>
        <p className="text-body leading-body text-text-secondary mt-4">{research.standfirst}</p>
      </div>
      <MechanismFlow />
      <section aria-labelledby="research-outline-heading" className="mt-12">
        <h2 id="research-outline-heading" className="text-heading leading-heading">
          Thesis sections
        </h2>
        <div className="mt-6 flex flex-col gap-8 max-w-(--width-prose)">
          {research.outline.map((section) => (
            <section key={section.id} id={section.id} aria-labelledby={`${section.id}-title`}>
              <h3 id={`${section.id}-title`} className="font-serif text-title leading-title">
                {section.title}
              </h3>
              <p className="text-body leading-body text-text-secondary mt-2">{section.body}</p>
            </section>
          ))}
        </div>
      </section>
    </article>
  );
}
