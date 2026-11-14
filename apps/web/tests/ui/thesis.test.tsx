/**
 * NI-014 public thesis: fifteen sections on stable anchors, the claim registry
 * CL-001–CL-009 with source/version/scope on every quantity, three-window
 * quantities and bounds copied exactly from the recorded documents, honest
 * statuses and pending markers, public-link allowlists and no private editor
 * metadata.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// The NI-045 duplication CTA on the research page is a client component that
// reads the router for the sign-in continuation; these structural tests stub
// the router (they render the page outside the app-router context). The CTA
// behavior itself is covered by tests/ui/duplicate-release.test.tsx.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import ResearchPage from "@/app/(public)/research/page";
import {
  claimRegistry,
  hypothesisIds,
  internalHrefAllowlist,
  thesis,
  thesisToc,
  verifiedExternalLinks,
  type ClaimQuantity,
} from "@/features/public-research/content";

const repoRoot = join(process.cwd(), "..", "..");

function readRepo(relative: string): string {
  return readFileSync(join(repoRoot, relative), "utf8");
}

/** Recorded documents every displayed value must trace back to. */
const recordedDocuments = [
  "docs/INVESTMENT_THESIS.md",
  "research/near-longitudinal/FINDINGS.md",
  "research/near-dollar/FINDINGS.md",
  "research/near-provenance/FINDINGS.md",
  "research/near-supply/FINDINGS.md",
  "research/near-treasury/FINDINGS.md",
];

/**
 * Normalization for the independent claim-value audit: the English thesis and
 * the (Russian) research findings write the same numbers with different
 * thousands/decimal separators, so compare whitespace-stripped digits with
 * either separator convention.
 */
function normalizeDocument(text: string): string {
  return text.replace(/[\s\u00A0\u202F]/g, "");
}

function valueCandidates(value: string): string[] {
  const base = value.replace(/[\s\u00A0\u202F]/g, "");
  const candidates = new Set<string>([base, base.replace(/,/g, "")]);
  if (base.includes(".")) {
    candidates.add(base.replace(/,/g, "").replace(/\./g, ","));
  }
  if (base.includes(",")) {
    candidates.add(base.replace(/,/g, "."));
  }
  return [...candidates];
}

function allQuantities(): { claimId: string; quantity: ClaimQuantity }[] {
  return claimRegistry.flatMap((claim) =>
    claim.quantities.map((quantity) => ({ claimId: claim.id, quantity })),
  );
}

function renderedPage() {
  return render(<ResearchPage />);
}

