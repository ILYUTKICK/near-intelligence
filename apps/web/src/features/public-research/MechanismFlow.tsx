import { mechanism } from "./content";

/**
 * The economic value chain as semantic HTML (NI-011): an ordered list of
 * stages with explicit cautions separating purchases from burns. No chart
 * library and no numbers — quantitative evidence binds to this structure in
 * later tasks. The arrow glyphs are decorative only.
 */
export function MechanismFlow() {
  return (
    <section aria-labelledby="mechanism-heading" id="mechanism" className="mt-12">
      <h2 id="mechanism-heading" className="text-heading leading-heading">
        {mechanism.heading}
      </h2>
      <p className="text-body leading-body text-text-secondary mt-3 max-w-(--width-prose)">
        {mechanism.intro}
      </p>
      <ol className="mt-6 flex flex-col gap-3 max-w-(--width-prose)">
        {mechanism.stages.map((stage, index) => (
          <li
            key={stage.id}
            id={stage.id}
            className="rounded-surface border border-border bg-surface p-4"
          >
            <p className="font-ui text-ui leading-ui text-text-secondary flex items-baseline gap-2">
              <span aria-hidden="true" className="font-medium">
                {index + 1}
                {index < mechanism.stages.length - 1 ? " →" : ""}
              </span>
              <span className="text-text font-medium">{stage.title}</span>
            </p>
            <p className="text-body leading-body text-text-secondary mt-1">{stage.body}</p>
          </li>
        ))}
      </ol>
      <ul className="text-ui leading-ui text-text-secondary mt-4 max-w-(--width-prose) list-disc pl-5">
        {mechanism.cautions.map((caution) => (
          <li key={caution}>{caution}</li>
        ))}
      </ul>
    </section>
  );
}
