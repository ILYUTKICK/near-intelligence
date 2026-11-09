import type { components } from "@near-intelligence/shared-types";

export type HypothesisAssessment = components["schemas"]["HypothesisInput"]["assessment"];

export const assessmentLabels: Record<HypothesisAssessment, string> = {
  untested: "Untested",
  supported: "Supported",
  mixed: "Mixed",
  weakened: "Weakened",
  insufficient_data: "Insufficient data",
};

export function assessmentLabel(value: string | null): string {
  return value && Object.hasOwn(assessmentLabels, value) ? assessmentLabels[value as HypothesisAssessment] : "—";
}
