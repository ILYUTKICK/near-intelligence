/**
 * Reviewed editorial copy for the public routes (NI-011, NI-013).
 *
 * Every string here is deliberately free of metric observations: quantitative
 * claims are bound to versioned datasets and definitions by later tasks
 * (NI-012, NI-014) and must never be typed by hand. The methodology content
 * (NI-013) carries methodology facts only — periods, coverage counts, gate
 * thresholds and verdicts, each mirroring a recorded document. No promises,
 * no live claims, no unfinished feature announcements.
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

export const research = {
  title: "Research",
  standfirst:
    "The published thesis with its supporting and contrary evidence. Quantitative sections are bound to versioned datasets; this page is the reading structure they will live in.",
  outline: [
    {
      id: "executive-summary",
      title: "Executive summary",
      body: "The complete argument in one place, with explicit status for every claim.",
    },
    {
      id: "question",
      title: "The question",
      body: "Does cross-chain adoption translate into sustainable revenue and measurable NEAR token value capture?",
    },
    {
      id: "ecosystem",
      title: "Ecosystem and activity",
      body: "What is observable on-chain, and what those observations can and cannot support.",
    },
    {
      id: "h1",
      title: "H1 — Revenue generation",
      body: "Status: to be published with the reviewed findings. This anchor exists so citations can already reference the section.",
    },
    {
      id: "h2",
      title: "H2 — Value capture",
      body: "Status: to be published with the reviewed findings.",
    },
    {
      id: "h3",
      title: "H3 — Retention effects",
      body: "Status: to be published with the reviewed findings.",
    },
    {
      id: "h4",
      title: "H4 — Supply dynamics",
      body: "Status: to be published with the reviewed findings.",
    },
    {
      id: "limits",
      title: "Limits and contrary evidence",
      body: "Evidence against the thesis is published with the same care as evidence for it.",
    },
  ],
} as const;

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
