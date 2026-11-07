/**
 * Reviewed editorial copy for the public routes (NI-011, NI-013, NI-014).
 *
 * The landing and mechanism content (NI-011) is deliberately free of metric
 * observations. The methodology content (NI-013) carries methodology facts
 * only — periods, coverage counts, gate thresholds and verdicts, each
 * mirroring a recorded document. The thesis content (NI-014) carries the
 * complete original conditional thesis and the claim registry CL-001–CL-009:
 * every numeric quantity is a typed object with an exact recorded value,
 * scope, source and definition version, and no private editor metadata.
 * No promises, no live claims, no unfinished feature announcements.
 */

export const landing = {
  title: "NEAR Intelligence",
  standfirst:
    "Evidence-first investment research on the NEAR ecosystem. Every published number carries its source, definition version and limitations — and a missing value is never shown as zero.",
  whatYouCanDo:
    "Read the full thesis, follow each economic mechanism, and check the methodology before trusting any conclusion.",
  links: [
    { label: "Read the research", href: "/research" },
    { label: "How the numbers are made", href: "/methodology" },
  ],
} as const;

export const mechanism = {
  heading: "The economic mechanism",
  intro:
    "The investment question is a chain of distinct steps, each of which can hold or break on its own evidence. Treating them as one number is the mistake this project exists to avoid.",
  stages: [
    {
      id: "activity",
      title: "Activity",
      body: "People use applications on NEAR. Usage is observable on-chain, but raw transaction counts say nothing about economic value by themselves.",
    },
    {
      id: "fees",
      title: "Fees",
      body: "Usage produces fees. Fee amounts are exact on-chain facts and are the first quantity worth measuring precisely.",
    },
    {
      id: "revenue",
      title: "Revenue",
      body: "Fees accrue somewhere — to validators, to a protocol treasury, to application contracts. Which part is economically attributable revenue is a definition question, answered per source with explicit boundaries.",
    },
    {
      id: "conversion",
      title: "Conversion",
      body: "A treasury may convert holdings or purchase NEAR on the market. Purchases are observable events with their own provenance.",
    },
    {
      id: "supply",
      title: "Retention & supply",
      body: "Purchases can support demand; burns permanently remove supply. These are different effects and are never presented as one movement.",
    },
  ],
  cautions: [
    "Treasury purchases do not reduce total supply — burns do.",
    "Gross fees, attributable revenue and treasury payouts are different metrics; this project never relabels one as another.",
  ],
} as const;

/**
 * NI-014 public thesis: the complete original conditional thesis with its
 * claim registry (CL-001–CL-009), mirroring docs/INVESTMENT_THESIS.md and the
 * recorded FINDINGS.md documents in the research directories.
 *
 * Every numeric quantity is a typed object carrying its exact recorded value,
 * unit, scope, source and — where the value maps to one — the registered
 * metric definition version (apps/api/src/near_api/metrics/registry.py).
 * Nothing is computed, re-rounded or fetched at render time; bounds stay
 * bounds ("lower bound"/"upper bound"), USD marks stay approximations, and the
 * model section stays explicitly pending until the NI-070 finalization.
 * The content carries no private editor metadata (no document, revision or
 * user identifiers). English-only per the recorded OQ-06 decision.
 */

export interface ClaimEvidenceLink {
  readonly label: string;
  readonly href: string;
}

export interface ClaimQuantity {
  /** Exact recorded magnitude (sign is expressed through direction/bound). */
  readonly value: string;
  readonly unit: string;
  /** Period and cohort the value was measured on, as recorded. */
  readonly scope: string;
  /** Recorded document the value is copied from. */
  readonly source: string;
  /** Anchor into this site's methodology page or a verified external URL. */
  readonly sourceHref: string;
  readonly direction?: "decrease" | "increase";
  /** Bounds stay bounds in every rendering; never rendered as exact values. */
  readonly bound?: "lower" | "upper";
  /** Price-mark or model basis when the same period supports alternatives. */
  readonly basis?: string;
}

export interface ThesisClaim {
  readonly id: string;
  readonly title: string;
  readonly assessment: string;
  /** Prose observation; exact magnitudes live in the typed quantities only. */
  readonly observation: string;
  /** Registered metric definition versions this claim's quantities map to. */
  readonly definitionVersions: readonly string[];
  /** Where the underlying dataset versions live today, stated honestly. */
  readonly datasetVersionReference: string;
  readonly quantities: readonly ClaimQuantity[];
  readonly evidence: readonly ClaimEvidenceLink[];
  readonly caution?: string;
  /** Required whenever quantities is empty (scoped negative observations). */
  readonly noQuantitiesReason?: string;
}

/**
 * Verified external references only. The set mirrors docs/SOURCE_VERIFICATION.md
 * (registers reviewed 5 November 2026) and the methodology page's verified
 * links; no other outbound links are rendered anywhere on the thesis page.
 */
export const verifiedExternalLinks = [
  "https://www.near.org/blog/evolving-near-tokenomics",
  "https://docs.near-intents.org/integration/distribution-channels/1click-api/fee-config",
  "https://github.com/DefiLlama/dimension-adapters/blob/master/fees/near-intents/index.ts",
  "https://docs.near.org/api/rpc/block-chunk",
  "https://docs.coingecko.com/reference/coins-id-market-chart-range",
] as const;

/**
 * Internal routes/anchors the thesis page may link to. Only implemented routes
 * and the stable methodology anchors (IA: /methodology#sources, #reproduce,
 * plus #definitions, #collection, #readiness) are allowed; /data and /charts
 * routes do not exist yet and are never linked.
 */
export const internalHrefAllowlist = [
  "/",
  "/research",
  "/methodology",
  "/methodology#sources",
  "/methodology#definitions",
  "/methodology#collection",
  "/methodology#readiness",
  "/methodology#reproduce",
] as const;

export const thesisToc: readonly { readonly id: string; readonly title: string }[] = [
  { id: "executive-summary", title: "Executive summary" },
  { id: "question", title: "Research question and canonical hypotheses" },
  { id: "ecosystem", title: "Ecosystem overview" },
  { id: "intents-mechanism", title: "Cross-chain execution and Intents" },
  { id: "adoption", title: "Adoption and network activity" },
  { id: "revenue-generation", title: "Revenue generation" },
  { id: "revenue-capture", title: "Revenue capture and actual observed findings" },
  { id: "token-economics", title: "Token economics" },
  { id: "econometrics", title: "Econometric evidence" },
  { id: "alternative-explanations", title: "Alternative explanations" },
  { id: "risks", title: "Risks and counterarguments" },
  { id: "scenarios", title: "Long-term scenarios" },
  { id: "assessment", title: "Final assessment" },
  { id: "limits", title: "Limitations" },
  { id: "sources-reproducibility", title: "Sources and reproducibility" },
];

export const hypothesisIds = ["h1", "h2", "h3", "h4"] as const;

