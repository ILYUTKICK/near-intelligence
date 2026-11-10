# Original research release — November 2026

Release task: **NI-070** (docs/TASKS.md, Epic 14). Authored 2026-11-10 on branch
`feat/ni-070-research-release` on top of `main` at `db0ec6a`, in the private
repository `ILYUTKICK/near-intelligence` (referenced throughout as checkout
paths; the repository is not publicly accessible and this document is not a
download). Content and evidence hashes for this release are pinned in the
companion manifest [original-research-release-2026-11.manifest.md](original-research-release-2026-11.manifest.md).

This is the finalization of the original research release: it publishes the
**actual verified outputs that exist today** — recorded descriptive findings,
the preregistered readiness-gate verdict, the implemented and
synthetic-verified estimator and its exact reproducible recipe — together with
an explicit **"real-archive fit run pending operator execution"** status. No
fitted coefficient, standard error, confidence interval, p-value or diagnostic
from the real archive exists anywhere in this release, and none may be invented
for it. The estimator (NI-052) is implemented and verified on synthetic
known-behavior fixtures only; no real-archive fit has been executed or
published (NI-051/NI-052/NI-054 cards record the real run as an operator step).

## 1. What this release publishes — and what it does not

Published today:

1. The complete original conditional thesis, publicly at `/research` (NI-014):
   fifteen sections, canonical hypotheses H1–H4 with statuses and weakening
   conditions, and the claim registry CL-001–CL-009 where every quantity is a
   typed object carrying its exact recorded value, scope, source and registered
   metric definition version. Contrary findings sit beside supporting ones.
2. The public methodology at `/methodology` (NI-013, updated by this release):
   provider register with rights decisions, the versioned definition registry,
   the collection/cleaning path, the model-data readiness verdicts, and the
   reproduction commands that the repository actually ships.
3. The model-data readiness verdict for the saved 90-day archive (NI-051,
   recorded real-archive run): overall `PROXY_ONLY_READY_WITH_LIMITS` with the
   named proxy `gross_fee_activity_v1` admitted — always with limits, never as
   protocol revenue (Section 2.1).
4. The implementation status of the deterministic model pipeline (NI-052/053/054):
   the fixed estimator and diagnostics battery are implemented, reviewed and
   synthetic-verified; the publication gate and public model APIs are
   implemented; the public model catalog at `/models` stays honestly empty
   until an operator publishes a reviewed run (Section 3).
5. This release report and its [content/evidence manifest](original-research-release-2026-11.manifest.md).

Not published, explicitly:

- **No fitted real-archive model results.** The real-archive fit run is
  pending operator execution; the exact reproducible recipe is published
  (Section 3). Until a run is verified and published through the NI-054 gate,
  the econometric evidence section of the public thesis reports an unmet
  release gate, not results.
- **No true protocol revenue claim.** The preferred daily economically
  attributable protocol-revenue series does not exist (open question OQ-01);
  the `true_revenue_daily_v1` specification is NOT_READY; gross fees, treasury
  payouts and purchases are never relabeled as protocol revenue.
- **No raw-data downloads.** Saved raw inputs stay in the operator's local
  archive and are shared only through verified, hash-checked handoffs
  (docs/REPRODUCIBILITY.md, docs/SOURCE_VERIFICATION.md).
- **No live/freshness claims.** Archival collection stays stopped
  (`STOP_PUBLIC_COLLECTION`); a fresh retrieval never makes an old observation
  fresh; every published value carries its recorded archive date.

## 2. Verified recorded findings

Every number below is copied from a merged task card in docs/TASKS.md, from a
tracked file in this repository, or from the recorded documents in the research
directories. Source citations are given per figure; the manifest pins the file
hashes of this report set.

### 2.1 Model data readiness verdict (NI-051; recorded real-archive gate run)

Window: `2026-08-06` through `2026-11-04` (UTC, end exclusive) — the preregistered
gate policy [readiness_gate_policy_v1.json](../models/configs/readiness_gate_policy_v1.json).

