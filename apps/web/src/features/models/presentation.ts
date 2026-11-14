/**
 * Readable presentation layer for published model runs (NI-097).
 *
 * The recorded run stays the single source of truth: every number, date and
 * limitation on the page comes from the API payload. This module only maps a
 * KNOWN specification id to its approved readable presentation (the owner
 * mockups) and derives everything else strictly from the recorded fields.
 *
 * Honesty rules enforced here:
 * - the curated finding is sign-aware: a positive slope renders the positive
 *   finding, anything else renders the neutral variant — a positive finding
 *   is never spread to another model or to a negative coefficient;
 * - unknown specifications get an identity-preserving fallback built from
 *   their recorded fields (spec id, family, the recorded interpretation
 *   sentences) — no invented names or claims;
 * - `rounded` marks every display-rounded value; the recorded floats stay
 *   available verbatim through the Exact coefficients disclosure.
 */

import type { ModelRunDetail, ModelRunSummary } from "./models-schema";
import { recordedFloat } from "./recorded";

/** One presented variable block (the two "what is compared" cards). */
export interface PresentedVariable {
  role: "dependent" | "explanatory";
  heading: string;
  /** The variable name the specification grid uses (mockup wording). */
  specLabel: string;
  description: string;
  transform: string;
  metricId: string;
  source: string;
}

/** The readable presentation of one published run. */
export interface ModelPresentation {
  /** Catalog card label, e.g. "Intents · Fee activity". */
  categoryLabel: string;
  /** Catalog card title, e.g. "Gross fees and Intents volume". */
  cardTitle: string;
  /** The research question the model answers (catalog + detail). */
  question: string;
  /** The detail-page headline (the question, phrased for the result). */
  headline: string;
  /** Detail subtitle lines under the headline. */
  subtitle: string[];
  /** Compact honest limit shown before any coefficient. */
  scopeLimit: string;
  /** Result-tab finding headline + body, sign-aware. */
  finding: { headline: string; body: string };
  /** The two compared variables. */
  variables: [PresentedVariable, PresentedVariable] | null;
  /** "What this supports" / "What remains unanswered". */
  supports: string;
  unanswered: string;
  /** Whether the curated presentation comes from the known-spec map. */
  curated: boolean;
}

interface KnownSpecPresentation {
  categoryLabel: string;
  cardTitle: string;
  question: string;
  headline: string;
  subtitle: string[];
  scopeLimit: string;
  variables: [PresentedVariable, PresentedVariable];
  supports: string;
  unanswered: string;
  findingPositive: { headline: string; body: string };
  findingNegative: { headline: string; body: string };
  findingNeutral: { headline: string; body: string };
}

/**
 * The approved presentation for the published `gross_fee_activity_v1`
 * specification. Every finding variant is phrased for its own slope sign —
 * the recorded coefficient picks the variant at render time.
 */
const KNOWN_SPECS: Record<string, KnownSpecPresentation> = {
  gross_fee_activity_v1: {
    categoryLabel: "Intents · Fee activity",
    cardTitle: "Gross fees and Intents volume",
    question:
      "How do daily changes in provider-reported gross fees relate to changes in reported trading volume?",
    headline: "Do gross fees move with trading volume?",
    subtitle: [
      "A model of daily changes in Intents activity.",
      "Provider-reported gross fees, measured against reported trading volume.",
    ],
    scopeLimit:
      "Gross fees are calculated from volume through a fee rate. Their relationship is therefore partly built into the data. Both series share Dune lineage. This short sample cannot establish causality, demand elasticity, sustainable revenue, protocol revenue or token value.",
    variables: [
      {
        role: "explanatory",
        heading: "Trading volume",
        specLabel: "Intents volume",
        description: "Reported Intents volume in USD.",
        transform: "The model uses its daily log change.",
        metricId: "provider_intents_volume_usd",
        source: "SRC-LLAMA",
      },
      {
        role: "dependent",
        heading: "Provider gross fees",
        specLabel: "Provider gross fees",
        description: "Reported fees in USD, before any claim about protocol revenue.",
        transform: "The model uses their daily log change.",
        metricId: "provider_gross_fees_usd",
        source: "SRC-LLAMA",
      },
    ],
    supports:
      "A short-run association between the two reported series over the fitted observations.",
    unanswered:
      "Protocol revenue, sustainable fee income and value captured by the NEAR token.",
    findingPositive: {
      headline: "Fees and volume move together in this sample.",
      body:
        "The model estimates a positive relationship between their daily log changes. Because fees are constructed from volume, this mostly describes the fee mechanism. It does not answer whether Intents creates sustainable value for NEAR.",
    },
    findingNegative: {
      headline: "Fees and volume move in opposite directions in this sample.",
      body:
        "The model estimates a negative relationship between their daily log changes. Because fees are constructed from volume, this mostly describes the fee mechanism. It does not answer whether Intents creates sustainable value for NEAR.",
    },
    findingNeutral: {
      headline: "The sample does not establish a directional relationship.",
      body:
        "The model estimates the relationship between the two daily log changes, and the interval includes no effect. Because fees are constructed from volume, this mostly describes the fee mechanism. It does not answer whether Intents creates sustainable value for NEAR.",
    },
  },
};

