import type { Metadata } from "next";

import { methodology } from "@/features/public-research/content";

export const metadata: Metadata = { title: "Methodology — NEAR Intelligence" };

/**
 * Public methodology route (NI-011 shell, NI-013 content): provider/definition/
 * cleaning/readiness/reproduction sections on the stable anchors required by
 * the IA (#sources, #reproduce — plus #definitions, #collection, #readiness).
 * Provider rows, verdicts and commands mirror the recorded registers; the page
 * offers no raw-data downloads and labels unimplemented commands as such.
 */

const sectionClasses = "mt-12 max-w-(--width-prose)";
const h2Classes = "font-serif text-title leading-title";
const bodyClasses = "text-body leading-body text-text-secondary mt-2";
const listClasses =
  "text-body leading-body text-text-secondary mt-3 max-w-(--width-prose) list-disc pl-5 flex flex-col gap-2";
const codeClasses =
  "block rounded-surface bg-surface-muted px-3 py-2 text-metadata leading-metadata text-text break-words";
const noteClasses = "text-ui leading-ui text-text-secondary mt-1";

export default function MethodologyPage() {
  const { sources, definitions, collection, readiness, reproduce } = methodology;

  return (
    <article className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <div className="max-w-(--width-prose)">
        <h1>{methodology.title}</h1>
        <p className="text-body leading-body text-text-secondary mt-4">{methodology.standfirst}</p>
      </div>

      {/* Sources and rights */}
      <section id={sources.id} aria-labelledby={`${sources.id}-title`} className={sectionClasses}>
        <h2 id={`${sources.id}-title`} className={h2Classes}>
          {sources.title}
        </h2>
        <p className={bodyClasses}>{sources.body}</p>
        <p className="text-ui leading-ui text-text-secondary mt-3">{sources.registerNote}</p>
        <div className="mt-4 overflow-x-auto rounded-surface border border-border bg-surface">
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">{sources.tableCaption}</caption>
            <thead>
              <tr className="border-b border-border">
                <th scope="col" className="font-ui text-ui leading-ui p-3 align-bottom">
                  Provider
                </th>
                <th scope="col" className="font-ui text-ui leading-ui p-3 align-bottom">
                  Provides
                </th>
                <th scope="col" className="font-ui text-ui leading-ui p-3 align-bottom">
                  Access status and verified periods
                </th>
                <th scope="col" className="font-ui text-ui leading-ui p-3 align-bottom">
                  Rights decision
                </th>
              </tr>
            </thead>
            <tbody>
              {sources.providers.map((provider) => (
                <tr key={provider.id} className="border-b border-border last:border-b-0 align-top">
                  <th scope="row" className="p-3 font-ui text-ui leading-ui text-text">
                    {provider.id}
                  </th>
                  <td className="text-metadata leading-metadata text-text p-3">{provider.provides}</td>
                  <td className="text-metadata leading-metadata text-text-secondary p-3">
                    {provider.access}
                  </td>
                  <td className="text-metadata leading-metadata text-text-secondary p-3">
                    {provider.rights}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-ui leading-ui text-text-secondary mt-4">{sources.documentation.label}</p>
        <ul className="text-ui leading-ui mt-1 list-disc pl-5 max-w-(--width-prose)">
          {sources.documentation.links.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                rel="noreferrer"
                className="text-accent underline underline-offset-2 hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <h3 className="text-heading leading-heading mt-6">Access and evidence boundaries</h3>
        <ul className={listClasses}>
          {sources.guarantees.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      {/* Definitions */}
      <section
        id={definitions.id}
        aria-labelledby={`${definitions.id}-title`}
        className={sectionClasses}
      >
        <h2 id={`${definitions.id}-title`} className={h2Classes}>
          {definitions.title}
        </h2>
        <p className={bodyClasses}>{definitions.body}</p>
        <p className={bodyClasses}>{definitions.registryNote}</p>
        <h3 className="text-heading leading-heading mt-6">Availability vocabulary</h3>
        <ul className={listClasses}>
          {definitions.availability.map((item) => (
            <li key={item.code}>
              <span className="font-medium text-text">{item.code}</span> — {item.meaning}
            </li>
          ))}
        </ul>
        <p className={bodyClasses}>{definitions.gatedNote}</p>
        <p className={bodyClasses}>{definitions.boundsNote}</p>
      </section>

      {/* Collection and cleaning */}
      <section
        id={collection.id}
        aria-labelledby={`${collection.id}-title`}
        className={sectionClasses}
      >
        <h2 id={`${collection.id}-title`} className={h2Classes}>
          {collection.title}
        </h2>
        <p className={bodyClasses}>{collection.body}</p>
        <ol className="mt-4 flex flex-col gap-3 max-w-(--width-prose)">
          {collection.stages.map((stage) => (
            <li key={stage.id} className="rounded-surface border border-border bg-surface p-4">
              <p className="font-ui text-ui leading-ui text-text font-medium">{stage.title}</p>
              <p className="text-body leading-body text-text-secondary mt-1">{stage.body}</p>
            </li>
          ))}
        </ol>
        <h3 className="text-heading leading-heading mt-6">Standing guardrails</h3>
        <ul className={listClasses}>
          {collection.guardrails.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <h3 className="text-heading leading-heading mt-6">One path, end to end</h3>
        <p className={bodyClasses}>{collection.exampleIntro}</p>
        <ol className="mt-4 flex flex-col gap-3 max-w-(--width-prose)">
          {collection.exampleSteps.map((step) => (
            <li key={step.label} className="rounded-surface border border-border bg-surface p-4">
              <p className="font-ui text-ui leading-ui text-text font-medium">{step.label}</p>
              <p className="text-body leading-body text-text-secondary mt-1">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Model data readiness */}
      <section
        id={readiness.id}
        aria-labelledby={`${readiness.id}-title`}
        className={sectionClasses}
      >
        <h2 id={`${readiness.id}-title`} className={h2Classes}>
          {readiness.title}
        </h2>
        <p className={bodyClasses}>{readiness.body}</p>
        <p className="rounded-surface border border-border bg-surface p-4 text-body leading-body text-text mt-4">
          {readiness.estimatorStatus}
        </p>
        <p className="rounded-surface border border-border bg-sage p-4 text-body leading-body text-text mt-4">
          {readiness.overall}
        </p>
        <h3 className="text-heading leading-heading mt-6">Per-specification verdicts</h3>
        <ul className="mt-4 flex flex-col gap-3 max-w-(--width-prose)">
          {readiness.specs.map((spec) => (
            <li key={spec.spec} className="rounded-surface border border-border bg-surface p-4">
              <p className="font-ui text-ui leading-ui flex flex-wrap items-baseline gap-x-2">
                <span className="text-text font-medium">{spec.spec}</span>
                <span className="text-text-secondary">—</span>
                <span className="text-text font-medium">{spec.verdict}</span>
              </p>
              <ul className="text-metadata leading-metadata text-text-secondary mt-2 flex flex-col list-disc pl-5 gap-1">
                {spec.codes.map((code) => (
                  <li key={code}>
                    <code>{code}</code>
                  </li>
                ))}
              </ul>
              <p className={noteClasses}>{spec.note}</p>
            </li>
          ))}
        </ul>
        <h3 className="text-heading leading-heading mt-6">Gate thresholds</h3>
        <ul className={listClasses}>
          {readiness.gateNumbers.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <h3 className="text-heading leading-heading mt-6">Window profiles</h3>
        <ul className={listClasses}>
          {readiness.profiles.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      {/* Reproduction */}
      <section
        id={reproduce.id}
        aria-labelledby={`${reproduce.id}-title`}
        className={sectionClasses}
      >
        <h2 id={`${reproduce.id}-title`} className={h2Classes}>
          {reproduce.title}
        </h2>
        <p className={bodyClasses}>{reproduce.body}</p>
        <h3 className="text-heading leading-heading mt-6">Implemented commands</h3>
        <p className={bodyClasses}>{reproduce.implementedIntro}</p>
        <ul
          aria-label="Implemented commands"
          className="mt-4 flex flex-col gap-3 max-w-(--width-prose)"
        >
          {reproduce.implemented.map((item) => (
            <li key={item.command} className="rounded-surface border border-border bg-surface p-4">
              <code className={codeClasses}>{item.command}</code>
              <p className={noteClasses}>{item.note}</p>
            </li>
          ))}
        </ul>
        <h3 className="text-heading leading-heading mt-6">Not implemented yet</h3>
        <p className={bodyClasses}>{reproduce.unavailableIntro}</p>
        <ul
          aria-label="Commands not implemented yet"
          className="mt-4 flex flex-col gap-3 max-w-(--width-prose)"
        >
          {reproduce.unavailable.map((item) => (
            <li key={item.command} className="rounded-surface border border-border bg-surface p-4">
              <code className={codeClasses}>{item.command}</code>
              <p className={noteClasses}>{item.note}</p>
            </li>
          ))}
        </ul>
        <p className={bodyClasses}>{reproduce.environmentNote}</p>
      </section>
    </article>
  );
}