export const thesis = {
  title: "Research",
  standfirst:
    "The complete original conditional thesis, with supporting and contrary evidence side by side. Every number carries its source, scope and definition version, bounds stay bounds, and the model section is explicitly pending.",
  evidenceStatus:
    "Recorded evidence basis: the saved 90-day cohort 2026-08-06 through 2026-11-04 (UTC, end exclusive) verified on 4 November 2026, plus the provider register reviewed 5 November 2026. No live values are published on this page; archival collection stays stopped, and a missing or unavailable value is never shown as zero.",
  tocLabel: "Thesis sections",

  executiveSummary: {
    id: "executive-summary",
    title: "Executive summary",
    lead:
      "NEAR's long-term investment case depends on its ability to convert growing cross-chain activity into sustainable protocol revenue and measurable token value capture.",
    paragraphs: [
      "Existing saved evidence supports a regularly operating conversion/payout channel within a defined cohort (CL-001, CL-003). It challenges a simple accelerating-demand narrative: NEAR quantities acquired declined across successive 30-day windows (CL-002), and observed acquisitions are small relative to positive net supply growth (CL-007, CL-008). Full fee provenance and economically attributable daily protocol revenue remain unresolved (CL-005, CL-006).",
      "The appropriate current assessment is mixed evidence with important identification gaps, not a proven investment case. A working research product should make both findings and gaps inspectable — which is what the claim registry below is for.",
    ],
  },

  question: {
    id: "question",
    title: "Research question and canonical hypotheses",
    intro:
      "The thesis is carried by four conditional hypotheses. Each states its current assessment and what evidence would weaken it. These H1–H4 differ from the old product-plan's H1–H6; no numeric remapping is valid without a semantic mapping.",
    hypothesesIntro: "Current assessment and falsification condition per hypothesis:",
    hypotheses: [
      {
        id: "h1",
        code: "H1",
        title: "Revenue growth",
        question: "Does increasing Intents activity correspond to sustainable protocol-revenue growth?",
        status: "Unresolved",
        rationale:
          "Daily economically attributable protocol revenue is not established (open question OQ-01): the preferred revenue specification is NOT_READY — the protocol-revenue metric is gated with zero observations. Gross-fee association alone is insufficient.",
        weakening:
          "Weakened if comparable net revenue stagnates or falls while activity rises after adjusting for policy, price and costs.",
        claimIds: ["CL-002", "CL-004"],
        evidence: [
          { label: "Model data readiness verdicts", href: "/methodology#readiness" },
          { label: "Gated definitions", href: "/methodology#definitions" },
        ],
      },
      {
        id: "h2",
        code: "H2",
        title: "Value capture",
        question: "How much generated revenue translates into measurable buybacks or other capture?",
        status: "Partial evidence",
        rationale:
          "Partial route evidence only: fee-funded conversions are established for a narrow cohort on narrow dates (CL-005, CL-006); the full fee-funded share of observed purchases is unknown because pooled balances prevent physical tracing.",
        weakening:
          "Weakened if executed fee receipts cannot be reconciled to conversion and retention, or if material outflows reverse the observed accumulation.",
        claimIds: ["CL-005", "CL-006"],
        evidence: [{ label: "Collection and cleaning path", href: "/methodology#collection" }],
      },
      {
        id: "h3",
        code: "H3",
        title: "Supply offset",
        question: "Under what conditions can buybacks and burns offset issuance?",
        status: "Not supported on current evidence",
        rationale:
          "Total supply grew over the measured window (CL-007) and purchases are not burns: the confirmed purchases are a small fraction of the net supply increase, and gross issuance/burn are known only as conservative lower bounds (CL-008).",
        weakening:
          "A supply-offset claim fails without actual destruction matching issuance; liquid-supply effects would require a separate verified retention/lock model.",
        claimIds: ["CL-007", "CL-008"],
        evidence: [
          { label: "Provider register (supply sources)", href: "/methodology#sources" },
        ],
      },
      {
        id: "h4",
        code: "H4",
        title: "Retention share",
        question: "Does protocol retention share rise or fall with adoption?",
        status: "Unresolved",
        rationale:
          "A compatible revenue numerator and economic-activity denominator are missing: the capture-rate metric is gated and never emits a value from gross fees or cash payouts.",
        weakening:
          "Weakened if matched accrual retention falls persistently or if costs and incentives exceed retained revenue.",
        claimIds: ["CL-004"],
        evidence: [{ label: "Gated definitions", href: "/methodology#definitions" }],
      },
    ],
  },

  ecosystem: {
    id: "ecosystem",
    title: "Ecosystem overview",
    paragraphs: [
      "Four economically distinct layers matter here: base-chain execution and gas economics; Intents-related product activity; distribution and affiliate economics; and governance-controlled accounts. A token can be the settlement or treasury asset without every dollar of ecosystem activity accruing to token holders.",
    ],
    externalNote:
      "The official tokenomics discussion describes discretionary governance tools; it is treated as policy context, not as a guaranteed cashflow claim.",
    links: [
      { label: "Evolving NEAR Tokenomics (official blog, 24 February 2026)", href: "https://www.near.org/blog/evolving-near-tokenomics" },
    ],
  },

  intentsMechanism: {
    id: "intents-mechanism",
    title: "Cross-chain execution and Intents",
    paragraphs: [
      "The relevant observed mechanism is: incoming multi-asset balances are exchanged into wrap.near, followed by native withdrawals arriving as treasury receipts, and subsequent holdings or use (CL-001, CL-003).",
      "The fee configuration documents declared appFees; a successful on-chain receipt and economic entitlement must be proven separately (CL-005). Common pooled balances prevent physical tracing of interchangeable tokens from a particular fee to a particular payout — which is why CL-006 is a conservative accounting model, not token tracing.",
    ],
    links: [
      { label: "1Click API fee configuration (declared appFees)", href: "https://docs.near-intents.org/integration/distribution-channels/1click-api/fee-config" },
    ],
  },

  adoption: {
    id: "adoption",
    title: "Adoption and network activity",
    paragraphs: [
      "Provider volume can describe Intents turnover; it is not independently reconstructed market-wide activity (CL-004).",
      "The measured cohort contains accounts that withdrew to three selected treasury wallets during the 90-day window. Collector accounts are not users, customers or independent integrators; their concentration says nothing about customer concentration.",
      "Network transaction and active-address series stay separate and unavailable until they are defined and sourced — the gated registry emits null with a recorded reason, never zero.",
    ],
    links: [{ label: "Metric registry and gated definitions", href: "/methodology#definitions" }],
  },

  revenueGeneration: {
    id: "revenue-generation",
    title: "Revenue generation",
    paragraphs: [
      "Gross provider fees are not protocol profit (CL-004). A source-qualified fee/volume series can support an exploratory association only, with the mechanical fee–volume construction, provider revisions, incentive policy and endogenous adoption disclosed — the readiness gate admits exactly that named proxy, with limits.",
      "Monthly captured revenue is not allocated across days. Provider sources disagree on overlapping days, and reported fee history has been revised after publication; the disagreement is recorded, not averaged away.",
    ],
    links: [
      { label: "Model data readiness verdicts", href: "/methodology#readiness" },
      { label: "Provider register", href: "/methodology#sources" },
    ],
  },

  revenueCapture: {
    id: "revenue-capture",
    title: "Revenue capture and actual observed findings",
    intro:
      "The claim registry binds each observation to its scope, definition version and recorded source. Values marked as bounds or approximations are rendered that way everywhere; nothing on this page is a live query.",
    claimIds: ["CL-001", "CL-002", "CL-003", "CL-004", "CL-005", "CL-006"],
    closing:
      "CL-001 and CL-003 are different flows and must not be added as independent token demand. Even the route attribution in CL-006 is a conservative accounting model, not an exact causal estimate of market impact.",
  },

  tokenEconomics: {
    id: "token-economics",
    title: "Token economics",
    intro:
      "Accounting identity for total supply: the net change equals gross issuance minus actual burns, plus any separately identified protocol adjustments. Ordinary purchases and treasury transfers are not a subtraction. Liquid circulating supply requires a distinct operational definition and verified locks or outflows; it is not measured here. Comparing acquisitions with issuance measures scale, not deflation or net selling pressure.",
    claimIds: ["CL-007", "CL-008", "CL-009"],
  },

  econometrics: {
    id: "econometrics",
    title: "Econometric evidence",
    pending:
      "Explicitly pending: no fitted model, coefficient, confidence interval or causal conclusion is published here yet. This section is finalized only with the original research release (NI-070); until then it reports an unmet release gate rather than results.",
    paragraphs: [
      "The preregistered readiness gate has already decided what the saved archive may support: the overall verdict for the 90-day window is PROXY_ONLY_READY_WITH_LIMITS, with gross_fee_activity_v1 the only admitted specification — always with limits, never labeled protocol revenue. The preferred true-revenue specification is NOT_READY, and lower-bound supply series are REJECTED as regression outcomes.",
      "Statistical nonsignificance is a valid finding. Any future published result must carry its dataset and definition versions, code, lock and config hashes, and must be reproducible offline.",
    ],
    links: [
      { label: "Model data readiness verdicts", href: "/methodology#readiness" },
      { label: "Reproduction path", href: "/methodology#reproduce" },
    ],
  },

  alternativeExplanations: {
    id: "alternative-explanations",
    title: "Alternative explanations",
    items: [
      "Price changes can reduce token quantity despite stable USD flows — the recorded decomposition in CL-004 shows this mechanically, without implying causation in either direction.",
      "Fee-rate changes, rebates, recipient allocations, batching and accrual lags, treasury stock movements and source revisions can alter observed relationships.",
      "Simultaneous volume and fees may be mechanically linked; the admitted readiness proxy is exactly that construction.",
      "A growing collector's activity can aggregate many sources; concentration of collectors is not concentration of customers.",
      "General market conditions may jointly influence adoption and revenue.",
    ],
  },

  risks: {
    id: "risks",
    title: "Risks and counterarguments",
    items: [
      "Governance can change deployment and retention of acquired NEAR at any time (CL-009).",
      "Fee competition can lower retained margins; costs and incentives are unknown.",
      "Declared appFees may omit other business channels and funding sources (CL-005).",
      "Source definitions and historical revisions disagree; provider-reported fee history has been revised after publication.",
      "Treasury accumulation is reversible, and positive supply growth persists (CL-007, CL-008).",
      "Existing evidence does not identify token holder contractual claims or a justified valuation multiple.",
    ],
  },

  scenarios: {
    id: "scenarios",
    title: "Long-term scenarios",
    intro:
      "Qualitative assumptions only — not probability-weighted forecasts, price projections or recommendations. Advanced simulation is outside the MVP scope.",
    cases: [
      {
        id: "downside",
        title: "Downside",
        body: "Adoption grows but retained revenue or fee rates fall and acquired assets are spent; no durable capture.",
      },
      {
        id: "conditional-base",
        title: "Conditional base",
        body: "Recurring receipts and conversions persist with transparent retention, but remain modest relative to issuance and costs.",
      },
      {
        id: "upside",
        title: "Upside",
        body: "Independently reconciled revenue scales, costs are covered and governance implements verifiable durable capture.",
      },
    ],
  },

  assessment: {
    id: "assessment",
    title: "Final assessment",
    paragraphs: [
      "The conversion channel is observable and recurrent in the selected cohort. Its NEAR quantity did not grow over the measured windows (CL-002).",
      "Some fee-to-conversion attribution is established on narrow dates (CL-005, CL-006), but neither full 90-day fee funding nor sustained protocol-revenue growth is proven.",
      "Positive supply growth and discretionary treasury use constrain stronger value-capture claims (CL-007, CL-008, CL-009).",
      "The investment thesis remains conditional on stronger revenue attribution, scale, costs and retention evidence. No price target or recommendation follows from these observations.",
    ],
  },

  limitations: {
    id: "limits",
    title: "Limitations",
    items: [
      "Cohort selection excludes converters without payouts to the selected treasury wallets.",
      "Index completeness is not independently universal.",
      "Amount-and-time payout matching differs from a full causal receipt graph (CL-003).",
      "USD marks approximate execution rather than recording trade prices (CL-004).",
      "Daily protocol revenue is missing; gross issuance and burn exist only as incomplete lower bounds (CL-008).",
      "The provenance period is much shorter than the 90-day cohort (CL-005, CL-006).",
      "The treasury index cannot establish all possible disposal or lock paths (CL-009).",
      "No out-of-sample long-term validation or econometric run exists yet — see the explicitly pending section.",
    ],
    staleness:
      "All recorded evidence is historical: the cohort was verified on 4 November 2026 and the provider register on 5 November 2026, and the archival mint-header audit stopped incomplete (CL-008). Values on this page are never refreshed in place — a provider revision becomes a new dataset version that supersedes the old one, and a fresh retrieval does not make an old observation fresh.",
  },

  sourcesReproducibility: {
    id: "sources-reproducibility",
    title: "Sources and reproducibility",
    paragraphs: [
      "Primary recorded findings and artifacts are cited per claim in the registry above, with the repository documents named as the source of every value. The metric catalog, source register and reproduction instructions define exact scope.",
      "The official DefiLlama adapter describes its own accounting; it is not proof of independent attribution.",
      "Future published claims must bind CL ids to dataset and definition versions, code, lock and config hashes, and an approved public evidence manifest.",
    ],
    datasetNote:
      "The recorded analysis artifacts (manifests and summaries) live in the operator's local research archive and are shared only through verified, hash-checked handoffs; a fresh clone of this repository intentionally does not contain them. Staged application dataset versions are not publicly listed yet, so public dataset-version references arrive with the delivery APIs. Until then, every quantity on this page carries its document-level source and registered definition version instead of implying a live link.",
    links: [
      { label: "Provider register and rights", href: "/methodology#sources" },
      { label: "Versioned metric registry", href: "/methodology#definitions" },
      { label: "Reproduction commands", href: "/methodology#reproduce" },
      { label: "DefiLlama NEAR Intents adapter (provider methodology)", href: "https://github.com/DefiLlama/dimension-adapters/blob/master/fees/near-intents/index.ts" },
    ],
  },
} as const;

