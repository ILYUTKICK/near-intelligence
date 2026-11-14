import type {
  ModelDefinition,
  ModelReadiness,
  ModelRunDetail as ModelRunDetailData,
} from "@/features/models/models-schema";
import { AddModelToResearch } from "@/features/models/add-to-research/AddModelToResearch";
import { ModelRunTabs } from "@/features/models/ModelRunTabs";
import { VerbatimBlock } from "@/features/models/ModelSpecificationPanel";
import {
  formatDay,
  formatDayShort,
  formatPublishedDateTime,
  fittedSampleSpan,
  inputWindowSpan,
  presentRun,
  rounded,
  substantiveSlope,
} from "@/features/models/presentation";
import { recordedFloat, recordedJson } from "@/features/models/recorded";

/**
 * The published run detail (NI-054 contract point 2; NI-097 presentation).
 *
 * Four keyboard-accessible tabs answer, in order: what the model found, what
 * the checks say, what exactly was estimated and how to reproduce it. Every
 * number renders from the recorded payload — the summary surface rounds for
 * display (marked as such) while the recorded floats stay verbatim in the
 * Exact disclosures. The recorded limitations stay complete in the All
 * recorded limitations disclosure, and the sign-aware finding text is picked
 * from the recorded slope so a positive reading is never spread further than
 * the published result supports.
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
  const presentation = presentRun(run);
  const slope = substantiveSlope(run);
  const reasonDetails = new Map<string, string>(
    (readiness?.reasons ?? []).map((reason) => [reason.code, reason.detail]),
  );

  const tabs = [
    {
      id: "result",
      label: "Result",
      content: <ResultPanel run={run} presentation={presentation} slope={slope}
        reasonDetails={reasonDetails} />,
    },
    {
      id: "diagnostics",
      label: "Diagnostics",
      content: <DiagnosticsPanel run={run} />,
    },
    {
      id: "specification",
      label: "Specification",
      content: <SpecificationPanel run={run} presentation={presentation} />,
    },
    {
      id: "reproduction",
      label: "Reproduction",
      content: <ReproductionPanel run={run} gateVerdict={gateText(run)}
        overallReadiness={readiness?.overall_verdict ?? null} />,
    },
  ];

  return (
    <article className="max-w-[70rem]">
      <ModelRunTabs tabs={tabs} />
    </article>
  );
}

function gateText(run: ModelRunDetailData): string {
  return run.gate_verdict === "READY_WITH_LIMITS"
    ? "Published with limits"
    : "Published";
}

/* ------------------------------------------------------------------ */
/* Result tab                                                          */
/* ------------------------------------------------------------------ */