| Specification | Verdict | Reason codes (recorded) |
| --- | --- | --- |
| `true_revenue_daily_v1` | NOT_READY | `GATED_METRIC_NO_OBSERVATIONS`, `PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01` |
| `gross_fee_activity_v1` | READY_WITH_LIMITS | `MECHANICAL_FEE_VOLUME_RELATIONSHIP`, `OQ02_JUDGING_ACCEPTANCE_RISK`, `SINGLE_PROVIDER_LINEAGE_NOT_INDEPENDENT`, `SHORT_SAMPLE_NO_LONG_RUN_CLAIM`, `PROXY_NOT_PROTOCOL_REVENUE`, `NO_CAUSAL_IDENTIFICATION` |
| `purchases_activity_v1` | READY_WITH_LIMITS | `COHORT_NOT_MARKET_DEMAND`, `PAYOUTS_ARE_CASH_FLOWS_NOT_REVENUE` |
| `supply_bounds_activity_v1` | REJECTED | `LOWER_BOUND_SERIES_NOT_EXACT_OUTCOME`, `WINDOW_AGGREGATE_NOT_DAILY`, `MINT_HEADER_AUDIT_INCOMPLETE` (archive numbers: 6 of 297 mint headers audited) |

Source: docs/TASKS.md NI-051 card (Verification and Result blocks, 2026-11-07);
the verdict strings and reason-code semantics are pinned by the tracked gate
code [readiness.py](../models/readiness.py) and the preregistered
specification configs under [configs/](../models/configs/).

Window profiles recorded by the same run: both provider series show zero
missing, zero-valued and negative days across the prepared 90-day table; the
two provider sources disagree on all 90 overlapping days and are kept unsummed
(the fee-reconciliation open question OQ-11 stays unresolved); all four report
invariants held; double runs over the real archive rendered byte-identical
JSON/Markdown reports (no wall-clock fields; inputs pinned by SHA-256). The
generated readiness reports stay local by design and are not committed.

Gate thresholds (tracked policy): at least 60 complete daily observations, at
least 10 observations per estimated parameter including the intercept, at most
3 substantive slopes, intercept required, 365-day minimum before any long-run
claim. The 90-day window therefore cannot establish a long-term stable
mechanism under the project's own rules.

### 2.2 Exact reconciliation of the recorded flows (NI-029; recorded operator evidence)

The NI-029 verification (docs/TASKS.md NI-029 card, 2026-11-07) reconciled the
saved archive exactly, in Decimal arithmetic at the `NUMERIC(78,30)` storage
scale, read-only:

- Payout matching reproduced **3,165 of 3,165 matched pairs with zero issues**;
  payout total **1,405,659.135989071036891726256814 NEAR**.
- Purchases aggregated to **524,480.127692882832410490617319 NEAR over 54,991
  events**.
- Exclusions reported, never silently dropped: **502,794 NEAR** of internal
  treasury hops, **7,751.94972615998997116 NEAR** of other-sender inflows, and
  the 14 out-of-window 2026-11-04 transfers.
- USD estimates reconciled exactly with the saved 90-day totals at full
  precision; fee basis points reconcile at the storage scale; supply stocks,
  net changes and conservative bounds reproduce the saved summary exactly; the
  purchases/issuance ratio is published only as an upper bound.

These are the same figures the claim registry publishes as CL-001/CL-003
(scope: the 90-day observed cohort of accounts withdrawing to the three
selected treasury wallets — not market demand). CL-001 and CL-003 are different
flows and are never added as independent token demand.

### 2.3 Fixed deterministic estimator and diagnostics battery (NI-052, NI-053; implemented, synthetic-verified)

The estimator ([fit.py](../models/fit.py), preregistered settings in
[fit_configs/gross_fee_activity_v1_fit.json](../models/fit_configs/gross_fee_activity_v1_fit.json))
implements exactly the declared specification, nothing else:

- Design: `Δlog` of the declared dependent/explanatory variables over
  calendar-adjacent complete pairs only; strict positivity checked on the
  exact Decimal sources (genuine zeros are structured errors — never epsiloned,
  interpolated or silently dropped); explicit finite float64 conversion.
