/**
 * Typed mirror of the canonical DataQuality contract from
 * docs/API_SPECIFICATION.md (NI-009 interim state).
 *
 * This file is deliberately a narrow copy of that contract so the UI can
 * render quality before NI-004 generates the shared client from OpenAPI.
 * When the generated types land (packages/shared-types), this module must be
 * replaced by them — do not extend it with fields the API does not define.
 */
export type QualityStatus = "ok" | "partial" | "missing" | "stale" | "unavailable" | "revised";

export type BoundKind = "exact" | "estimate" | "lower" | "upper" | null;

/** Exact shape of DataQuality in API_SPECIFICATION.md. */
export interface DataQuality {
  status: QualityStatus;
  bound_kind: BoundKind;
  reasons: string[];
  coverage: { observed: number; expected: number };
  freshness_target_seconds: number | null;
}

/** Presentation metadata retained by partial/stale/bound states. */
export interface DataMetadata {
  /** Measurement units, e.g. "NEAR" or "NEAR / day" — never dropped. */
  units?: string;
  /** Period the data covers, e.g. "2026-08-06 … 2026-11-03 UTC". */
  period?: string;
  /** Last observation/retrieval timestamp shown to the user. */
  asOf?: string;
  /** Documented limitation that survives every state. */
  limitation?: string;
}

export interface QualityPresentation {
  /** Visible text label — status is never conveyed by color alone. */
  label: string;
  /** Semantic tone mapped to design tokens. */
  tone: "neutral" | "positive" | "warning" | "critical" | "info";
  /** Short explanation used in state panels and aria descriptions. */
  description: string;
}

export const qualityPresentation: Record<QualityStatus, QualityPresentation> = {
  ok: {
    label: "Complete",
    tone: "positive",
    description: "All expected observations are present and verified.",
  },
  partial: {
    label: "Partial",
    tone: "warning",
    description: "Some observations are missing; shown values cover only part of the period.",
  },
  missing: {
    label: "No data",
    tone: "neutral",
    description: "Nothing was observed for this selection. This is not zero.",
  },
  stale: {
    label: "Stale",
    tone: "warning",
    description: "The latest available data is older than its freshness target.",
  },
  unavailable: {
    label: "Unavailable",
    tone: "critical",
    description: "The source cannot provide this data right now. This is not zero.",
  },
  revised: {
    label: "Revised",
    tone: "info",
    description: "The source revised previously published values.",
  },
};

const boundLabels: Record<Exclude<BoundKind, null>, string> = {
  exact: "exact",
  estimate: "estimate",
  lower: "lower bound",
  upper: "upper bound",
};

export function boundLabel(kind: BoundKind): string | null {
  return kind ? boundLabels[kind] : null;
}
