import type { ClaimQuantity, ThesisClaim } from "./content";

/**
 * One claim-registry entry (NI-014): the observation, its typed recorded
 * quantities (each with scope and source), the definition/dataset version
 * references, evidence links and the standing caution. Bounds render as
 * bounds and directions render as words; nothing here computes or rounds.
 */

const tableWrapClasses = "mt-3 overflow-x-auto border-y border-border";
const headCellClasses = "p-3 font-ui text-ui leading-ui text-left align-bottom border-b border-border";
const rowHeaderClasses = "p-3 align-top font-ui text-ui leading-ui text-text";
const cellClasses = "p-3 align-top text-metadata leading-metadata text-text-secondary";
const linkClasses =
  "text-accent underline underline-offset-2 hover:text-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

function QuantityHeadline({ quantity }: { readonly quantity: ClaimQuantity }) {
  return (
    <>
      <span className="text-text font-medium">{quantity.value}</span> <span>{quantity.unit}</span>
      {quantity.bound ? (
        <span className="block mt-1 font-medium text-text">
          {quantity.bound === "lower" ? "Lower bound (at least)" : "Upper bound (at most)"}
        </span>
      ) : null}
      {quantity.direction ? (
        <span className="block mt-1 font-medium text-text">
          {quantity.direction === "decrease" ? "Decrease" : "Increase"}
        </span>
      ) : null}
      {quantity.basis ? <span className="block mt-1">Basis: {quantity.basis}</span> : null}
    </>
  );
}

export function ClaimCard({ claim }: { readonly claim: ThesisClaim }) {
  return (
    <article
      aria-labelledby={`${claim.id}-heading`}
      className="min-w-0 py-5"
    >
      <p className="font-ui text-ui leading-ui text-text-secondary">
        <span className="font-medium text-text">{claim.id}</span> — {claim.assessment}
      </p>
      <h3 id={`${claim.id}-heading`} className="mt-1 scroll-mt-8 text-heading leading-heading">
        {claim.title}
      </h3>
      <p className="text-body leading-body text-text-secondary mt-2">{claim.observation}</p>
      {claim.caution ? <p className="mt-2 text-ui leading-ui text-text-secondary">{claim.caution}</p> : null}

      <details className="mt-2">
        <summary className="w-fit cursor-pointer py-2 text-ui font-medium text-accent">
          {claim.quantities.length > 0 ? "Recorded values and sources" : "Sources and definitions"}
          <span className="sr-only"> for {claim.id}</span>
        </summary>
        {claim.quantities.length > 0 ? (
          <div className={tableWrapClasses}>
            <table className="w-full table-fixed border-collapse break-words text-left">
              <caption className="sr-only">{`${claim.id} recorded quantities, scopes and sources`}</caption>
              <thead>
                <tr>
                  <th scope="col" className={headCellClasses}>
                    Recorded quantity
                  </th>
                  <th scope="col" className={headCellClasses}>
                    Scope
                  </th>
                  <th scope="col" className={headCellClasses}>
                    Source
                  </th>
                </tr>
              </thead>
              <tbody>
                {claim.quantities.map((quantity, index) => (
                  <tr key={`${claim.id}-quantity-${index}`} className="border-b border-border last:border-b-0">
                    <th scope="row" className={rowHeaderClasses}>
                      <QuantityHeadline quantity={quantity} />
                    </th>
                    <td className={cellClasses}>{quantity.scope}</td>
                    <td className={cellClasses}>
                      <a href={quantity.sourceHref} className={linkClasses}>
                        Recorded source
                      </a>
                      <span className="block mt-1 break-words">{quantity.source}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        <p className="text-ui leading-ui text-text-secondary mt-3">
          Definition versions:{" "}
          {claim.definitionVersions.length > 0
            ? claim.definitionVersions.join("; ")
            : "none — this claim's values come from recorded analysis artifacts, not a registered metric"}
        </p>
        <p className="text-ui leading-ui text-text-secondary mt-1">
          Dataset versions: {claim.datasetVersionReference}
        </p>

        <ul aria-label={`${claim.id} evidence links`} className="text-ui leading-ui text-text-secondary mt-3 list-disc pl-5 flex flex-col gap-1">
          {claim.evidence.map((link) => (
            <li key={link.href}>
              <a href={link.href} className={linkClasses}>
                {link.label}
              </a>
            </li>
          ))}
        </ul>

      </details>
    </article>
  );
}