- Estimation: OLS through the already-locked statsmodels 0.15.0 with preregistered
  Newey–West HAC covariance (Bartlett kernel, fixed `maxlags 7` under
  `maxlags_rule: fixed`, `use_correction` and `use_t` from the config — never
  data-selected). Explicit intercept; parameter-count, rank and condition
  checks run before estimation; a rank-deficient design is a structured error,
  never fitted through a pseudo-inverse or column dropping.
- No p-value-driven search anywhere: the design columns are exactly the
  declared ones (structural invariant), and no variable, sample or lag choice
  uses p-values.
- Output: a deterministic manifest (same inputs/config/lock render it
  byte-identically on one platform; cross-platform comparison under the
  declared tolerances rtol `1e-8` / atol `1e-10`), carrying the gate exclusion
  table verbatim, the exact-decimal design source hash, coefficients/SE/95% CI,
  the limitations attached verbatim, and the environment (Python/numpy/scipy/
  statsmodels/BLAS, operator-provided code commit, dependency lock hash).
- Synthetic verification (NI-052 card, 2026-11-08 — never the real archive):
  an exact-construction archive (`fees = 0.015 × volume`) recovers the known
  coefficients intercept 0 / slope 1 within atol 1e-10; the wrapper matches a
  direct statsmodels OLS+HAC call on the same design to 1e-15; HAC settings
  serialize from the config and changing maxlags moves standard errors but not
  point estimates; 20 synthetic tests cover rank failure, zero policy,
  byte-identical double runs and CLI exit codes.

The diagnostics battery ([diagnostics.py](../models/diagnostics.py),
preregistered in
[diagnostics_configs/gross_fee_activity_v1_diagnostics.json](../models/diagnostics_configs/gross_fee_activity_v1_diagnostics.json))
is implemented the same way (NI-053 card, 2026-11-08): the gate's
sample/exclusion table verbatim; the coefficient/SE/95% CI table; ADF (fixed
maxlag, autolag disabled) and KPSS (fixed nlags) with settings recorded next to
every result; residual ACF, Ljung–Box at declared lags [3, 7] with
`model_df` consuming the estimated parameter count; Breusch–Pagan (the
preregistered response to a rejection is the already-declared HAC covariance —
no reweighting, no removal); Cook's distance flags at the config's 4/nobs
threshold (flagged days reported, sample unchanged); sensitivity limited to the
preregistered presets (HAC maxlags 3 and 14 when the sample supports them, the
alternate provider source, and the alternate price basis recorded
`not_applicable` with a reason when no bound variable uses a price-basis
dimension); interpretation rendered only from the fixed bounded-association
template (`bounded_association_v1`), never authored economics text. 30
synthetic tests compare every battery output to direct statsmodels calls.

Limitations attached verbatim to the admitted specification
([gross_fee_activity_v1.json](../models/configs/gross_fee_activity_v1.json)):
the mechanical fee–volume construction warning (provider gross fees are
reported as a fee applied to the same provider's reported volume, so a
fee-on-volume association largely restates the effective fee rate and must be
displayed before any coefficient interpretation); both variables share one
provider lineage (Dune), so the association is not independent confirmation of
anything; the output is the named proxy association only — never protocol
revenue (OQ-01), with H1/H4 staying unresolved (OQ-02 judging risk). Prohibited
labels: protocol_revenue, token_valuation, causal_effect, demand_elasticity,
sustainable_revenue.

### 2.4 Publication gate and public model APIs (NI-054; implemented, catalog honestly empty)