/** The substantive (non-intercept) coefficient of a run, if identifiable. */
export function substantiveSlope(run: ModelRunDetail) {
  return run.coefficients.find((coefficient) => coefficient.name !== "const"
    && !coefficient.name.startsWith("Intercept"))
    ?? run.coefficients.find((coefficient) => !coefficient.name.toLowerCase().includes("const")
      && !coefficient.name.toLowerCase().includes("intercept"))
    ?? null;
}

/** Sign-aware finding selection from the recorded slope and its interval. */
function pickFinding(
  known: KnownSpecPresentation,
  run: ModelRunDetail,
): { headline: string; body: string } {
  const slope = substantiveSlope(run);
  if (slope === null) {
    return known.findingNeutral;
  }
  if (slope.ci95_low > 0) {
    return known.findingPositive;
  }
  if (slope.ci95_high < 0) {
    return known.findingNegative;
  }
  return known.findingNeutral;
}

/** A readable fallback that preserves the model's recorded identity. */
function fallbackPresentation(run: ModelRunDetail): ModelPresentation {
  const knownShape = KNOWN_SPECS[run.model_id];
  if (knownShape) {
    return presentKnown(knownShape, run);
  }
  const slope = substantiveSlope(run);
  const direction = slope === null
    ? ""
    : slope.ci95_low > 0
      ? "positive"
      : slope.ci95_high < 0 ? "negative" : "statistically unresolved";
  return {
    categoryLabel: `${prettifySpecId(run.model_id)} · v${run.model_version}`,
    cardTitle: prettifySpecId(run.model_id),
    question: `What does the recorded ${prettifySpecId(run.model_id)} specification estimate?`,
    headline: `${prettifySpecId(run.model_id)} — published result`,
    subtitle: [
      "A published model run exactly as the publication gate recorded it.",
    ],
    scopeLimit:
      "This is a recorded statistical association over the fitted sample. It is not a causal effect, not protocol revenue and not a token valuation; read the recorded limitations before any coefficient.",
    finding: {
      headline: direction
        ? `The recorded slope is ${direction}.`
        : "The published result is presented exactly as recorded.",
      body: slope
        ? `The recorded estimate is ${recordedFloat(slope.estimate)} with a 95% interval of ${recordedFloat(slope.ci95_low)} to ${recordedFloat(slope.ci95_high)}. Read the recorded limitations before using this result.`
        : "The recorded coefficients are listed in the Exact coefficients disclosure.",
    },
    variables: null,
    // (the fallback has no curated variable blocks; the specification grid
    // falls back to the recorded metric ids)
    supports:
      "The recorded association over the fitted sample, exactly as the publication gate recorded it.",
    unanswered:
      "Causal effects, protocol revenue and token valuation remain outside this result.",
    curated: false,
  };
}

