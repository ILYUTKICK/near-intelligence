# Investment thesis — conditional, evidence first

Editorial foundation, 5 November 2026. Historical evidence mainly spans **2026-08-06 ≤ UTC date < 2026-11-04**. This document is an implementation-ready research outline with actual descriptive findings; econometric outputs have not been fitted in this phase. No price target or recommendation follows from these observations.

## 1. Executive summary

**NEAR's long-term investment case depends on its ability to convert growing cross-chain activity into sustainable protocol revenue and measurable token value capture.** Existing saved evidence supports a regularly operating conversion/payout channel within a defined cohort. It challenges a simple accelerating-demand narrative: NEAR quantities acquired declined across successive 30-day windows, and observed acquisitions are small relative to positive net supply growth. Full fee provenance and economically attributable daily protocol revenue remain unresolved.

The appropriate current assessment is mixed evidence with important identification gaps, not a proven investment case. A working research product should make both findings and gaps inspectable.

## 2. Research question and canonical hypotheses

| ID | Question | Current assessment / falsification condition |
| --- | --- | --- |
| H1 | Does increasing Intents activity correspond to sustainable protocol-revenue growth? | Unresolved: daily attributable revenue not established. Weaken if comparable net revenue stagnates/falls while activity rises after adjusting for policy/price/costs; gross-fee association alone is insufficient |
| H2 | How much generated revenue translates into measurable buybacks or other capture? | Partial route evidence only; full fee-funded share unknown. Weaken if executed fee receipts cannot be reconciled to conversion/retention, or material outflows reverse accumulation |
| H3 | Under what conditions can buybacks and burns offset issuance? | Total supply grew; purchases are not burns. A supply-offset claim fails without actual destruction matching issuance. Liquid-supply effects require a separate verified retention/lock model |
| H4 | Does protocol retention share rise or fall with adoption? | Unresolved: compatible revenue numerator and economic-activity denominator missing. Weaken if matched accrual retention falls persistently or costs/incentives exceed retained revenue |

These H1–H4 differ from the old product-plan's H1–H6. No numeric remapping is valid without a semantic mapping.

## 3. Ecosystem overview