/**
 * Where the recorded dataset versions live today, shared by all claims: the
 * NI-028 staging holds dataset versions in the operator database and the raw
 * recorded artifacts stay in the local research archive; neither is publicly
 * listed yet. This is the honest dataset-version reference until the delivery
 * APIs publish immutable public references.
 */
const datasetVersionReference =
  "Recorded analysis artifacts and manifests in the local research archive; application dataset versions staged by NI-028 are held in the operator database and are not publicly listed yet — public dataset-version references arrive with the delivery APIs.";

/**
 * The claim registry CL-001–CL-009, copied from docs/INVESTMENT_THESIS.md
 * (sections 7–8) and the recorded research findings. Values are the exact
 * recorded strings; window scopes mirror the recorded 30-day windows
 * (both dates inclusive) and the 90-day cohort (end exclusive).
 */
export const claimRegistry: readonly ThesisClaim[] = [
  {
    id: "CL-001",
    title: "Observed conversion cohort",
    assessment: "Observed — cohort-scoped",
    observation:
      "Successful conversions of other assets into wrap.near occurred in every day of the 90-day cohort, and the acquired quantities are exact sums over deduplicated on-chain events within the observed cohort.",
    definitionVersions: [
      "conversion_count v1 (availability A)",
      "observed_near_purchases v1 (availability A)",
    ],
    datasetVersionReference,
    quantities: [
      {
        value: "54,991",
        unit: "successful observed conversion events",
        scope:
          "90-day observed cohort, 2026-08-06 through 2026-11-04 (UTC, end exclusive), accounts that withdrew to the three selected treasury wallets",
        source: "docs/INVESTMENT_THESIS.md CL-001; research/near-longitudinal/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "524,480.127692882832410490617319",
        unit: "NEAR acquired",
        scope:
          "90-day observed cohort, 2026-08-06 through 2026-11-04 (UTC, end exclusive), accounts that withdrew to the three selected treasury wallets",
        source: "docs/INVESTMENT_THESIS.md CL-001; research/near-longitudinal/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "90",
        unit: "of 90 days contained at least one observed conversion",
        scope: "90-day observed cohort, 2026-08-06 through 2026-11-04 (UTC, end exclusive)",
        source: "docs/INVESTMENT_THESIS.md CL-001; research/near-longitudinal/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
    ],
    evidence: [
      { label: "Observed-conversion metric path (SRC-BQ → import → staging → compute)", href: "/methodology#collection" },
      { label: "Provider register: SRC-BQ saved exports", href: "/methodology#sources" },
    ],
    caution:
      "The cohort covers treasury-linked collector accounts only — it is not whole-market demand and cannot estimate protocol revenue.",
  },
  {
    id: "CL-002",
    title: "Declining NEAR quantities across windows",
    assessment: "Observed — contrary to an accelerating-demand narrative",
    observation:
      "Acquired quantities in successive 30-day windows declined, so the observed channel is recurrent but not accelerating in token units. Values are rounded for display; exact values live in the recorded summaries.",
    definitionVersions: ["observed_near_purchases v1 (availability A)"],
    datasetVersionReference,
    quantities: [
      {
        value: "244,845.70",
        unit: "NEAR acquired",
        scope: "First 30-day window, 2026-08-06 through 2026-09-04 (UTC, both dates inclusive)",
        source: "docs/INVESTMENT_THESIS.md CL-002; research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "165,809.44",
        unit: "NEAR acquired",
        scope: "Second 30-day window, 2026-09-05 through 2026-10-04 (UTC, both dates inclusive)",
        source: "docs/INVESTMENT_THESIS.md CL-002; research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "113,825.00",
        unit: "NEAR acquired",
        scope: "Third 30-day window, 2026-10-05 through 2026-11-03 (UTC, both dates inclusive)",
        source: "docs/INVESTMENT_THESIS.md CL-002; research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "31.35",
        unit: "percent",
        direction: "decrease",
        basis: "third window relative to the preceding window, in NEAR quantities",
        scope: "Third window relative to the second window",
        source: "docs/INVESTMENT_THESIS.md CL-002; research/near-longitudinal/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
    ],
    evidence: [
      { label: "Observed-conversion metric path", href: "/methodology#collection" },
      { label: "Provider register: SRC-BQ saved exports", href: "/methodology#sources" },
    ],
    caution:
      "Rounded for display; the decline is in NEAR units and must not be read as an equally sized fall in economic demand — see CL-004.",
  },
  {
    id: "CL-003",
    title: "Matched treasury payouts",
    assessment: "Observed — matched flows, not provenance",
    observation:
      "Matched native payouts from the Intents contract to the three selected wallets arrived every day of the cohort; internal treasury transfers are excluded from this flow.",
    definitionVersions: [
      "treasury_payouts_near v1 (availability A)",
      "treasury_payout_count v1 (availability A)",
    ],
    datasetVersionReference,
    quantities: [
      {
        value: "1,405,659.135989071036891726256814",
        unit: "NEAR in matched native payouts",
        scope:
          "90-day observed cohort, 2026-08-06 through 2026-11-04 (UTC, end exclusive), three selected treasury wallets, internal treasury transfers excluded",
        source: "docs/INVESTMENT_THESIS.md CL-003; research/near-longitudinal/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "3,165",
        unit: "matched native payout events",
        scope: "90-day observed cohort, 2026-08-06 through 2026-11-04 (UTC, end exclusive)",
        source: "docs/INVESTMENT_THESIS.md CL-003; research/near-longitudinal/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "502,794",
        unit: "NEAR of internal treasury transfers excluded",
        scope: "Same 90-day window; transfers between the selected wallets are not counted as new payouts",
        source: "docs/INVESTMENT_THESIS.md CL-003; research/near-longitudinal/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
    ],
    evidence: [
      { label: "Payout matching rules in the metric computation", href: "/methodology#collection" },
      { label: "Provider register: SRC-BQ saved exports", href: "/methodology#sources" },
    ],
    caution:
      "Matching used amount and recipient with a unique candidate within a recorded 300-second tolerance — this is not a full parent-graph proof. CL-001 and CL-003 are different flows and must not be added as independent token demand.",
  },
  {
    id: "CL-004",
    title: "USD valuation and the price effect",
    assessment: "Estimate — valuation, not execution",
    observation:
      "Approximate USD acquisitions stayed near one level across the last two windows while NEAR quantities fell sharply, because the quantity-weighted price rose. The decomposition is arithmetic, not causation.",
    definitionVersions: [
      "estimated_purchase_usd v1 (availability B — valuation estimate)",
      "near_price_usd v1 (availability P)",
      "provider_intents_volume_usd v1 (availability P)",
      "provider_gross_fees_usd v1 (availability P)",
    ],
    datasetVersionReference,
    quantities: [
      {
        value: "437,374",
        unit: "USD (approximate acquisition value)",
        basis: "daily start-of-day price marks",
        scope: "First 30-day window, 2026-08-06 through 2026-09-04 (UTC, both dates inclusive)",
        source: "docs/INVESTMENT_THESIS.md CL-004; research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "557,914",
        unit: "USD (approximate acquisition value)",
        basis: "daily start-of-day price marks",
        scope: "Second 30-day window, 2026-09-05 through 2026-10-04 (UTC, both dates inclusive)",
        source: "docs/INVESTMENT_THESIS.md CL-004; research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "547,026",
        unit: "USD (approximate acquisition value)",
        basis: "daily start-of-day price marks",
        scope: "Third 30-day window, 2026-10-05 through 2026-11-03 (UTC, both dates inclusive)",
        source: "docs/INVESTMENT_THESIS.md CL-004; research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "1.95",
        unit: "percent",
        direction: "decrease",
        basis: "start-of-day price marks",
        scope: "Third window relative to the second window",
        source: "docs/INVESTMENT_THESIS.md CL-004; research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "5.45",
        unit: "percent",
        direction: "decrease",
        basis: "end-of-day alternative price marks — a second valuation scenario, not a confidence interval",
        scope: "Third window relative to the second window",
        source: "docs/INVESTMENT_THESIS.md CL-004; research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "3.3648",
        unit: "USD quantity-weighted average daily price",
        basis: "quantity-weighted average of daily start prices, not an execution price",
        scope: "Second 30-day window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "4.8059",
        unit: "USD quantity-weighted average daily price",
        basis: "quantity-weighted average of daily start prices, not an execution price",
        scope: "Third 30-day window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "42.83",
        unit: "percent",
        direction: "increase",
        basis: "change of the quantity-weighted average daily price between the second and third windows",
        scope: "Third window relative to the second window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "0.68648",
        unit: "ratio of NEAR quantities",
        basis: "third window relative to the second window — quantity factor of the recorded decomposition",
        scope: "Third window relative to the second window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "1.42828",
        unit: "ratio of weighted daily prices",
        basis: "third window relative to the second window — price factor of the recorded decomposition",
        scope: "Third window relative to the second window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "0.98048",
        unit: "ratio of USD values",
        basis: "product of the two factors above — the recorded decomposition shows the unit effect, not causation",
        scope: "Third window relative to the second window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "12.54",
        unit: "percent",
        direction: "decrease",
        basis: "provider-reported Intents volume, fresh dashboard retrieval of 4 November 2026; revisable",
        scope: "Third window relative to the second window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "21.88",
        unit: "percent",
        direction: "decrease",
        basis: "provider-reported all fees, fresh dashboard retrieval of 4 November 2026; revisable",
        scope: "Third window relative to the second window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "10.06",
        unit: "percent of all reported fees",
        basis: "descriptive ratio of observed purchase value to all reported fees — not a contracted rate and not a proven fee share",
        scope: "First 30-day window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "7.37",
        unit: "percent of all reported fees",
        basis: "descriptive ratio of observed purchase value to all reported fees — not a contracted rate and not a proven fee share",
        scope: "Second 30-day window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "9.25",
        unit: "percent of all reported fees",
        basis: "descriptive ratio of observed purchase value to all reported fees — not a contracted rate and not a proven fee share",
        scope: "Third 30-day window",
        source: "research/near-dollar/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
    ],
    evidence: [
      { label: "Provider register: SRC-PRICE and SRC-DASHBOARD", href: "/methodology#sources" },
      { label: "CoinGecko historical range documentation", href: "https://docs.coingecko.com/reference/coins-id-market-chart-range" },
    ],
    caution:
      "USD values are approximations at daily price marks, never execution prices; missing prices make USD values missing, never zero. Purchases and payouts are not added together.",
  },
  {
    id: "CL-005",
    title: "Fee provenance cohort",
    assessment: "Partial — narrow cohort",
    observation:
      "A share of declared fees in the creation cohort is matched end to end — API record, on-chain transfer and unique internal credit — establishing observable fee funding of purchases on those dates. The remainder is not labeled unpaid or erroneous.",
    definitionVersions: [],
    datasetVersionReference,
    quantities: [
      {
        value: "21,361",
        unit: "API creation-cohort records",
        scope: "Explorer API SUCCESS affiliate records with request-creation dates 2026-11-01 through 2026-11-03 (UTC)",
        source: "docs/INVESTMENT_THESIS.md CL-005; research/near-provenance/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "8,420",
        unit: "matched fee events (API record, logical transfer and unique canonical credit)",
        scope: "Same creation cohort; execution dates 2026-11-01 through 2026-11-03",
        source: "docs/INVESTMENT_THESIS.md CL-005; research/near-provenance/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "3,377",
        unit: "matches with exact-integer formula agreement",
        scope: "Subset of the matched fee events where amountIn × bps / 10000 is an exact integer",
        source: "docs/INVESTMENT_THESIS.md CL-005; research/near-provenance/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
    ],
    evidence: [
      { label: "Provider register: SRC-INTENTS", href: "/methodology#sources" },
      { label: "1Click API fee configuration (declared appFees)", href: "https://docs.near-intents.org/integration/distribution-channels/1click-api/fee-config" },
    ],
    caution:
      "The cohort is defined by request-creation date, not execution date, and appFees do not cover every funding channel; matched shares of this cohort must not be extrapolated to all Intents fees, weekly purchases or the 90-day flow.",
  },
  {
    id: "CL-006",
    title: "Strict inventory attribution minimum",
    assessment: "Bound — model minimum",
    observation:
      "Under the strict short-window inventory model, a minimum amount of confirmed fee assets must have been sold into NEAR conversions, and a modeled minimum NEAR-equivalent of those sales cannot have remained in the collector's closing stock. This is an accounting minimum within the stated model, not physical token tracing.",
    definitionVersions: [
      "strict_fee_conversion_equivalent_near v1 (availability B — bound/model)",
    ],
    datasetVersionReference,
    quantities: [
      {
        value: "1,427.13",
        unit: "NEAR equivalent sold out of confirmed fees",
        bound: "lower",
        basis: "strict short-window inventory model — a minimum within the stated model, not physical token tracing",
        scope: "Confirmed fees executed 2026-11-01 through 2026-11-02 against the reconciled week 2026-10-27 through 2026-11-02",
        source: "docs/INVESTMENT_THESIS.md CL-006; research/near-provenance/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "5.69",
        unit: "percent of the reference week's observed purchases",
        basis: "share of the week's observed purchases accounted for by the strict inventory minimum",
        scope: "Relative to the observed purchases of the reconciled week 2026-10-27 through 2026-11-02",
        source: "docs/INVESTMENT_THESIS.md CL-006; research/near-provenance/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "25,082.81",
        unit: "NEAR observed purchases in the reference week",
        scope: "Reconciled week 2026-10-27 through 2026-11-02, the cohort baseline referenced by the share above",
        source: "research/near-provenance/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
      {
        value: "1,407.21",
        unit: "NEAR equivalent routed to payout in the model",
        bound: "lower",
        basis: "modeled route minimum after subtracting all closing stock — a minimum within the stated model",
        scope: "Same reconciled week and model",
        source: "docs/INVESTMENT_THESIS.md CL-006; research/near-provenance/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#collection",
      },
    ],
    evidence: [
      { label: "Metric computation and inventory rules", href: "/methodology#collection" },
      { label: "1Click API fee configuration (declared appFees)", href: "https://docs.near-intents.org/integration/distribution-channels/1click-api/fee-config" },
    ],
    caution:
      "Not physical token tracing and not extrapolatable to 90 days; even this route attribution is a conservative accounting model, not an exact causal estimate of market impact.",
  },
  {
    id: "CL-007",
    title: "Supply growth scale comparison",
    assessment: "Observed — scale comparison",
    observation:
      "Total supply grew over the same 90 days, and the observed purchases are a small fraction of that growth. This is a scale comparison: it is not deflation, not a capture rate, and purchases are never subtracted from total supply.",
    definitionVersions: [
      "net_supply_change_near v1 (availability A)",
      "purchases_to_net_supply_pct v1 (availability A)",
    ],
    datasetVersionReference,
    quantities: [
      {
        value: "7,936,181.547057263680300503519861",
        unit: "NEAR exact boundary total-supply increase",
        scope: "Boundary difference over 2026-08-06 through 2026-11-03 (UTC day closes), verified on four exact boundary blocks",
        source: "docs/INVESTMENT_THESIS.md CL-007; research/near-supply/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "0.60915",
        unit: "percent of the opening supply",
        direction: "increase",
        basis: "rounded; an observed change over 90 days, not a forecast or an annualized rate",
        scope: "Same 90-day window",
        source: "docs/INVESTMENT_THESIS.md CL-007; research/near-supply/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "6.60872",
        unit: "percent of the net supply increase",
        basis: "scale comparison of observed purchases with the net supply increase — not deflation and not a capture rate",
        scope: "Observed purchases over the same 90-day window",
        source: "docs/INVESTMENT_THESIS.md CL-007; research/near-supply/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
    ],
    evidence: [
      { label: "Provider register: SRC-NEAR-RPC and supply boundaries", href: "/methodology#sources" },
      { label: "NEAR RPC block interface documentation", href: "https://docs.near.org/api/rpc/block-chunk" },
    ],
    caution:
      "Purchases are not subtracted from total supply. Emission does not equal market selling pressure; recipients may hold or stake their rewards.",
  },
  {
    id: "CL-008",
    title: "Issuance and burn lower bounds",
    assessment: "Bounds — incomplete audit",
    observation:
      "Gross issuance and burns are known only as conservative lower bounds because the archival mint-header audit stopped incomplete; the unverified remainder is never assumed zero.",
    definitionVersions: [
      "issuance_lower_bound_near v1 (availability B — lower bound)",
      "burns_lower_bound_near v1 (availability B — lower bound)",
      "purchases_to_issuance_upper_pct v1 (availability B — upper bound)",
    ],
    datasetVersionReference,
    quantities: [
      {
        value: "8,012,834",
        unit: "NEAR gross issuance",
        bound: "lower",
        basis: "rounded down so the lower bound stays mathematically correct; simultaneous burns in the same blocks could hide further issuance",
        scope: "Same 90-day window; positive supply changes plus verified simultaneous burn, less a conservative tolerance",
        source: "docs/INVESTMENT_THESIS.md CL-008; research/near-supply/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "76,652",
        unit: "NEAR burns",
        bound: "lower",
        basis: "rounded down so the lower bound stays mathematically correct; simultaneous issuance in the same blocks could hide further burns",
        scope: "Same 90-day window; negative supply changes plus verified simultaneous burn, less a conservative tolerance",
        source: "docs/INVESTMENT_THESIS.md CL-008; research/near-supply/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "6",
        unit: "of 297 positive supply-jump blocks with fully audited headers",
        scope: "Archival header audit stopped after rate limiting; the remaining blocks are unverified, not assumed zero",
        source: "docs/INVESTMENT_THESIS.md CL-008; research/near-supply/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
      {
        value: "6.54551",
        unit: "percent of gross issuance",
        bound: "upper",
        basis: "purchases divided by the strictly positive issuance lower bound, rounded outward — not an exact share",
        scope: "Observed purchases over the same 90-day window",
        source: "docs/INVESTMENT_THESIS.md CL-008 (exact bound; the supply findings round it to about 6.55 percent)",
        sourceHref: "/methodology#sources",
      },
    ],
    evidence: [
      { label: "Provider register: SRC-NEAR-RPC access status", href: "/methodology#sources" },
      { label: "NEAR RPC block interface documentation", href: "https://docs.near.org/api/rpc/block-chunk" },
    ],
    caution:
      "These are not exact gross totals. Purchases, fees, protocol revenue, treasury payouts, burns and issuance are different metrics and are never relabeled as one another.",
  },
  {
    id: "CL-009",
    title: "Treasury retention is reversible",
    assessment: "Scoped absence — retention, not removal",
    observation:
      "A role-index audit of the selected treasury wallets found no outgoing receipt-actions in the available index for the audited 30 days, and the observed funds sat on native balances under multisig/DAO control. Governance-controlled retention does not establish permanent supply removal.",
    definitionVersions: ["treasury_balance_near v1 (availability A — saved point)"],
    datasetVersionReference,
    quantities: [
      {
        value: "4,140,077.36974892",
        unit: "NEAR combined native balance of the three wallets",
        basis: "accumulated balances at a fixed finalized slice — not weekly revenue and not permanently removed supply",
        scope: "Fixed RPC slice 2026-11-04 11:31:03 UTC at finalized block 223010763; storage collateral is included in the raw amounts",
        source: "research/near-treasury/FINDINGS.md (verified 4 November 2026)",
        sourceHref: "/methodology#sources",
      },
    ],
    evidence: [
      { label: "Provider register: SRC-FASTNEAR indexed history", href: "/methodology#sources" },
    ],
    caution:
      "An index-scoped absence is not universal proof of no selling or locking, and account-level locked values do not exclude external delegation. The audit window is 2026-10-05 through 2026-11-03 (UTC).",
  },
];


/**
 * NI-013 methodology content. Every fact here mirrors a recorded document:
 * provider rows follow docs/SOURCE_VERIFICATION.md (registers reviewed
 * 5 November 2026, role-B operational review and the single OQ-03 probe
 * 6 November 2026), definitions follow the versioned metric registry
 * (apps/api/src/near_api/metrics/registry.py), pipeline gates follow
 * docs/DATA_PIPELINE.md, readiness verdicts follow the NI-051 gate policy and
 * its recorded real-archive run. Numbers on this page are methodology facts
 * (periods, coverage counts, gate thresholds) — never metric observations.
 * Commands are listed as implemented only where the repository actually
 * ships them; planned CLI verbs are labeled unavailable.
 */

export const methodology = {
  title: "Methodology",
  standfirst:
    "How the numbers are made: providers, definitions, collection, cleaning and the reproduction path. Published so a reader can assess the evidence before trusting a conclusion.",

  sources: {
    id: "sources",
    title: "Sources and rights",
    body: "Every provider is recorded with its endpoints, verification date, license and access status. Raw historical inputs remain in the operator's archive and are shared only through verified, hash-checked handoffs — a fresh clone of this repository intentionally does not contain them.",
    registerNote:
      "Status below mirrors the source verification register: register reviewed 5 November 2026; operational capability review 6 November 2026; one bounded finalized-header probe executed 2026-11-06T19:13:45Z under the operator's OQ-03 approval. A documentation page being reachable does not establish entitlement, an SLA, full historical coverage or redistribution rights.",
    tableCaption: "Provider register (verified periods and access status)",
    providers: [
      {
        id: "SRC-NEAR-RPC",
        provides: "NEAR block headers and account/protocol state from public mainnet RPC",
        access:
          "One bounded finalized-header probe on 2026-11-06 (HTTP 200, 18,496 bytes at a 65,536-byte cap, final height 223357966). Scheduled polling is approved within 1 request/minute and at most 1,440 requests/day but is not wired yet; no SLA and no numeric provider quota are established.",
        rights:
          "Approved via the OQ-03 resolution: free tier, no account or key, header-only responses with byte caps, public on-chain header data, derived-metric publication permitted. No bulk calls.",
      },
      {
        id: "SRC-BQ",
        provides: "NEAR public BigQuery tables used by the saved SQL analyses",
        access:
          "Saved execution_outcomes/receipt_actions exports cover a 90-day cohort with query timestamps and job IDs in the manifests. New execution requires a cloud identity, project, region and byte caps — none approved.",
        rights:
          "Existing exports reproduce offline. Dataset-specific terms and redistribution remain unresolved; no cloud SQL is executed.",
      },
      {
        id: "SRC-INTENTS",
        provides: "Explorer API swap records and fee declarations",
        access:
          "Saved creation cohort 2026-11-01 through 2026-11-03: 21,361 SUCCESS affiliate records across 23 pages, cohort marked complete. Current endpoint auth, quota and entitlement remain probe pending.",
        rights:
          "An appFees declaration is not executed revenue. Only sanitized artifacts are publishable; no token is stored or logged.",
      },
      {
        id: "SRC-LLAMA",
        provides: "Provider-reported fees/volume and revenue methodology",
        access:
          "Saved daily series with 90-day data; start-of-history and missing-date behavior still need a probe. The adapter is reachable; API subscription has separate access limits.",
        rights:
          "Provider methodology only: it reads Dune inputs and selected wallet flows, so it is not independent confirmation of original dashboard claims. Redistribution and attribution rights need an explicit record.",
      },
      {
        id: "SRC-DASHBOARD",
        provides: "Captured public research pages (revenue.near.org)",
        access:
          "Saved HTML/RSC/JSON snapshots with daily fees/volume and monthly captured revenue. No stable public server API, quota or refresh interval is established.",
        rights:
          "Saved source-qualified observations only; production collection on hashed JS bundles is not built.",
      },
      {
        id: "SRC-DUNE",
        provides: "SQL query results and saved reconciliation data",
        access:
          "Official API uses keys and scoped access with plan-dependent limits; no key or quota was checked. Saved reconciliation cites queries 6740088 and 6732239.",
        rights:
          "Dune-derived sources share one lineage. Permission, credits, retention and dataset redistribution need review before any use.",
      },
      {
        id: "SRC-PRICE",
        provides: "NEAR/USD historical prices",
        access:
          "Saved daily points cover the analysis window including the boundary price for the end-of-day alternative. History, granularity and auth depend on the chosen tier.",
        rights:
          "Daily USD valuations are approximations, never execution prices. Provider attribution required; paid-tier entitlement and redistribution unresolved. Missing prices stay missing.",
      },
      {
        id: "SRC-FASTNEAR",
        provides: "Indexed treasury action history",
        access:
          "Saved API responses with exhausted pagination from a 30-day role-index audit. No current quota or SLA verified.",
        rights:
          "The limited index supports a scoped “no indexed outgoing actions” observation, not universal proof of no selling or locking.",
      },
      {
        id: "SRC-NEARBLOCKS",
        provides: "Indexed daily supply boundaries",
        access:
          "Saved daily-close/block hashes agree with RPC and BigQuery on four supply boundaries; current entitlement, quota, history and license unverified.",
        rights:
          "Secondary reconciliation source only; no independent full gross-issuance proof.",
      },
      {
        id: "SRC-GOV",
        provides: "Official NEAR tokenomics and governance materials",
        access:
          "Official dated blog (24 February 2026) reachable; it describes discretionary governance tools.",
        rights:
          "Editorial context, not a guaranteed policy or numeric feed; blog retrieval and on-chain state are versioned separately.",
      },
    ],
    documentation: {
      label: "Provider documentation consulted for the register (verified live 2026-11-06):",
      links: [
        { label: "NEAR RPC providers", href: "https://docs.near.org/api/rpc/providers" },
        { label: "NEAR block/chunk interface", href: "https://docs.near.org/api/rpc/block-chunk" },
        { label: "NEAR Intents documentation index", href: "https://docs.near-intents.org/llms.txt" },
        { label: "DefiLlama API access tiers", href: "https://docs.llama.fi/pro-api" },
        { label: "DefiLlama NEAR Intents adapter", href: "https://github.com/DefiLlama/dimension-adapters/blob/master/fees/near-intents/index.ts" },
        { label: "Dune authentication", href: "https://docs.dune.com/api-reference/overview/authentication" },
        { label: "Dune rate limits", href: "https://docs.dune.com/api-reference/overview/rate-limits" },
        { label: "CoinGecko historical range", href: "https://docs.coingecko.com/reference/coins-id-market-chart-range" },
        { label: "BigQuery public datasets", href: "https://docs.cloud.google.com/bigquery/public-data" },
        { label: "Evolving NEAR Tokenomics (blog, 24 Feb 2026)", href: "https://www.near.org/blog/evolving-near-tokenomics" },
      ],
    },
    guarantees: [
      "No raw-data downloads are offered here. Archive receipts alone do not resolve rights for public raw-data distribution; each future enablement needs a recorded endpoint, quota, budget and license decision plus a sanitized probe.",
      "Treasury purchases do not reduce total supply — burns do. Purchases, fees, attributable revenue, treasury payouts, burns and issuance are never relabeled as one another.",
      "Gross issuance and burn stay conservative lower bounds: the mint-header audit behind them verified 6 of 297 headers before stopping, and the unverified remainder is never assumed zero.",
      "Short attribution cohorts (for example the 3-day provenance attribution cohort and the 7-day reconciliation week) stay descriptive evidence; they are rejected for daily long-run inference, and the 90-day window cannot establish a long-term stable mechanism.",
      "The observed purchases cohort covers treasury-linked collector accounts only — it is not whole-market demand and cannot estimate protocol revenue.",
    ],
  },

  definitions: {
    id: "definitions",
    title: "Definitions",
    body: "Metrics are defined once, in a versioned registry, and every chart references that definition. Gross fees, attributable revenue, treasury payouts and supply movements stay distinct quantities.",
    registryNote:
      "The versioned metric registry (NI-029/NI-031) holds one immutable definition per catalog concept. Each version carries a deterministic identity derived from its metric id and version number; a changed meaning appends a new version and never edits the old one. Registry registration is idempotent and content-verified: a stored row that diverges from the code registry is an error. Chart definitions reference metric ids and never restate formulas.",
    availability: [
      { code: "A", meaning: "saved observed data" },
      { code: "P", meaning: "provider-reported, source-qualified and revisable" },
      { code: "B", meaning: "bound or estimate only" },
      { code: "G", meaning: "gated — unavailable until source and definition are verified" },
    ],
    gatedNote:
      "Currently 19 definitions are registered. Three of them are gated and always emit null with a recorded reason, never zero: protocol_revenue_usd, protocol_capture_rate and fee_funded_buybacks_near. No verified daily economically attributable protocol-revenue ledger exists (open question OQ-01), so capture-rate and buyback quantities are likewise unavailable.",
    boundsNote:
      "Raw token amounts use integers and decimal strings with exact decimal arithmetic (yoctoNEAR converts to NEAR at 10^24). Missing prices make USD values missing, never zero; flows are never forward-filled. Purchases are never deducted from supply; the purchases-to-issuance ratio is published only as an upper bound, and net supply change stays separate from its incomplete components.",
  },

  collection: {
    id: "collection",
    title: "Collection and cleaning",
    body: "Collection runs with explicit caps and allowlists; stopped collectors stay stopped. Cleaning steps are documented next to the datasets they produced.",
    stages: [
      {
        id: "import",
        title: "Archive import (NI-027)",
        body: "Read-only import of the saved research archive. Every byte is verified against its recorded SHA-256 before any content is read; any divergence rejects the whole batch. Only sanitized metadata-only lineage is stored, and re-import is idempotent, keyed by the manifest hash.",
      },
      {
        id: "staging",
        title: "Dataset staging (NI-028)",
        body: "Prepared manifests are staged with canonical SHA-256 hashing, so identical semantic input deduplicates per dataset key and content hash. Staging persists version, member metrics, inputs and observations and runs membership, window, alignment and coverage validation inside one advisory-locked transaction; committed status is validated or rejected, and a contract failure leaves zero rows.",
      },
      {
        id: "compute",
        title: "Metric computation (NI-029)",
        body: "Pure registered formulas compute observations from canonical records: exact decimal arithmetic in a 100-digit context, deduplication and quarantine by canonical event identity, and payout matching by unique amount-and-receiver candidate within the recorded 300-second tolerance. Only successful execution can establish a conversion or transfer; a fee declaration alone cannot.",
      },
      {
        id: "publish",
        title: "Publication (NI-028)",
        body: "Publication is a single transaction that approves a validated version and switches the active dataset pointer. The revision delta is recorded and the previous pointer is retained on any failure; rejected data can never become the latest version.",
      },
    ],
    guardrails: [
      "Time is UTC with half-open day boundaries [00:00, next 00:00); incomplete current days are omitted or labeled, never compared against a full day.",
      "Ingestion is disabled by default: the default configuration keeps scheduled collection off with an empty source allowlist and zero request budgets. No scheduled collection is enabled today.",
      "The STOP_PUBLIC_COLLECTION markers and recorded pause files take precedence for the legacy collectors; new adapters cannot evade them, and the stopped supply audit is never auto-resumed.",
      "Provider revision is a new dataset version with a supersedes link and a changed-date report — the old version is never overwritten, and a fresh retrieval does not make an old observation fresh.",
    ],
    exampleIntro:
      "One source→transform→metric path, end to end, as implemented today:",
    exampleSteps: [
      {
        label: "Source",
        body: "SRC-BQ saved export flows_90d_raw.json — the 90-day conversion/payout cohort covering 2026-08-06 through 2026-11-04 (UTC, end exclusive) in the near-longitudinal research directory.",
      },
      {
        label: "Transform",
        body: "The NI-027 archive import verifies the file hashes offline; the NI-029 metrics build reads the verified aggregates read-only and deduplicates canonical events; the NI-028 stage-from-import command binds the resulting observations into a staged dataset version after re-verifying digests on disk.",
      },
      {
        label: "Metric",
        body: "observed_near_purchases v1 (availability A) — successful wrap.near conversions by collector accounts observed paying the three named intents treasuries. Published only as the observed cohort, never as market demand and never as protocol revenue.",
      },
    ],
  },

  readiness: {
    id: "readiness",
    title: "Model data readiness",
    body: "Before any model is fitted, a preregistered readiness gate decides which empirical question the saved archive can support. The gate fits nothing; the estimator itself is a later task, so no fitted results exist yet.",
    overall:
      "Overall verdict for the 90-day window 2026-08-06 through 2026-11-04: PROXY_ONLY_READY_WITH_LIMITS, with gross_fee_activity_v1 the selected specification. That verdict limits what any published model may claim — it does not license revenue or value-capture conclusions.",
    specs: [
      {
        spec: "true_revenue_daily_v1",
        verdict: "NOT_READY",
        codes: ["GATED_METRIC_NO_OBSERVATIONS", "PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01"],
        note: "The preferred dependent variable is the gated protocol-revenue metric with zero observations; the gate never fits around a missing series.",
      },
      {
        spec: "gross_fee_activity_v1",
        verdict: "READY_WITH_LIMITS",
        codes: [
          "MECHANICAL_FEE_VOLUME_RELATIONSHIP",
          "OQ02_JUDGING_ACCEPTANCE_RISK",
          "SINGLE_PROVIDER_LINEAGE_NOT_INDEPENDENT",
          "SHORT_SAMPLE_NO_LONG_RUN_CLAIM",
          "PROXY_NOT_PROTOCOL_REVENUE",
          "NO_CAUSAL_IDENTIFICATION",
        ],
        note: "Admitted only as the explicitly named fee-versus-volume proxy association: a largely mechanical fee-on-volume construction, single provider lineage, short sample, no causal or demand-elasticity reading, never labeled protocol revenue.",
      },
      {
        spec: "purchases_activity_v1",
        verdict: "READY_WITH_LIMITS",
        codes: ["COHORT_NOT_MARKET_DEMAND", "PAYOUTS_ARE_CASH_FLOWS_NOT_REVENUE"],
        note: "The optional cohort fallback carries cohort limits only: treasury-linked collectors are not market demand, and payouts are cash flows, not revenue.",
      },
      {
        spec: "supply_bounds_activity_v1",
        verdict: "REJECTED",
        codes: [
          "LOWER_BOUND_SERIES_NOT_EXACT_OUTCOME",
          "WINDOW_AGGREGATE_NOT_DAILY",
          "MINT_HEADER_AUDIT_INCOMPLETE",
        ],
        note: "Issuance and burn are conservative lower bounds over 30-day windows with a partially audited mint-header set (6 of 297); bounds never serve as exact daily regression outcomes.",
      },
    ],
    gateNumbers: [
      "At least 60 complete daily observations, and at least 10 per estimated parameter including the intercept.",
      "At most 3 substantive slopes in a first specification, with an intercept required.",
      "A minimum of 365 days before any long-run claim; shorter windows stay short-run and descriptive.",
    ],
    profiles: [
      "Across the 90-day window, both provider series show zero missing, zero-valued and negative days in the prepared table, and all four report invariants held.",
      "The two provider sources disagree on all 90 overlapping days; they are kept unsummed and the reconciliation stays unresolved (OQ-11).",
      "Readiness reports are generated locally from hash-pinned inputs and render byte-identically for identical inputs; they are not committed to the repository.",
    ],
  },

  reproduce: {
    id: "reproduce",
    title: "Reproduction",
    body: "Published analyses ship their inputs' provenance, code and locks so a reader can rerun them offline. The exact reproduction recipe is published together with the first quantitative release.",
    implementedIntro:
      "Commands that exist in the repository today (labels verified against the repository's own scripts):",
    implemented: [
      {
        command: "corepack pnpm test:api:unit",
        note: "Runs the API contract and source-capability unit suites offline (no database).",
      },
      {
        command: "corepack pnpm test:api:db",
        note: "Runs the database suites against a disposable PostgreSQL 18 cluster; requires local PostgreSQL binaries (pass --pg-bin when they are not on the default path).",
      },
      {
        command: "corepack pnpm --filter web test",
        note: "Runs the web unit and component suite.",
      },
      {
        command:
          "uv run --project apps/api python -m near_api.ingestion.archive --archive-root DIR --manifest FILE --cohorts FILE --database-url URL [--dry-run]",
        note: "NI-027 read-only archive import. Needs the authorized local archive bundle, which a fresh clone does not contain.",
      },
      {
        command:
          "uv run --project apps/api python -m near_api.datasets {stage,stage-from-import,validate,publish,show}",
        note: "NI-028 staging, validation and publication CLI; requires the operator database credentials.",
      },
      {
        command:
          "uv run --project apps/api python -m near_api.metrics build --spec FILE --out-dir DIR",
        note: "NI-029 metric emission into prepared manifests; offline, database-free.",
      },
      {
        command:
          "uv run --project apps/api python research/models/readiness.py --archive-root DIR --configs-dir research/models/configs --out-dir DIR",
        note: "NI-051 readiness gate over the local research archive; the report prints or writes locally and is not committed.",
      },
    ],
    unavailableIntro:
      "Deliberately not listed as runnable — these are future tasks, not implemented commands:",
    unavailable: [
      {
        command: "python -m near_api.cli ingest refresh …",
        note: "The scheduled refresh adapter (NI-030) is not implemented; polling stays disabled.",
      },
      {
        command: "python -m near_api.cli research run / verify …",
        note: "The estimator and publication CLI (NI-052–NI-054) is not implemented; the commands sketched in the reproducibility document's “planned” section do not exist yet.",
      },
      {
        command: "dataset download endpoints",
        note: "No public download API for datasets or raw inputs exists; delivery runs through the typed API of a later task, and raw archive access stays restricted regardless.",
      },
    ],
    environmentNote:
      "Install the frozen dependencies first: corepack pnpm install --frozen-lockfile and uv sync --project apps/api --frozen. The repository artifacts referenced above (the registry at apps/api/src/near_api/metrics/registry.py, the datasets CLI at apps/api/src/near_api/datasets/cli.py, the archive importer at apps/api/src/near_api/ingestion/archive.py, and the readiness gate at research/models/readiness.py with its configs) are inspectable in the repository checkout; this page does not serve or link them as downloads.",
  },
} as const;