function presentKnown(known: KnownSpecPresentation, run: ModelRunDetail): ModelPresentation {
  return {
    categoryLabel: known.categoryLabel,
    cardTitle: known.cardTitle,
    question: known.question,
    headline: known.headline,
    subtitle: known.subtitle,
    scopeLimit: known.scopeLimit,
    finding: pickFinding(known, run),
    variables: known.variables,
    supports: known.supports,
    unanswered: known.unanswered,
    curated: true,
  };
}

/** The presentation of one run: curated for known specs, fallback otherwise. */
export function presentRun(run: ModelRunDetail): ModelPresentation {
  return KNOWN_SPECS[run.model_id]
    ? presentKnown(KNOWN_SPECS[run.model_id], run)
    : fallbackPresentation(run);
}

/** Catalog-card presentation from the run summary alone. */
export function presentSummary(item: ModelRunSummary): {
  categoryLabel: string;
  cardTitle: string;
  question: string;
  statusLabel: string;
  methodLabel: string | null;
} {
  const known = KNOWN_SPECS[item.model_id];
  const statusLabel = item.gate_verdict === "READY_WITH_LIMITS"
    ? "Published with limits"
    : "Published";
  if (known) {
    return {
      categoryLabel: known.categoryLabel,
      cardTitle: known.cardTitle,
      question: known.question,
      statusLabel,
      methodLabel: "OLS · daily log changes",
    };
  }
  return {
    categoryLabel: `${prettifySpecId(item.model_id)} · v${item.model_version}`,
    cardTitle: prettifySpecId(item.model_id),
    question: `What does the recorded ${prettifySpecId(item.model_id)} specification estimate?`,
    statusLabel,
    // The estimator is a detail-page recorded field; the fallback card does
    // not invent it from the summary alone.
    methodLabel: null,
  };
}

/** "gross_fee_activity_v1" → "Gross fee activity" (identity-preserving). */
function prettifySpecId(specId: string): string {
  const base = specId.replace(/_v[0-9]+$/, "").replace(/_/g, " ").trim();
  return base.charAt(0).toUpperCase() + base.slice(1);
}

/** Display rounding: 4 significant decimals for the summary surface. */
export function rounded(value: number): string {
  const fixed = value.toFixed(4);
  return fixed === "-0.0000" ? "0.0000" : fixed;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-08-06" → "6 Aug 2026" (UTC, no locale re-formatting). */
export function formatDay(iso: string): string {
  const [year, month, day] = iso.split("-").map((part) => Number(part));
  if (!year || !month || !day) {
    return iso;
  }
  return `${day} ${MONTHS[month - 1] ?? month} ${year}`;
}

/** "2026-08-06" → "6 Aug" (same year, compact). */
export function formatDayShort(iso: string): string {
  const [, month, day] = iso.split("-").map((part) => Number(part));
  if (!month || !day) {
    return iso;
  }
  return `${day} ${MONTHS[month - 1] ?? month}`;
}

/** An ISO timestamp → "14 Nov 2026" (UTC). */
export function formatPublishedDay(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}

/** An ISO timestamp → "14 Nov 2026, 13:04:57 UTC". */
export function formatPublishedDateTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${formatPublishedDay(timestamp)}, ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())} UTC`;
}

/** The fitted-sample span "7 Aug – 3 Nov 2026" from the recorded sample. */
export function fittedSampleSpan(run: ModelRunDetail | ModelRunSummary): string {
  const start = formatDayShort(run.sample.start);
  const end = formatDay(run.sample.end_exclusive);
  // The fitted sample ends one calendar day before the exclusive window end.
  const endDate = new Date(`${run.sample.end_exclusive}T00:00:00Z`);
  endDate.setUTCDate(endDate.getUTCDate() - 1);
  const fittedEnd = `${endDate.getUTCDate()} ${MONTHS[endDate.getUTCMonth()]} ${endDate.getUTCFullYear()}`;
  return start === end ? fittedEnd : `${start} – ${fittedEnd}`;
}

/** "6 Aug – 3 Nov 2026" for the input window column. */
export function inputWindowSpan(run: ModelRunDetail | ModelRunSummary): string {
  return `${formatDayShort(run.sample.start)} – ${formatDay(run.sample.end_exclusive)}`;
}