Distinguish base-chain execution/gas economics, Intents-related product activity, distribution/affiliate economics and governance-controlled accounts. A token can be the settlement/treasury asset without every dollar of ecosystem activity accruing to token holders. The official [tokenomics discussion](https://www.near.org/blog/evolving-near-tokenomics) describes governance discretion; treat it as policy context rather than a guaranteed cashflow claim.

## 4. Cross-chain execution and Intents

The relevant observed mechanism is incoming multi-asset balances → exchange into wrap.near → native withdrawals/treasury receipts → subsequent holdings or use. [Fee configuration](https://docs.near-intents.org/integration/distribution-channels/1click-api/fee-config) describes declared appFees; successful onchain receipt and economic entitlement must be proven separately. Common pooled balances prevent physical tracing of interchangeable tokens from a particular fee to a particular payout.

## 5. Adoption and network activity

Provider volume can describe Intents turnover; it is not independently reconstructed market-wide activity. The measured cohort contains accounts that withdrew to three selected treasury wallets during the 90-day window. Collector accounts are not users, customers or independent integrators. Keep network transaction/active-address series separate and unavailable until defined and sourced.

## 6. Revenue generation

Gross provider fees are not protocol profit. Source-qualified fee/volume series can support an exploratory association, with mechanical fee-volume construction, revisions, incentive policy and endogenous adoption disclosed. Do not allocate monthly captured revenue across days. [Saved USD analysis](../research/near-dollar/FINDINGS.md) documents provider disagreement and price sensitivity.

## 7. Revenue capture and actual observed findings

| Claim ID | Observation, defined scope | Source / reproduction |
| --- | --- | --- |
| CL-001 | 54,991 successful observed conversion events acquired **524,480.127692882832410490617319 NEAR** across the 90-day cohort; conversions occurred in all 90 days | [Longitudinal findings](../research/near-longitudinal/FINDINGS.md), [summary](../research/near-longitudinal/analysis/summary.json); `python3 research/near-longitudinal/scripts/analyze.py` |
| CL-002 | Acquired quantities in successive 30-day windows: **244,845.70 → 165,809.44 → 113,825.00 NEAR**, rounded for display. Last window fell **31.35%** from preceding window | Same source; exact values in [USD summary](../research/near-dollar/analysis/summary.json) and underlying outputs |
| CL-003 | **1,405,659.135989071036891726256814 NEAR** in 3,165 matched native payouts to three wallets; excludes **502,794 NEAR** of internal treasury transfers | Same longitudinal source and payout matching artifacts; matched amount/recipient with up-to300s tolerance, not full parent-graph proof |
| CL-004 | Approximate USD acquisitions (daily start price): **$437,374 → $557,914 → $547,026**; last change **−1.95%**, versus **−5.45%** using end-of-day alternative | [USD findings](../research/near-dollar/FINDINGS.md), [summary](../research/near-dollar/analysis/summary.json); `python3 research/near-dollar/scripts/analyze.py` |
| CL-005 | API creation-cohort 1–3 Nov: **21,361** records; **8,420** matched fee events, including **3,377** exact-integer formula matches | [Provenance findings](../research/near-provenance/FINDINGS.md), [final summary](../research/near-provenance/analysis/final_summary.json); audit_cohort.py |
| CL-006 | Strict short-window inventory model yields **1,427.13 NEAR equivalent**, **5.69%** of the earlier week's observed purchases; modeled route minimum **1,407.21 NEAR equivalent** after subtracting all closing stock | Same provenance source and strict inventory summary; not physical token tracing, not extrapolatable to 90 days |

CL-001 and CL-003 are different flows and must not be added as independent token demand. Even the route attribution in CL-006 is a conservative accounting model, not an exact causal estimate of market impact. See [attribution rules](../research/near-provenance/analysis/ATTRIBUTION_RULES.md).

## 8. Token economics

| Claim ID | Observation / limit | Source |
| --- | --- | --- |
| CL-007 | Exact boundary total-supply increase over same 90 days: **7,936,181.547057263680300503519861 NEAR**, **+0.60915%** rounded; purchases equal **6.60872%** of that increase as a scale comparison | [Supply findings](../research/near-supply/FINDINGS.md), [summary](../research/near-supply/analysis/summary.json); analyze.py |
| CL-008 | Gross issuance **≥8,012,834 NEAR**, burns **≥76,652 NEAR** (rounded down lower bounds); full mint audit completed only **6/297** headers. Purchases/gross issuance has an upper bound about **6.54551%** | Same source; not exact gross totals; archival collection stopped |
| CL-009 | Treasury role-index audit found no indexed outgoing receipt-actions in 5 Oct–3 Nov for selected wallets; governance-controlled retention does not establish permanent supply removal | [Treasury findings](../research/near-treasury/FINDINGS.md), data/summary.json; analyze.py |

Accounting identity for total supply: ΔS = gross issuance − actual burns (plus any separately identified protocol adjustments). Ordinary purchases/treasury transfers are not a subtraction. Liquid circulating supply requires a distinct operational definition and verified locks/outflows; it is not measured here. A thought experiment comparing acquisitions with issuance measures scale, not deflation or net selling pressure.

## 9. Econometric evidence

No fitted model, coefficient, confidence interval or causal conclusion is asserted here. [Methodology](ECONOMETRIC_METHODOLOGY.md) specifies data readiness, exploratory proxy alternatives, stationarity/autocorrelation checks and reproducible reporting. Release status (NI-070, November 2026): the preregistered readiness gate recorded overall `PROXY_ONLY_READY_WITH_LIMITS` with `gross_fee_activity_v1` admitted with limits, `true_revenue_daily_v1` NOT_READY (OQ-01) and `supply_bounds_activity_v1` REJECTED; the fixed deterministic estimator and diagnostics battery are implemented and synthetic-verified, and the real-archive fit run is pending operator execution under the published recipe — the release reports the unmet publication gate honestly instead of results. Statistical nonsignificance is a valid finding.

## 10. Alternative explanations

Price changes can reduce token quantity despite stable USD flows (CL-004). Fee-rate changes, rebates, recipient allocations, batching/accrual lags, treasury stock movements and source revisions can alter observed relationships. Simultaneous volume/fees may be mechanically linked. A growing collector's activity can aggregate many sources; concentration of collectors is not concentration of customers. General market conditions may jointly influence adoption and revenue.

## 11. Risks and counterarguments

Governance can change deployment/retention of acquired NEAR; fee competition can lower retained margins; costs/incentives are unknown; appFees may omit other business channels; source definitions and historical revisions disagree; treasury accumulation is reversible; positive supply growth persists. Existing evidence does not identify token holder contractual claims or a justified valuation multiple.

## 12. Long-term scenarios

Downside: adoption grows but retained revenue/fee rate falls and acquired assets are spent; no durable capture. Conditional base: recurring receipts and conversions persist with transparent retention, but remain modest relative to issuance and costs. Upside: independently reconciled revenue scales, costs are covered and governance implements verifiable durable capture. These are qualitative assumptions, not probability-weighted forecasts or price projections. Advanced simulation is P2.

## 13. Final assessment

The conversion channel is observable and recurrent in the selected cohort. Its NEAR quantity did not grow over the measured windows. Some fee-to-conversion attribution is established on narrow dates, but neither full 90-day fee funding nor sustained protocol-revenue growth is proven. Positive supply growth and discretionary treasury use constrain stronger value-capture claims. The investment thesis remains conditional on stronger revenue attribution, scale, costs and retention evidence.

## 14. Limitations

Cohort selection excludes converters without selected treasury payouts; index completeness is not independently universal; amount/time payout matching differs from full causal receipt graph; USD marks approximate execution; daily protocol revenue missing; provenance period much shorter than 90 days; gross issuance/burn incomplete; treasury index cannot establish all possible disposal/lock paths; no out-of-sample long-term validation or econometric run yet. Do not project observed 90 days into years without explicit assumptions.

## 15. Sources and reproducibility

Primary local findings and artifacts are linked per claim. [Metric catalog](METRIC_CATALOG.md), [source register](SOURCE_VERIFICATION.md) and [reproduction instructions](REPRODUCIBILITY.md) define exact scope. Official source code [DefiLlama adapter](https://github.com/DefiLlama/dimension-adapters/blob/master/fees/near-intents/index.ts) describes its own accounting; it is not proof of independent attribution. Future published claims must bind CL IDs to dataset/definition versions, code/lock/config hashes and an approved public evidence manifest. The original research release (NI-070, November 2026) documents the publication state, thesis audit and evidence manifest in [the release report](../research/reports/original-research-release-2026-11.md).
