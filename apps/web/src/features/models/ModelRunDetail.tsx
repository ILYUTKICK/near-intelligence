import type {
  ModelDefinition,
  ModelReadiness,
  ModelRunDetail as ModelRunDetailData,
} from "@/features/models/models-schema";
import { templateInterpretationSchema as templateInterpretation } from "@/features/models/models-schema";
import {
  gateVerdictWording,
  recordedFloat,
} from "@/features/models/recorded";
import {
  ModelSpecificationPanel,
  ReasonCodeList,
  VerbatimBlock,
} from "@/features/models/ModelSpecificationPanel";

/**
 * The published run detail (NI-054 handoff, contract point 2).
 *
 * Ordering contract enforced here and asserted by the UI test: the
 * mechanical fee-volume warning and the prohibited labels render BEFORE any
 * coefficient, and every gate limit code stays visible. All statistical
 * values render through the verbatim recorded-float conversion (no rounding,
 * no locale re-formatting), and every recorded open-object block is rendered
 * verbatim rather than re-keyed.
 */
export function ModelRunDetail({
  run,
  definition,
  readiness,
}: {
  run: ModelRunDetailData;
  definition: ModelDefinition | null;
  readiness: ModelReadiness | null;
}) {
  return (
    <article className="max-w-[58rem]">
      <header>
        <p className="eyebrow mt-5">Published model run</p>
        <h1 className="mt-2 text-page">
          Model run {run.model_id} v{run.model_version}
        </h1>
        <p className="text-body leading-body text-text-secondary mt-2">
          One published run exactly as the publication gate recorded and the reviewer approved.
          Values below are recorded results, not live estimates.
        </p>
        <dl className="paper-panel mt-6 grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-2 p-6 text-ui leading-ui">
          <dt className="text-text-secondary">Run id</dt>
          <dd className="font-mono break-all">{run.run_id}</dd>
          <dt className="text-text-secondary">Gate verdict</dt>
          <dd>{gateVerdictWording(run.gate_verdict)}</dd>
          <dt className="text-text-secondary">Sample</dt>
          <dd>
            {`${run.sample.start} to ${run.sample.end_exclusive} (end exclusive) · ${run.sample.nobs} observations`}
          </dd>
          <dt className="text-text-secondary">Reproduction tolerances</dt>
          <dd>
            {`rtol ${run.tolerances.coefficient_rtol} / atol ${run.tolerances.coefficient_atol} (recorded)`}
          </dd>
          <dt className="text-text-secondary">Published</dt>
          <dd>{`${run.published_at} by ${run.published_by}`}</dd>
          <dt className="text-text-secondary">Code commit</dt>
          <dd className="font-mono break-all">{run.code_commit}</dd>
        </dl>
      </header>

      {/*
        LIMITS FIRST (handoff contract point 2): the mechanical fee-volume
        warning and the prohibited labels appear before any coefficient, and
        every gate limit code is visible.
      */}
      <section aria-labelledby="model-limits-heading" className="mt-10">
        <h2 id="model-limits-heading">Limits and prohibitions — read before any coefficient</h2>
        <div className="mt-4 rounded-surface border border-danger bg-surface-muted p-6">
          <h3 className="text-base">
            Prohibited labels — this result must never be presented as:
          </h3>
          <ul className="mt-2 list-disc pl-5 text-ui leading-ui font-medium">
            {run.limitations.prohibited_labels.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
          <h3 className="mt-6 text-base">Recorded limitation notes (verbatim):</h3>
          <ul className="mt-2 list-disc pl-5 text-ui leading-ui">
            {run.limitations.spec_limitation_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
          {run.limitations.gate_limit_codes.length > 0 ? (
            <>
              <h3 className="mt-6 text-base">Gate limit codes (all recorded codes visible):</h3>
              <ul className="mt-2 list-disc pl-5 text-ui leading-ui">
                {run.limitations.gate_limit_codes.map((code) => (
                  <li key={code} className="font-mono">
                    {code}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="mt-6 text-ui leading-ui text-text-secondary">
              The gate recorded no limit codes for this run.
            </p>
          )}
          {run.admission_reasons.length > 0 ? (
            <ReasonCodeList label="Recorded admission reasons" reasons={run.admission_reasons.map((reason) => ({
              code: reason.code,
              severity: reason.severity,
              detail: reason.detail,
            }))} />
          ) : null}
          <p className="mt-4 text-ui leading-ui text-text-secondary">
            Every number below is subject to the limits on this list. Nothing on this page is a
            causal effect, a demand elasticity or protocol revenue.
          </p>
        </div>
      </section>

      <section aria-labelledby="model-interpretation-heading" className="mt-10">
        <h2 id="model-interpretation-heading">Interpretation — mechanical template, not authored text</h2>
        <TemplateInterpretation interpretation={run.interpretation} />
      </section>

      <ModelSpecificationPanel definition={definition} readiness={readiness} />

      <section aria-labelledby="model-spec-heading" className="mt-10">
        <h2 id="model-spec-heading">Specification (recorded verbatim)</h2>
        <VerbatimBlock label="The preregistered specification this run fitted" value={run.specification} />
      </section>

      <section aria-labelledby="model-design-heading" className="mt-10">
        <h2 id="model-design-heading">Design (recorded verbatim)</h2>
        <VerbatimBlock label="The transformed design matrix record" value={run.design} />
      </section>

      <section aria-labelledby="model-estimation-heading" className="mt-10">
        <h2 id="model-estimation-heading">Estimation (recorded verbatim)</h2>
        <VerbatimBlock label="The estimation summary" value={run.estimation} />
      </section>

      {/*
        The coefficient table: exact recorded floats only (recordedFloat),
        after the limits/interpretation/specification sections above.
      */}
      <section aria-labelledby="model-coefficients-heading" className="mt-10">
        <h2 id="model-coefficients-heading">Coefficients (recorded values)</h2>
        <table className="mt-4 w-full border-collapse text-ui leading-ui">
          <caption className="caption-top text-left text-ui leading-ui text-text-secondary pb-2">
            Exact recorded float64 values, shown without rounding. p-values are recorded
            evidence, never a selection input — nothing on this page was chosen or filtered by
            them.
          </caption>
          <thead>
            <tr className="border-b border-border text-left">
              <th scope="col" className="py-2 pr-4 font-medium">Term</th>
              <th scope="col" className="py-2 pr-4 font-medium">Estimate</th>
              <th scope="col" className="py-2 pr-4 font-medium">Std. error</th>
              <th scope="col" className="py-2 pr-4 font-medium">t</th>
              <th scope="col" className="py-2 pr-4 font-medium">p-value</th>
              <th scope="col" className="py-2 pr-4 font-medium">95% CI low</th>
              <th scope="col" className="py-2 font-medium">95% CI high</th>
            </tr>
          </thead>
          <tbody>
            {run.coefficients.map((coefficient) => (
              <tr key={coefficient.name} className="border-b border-border">
                <th scope="row" className="py-2 pr-4 text-left font-mono font-normal break-all">
                  {coefficient.name}
                </th>
                <td className="py-2 pr-4 font-mono">{recordedFloat(coefficient.estimate)}</td>
                <td className="py-2 pr-4 font-mono">{recordedFloat(coefficient.std_error)}</td>
                <td className="py-2 pr-4 font-mono">{recordedFloat(coefficient.t_stat)}</td>
                <td className="py-2 pr-4 font-mono">{recordedFloat(coefficient.p_value)}</td>
                <td className="py-2 pr-4 font-mono">{recordedFloat(coefficient.ci95_low)}</td>
                <td className="py-2 font-mono">{recordedFloat(coefficient.ci95_high)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="model-diagnostics-heading" className="mt-10">
        <h2 id="model-diagnostics-heading">Diagnostics (recorded verbatim)</h2>
        <VerbatimBlock
          label="The NI-053 diagnostics battery as recorded"
          value={run.diagnostics}
        />
      </section>

      <section aria-labelledby="model-environment-heading" className="mt-10">
        <h2 id="model-environment-heading">Environment and reproduction (recorded verbatim)</h2>
        <VerbatimBlock label="The recorded environment" value={run.environment} />
        <VerbatimBlock label="The recorded reproduction contract" value={run.reproduction} />
      </section>

      <section aria-labelledby="model-approval-heading" className="mt-10">
        <h2 id="model-approval-heading">Review approval</h2>
        <dl className="mt-4 grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-ui leading-ui">
          <dt className="text-text-secondary">Decision</dt>
          <dd className="font-mono">{run.approval.decision}</dd>
          <dt className="text-text-secondary">Reviewer</dt>
          <dd>{run.approval.reviewer}</dd>
          <dt className="text-text-secondary">Review reference</dt>
          <dd className="break-all">{run.approval.review_reference}</dd>
          {run.approval.reviewed_at != null ? (
            <>
              <dt className="text-text-secondary">Reviewed at</dt>
              <dd>{run.approval.reviewed_at}</dd>
            </>
          ) : null}
          {run.approval.notes != null ? (
            <>
              <dt className="text-text-secondary">Notes</dt>
              <dd>{run.approval.notes}</dd>
            </>
          ) : null}
        </dl>
      </section>

      {/*
        Reproduction artifact (handoff contract point 3): the immutable
        manifest bundle download plus the offline verify pointer.
      */}
      <section aria-labelledby="model-manifest-heading" className="mt-10">
        <h2 id="model-manifest-heading">Reproduction artifact</h2>
        <p className="mt-2 text-body leading-body text-text-secondary">
          The full manifest bundle of this run is downloadable below. It is served immutably
          with a run-id ETag and downloads as an attachment; the same bytes are what the
          publication gate verified.
        </p>
        <p className="mt-4">
          <a
            href={run.manifest_url}
            download
            className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Download the manifest bundle
          </a>
        </p>
        <p className="mt-4 text-body leading-body text-text-secondary">
          A reviewer re-verifies the downloaded bundle offline — no operator tooling, no
          network, no re-fit — with:
        </p>
        <pre className="mt-2 overflow-x-auto rounded-surface border border-border bg-surface-muted p-4 text-ui leading-ui font-mono">
          <code>{verifyCommand}</code>
        </pre>
      </section>
    </article>
  );
}

const verifyCommand =
  "python -m near_api.research verify --bundle <downloaded.json> --offline";

/**
 * Best-effort structural rendering of the template interpretation: the fixed
 * sentences with their template labels when the recorded block matches the
 * NI-053 template shape, otherwise the whole block verbatim as JSON. The
 * mechanical-template framing is visible in both cases.
 */
function TemplateInterpretation({ interpretation }: { interpretation: Record<string, unknown> }) {
  const parsed = templateInterpretation.safeParse(interpretation);
  if (!parsed.success) {
    return (
      <div className="mt-4">
        <p className="text-ui leading-ui text-text-secondary">
          The interpretation block did not match the known template shape, so it is rendered
          verbatim below instead of being paraphrased.
        </p>
        <VerbatimBlock label="Recorded interpretation (verbatim)" value={interpretation} />
      </div>
    );
  }
  const template = parsed.data;
  return (
    <div className="mt-4 rounded-surface border border-border bg-surface-muted p-6">
      <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-ui leading-ui">
        <dt className="text-text-secondary">Template</dt>
        <dd className="font-mono">{template.template_id}</dd>
        <dt className="text-text-secondary">Rendering policy</dt>
        <dd>{template.rendering_policy}</dd>
      </dl>
      <ul className="mt-4 list-disc pl-5 text-body leading-body">
        {template.sentences.map((sentence) => (
          <li key={sentence}>{sentence}</li>
        ))}
      </ul>
      {template.authoring_note != null ? (
        <p className="mt-4 text-ui leading-ui text-text-secondary">
          Authoring note (recorded): {template.authoring_note}
        </p>
      ) : null}
    </div>
  );
}