describe("Thesis structure and anchors", () => {
  it("carries all fifteen section anchors as real sections", async () => {
    const { container } = renderedPage();
    expect(thesisToc).toHaveLength(15);
    for (const entry of thesisToc) {
      const element = document.getElementById(entry.id);
      expect(element, `missing #${entry.id}`).not.toBeNull();
      expect(element!.tagName).toBe("SECTION");
      expect(within(element as HTMLElement).getByRole("heading", { level: 2, name: entry.title })).toBeInTheDocument();
    }
    // The stable hypothesis and mechanism anchors from the IA and NI-011 shell.
    for (const anchor of [...hypothesisIds, "mechanism"]) {
      expect(document.getElementById(anchor), `missing #${anchor}`).not.toBeNull();
    }
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("renders a complete table of contents matching the sections", () => {
    renderedPage();
    const toc = screen.getByRole("navigation", { name: "Thesis sections", hidden: true });
    const links = within(toc).getAllByRole("link", { hidden: true });
    expect(links).toHaveLength(15);
    links.forEach((link, index) => {
      expect(link.getAttribute("href")).toBe(`#${thesisToc[index].id}`);
      expect(link.textContent).toBe(thesisToc[index].title);
    });
  });
});

describe("Claim registry structure (source/version/scope)", () => {
  it("registers exactly CL-001 through CL-009 in order", () => {
    expect(claimRegistry.map((claim) => claim.id)).toEqual([
      "CL-001",
      "CL-002",
      "CL-003",
      "CL-004",
      "CL-005",
      "CL-006",
      "CL-007",
      "CL-008",
      "CL-009",
    ]);
  });

  it("gives every claim an assessment, observation and dataset-version reference", () => {
    for (const claim of claimRegistry) {
      expect(claim.assessment.length).toBeGreaterThan(0);
      expect(claim.observation.length).toBeGreaterThan(0);
      expect(claim.datasetVersionReference).toMatch(/no public dataset catalog/);
      expect(claim.evidence.length).toBeGreaterThan(0);
    }
  });

  it("wraps every numeric quantity with unit, scope, source and an allowed sourceHref", () => {
    const allowedInternal = new Set<string>(internalHrefAllowlist);
    const allowedExternal = new Set<string>(verifiedExternalLinks);
    for (const { claimId, quantity } of allQuantities()) {
      expect(quantity.value, `${claimId} value`).toMatch(/^\d[\d.,]*$/);
      expect(quantity.unit, `${claimId} unit`).not.toHaveLength(0);
      expect(quantity.scope, `${claimId} scope`).not.toHaveLength(0);
      expect(quantity.source, `${claimId} source`).not.toHaveLength(0);
      expect(
        allowedInternal.has(quantity.sourceHref) || allowedExternal.has(quantity.sourceHref),
        `${claimId} sourceHref ${quantity.sourceHref}`,
      ).toBe(true);
    }
  });

  it("attaches registered definition versions or states the honest fallback", () => {
    for (const claim of claimRegistry) {
      if (claim.definitionVersions.length > 0) {
        for (const version of claim.definitionVersions) {
          expect(version).toMatch(/ v1 \(availability [ABPG]/);
        }
      } else {
        expect(claim.id).toBe("CL-005");
      }
    }
    // The rendered fallback text for the claim without registered metrics.
    renderedPage();
    expect(
      screen.getByText(/none — this claim's values come from recorded analysis artifacts/),
    ).toBeInTheDocument();
  });
});

describe("Independent claim-value audit against recorded documents", () => {
  const documents = recordedDocuments.map((path) => ({ path, text: normalizeDocument(readRepo(path)) }));

  it("traces every displayed quantity value to a recorded document", () => {
    for (const { claimId, quantity } of allQuantities()) {
      const candidates = valueCandidates(quantity.value);
      const matches = documents.filter((document) =>
        candidates.some((candidate) => document.text.includes(candidate)),
      );
      expect(matches, `${claimId}: value ${quantity.value} must appear in a recorded document`).not.toHaveLength(0);
    }
  });

  it("keeps the source strings pointing at the recorded documents", () => {
    for (const { quantity } of allQuantities()) {
      expect(
        recordedDocuments.some((path) => quantity.source.includes(path.split("/").pop() as string)),
        `source ${quantity.source}`,
      ).toBe(true);
    }
  });

  it("renders the exact recorded values, including the long exact amounts", () => {
    renderedPage();
    const text = document.body.textContent as string;
    expect(text).toContain("524,480.127692882832410490617319");
    expect(text).toContain("1,405,659.135989071036891726256814");
    expect(text).toContain("7,936,181.547057263680300503519861");
    expect(text).toContain("244,845.70");
    expect(text).toContain("547,026");
  });
});

describe("Three-window quantities and bounds", () => {
  it("shows the CL-002 window decline in order with its recorded decrease", () => {
    const claim = claimRegistry.find((entry) => entry.id === "CL-002");
    expect(claim).toBeDefined();
    const windows = claim!.quantities.slice(0, 3).map((quantity) => quantity.value);
    expect(windows).toEqual(["244,845.70", "165,809.44", "113,825.00"]);
    const change = claim!.quantities[3];
    expect(change.value).toBe("31.35");
    expect(change.direction).toBe("decrease");
    expect(change.scope).toMatch(/Third window relative to the second/);
  });

  it("shows the CL-004 USD windows with both price-mark alternatives", () => {
    const claim = claimRegistry.find((entry) => entry.id === "CL-004");
    expect(claim).toBeDefined();
    const usdWindows = claim!.quantities.slice(0, 3).map((quantity) => quantity.value);
    expect(usdWindows).toEqual(["437,374", "557,914", "547,026"]);
    const startOfDay = claim!.quantities.find((quantity) => quantity.value === "1.95");
    const endOfDay = claim!.quantities.find((quantity) => quantity.value === "5.45");
    expect(startOfDay!.direction).toBe("decrease");
    expect(startOfDay!.basis).toMatch(/start-of-day/);
    expect(endOfDay!.direction).toBe("decrease");
    expect(endOfDay!.basis).toMatch(/end-of-day/);
  });

  it("renders CL-008 bounds as bounds, never as exact totals", () => {
    const claim = claimRegistry.find((entry) => entry.id === "CL-008");
    expect(claim).toBeDefined();
    expect(claim!.quantities[0].bound).toBe("lower");
    expect(claim!.quantities[1].bound).toBe("lower");
    expect(claim!.quantities[2].bound).toBeUndefined();
    expect(claim!.quantities[3].bound).toBe("upper");
    renderedPage();
    expect(screen.getAllByText("Lower bound (at least)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Upper bound (at most)").length).toBeGreaterThan(0);
    expect(screen.getByText(/not exact gross totals/i)).toBeInTheDocument();
  });
});

describe("Honest statuses and pending markers", () => {
  it("publishes the recorded H1–H4 assessments", () => {
    renderedPage();
    const statuses = thesis.question.hypotheses.map((hypothesis) => hypothesis.status);
    expect(statuses).toEqual([
      "Unresolved",
      "Partial evidence",
      "Not supported on current evidence",
      "Unresolved",
    ]);
    expect(screen.getAllByText("What would weaken it.")).toHaveLength(4);
    for (const code of ["H1", "H2", "H3", "H4"]) {
      expect(screen.getAllByText(code).length).toBeGreaterThan(0);
    }
  });

  it("keeps the model section on the honest NI-070 release status", () => {
    renderedPage();
    // The release status block: implemented + synthetic-verified estimator,
    // real-archive fit pending operator execution, no fitted values anywhere.
    const status = screen.getByText(/Release status \(original research release/);
    expect(status.textContent).toMatch(/implemented and reviewed/);
    expect(status.textContent).toMatch(/synthetic known-behavior fixtures only/);
    expect(status.textContent).toMatch(/real-archive fit run is pending operator execution/);
    expect(status.textContent).toMatch(/No fitted model, coefficient, standard error, confidence interval or causal conclusion/);
    expect(status.textContent).toMatch(/public model catalog stays empty/);
    // The preregistered estimator description carries the prohibited labels,
    // never an interpretation.
    expect(document.body.textContent).toMatch(/Newey–West HAC covariance/);
    expect(document.body.textContent).toMatch(/prohibited labels protocol_revenue/);
    expect(document.body.textContent).not.toMatch(/coefficient of|β\s*=/);
    // The insufficient-data assessment cases are visible, not hidden.
    expect(document.body.textContent).toMatch(/PROXY_ONLY_READY_WITH_LIMITS/);
    expect(document.body.textContent).toMatch(/NOT_READY/);
    // The model catalog link is honest about emptiness and targets /models.
    const modelsLink = screen.getByRole("link", {
      name: "Published model runs (empty until a reviewed run is published)",
    });
    expect(modelsLink.getAttribute("href")).toBe("/models");
  });

  it("marks the recorded evidence as historical and never live", () => {
    renderedPage();
    const text = document.body.textContent as string;
    expect(text).toContain("2026-08-06");
    expect(text).toContain("2026-11-04");
    expect(text).toMatch(/No live values are published on this page/);
    expect(text).toMatch(/never shown as zero/);
    expect(text).toMatch(/a fresh retrieval does not make an old observation fresh/);
  });

  it("includes the contrary quantity, supply and price findings", () => {
    renderedPage();
    expect(screen.getByText("Fewer NEAR in each window")).toBeInTheDocument();
    expect(screen.getByText("Purchases and supply growth")).toBeInTheDocument();
    expect(screen.getByText("What the incomplete audit establishes")).toBeInTheDocument();
    expect(screen.getByText("A steadier dollar value")).toBeInTheDocument();
    // The mechanical construction is disclosed in several sections (revenue
    // generation, econometrics, alternative explanations).
    expect(screen.getAllByText(/mechanical fee–volume construction/).length).toBeGreaterThan(0);
    expect(screen.getByText(/concentration of collectors is not concentration of customers/)).toBeInTheDocument();
  });
});

describe("NI-070 release facts vs preregistered configs", () => {
  /** Tracked preregistered estimator settings (NI-052). */
  const fitConfig = JSON.parse(readRepo("research/models/fit_configs/gross_fee_activity_v1_fit.json")) as {
    covariance: { kernel: string; maxlags: number; maxlags_rule: string; use_correction: boolean; use_t: boolean };
    reproduction: { coefficient_rtol: string; coefficient_atol: string };
  };
  /** Tracked preregistered specification (NI-051): the admitted proxy design. */
  const specConfig = JSON.parse(readRepo("research/models/configs/gross_fee_activity_v1.json")) as {
    transformations: { baseline: string; difference_adjacency: string; strictly_positive_required: boolean };
  };

  it("describes the estimator exactly as the tracked configs declare it", () => {
    // The tracked config is the source of truth for every estimator fact.
    expect(fitConfig.covariance.kernel).toBe("bartlett");
    expect(fitConfig.covariance.maxlags_rule).toBe("fixed");
    expect(fitConfig.covariance.use_correction).toBe(true);
    expect(fitConfig.covariance.use_t).toBe(true);
    expect(specConfig.transformations.baseline).toBe("difference_log");
    expect(specConfig.transformations.difference_adjacency).toBe("calendar_adjacent_only");
    expect(specConfig.transformations.strictly_positive_required).toBe(true);

    renderedPage();
    const text = document.body.textContent as string;
    expect(text).toMatch(/Newey–West HAC covariance/);
    expect(text).toMatch(/Bartlett kernel/);
    expect(text).toMatch(/fixed lag count from the config — never data-selected/);
    expect(text).toMatch(/Δlog fee-on-volume association/);
    // No fitted value can exist: no coefficient notation, no interval, no
    // p-value is rendered anywhere on the thesis page.
    expect(text).not.toMatch(/β\s*=|p\s*[=<]\s*0\.|\b95% CI\b/);
  });

  it("names the release documents as checkout paths, never as downloads", () => {
    renderedPage();
    const text = document.body.textContent as string;
    expect(text).toMatch(/research\/reports\/ — the release report and its content\/evidence manifest/);
    expect(text).toMatch(/checkout paths, never as downloads/);
    for (const anchor of Array.from(document.querySelectorAll("a"))) {
      expect(anchor.getAttribute("download")).toBeNull();
    }
  });
});

describe("Public projection allowlists", () => {
  it("renders only allowlisted internal routes and verified external links", () => {
    const { container } = renderedPage();
    const allowed = new Set<string>([
      ...internalHrefAllowlist,
      ...verifiedExternalLinks,
      ...thesisToc.map((entry) => `#${entry.id}`),
      ...hypothesisIds.map((id) => `#${id}`),
      "#purchase-windows",
      "#hypothesis-assessment",
      "#interactive-history",
      "#thesis-usd-windows",
      ...claimRegistry.map((claim) => `#${claim.id}-heading`),
    ]);
    const hrefs = Array.from(container.querySelectorAll("a")).map((anchor) => anchor.getAttribute("href"));
    expect(hrefs.length).toBeGreaterThan(0);
    for (const href of hrefs) {
      expect(allowed.has(href as string), `unexpected public link ${href}`).toBe(true);
      if (href?.startsWith("#")) expect(document.getElementById(href.slice(1))).not.toBeNull();
    }
    // Unimplemented routes are never advertised. /models is the implemented
    // model catalog (NI-054) and is allowlisted; /data, /charts and /workspace
    // stay unlinked from the thesis page.
    for (const href of hrefs) {
      expect(href).not.toMatch(/^\/(data|charts|workspace)/);
    }
  });

  it("exposes no download affordances", () => {
    const { container } = renderedPage();
    for (const anchor of Array.from(container.querySelectorAll("a"))) {
      expect(anchor.getAttribute("download")).toBeNull();
    }
  });
});

describe("No private editor metadata in public content", () => {
  const privateMetadataPatterns: RegExp[] = [
    /document[_-]?id/i,
    /revision[_-]?id/i,
    /revision_?number/i,
    /user[_-]?id/i,
    /owner[_-]?id/i,
    /\bsupabase\b/i,
    /\bBearer\b/,
    /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i,
  ];

  it("keeps identifiers and revision pins out of the rendered page", () => {
    const { container } = renderedPage();
    const text = (container.textContent ?? "") + " " + container.innerHTML;
    for (const pattern of privateMetadataPatterns) {
      expect(text).not.toMatch(pattern);
    }
  });

  it("keeps identifiers and revision pins out of the content module data", () => {
    const serialized = JSON.stringify({ thesis, claimRegistry });
    for (const pattern of privateMetadataPatterns) {
      expect(serialized).not.toMatch(pattern);
    }
  });
});

describe("Claim cards render with sources and evidence", () => {
  it("renders one card per registry claim with its quantity table", () => {
    renderedPage();
    for (const claim of claimRegistry) {
      expect(
        screen.getByRole("heading", { level: 3, name: claim.title }),
      ).toBeInTheDocument();
      expect(screen.getByText(`${claim.id} recorded quantities, scopes and sources`)).toBeInTheDocument();
      const evidenceList = screen.getByRole("list", { name: `${claim.id} evidence links`, hidden: true });
      expect(within(evidenceList).getAllByRole("link", { hidden: true }).length).toBe(claim.evidence.length);
    }
  });

  it("renders the CL-009 scoped absence without pretending a measured zero", () => {
    renderedPage();
    expect(screen.getByText(/index cannot rule out every sale, lock or external delegation/)).toBeInTheDocument();
    expect(screen.getByText(/Holding these balances does not establish permanent supply removal/i)).toBeInTheDocument();
  });
});

describe("Compact hypothesis assessment (NI-076 D1)", () => {
  it("renders the H1–H4 overview with each recorded status and a real anchor link", () => {
    renderedPage();
    const overview = document.getElementById("hypothesis-assessment");
    expect(overview).not.toBeNull();
    expect(
      screen.getByRole("heading", { level: 2, name: "Hypothesis assessment at a glance" }),
    ).toBeInTheDocument();
    for (const hypothesis of thesis.question.hypotheses) {
      // The status wording restates the thesis verbatim — no new claims.
      const card = within(overview as HTMLElement).getByText(hypothesis.code, { exact: true })
        .closest("li");
      expect(card).not.toBeNull();
      expect(card!.textContent).toContain(hypothesis.status);
      expect(card!.textContent).toContain(hypothesis.title);
      const link = within(card as HTMLElement).getByRole("link", {
        name: `${hypothesis.code} ${hypothesis.title} ${hypothesis.status}`,
      });
      expect(link).toHaveAttribute("href", `#${hypothesis.id}`);
      // The anchor target is the unchanged full section below.
      expect(document.getElementById(hypothesis.id)).not.toBeNull();
    }
  });

  it("links the verdicts to the full research question and test criteria", () => {
    renderedPage();
    expect(screen.getByRole("link", { name: "Read the research question and test criteria" }))
      .toHaveAttribute("href", "#question");
    for (const entry of thesisToc) {
      expect(document.getElementById(entry.id)).not.toBeNull();
    }
  });
});