The publication gate
(`apps/api/src/near_api/research/publication.py`) verifies a run bundle
offline and fail-closed through sixteen named checks (bundle completeness and
types; the content-addressed approval binding — reviewed bytes must equal
published bytes; the data manifest pinning one archive state identically
across fit, diagnostics and readiness artifacts; one code commit; the frozen
`uv.lock` hash checked against the checkout; every config hash checked against
the committed preregistered files; cross-manifest identity; design and result
consistency under the declared tolerances; diagnostics completeness with the
prereqistered sensitivity presets only; limitations attached verbatim;
reproduction tolerances). Publication writes one immutable, write-once,
published-only row (`app.model_runs`, migration 0010, FORCE RLS,
content-derived run id); rejected, failed or unreviewed runs have no storage
and can never look like results. The six public GET routes
(`/api/model-runs[/{run_id}[/manifest]]`, `/api/model-definitions[/{model_id}
[/readiness]]`) project only published rows and import nothing from the
research package, so reading a published result can never trigger a fit or a
provider call. Source: docs/TASKS.md NI-054 card (2026-11-08; 53 offline gate
tests + 17 public-API tests recorded there).

Because no real-archive run has been produced and approved, **the public model
catalog is empty today by design** — the honest "no published model yet" state,
never a placeholder result. This release does not seed it.

## 3. Real-archive fit run — pending operator execution

The saved research archive is local to the operator machine and is never
committed (AGENTS.md repository sharing scope), so the real fit run is an
operator step recorded as evidence, exactly as recorded in the NI-051/NI-052/
NI-053/NI-054 cards. The reproducible recipe (verbatim from
docs/REPRODUCIBILITY.md and the NI-052 card):

```sh
uv sync --project apps/api --frozen
# NI-051 readiness gate (decides which empirical question is admissible):
uv run --project apps/api python research/models/readiness.py \
    --archive-root /path/to/research --configs-dir research/models/configs \
    --out-dir research/models/reports
# NI-052 fixed deterministic estimator (same specification, unchanged):
uv run --project apps/api python -m near_api.research fit \
    --archive-root /path/to/research --out-dir research/models/reports \
    --code-commit <git sha>
# NI-053 diagnostics battery over the same fit:
uv run --project apps/api python -m near_api.research diagnostics \
    --archive-root /path/to/research --out-dir research/reports/<run> \
    --code-commit <git sha>
# NI-054 offline verification of the run bundle, then operator publication:
uv run --project apps/api python -m near_api.research verify \
    --bundle research/reports/<run> --offline
uv run --project apps/api python -m near_api.research publish \
    --bundle research/reports/<run> \
    --database-url <near_operator psycopg URL>
```

The estimator refuses to fit unless the gate verdict for
`gross_fee_activity_v1` is `READY`/`READY_WITH_LIMITS` on the same archive, and
publication refuses anything that fails the sixteen checks. Until that operator
run exists, is verified, reviewed and published, every model-facing public
surface states the pending status above and the catalog stays empty.

## 4. Thesis audit: original product plan → delivered product

