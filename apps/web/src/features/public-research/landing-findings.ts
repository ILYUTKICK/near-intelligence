/**
 * NI-012 landing for/against findings — editorial selection over the NI-014
 * claim registry (consumption only; the registry entries themselves are never
 * modified or re-numbered here).
 *
 * The landing shows two supporting and two contrary recorded claims so the
 * introduction carries evidence in both directions. Every rendered claim is
 * the full ClaimCard from the thesis feature (exact quantities, scopes,
 * sources, definition/dataset references and cautions), plus a link into the
 * thesis section that owns the claim. English only (OQ-06); no marketing
 * rhetoric — the claims speak through their recorded values.
 */

import { claimRegistry, type ThesisClaim } from "./content";

export interface LandingFindingSide {
  readonly id: string;
  readonly heading: string;
  readonly lead: string;
  readonly claimIds: readonly string[];
  /** Thesis section that owns these claims (stable thesis anchor). */
  readonly thesisAnchor: string;
  readonly anchorLabel: string;
}

export const landingFindings = {
  id: "findings",
  heading: "What the recorded evidence shows",
  intro:
    "Two recorded findings support a regularly operating conversion and payout channel inside the observed cohort, and two recorded findings contradict a simple accelerating-demand narrative. Both directions are shown; the full thesis carries all nine registered claims (CL-001 through CL-009) with their complete quantity tables.",
  recordedBasis:
    "Recorded evidence basis: the saved 90-day cohort 2026-08-06 through 2026-11-04 (UTC, end exclusive), verified on 4 November 2026. The quantities below are copied from the claim registry; unavailable sources render explicit states instead of values.",
  forSide: {
    id: "findings-for",
    heading: "Supporting observations",
    lead: "The conversion and payout channel operated across the whole recorded cohort:",
    claimIds: ["CL-001", "CL-003"],
    thesisAnchor: "/research#revenue-capture",
    anchorLabel: "Read these claims in the full thesis (revenue capture section)",
  } satisfies LandingFindingSide,
  againstSide: {
    id: "findings-against",
    heading: "Contrary observations",
    lead: "The same recorded evidence contradicts a simple accelerating-demand narrative:",
    claimIds: ["CL-002", "CL-007"],
    thesisAnchor: "/research#token-economics",
    anchorLabel: "Read these claims in the full thesis (token economics section)",
    note: "These are different flows measured on the same cohort: acquired NEAR quantities declined window over window while total supply grew, and observed purchases stayed a small fraction of that growth. Neither finding by itself establishes or rejects a valuation.",
  } satisfies LandingFindingSide & { readonly note: string },
} as const;

const claimById: Map<string, ThesisClaim> = new Map(
  claimRegistry.map((claim) => [claim.id, claim]),
);

/** Resolves a landing claim id against the NI-014 registry; unknown ids fail loudly. */
export function getLandingClaim(id: string): ThesisClaim {
  const claim = claimById.get(id);
  if (!claim) {
    throw new Error(`Landing findings reference an unknown claim id: ${id}`);
  }
  return claim;
}