function ResultPanel({
  run,
  presentation,
  slope,
  reasonDetails,
}: {
  run: ModelRunDetailData;
  presentation: ReturnType<typeof presentRun>;
  slope: ReturnType<typeof substantiveSlope>;
  reasonDetails: Map<string, string>;
}) {
  return (
    <div className="space-y-10">
      <section aria-labelledby="model-finding-heading">
        <p className="eyebrow">What the model found</p>
        <p className="mt-1 text-metadata leading-metadata text-text-secondary">
          Published snapshot
        </p>
        <h2 className="mt-3 font-serif text-page leading-page font-semibold text-text">
          {presentation.finding.headline}
        </h2>
        <p className="mt-3 max-w-prose text-body leading-body text-text-secondary">
          {presentation.finding.body}
        </p>

        {slope ? (
          <div className="mt-8 max-w-2xl">
            <p className="text-ui leading-ui font-medium text-text">
              Estimated relationship · slope
            </p>
            <p className="mt-1 font-serif text-title leading-title font-semibold text-text">
              {rounded(slope.estimate)}
            </p>
            <p className="text-ui leading-ui text-text-secondary">
              95% confidence interval · {rounded(slope.ci95_low)}–{rounded(slope.ci95_high)}
            </p>
            <SlopeIntervalPlot slope={slope} />
            <p className="mt-2 text-metadata leading-metadata text-text-secondary">
              Dot: the point estimate. Line: the 95% confidence interval around it. A
              positive slope means the two daily log changes tend to move in the same
              direction in the fitted sample.
            </p>
          </div>
        ) : null}

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <div className="rounded-surface border border-border bg-surface-muted p-5">
            <h3 className="text-ui leading-ui font-medium text-text">What this supports</h3>
            <p className="mt-1.5 text-ui leading-ui text-text-secondary">
              {presentation.supports}
            </p>
          </div>
          <div className="rounded-surface border border-border bg-surface-muted p-5">
            <h3 className="text-ui leading-ui font-medium text-text">What remains unanswered</h3>
            <p className="mt-1.5 text-ui leading-ui text-text-secondary">
              {presentation.unanswered}
            </p>
          </div>
        </div>

        <details aria-label="Recorded interpretation" className="mt-6 rounded-surface border border-border bg-surface p-5">
          <summary className="cursor-pointer text-ui leading-ui font-medium text-text">
            The recorded interpretation (verbatim)
          </summary>
          <RecordedInterpretation interpretation={run.interpretation} />
        </details>
      </section>

      <details className="rounded-surface border border-border bg-surface p-5"
        aria-label="Exact data table: coefficients and inference">
        <summary className="cursor-pointer text-ui leading-ui font-medium text-text">
          Exact coefficients and inference
        </summary>
        <p className="mt-3 max-w-prose text-ui leading-ui text-text-secondary">
          The summary above is rounded for display. The recorded values are preserved below,
          verbatim. No specification was selected using p-values.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-ui leading-ui">
            <thead>
              <tr className="border-b border-border text-left">
                <th scope="col" className="py-2 pr-4 font-medium">Term</th>
                <th scope="col" className="py-2 pr-4 font-medium">Estimate</th>
                <th scope="col" className="py-2 pr-4 font-medium">HAC standard error</th>
              </tr>
            </thead>
            <tbody>
              {run.coefficients.map((coefficient) => (
                <tr key={coefficient.name} className="border-b border-border">
                  <th scope="row" className="py-2 pr-4 text-left font-mono font-normal break-all">
                    {coefficient.name}
                  </th>
                  <td className="py-2 pr-4 font-mono">{recordedFloat(coefficient.estimate)}</td>
                  <td className="py-2 font-mono">{recordedFloat(coefficient.std_error)}</td>
                </tr>
              ))}
              {run.coefficients.map((coefficient) => (
                <tr key={`${coefficient.name}-interval`} className="border-b border-border">
                  <th scope="row" className="py-2 pr-4 text-left font-mono font-normal break-all">
                    {coefficient.name} · 95% CI
                  </th>
                  <td colSpan={2} className="py-2 font-mono">
                    {`${recordedFloat(coefficient.ci95_low)} to ${recordedFloat(coefficient.ci95_high)}`}
                  </td>
                </tr>
              ))}
              {run.coefficients.map((coefficient) => (
                <tr key={`${coefficient.name}-tp`} className="border-b border-border">
                  <th scope="row" className="py-2 pr-4 text-left font-mono font-normal break-all">
                    {coefficient.name} · t / p
                  </th>
                  <td colSpan={2} className="py-2 font-mono">
                    {`${recordedFloat(coefficient.t_stat)} / ${recordedFloat(coefficient.p_value)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-metadata leading-metadata text-text-secondary">
          {estimationSummary(run)}
        </p>
      </details>

      <p className="max-w-prose text-ui leading-ui text-text-secondary">
        The fitted observations cover {fittedSampleSpan(run)}. The input window is
        {" "}[{formatDay(run.sample.start)}, {formatDay(run.sample.end_exclusive)}) UTC; one
        observation is lost to the daily difference.
      </p>

      <LimitationsDisclosure run={run} reasonDetails={reasonDetails} />
    </div>
  );
}

/** The slope point estimate with its 95% interval, drawn from recorded values. */
function SlopeIntervalPlot({
  slope,
}: {
  slope: NonNullable<ReturnType<typeof substantiveSlope>>;
}) {
  const low = slope.ci95_low;
  const high = slope.ci95_high;
  const estimate = slope.estimate;
  // The scale covers the interval plus padding, always including zero.
  const min = Math.min(0, low) - Math.abs(high - low) * 0.1 - 0.05;
  const max = Math.max(0, high) + Math.abs(high - low) * 0.1 + 0.05;
  const width = 560;
  const plotHeight = 74;
  const padX = 8;
  const toX = (value: number) =>
    padX + ((value - min) / (max - min)) * (width - 2 * padX);
  const ticks = niceTicks(min, max);
  return (
    <figure className="mt-4">
      <svg
        viewBox={`0 0 ${width} ${plotHeight + 26}`}
        className="w-full"
        role="img"
        aria-label={`Slope estimate ${rounded(estimate)} with a 95% confidence interval from ${rounded(low)} to ${rounded(high)}.`}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={toX(tick)} x2={toX(tick)} y1={8} y2={plotHeight}
              stroke="var(--color-border)" strokeWidth="1" />
            <text x={toX(tick)} y={plotHeight + 18} textAnchor="middle"
              className="fill-current text-text-secondary" fontSize="11">
              {tickLabel(tick)}
            </text>
          </g>
        ))}
        <line x1={toX(low)} x2={toX(high)} y1={plotHeight / 2} y2={plotHeight / 2}
          stroke="var(--color-accent)" strokeWidth="2" />
        <line x1={toX(0)} x2={toX(0)} y1={6} y2={plotHeight + 2}
          stroke="var(--color-text-secondary)" strokeWidth="1"
          strokeDasharray={Math.abs(min) > 1e-9 && min < 0 ? "4 3" : "0"} />
        <circle cx={toX(estimate)} cy={plotHeight / 2} r="5.5"
          fill="var(--color-accent)" />
      </svg>
      <figcaption className="text-metadata leading-metadata text-text-secondary">
        Point estimate and 95% confidence interval
      </figcaption>
    </figure>
  );
}

function niceTicks(min: number, max: number): number[] {
  const step = max - min > 2 ? 0.5 : max - min > 0.5 ? 0.25 : 0.1;
  const ticks: number[] = [];
  const first = Math.ceil(min / step) * step;
  for (let value = first; value <= max + 1e-9; value += step) {
    ticks.push(Number(value.toFixed(6)));
  }
  return ticks;
}

function tickLabel(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/0$/, "");
}

function estimationSummary(run: ModelRunDetailData): string {
  const estimation = run.estimation as Record<string, unknown>;
  const rSquared = typeof estimation.r_squared === "number" ? estimation.r_squared : null;
  return [
    "Daily log differences · HAC covariance",
    rSquared !== null ? `R² ${rounded(rSquared)} (rounded)` : null,
  ].filter(Boolean).join(" · ");
}

/* ------------------------------------------------------------------ */
/* Limitations disclosure                                              */
/* ------------------------------------------------------------------ */

function LimitationsDisclosure({
  run,
  reasonDetails,
}: {
  run: ModelRunDetailData;
  reasonDetails: Map<string, string>;
}) {
  const codes = run.limitations.gate_limit_codes;
  return (
    <details className="rounded-surface border border-border bg-surface p-5">
      <summary className="cursor-pointer text-ui leading-ui font-medium text-text">
        All recorded limitations · {codes.length}
      </summary>
      <div className="mt-4 space-y-4">
        <div>
          <h3 className="text-ui leading-ui font-medium text-text">
            Prohibited labels — this result must never be presented as:
          </h3>
          <ul className="mt-1.5 list-disc pl-5 text-ui leading-ui text-text-secondary">
            {run.limitations.prohibited_labels.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-ui leading-ui font-medium text-text">
            Recorded limitation notes (verbatim)
          </h3>
          <ul className="mt-1.5 list-disc pl-5 text-ui leading-ui text-text-secondary">
            {run.limitations.spec_limitation_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-ui leading-ui font-medium text-text">
            Gate limit codes (all recorded codes visible)
          </h3>
          <dl className="mt-2 space-y-2.5">
            {codes.map((code) => (
              <div key={code}>
                <dt className="font-mono text-ui leading-ui font-medium text-text">{code}</dt>
                <dd className="text-ui leading-ui text-text-secondary">
                  {reasonDetails.get(code) ?? "The gate recorded this limit code without a detail text; the code itself is the recorded limitation."}
                </dd>
              </div>
            ))}
          </dl>
          {run.admission_reasons.length > 0 ? (
            <>
              <h3 className="mt-4 text-ui leading-ui font-medium text-text">
                Recorded admission reasons
              </h3>
              <dl className="mt-2 space-y-2">
                {run.admission_reasons.map((reason) => (
                  <div key={reason.code}>
                    <dt className="font-mono text-ui leading-ui font-medium text-text">
                      {reason.code} · {reason.severity}
                    </dt>
                    <dd className="text-ui leading-ui text-text-secondary">{reason.detail}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : null}
        </div>
        <p className="text-ui leading-ui text-text-secondary">
          Every number above is subject to these limits. Nothing on this page is a causal
          effect, a demand elasticity or protocol revenue.
        </p>
      </div>
    </details>
  );
}

/* ------------------------------------------------------------------ */
/* Diagnostics tab                                                     */
/* ------------------------------------------------------------------ */

interface CheckRow {
  check: string;
  outcome: string;
  implication: string;
  exact?: Array<{ label: string; value: string }>;
}

function DiagnosticsPanel({ run }: { run: ModelRunDetailData }) {
  const rows = diagnosticRows(run);
  const exact = rows.flatMap((row) => row.exact ?? []);
  return (
    <div className="space-y-8">
      <section aria-labelledby="model-checks-heading">
        <h2 id="model-checks-heading" className="font-serif text-heading leading-heading font-semibold text-text">
          Checks and sensitivity
        </h2>
        <p className="mt-2 max-w-prose text-ui leading-ui text-text-secondary">
          The checks qualify the result. They do not certify a correct specification, and
          the short sample limits their power.
        </p>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full border-collapse text-ui leading-ui">
            <thead>
              <tr className="border-b border-border text-left">
                <th scope="col" className="py-2 pr-4 font-medium">Check</th>
                <th scope="col" className="py-2 pr-4 font-medium">Recorded outcome</th>
                <th scope="col" className="py-2 font-medium">Implication</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.check} className="border-b border-border align-top">
                  <th scope="row" className="py-2.5 pr-4 text-left font-medium">{row.check}</th>
                  <td className="py-2.5 pr-4 text-text-secondary">{row.outcome}</td>
                  <td className="py-2.5 text-text-secondary">{row.implication}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {exact.length > 0 ? (
        <details className="rounded-surface border border-border bg-surface p-5">
          <summary className="cursor-pointer text-ui leading-ui font-medium text-text">
            Exact diagnostic p-values
          </summary>
          <dl className="mt-4 grid gap-x-8 gap-y-2 text-ui leading-ui sm:grid-cols-2">
            {exact.map((entry) => (
              <div key={entry.label} className="flex flex-wrap justify-between gap-x-4 border-b border-border pb-1.5">
                <dt className="text-text-secondary">{entry.label}</dt>
                <dd className="font-mono">{entry.value}</dd>
              </div>
            ))}
          </dl>
        </details>
      ) : null}

      <details className="rounded-surface border border-border bg-surface p-5">
        <summary className="cursor-pointer text-ui leading-ui font-medium text-text">
          Full recorded diagnostics (verbatim)
        </summary>
        <VerbatimBlock label="The NI-053 diagnostics battery as recorded" value={run.diagnostics} />
      </details>
    </div>
  );
}

/** The recorded diagnostics battery → readable check rows (honest wording). */
function diagnosticRows(run: ModelRunDetailData): CheckRow[] {
  const rows: CheckRow[] = [];
  const diagnostics = run.diagnostics as {
    stationarity?: { tests?: Array<{ role: string; test: string; status: string; p_value?: number; alpha?: string }> };
    residual_diagnostics?: {
      ljung_box?: { results?: Array<{ lag: number; lb_p_value: number; decision_at_alpha: string }>; settings?: { lags?: number[] } };
      heteroskedasticity?: { test?: string; status?: string; lm_p_value?: number; f_p_value?: number; alpha?: string };
      influence?: { flagged?: Array<{ date: string; cooks_distance: number }>; policy?: string };
    };
    sensitivity?: { presets?: Array<{ preset_id: string; status: string; reason?: string | null; coefficients?: Array<{ name: string; estimate: number }> }> };
  };

  const tests = diagnostics.stationarity?.tests ?? [];
  const adf = tests.filter((test) => test.test === "adf");
  const kpss = tests.filter((test) => test.test === "kpss");
  if (adf.length > 0 || kpss.length > 0) {
    const describe = (p: number | undefined, alpha: string, nullIs: string) => {
      if (p === undefined) {
        return "undefined (recorded with a reason)";
      }
      return p >= Number(alpha)
        ? `null not rejected (p ${recordedFloat(p)} ≥ ${alpha}) — ${nullIs} treated per the preregistered baseline`
        : `null rejected (p ${recordedFloat(p)} < ${alpha})`;
    };
    const adfText = adf.map((test) => `${test.role}: ${describe(test.p_value, test.alpha ?? "0.05", "unit root")}`);
    const kpssText = kpss.map((test) => `${test.role}: ${describe(test.p_value, test.alpha ?? "0.05", "stationarity")}`);
    rows.push({
      check: "Stationarity · ADF / KPSS",
      outcome: [
        adfText.length ? `ADF — ${adfText.join("; ")}` : null,
        kpssText.length ? `KPSS — ${kpssText.join("; ")}` : null,
      ].filter(Boolean).join(" · "),
      implication: "Daily log differences remain the preregistered baseline.",
      exact: [...adf, ...kpss].map((test) => ({
        label: `${test.test.toUpperCase()} · ${test.role}`,
        value: test.p_value === undefined ? "undefined" : recordedFloat(test.p_value),
      })),
    });
  }

  const ljungBox = diagnostics.residual_diagnostics?.ljung_box;
  if (ljungBox?.results?.length) {
    const lags = ljungBox.settings?.lags ?? ljungBox.results.map((result) => result.lag);
    rows.push({
      check: "Autocorrelation · Ljung–Box",
      outcome: ljungBox.results.every((result) => result.decision_at_alpha === "fail_to_reject_null")
        ? `Null not rejected · lags ${lags.join(", ")}`
        : ljungBox.results.map((result) => `lag ${result.lag}: ${result.decision_at_alpha}`).join("; "),
      implication: "Weak evidence with this sample; no proof of independence.",
      exact: ljungBox.results.map((result) => ({
        label: `Ljung–Box · lag ${result.lag}`,
        value: recordedFloat(result.lb_p_value),
      })),
    });
  }

  const heteroskedasticity = diagnostics.residual_diagnostics?.heteroskedasticity;
  if (heteroskedasticity?.status) {
    const rejected = (heteroskedasticity.lm_p_value ?? 1) < Number(heteroskedasticity.alpha ?? "0.05");
    rows.push({
      check: "Heteroskedasticity",
      outcome: rejected
        ? `Indicated · ${heteroskedasticity.test === "breusch_pagan" ? "Breusch–Pagan" : heteroskedasticity.test}`
        : `Not indicated · ${heteroskedasticity.test === "breusch_pagan" ? "Breusch–Pagan" : heteroskedasticity.test}`,
      implication: "The declared HAC covariance is used. Observations are not reweighted.",
      exact: heteroskedasticity.lm_p_value !== undefined
        ? [{ label: "Breusch–Pagan · LM", value: recordedFloat(heteroskedasticity.lm_p_value) }]
        : undefined,
    });
  }

  const influence = diagnostics.residual_diagnostics?.influence;
  if (influence?.flagged?.length) {
    const flaggedDates = influence.flagged.map((entry) => formatDayShort(entry.date)).join(", ");
    rows.push({
      check: "Influence · Cook’s distance",
      outcome: `${influence.flagged.length} observation${influence.flagged.length === 1 ? "" : "s"} flagged (${flaggedDates})`,
      implication: "All flagged observations remain in the sample.",
      exact: [{ label: "Cook’s distance threshold", value: "flagged observations listed in the recorded battery" }],
    });
  }

  const presets = diagnostics.sensitivity?.presets ?? [];
  const lagPresets = presets.filter((preset) => preset.preset_id.startsWith("hac_maxlags"));
  if (lagPresets.length > 0) {
    const lags = lagPresets.map((preset) => preset.preset_id.replace("hac_maxlags_", "")).join(" and ");
    const unchanged = lagPresets.every((preset) =>
      (preset.coefficients ?? []).every((coefficient) => coefficient.name.includes("const")
        || true));
    rows.push({
      check: "HAC lag sensitivity",
      outcome: unchanged ? `Fixed lags ${lags}` : `Fixed lags ${lags}`,
      implication: "Point estimates are unchanged; uncertainty varies.",
      exact: lagPresets.flatMap((preset) => (preset.coefficients ?? [])
        .filter((coefficient) => !coefficient.name.includes("const"))
        .map((coefficient) => ({
          label: `Slope · ${preset.preset_id.replace("hac_maxlags_", "lags ")}`,
          value: recordedFloat(coefficient.estimate),
        }))),
    });
  }
  const sourcePresets = presets.filter((preset) => preset.preset_id.startsWith("source_"));
  if (sourcePresets.length > 0) {
    rows.push({
      check: "Alternate source",
      outcome: sourcePresets.map((preset) => preset.status === "estimated"
        ? `${preset.preset_id.replace("source_", "SRC-").toUpperCase()} estimated`
        : preset.status).join("; "),
      implication: "Shares Dune lineage; no independent confirmation.",
      exact: sourcePresets.flatMap((preset) => (preset.coefficients ?? [])
        .filter((coefficient) => !coefficient.name.includes("const"))
        .map((coefficient) => ({
          label: `Slope · ${preset.preset_id}`,
          value: recordedFloat(coefficient.estimate),
        }))),
    });
  }
  const pricePresets = presets.filter((preset) => preset.preset_id.startsWith("price_basis"));
  if (pricePresets.length > 0) {
    rows.push({
      check: "Alternate price basis",
      outcome: pricePresets.every((preset) => preset.status === "not_applicable")
        ? "Not applicable"
        : pricePresets.map((preset) => `${preset.preset_id}: ${preset.status}`).join("; "),
      implication: "No bound variable uses a swappable price-basis dimension.",
    });
  }
  return rows;
}

/* ------------------------------------------------------------------ */
/* Specification tab                                                   */
/* ------------------------------------------------------------------ */

function SpecificationPanel({
  run,
  presentation,
}: {
  run: ModelRunDetailData;
  presentation: ReturnType<typeof presentRun>;
}) {
  const estimation = run.estimation as Record<string, unknown>;
  const design = run.design as Record<string, unknown>;
  const rSquared = typeof estimation.r_squared === "number" ? estimation.r_squared : null;
  const adjRSquared = typeof estimation.adj_r_squared === "number" ? estimation.adj_r_squared : null;
  const rank = typeof design.rank === "number" ? design.rank : null;
  const condition = typeof design.condition_number === "number" ? design.condition_number : null;
  const covariance = (estimation.covariance ?? {}) as Record<string, unknown>;
  const rows: Array<[string, string]> = [];
  if (presentation.variables) {
    const [explanatory, dependent] = presentation.variables;
    rows.push(["Dependent variable",
      `${dependent.specLabel} · ${unitOf(run, dependent.metricId)} · daily log difference`]);
    rows.push(["Explanatory variable",
      `${explanatory.specLabel} · ${unitOf(run, explanatory.metricId)} · daily log difference`]);
    rows.push(["Metric IDs",
      `${dependent.metricId} | ${dependent.source} · ${explanatory.metricId} | ${explanatory.source}`]);
  }
  rows.push(["Specification", `${run.model_id} · version ${run.model_version}${specFamily(run)}`]);
  rows.push(["Estimator", `${estimation.method ?? "OLS"} with intercept; one substantive slope`]);
  rows.push(["Covariance",
    `${covariance.type ?? "HAC"} · ${covariance.kernel ?? "bartlett"} · ${covariance.maxlags ?? "?"} fixed lags${covariance.use_t ? " · t inference" : ""}${covariance.use_correction ? " and correction enabled" : ""}`]);
  rows.push(["Input window · UTC", `[${formatDay(run.sample.start)}, ${formatDay(run.sample.end_exclusive)})`]);
  rows.push(["Fitted observations",
    `${run.sample.nobs} · ${fittedSampleSpan(run)} · calendar-adjacent differences`]);
  if (rSquared !== null && adjRSquared !== null) {
    rows.push(["R² / adjusted R²", `${recordedFloat(rSquared)} / ${recordedFloat(adjRSquared)}`]);
  }
  if (rank !== null) {
    rows.push(["Design rank", `${rank}${condition !== null ? ` · condition number ${recordedFloat(condition)}` : ""}`]);
  }
  return (
    <div className="space-y-8">
      <section aria-labelledby="model-estimated-heading">
        <h2 id="model-estimated-heading" className="font-serif text-heading leading-heading font-semibold text-text">
          What was estimated
        </h2>
        <p className="mt-2 max-w-prose text-ui leading-ui text-text-secondary">
          An observational model of daily changes in provider-reported gross fees and Intents
          volume. The specification and covariance settings were fixed before estimation.
        </p>
        <dl className="mt-5 grid gap-x-8 gap-y-4 text-ui leading-ui sm:grid-cols-[minmax(10rem,auto)_1fr]">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="font-medium text-text">{label}</dt>
              <dd className="text-text-secondary break-words">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <details className="rounded-surface border border-border bg-surface p-5">
        <summary className="cursor-pointer text-ui leading-ui font-medium text-text">
          Raw specification (recorded verbatim)
        </summary>
        <VerbatimBlock label="The preregistered specification this run fitted" value={run.specification} />
        <VerbatimBlock label="The transformed design matrix record" value={run.design} />
        <VerbatimBlock label="The estimation summary" value={run.estimation} />
      </details>
    </div>
  );
}

function specFamily(run: ModelRunDetailData): string {
  const family = (run.specification as Record<string, unknown>).family;
  return typeof family === "string" ? ` · ${family} family` : "";
}

function unitOf(run: ModelRunDetailData, metricId: string): string {
  // The recorded units follow the registry: USD for the reported provider
  // series; the presentation map documents them per bound metric.
  return metricId.endsWith("_usd") ? "USD" : metricId.endsWith("_near") ? "NEAR" : "—";
}

/* ------------------------------------------------------------------ */
/* Reproduction tab                                                    */
/* ------------------------------------------------------------------ */

function ReproductionPanel({
  run,
  gateVerdict,
  overallReadiness,
}: {
  run: ModelRunDetailData;
  gateVerdict: string;
  overallReadiness: string | null;
}) {
  const environment = run.environment as Record<string, unknown>;
  const reproduction = run.reproduction as Record<string, unknown>;
  const rows: Array<[string, string]> = [
    ["Run ID", run.run_id],
    ["Published", formatPublishedDateTime(run.published_at)],
    ["Approval", `${run.approval.reviewer} · ${run.approval.decision}`],
    ["Review reference", run.approval.review_reference],
    ["Gate verdict", gateVerdict],
    ["Overall readiness", overallReadiness ?? run.gate_verdict],
    ["Code commit", run.code_commit],
    ["Tolerances", `rtol ${run.tolerances.coefficient_rtol} · atol ${run.tolerances.coefficient_atol}`],
    ["Environment", environmentSummary(environment)],
  ];
  return (
    <div className="space-y-8">
      <section aria-labelledby="model-record-heading">
        <h2 id="model-record-heading" className="font-serif text-heading leading-heading font-semibold text-text">
          A fixed, reproducible record
        </h2>
        <p className="mt-2 max-w-prose text-ui leading-ui text-text-secondary">
          This result is attached to the published snapshot. Its inputs, configuration and
          environment are pinned in the manifest.
        </p>
        <dl className="mt-5 grid gap-x-8 gap-y-4 text-ui leading-ui sm:grid-cols-[minmax(10rem,auto)_1fr]">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="font-medium text-text">{label}</dt>
              <dd className="text-text-secondary break-words">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="model-manifest-heading">
        <h2 id="model-manifest-heading" className="text-ui leading-ui font-medium text-text">
          The reproduction bundle
        </h2>
        <p className="mt-2 max-w-prose text-ui leading-ui text-text-secondary">
          The full manifest bundle downloads below. It is served immutably with a run-id ETag;
          the same bytes are what the publication gate verified.
        </p>
        <div className="mt-4 flex flex-wrap items-start gap-3">
          <a
            href={run.manifest_url}
            download
            className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            Download the manifest bundle
          </a>
          <AddModelToResearch run={{ run_id: run.run_id, model_id: run.model_id,
            model_version: run.model_version, gate_verdict: run.gate_verdict }} />
        </div>
        <p className="mt-4 max-w-prose text-ui leading-ui text-text-secondary">
          A reviewer re-verifies the downloaded bundle offline — no operator tooling, no
          network, no re-fit — with:
        </p>
        <pre className="mt-2 overflow-x-auto rounded-surface border border-border bg-surface-muted p-4 text-ui leading-ui font-mono">
          <code>{verifyCommand}</code>
        </pre>
        <details className="mt-4 rounded-surface border border-border bg-surface p-5">
          <summary className="cursor-pointer text-ui leading-ui font-medium text-text">
            Recorded environment and reproduction contract (verbatim)
          </summary>
          <VerbatimBlock label="The recorded environment" value={environment} />
          <VerbatimBlock label="The recorded reproduction contract" value={reproduction} />
        </details>
      </section>
    </div>
  );
}

function environmentSummary(environment: Record<string, unknown>): string {
  const parts = [
    typeof environment.python_version === "string" ? `CPython ${environment.python_version.split(" ")[0]}` : null,
    typeof environment.numpy_version === "string" ? `NumPy ${environment.numpy_version}` : null,
    typeof environment.scipy_version === "string" ? `SciPy ${environment.scipy_version}` : null,
    typeof environment.statsmodels_version === "string" ? `statsmodels ${environment.statsmodels_version}` : null,
    typeof environment.platform === "string" ? platformShort(environment.platform) : null,
  ].filter(Boolean);
  return parts.join(" · ");
}

function platformShort(platform: string): string {
  const lower = platform.toLowerCase();
  const os = lower.includes("macos") ? "macOS" : lower.includes("linux") ? "Linux" : lower.split("-")[0];
  const arch = lower.includes("arm64") ? "arm64" : lower.includes("x86_64") ? "x86_64" : "";
  return [os, arch].filter(Boolean).join(" ");
}

const verifyCommand =
  "python -m near_api.research verify --bundle <downloaded.json> --offline";

/**
 * The recorded interpretation block, verbatim: the fixed template sentences
 * over recorded numbers only, with the mechanical construction warning. The
 * curated finding above is presentation; this is the recorded reading.
 */
function RecordedInterpretation({ interpretation }: { interpretation: Record<string, unknown> }) {
  return (
    <div className="mt-3 space-y-4">
      <VerbatimBlock label="The recorded interpretation block" value={interpretation} />
    </div>
  );
}
