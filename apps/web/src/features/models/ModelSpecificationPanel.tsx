import type { ModelDefinition, ModelReadiness } from "@/features/models/models-schema";
import { recordedJson, severityWording } from "@/features/models/recorded";

/**
 * The public specification record of a published model (NI-054 handoff,
 * contract point 4): the definition with its mechanically composed question
 * and the recorded NI-051 readiness verdict.
 *
 * Honesty contract:
 * - `question` is presented as the mechanical template composition it is —
 *   a fixed template over the specification's declared fields — never as
 *   authored text.
 * - `ready: false` is rendered as the honest not-admitted state; the
 *   recorded verdict and every reason code stay visible and nothing is
 *   presented as a usable model.
 */
export function ModelSpecificationPanel({
  definition,
  readiness,
}: {
  definition: ModelDefinition | null;
  readiness: ModelReadiness | null;
}) {
  return (
    <section aria-labelledby="model-specification-heading" className="mt-10 max-w-prose">
      <h2 id="model-specification-heading">Specification and readiness</h2>
      {definition !== null ? (
        <div className="mt-4 rounded-surface border-2 border-panel-border bg-surface-muted p-6">
          <h3 className="text-base">Public model definition (v{definition.version})</h3>
          <p className="mt-2 font-ui text-ui leading-ui font-medium">
            Mechanically composed question — a fixed template over the specification&rsquo;s
            declared fields; this is not an authored claim.
          </p>
          <blockquote className="mt-2 border-l-2 border-border pl-4 text-body leading-body text-text">
            {definition.question}
          </blockquote>
          <dl className="mt-4 grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-ui leading-ui">
            <dt className="text-text-secondary">Required metrics</dt>
            <dd className="font-mono break-all">{definition.required_metric_ids.join(", ")}</dd>
            <dt className="text-text-secondary">Latest published run</dt>
            <dd className="font-mono break-all">{definition.latest_published_run_id}</dd>
          </dl>
          {definition.limitations.gate_limit_codes.length > 0 ? (
            <>
              <p className="mt-4 font-ui text-ui leading-ui font-medium">
                Gate limit codes recorded on the definition:
              </p>
              <ul className="mt-2 list-disc pl-5 text-ui leading-ui">
                {definition.limitations.gate_limit_codes.map((code) => (
                  <li key={code} className="font-mono">
                    {code}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <VerbatimBlock
            label="Readiness rules (recorded verbatim)"
            value={definition.readiness_rules}
          />
        </div>
      ) : (
        <div role="status" className="mt-4 rounded-surface border-2 border-panel-border bg-surface-muted p-4">
          <p className="text-ui leading-ui text-text-secondary">
            The public model definition could not be resolved for this run&rsquo;s specification
            right now. Nothing is paraphrased in its place.
          </p>
        </div>
      )}

      {readiness !== null ? (
        <div className="mt-6 rounded-surface border-2 border-panel-border bg-surface-muted p-6">
          <h3 className="text-base">Recorded readiness (NI-051 gate verdict)</h3>
          {readiness.ready ? (
            <p className="mt-2 font-ui text-ui leading-ui font-medium text-text">
              Ready: yes — the gate admitted this specification, with the recorded limits below.
            </p>
          ) : (
            <p className="mt-2 font-ui text-ui leading-ui font-medium text-danger">
              Ready: NO — this specification is not admitted. The recorded verdict is shown
              verbatim and nothing on this page presents a usable model.
            </p>
          )}
          <dl className="mt-4 grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-ui leading-ui">
            <dt className="text-text-secondary">Verdict</dt>
            <dd className="font-mono">{readiness.verdict}</dd>
            <dt className="text-text-secondary">Overall verdict</dt>
            <dd>{readiness.overall_verdict}</dd>
            {readiness.selected_specification != null ? (
              <>
                <dt className="text-text-secondary">Selected specification</dt>
                <dd className="font-mono">{readiness.selected_specification}</dd>
              </>
            ) : null}
            <dt className="text-text-secondary">Recorded in run</dt>
            <dd className="font-mono break-all">{readiness.recorded_in_run_id}</dd>
          </dl>
          {readiness.reasons.length > 0 ? (
            <ReasonCodeList
              label="Recorded gate reasons"
              reasons={readiness.reasons.map((reason) => ({
                code: reason.code,
                severity: reason.severity,
                detail: reason.detail,
              }))}
            />
          ) : null}
        </div>
      ) : (
        <div role="status" className="mt-6 rounded-surface border-2 border-panel-border bg-surface-muted p-4">
          <p className="text-ui leading-ui text-text-secondary">
            The recorded readiness verdict could not be resolved for this specification right
            now. A verdict is never guessed here.
          </p>
        </div>
      )}
    </section>
  );
}

/** Shared reason-code list (code stays verbatim, severity is spelled out). */
export function ReasonCodeList({
  label,
  reasons,
}: {
  label: string;
  reasons: Array<{ code: string; severity: "rejecting" | "limit" | "informational"; detail: string }>;
}) {
  return (
    <>
      <p className="mt-4 font-ui text-ui leading-ui font-medium">{label}:</p>
      <ul className="mt-2 list-disc pl-5 text-ui leading-ui">
        {reasons.map((reason) => (
          <li key={`${reason.code}-${reason.detail}`}>
            <span className="font-mono font-medium">{reason.code}</span> —{" "}
            <span>{severityWording(reason.severity)}</span>: {reason.detail}
          </li>
        ))}
      </ul>
    </>
  );
}

/** A recorded open-object block rendered verbatim as JSON. */
export function VerbatimBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <figure className="mt-4">
      <figcaption className="font-ui text-ui leading-ui font-medium text-text-secondary">
        {label}
      </figcaption>
      <pre className="mt-2 overflow-x-auto rounded-surface border-2 border-panel-border bg-surface p-4 text-ui leading-ui font-mono">
        <code>{recordedJson(value)}</code>
      </pre>
    </figure>
  );
}