The original plan ([PRODUCT_PLAN.md](../../product-plan/PRODUCT_PLAN.md),
version 1, 4 November 2026) specified five public/private sections (Thesis →
Data → Model → Strategy → Portfolio) with its own hypothesis list H1–H6. Its
numbering and Strategy/Portfolio scope are **superseded** for the new product
by docs/INVESTMENT_THESIS.md (fifteen sections, canonical H1–H4, claim registry
CL-001–CL-009) and docs/MVP_SCOPE.md; this mapping preserves the original
numbering as historical reference and claims no numeric remapping (the thesis
states explicitly: "These H1–H4 differ from the old product-plan's H1–H6. No
numeric remapping is valid without a semantic mapping.").

### 4.1 Section mapping (original numbering preserved)

| Original plan section | Current-product status |
| --- | --- |
| 01 Thesis (`/thesis`, H1–H6 statuses, evidence links) | **Delivered, respecified.** The public thesis lives at `/research` (NI-014): fifteen sections, four canonical hypotheses with recorded statuses, claim registry CL-001–CL-009. The old H1–H6 are not remapped (see 4.2). The old "RevisionLog/hypothesis status automation" ideas are not built (automatic hypothesis monitoring is P2-excluded). |
| 02 Data (`/data`, metric cards, events table, CSV export) | **Delivered, respecified.** `/data` explorer (NI-015) over the versioned metric registry (NI-029/NI-031, 19 immutable v1 definitions) and the NI-032 delivery APIs; the landing strip (NI-012) binds three approved metrics. Exact saved-sum reconciliation delivered (NI-029, Section 2.2). The old "operations ledger table" (raw event rows with tx/receipt) is **not** implemented publicly — raw events are not a public surface; delivery is through prepared, validated dataset versions. Chart CSV export of the exact frozen selection is delivered (NI-034/NI-057); the document-level Markdown ZIP export is delivered separately (NI-056/NI-057/NI-058). |
| 03 Model (`/model`, assumption/scenario tabs, stress test) | **Partially delivered, honestly bounded.** The scenario/assumption simulator is P2-excluded (docs/MVP_SCOPE.md). The econometric core was delivered as the preregistered pipeline: readiness gate (NI-051) → fixed estimator (NI-052) → diagnostics battery (NI-053) → publication gate + public model APIs and pages (NI-054). Honest status: **no real-archive fit published; fit run pending operator execution** (Section 3). The old plan's econometric caution ("корреляция не объявляется причинностью" — correlation is never declared causality) is enforced structurally by the prohibited-labels list and the bounded-association interpretation template. |
| 04 Strategy (rule builder, condition evaluation) | **Excluded from MVP scope** (docs/MVP_SCOPE.md P2 list: rule engine/strategy screens belong to the legacy plan; no trading execution in MVP). Not built; no page advertises it. |
| 05 Portfolio (private positions, PnL) | **Excluded from MVP scope** (docs/MVP_SCOPE.md: no portfolio product in MVP). Not built; no page advertises it. |
| Development order 1–6 | 1–2 delivered (registries + Thesis/Data); 3 delivered as the preregistered econometrics pipeline (scenario comparison excluded); 4–5 excluded by scope; 6 partially delivered (one bounded scheduled refresh adapter implemented opt-in and disabled by default, NI-030, with one recorded authorized live smoke; no daemon exists in MVP). |

### 4.2 Old hypotheses H1–H6 — semantic fate (no numeric remapping)

The old plan's hypothesis states (PRODUCT_PLAN.md, "Данные и что уже есть"):

| Old hypothesis (paraphrased) | Semantic fate in the delivered product |
| --- | --- |
| Old H1–H3 (repeat conversions, channel distribution, revenue dependence — "require separate research") | Still unresolved. The revenue-dependence question is carried by canonical H1 (Unresolved): the preferred revenue series is NOT_READY (OQ-01) and the admitted proxy is explicitly not revenue. Channel-distribution/market-wide activity metrics stay gated in the registry (availability G) — never emitted from cohort data. |
| Old H4 (own-product revenue needs a recipient map) | Carried as partial evidence only: the fee-provenance cohort (CL-005) and the strict inventory minimum (CL-006) establish fee funding on narrow dates; the full fee-funded share is unknown (pooled balances prevent physical tracing). Canonical H2 (value capture) = Partial evidence. |
| Old H5 (cost coverage needs defined costs) | Not measurable: costs are unknown (thesis §11/§14; `protocol_profit_usd` is a gated P2 concept). No metric published; the gap is stated, not filled. |
| Old H6 (repeatable conversions/payouts measured; fee provenance confirmed in limited scope) | **Measured and published**: CL-001 (54,991 conversion events; 524,480.127692882832410490617319 NEAR), CL-003 (1,405,659.135989071036891726256814 NEAR in 3,165 matched payouts; 502,794 NEAR internal hops excluded), CL-005/CL-006 (narrow-date fee provenance). This is the old plan's "already confirmed by research" list, now delivered as a public, source-bound registry. |

### 4.3 Canonical H1–H4 — recorded statuses (unchanged by this release, now fully evidenced)

- **H1 Revenue growth — Unresolved.** Daily attributable protocol revenue not
  established (OQ-01); `true_revenue_daily_v1` NOT_READY; the admitted proxy
  association is a largely mechanical fee-on-volume construction and is
  insufficient for H1 by itself.
- **H2 Value capture — Partial evidence.** Narrow-cohort fee funding
  established (CL-005, CL-006); the full fee-funded share of observed purchases
  is unknown.
- **H3 Supply offset — Not supported on current evidence.** Total supply grew
  over the measured window (CL-007) and purchases are not burns; gross
  issuance/burn are conservative lower bounds with the mint-header audit
  incomplete at 6 of 297 (CL-008); the `supply_bounds_activity_v1`
  specification is REJECTED as a regression outcome.
- **H4 Retention share — Unresolved.** A compatible revenue numerator and
  economic-activity denominator are missing; the capture-rate metric is gated
  and never emits a value from gross fees or cash payouts.

### 4.4 Claim registry CL-001–CL-009 — publication status

All nine claims are delivered at `/research` with full typed quantity tables
(41 quantities independently audited against the recorded documents during the
NI-014 review). All quantities remain bound to the recorded 2026-11-04/05
evidence dates; none was refreshed or re-derived for this release. The release
adds no new claims; the econometric evidence section carries the release status
instead of numbers (Section 1/3).

## 5. Contrary evidence and negative findings — preserved

The release publishes contrary evidence with the same prominence as
supporting evidence. Nothing below was weakened or removed:

- Acquired NEAR quantities **declined** across successive 30-day windows —
  244,845.70 → 165,809.44 → 113,825.00 NEAR; the last window fell 31.35% from
  the preceding one (CL-002). USD values stayed near one level only because the
  quantity-weighted price rose (CL-004 decomposition; arithmetic, not
  causation).
- Observed purchases are **small relative to supply growth**: 7,936,181.547057263680300503519861
  NEAR exact boundary supply increase (+0.60915% rounded) over the same 90
  days; purchases equal 6.60872% of that increase as a scale comparison
  (CL-007). Purchases are never subtracted from supply.
- Gross issuance ≥ 8,012,834 NEAR and burns ≥ 76,652 NEAR are **conservative
  lower bounds**; the mint-header audit stopped at 6 of 297 verified headers
  and the unverified remainder is never assumed zero (CL-008). The
  `supply_bounds_activity_v1` regression specification is **REJECTED**
  (NI-051) — bounds never serve as exact daily regression outcomes.
- Treasury retention is **reversible**: governance-controlled multisig/DAO
  balances are not permanent supply removal (CL-009).
- The two provider fee/volume series **disagree on all 90 overlapping days**
  and are kept unsummed; the reconciliation stays unresolved (OQ-11).
- The admitted proxy carries the **mechanical fee–volume construction** and the
  **single-provider lineage** limits, and the **OQ-02 judging risk** — the
  hackathon's evaluation may not accept the limited empirical question — is
  recorded rather than argued away (docs/MVP_SCOPE.md research feasibility
  gate).
- **No true protocol revenue claim exists anywhere in the release** (OQ-01
  gate; `PROXY_CANNOT_PASS_AS_PROTOCOL_REVENUE` is a hard gate invariant).

## 6. Rights, attribution and publication visibility

- **Providers and rights** mirror the register reviewed 5 November 2026 with
  the 6 November role-B verification and the single OQ-03 probe
  (2026-11-06T19:13:45Z) recorded in docs/SOURCE_VERIFICATION.md; the public
  methodology page renders the same decisions (access status, verified periods,
  rights decision per provider). A documentation page being reachable does not
  establish entitlement, an SLA, full historical coverage or redistribution
  rights.
- **Attribution:** provider-reported series (SRC-LLAMA/SRC-DASHBOARD lineage,
  shared Dune lineage) are labeled provider methodology, revisable and
  source-qualified — never independent confirmation; the DefiLlama adapter
  describes its own accounting and is cited as such. USD valuations carry
  provider attribution and stay approximations at recorded daily price marks.
- **Visibility rules enforced on public pages:** no raw-data downloads; no
  private editor metadata (document/revision/user identifiers) in public
  content (asserted by tests); the repository is private, so public pages
  reference repository artifacts as checkout paths, never hyperlinks (NI-013
  link allowlist, test-enforced); contrary and supporting claims render through
  the same component; missing values render as explicit states, never zeros.
- **Release documents themselves:** this report and its manifest are repository
  Markdown (permitted content per AGENTS.md repository sharing scope). They
  contain no raw artifact bytes, no credentials, no private editor metadata and
  no absolute local filesystem paths.

## 7. Evidence base and metric definition versions

- Metric definitions: the versioned registry
  (`apps/api/src/near_api/metrics/registry.py`) — 19 immutable v1 definitions
  with deterministic identities (NI-029/NI-031). The claims on public pages
  reference: `observed_near_purchases` v1 (A), `conversion_count` v1 (A),
  `treasury_payouts_near` v1 (A), `treasury_payout_count` v1 (A),
  `estimated_purchase_usd` v1 (B), `near_price_usd` v1 (P),
  `provider_intents_volume_usd` v1 (P), `provider_gross_fees_usd` v1 (P),
  `net_supply_change_near` v1 (A), `purchases_to_net_supply_pct` v1 (A),
  `issuance_lower_bound_near` v1 (B), `burns_lower_bound_near` v1 (B),
  `purchases_to_issuance_upper_pct` v1 (B), `treasury_balance_near` v1 (A);
  `strict_fee_conversion_equivalent_near` is a catalog concept (B) recorded as
  not registered in the code registry. Three gated definitions
  (`protocol_revenue_usd`, `protocol_capture_rate`, `fee_funded_buybacks_near`)
  always emit null with recorded reasons.
- Recorded input integrity (as recorded in the NI-012 card, 2026-11-08):
  `research/near-longitudinal/data/flows_90d_raw.json` — 3,147,156 bytes,
  SHA-256 `7680c5755c2efe5c1694544e68ede0f1f609c29b033ed5d9bdc62899e2024be8`;
  `research/near-dollar/analysis/daily.json` — 62,432 bytes, SHA-256
  `99fdb09823ff5dd80a46387f957bb6f54f71087abee87542e65cdd3f0674b8cd`.
- Findings documents (tracked): [near-longitudinal/FINDINGS.md](../near-longitudinal/FINDINGS.md),
  [near-dollar/FINDINGS.md](../near-dollar/FINDINGS.md),
  [near-provenance/FINDINGS.md](../near-provenance/FINDINGS.md) (with
  [attribution rules](../near-provenance/analysis/ATTRIBUTION_RULES.md)),
  [near-supply/FINDINGS.md](../near-supply/FINDINGS.md),
  [near-treasury/FINDINGS.md](../near-treasury/FINDINGS.md); canonical thesis
  docs/INVESTMENT_THESIS.md; metric catalog docs/METRIC_CATALOG.md; source
  register docs/SOURCE_VERIFICATION.md; reproducibility docs/REPRODUCIBILITY.md.
- Task evidence: docs/TASKS.md cards NI-012/013/014, NI-029, NI-051, NI-052,
  NI-053, NI-054, NI-061, NI-063 (each with its own verification record).

## 8. Limitations of this release

- The econometric section is a **status, not a result**: the estimator is
  synthetic-verified only; the real-archive fit run is pending operator
  execution. Release-checklist item "one published deterministic empirical
  model reproduces offline" is **not yet met** and is not claimed.
- The saved archive covers one 90-day cohort of treasury-linked collector
  accounts; it is not whole-market demand, and the 90-day window cannot
  establish a long-term mechanism under the project's own gate thresholds.
- Gross issuance/burn remain incomplete lower bounds; daily protocol revenue
  does not exist; the provenance period (narrow dates) is much shorter than the
  90-day cohort; the treasury index cannot establish all disposal/lock paths.
- Publication visibility is desktop-scoped per the 8 November 2026 user scope
  update (no mobile passes claimed by this release).
- The release does not change any metric definition, gate threshold,
  preregistered config or claim value; it publishes existing verified state and
  honest statuses only.
