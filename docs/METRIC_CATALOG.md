# Metric catalog

Canonical metric IDs below are stable; definition versions are immutable. Planned availability is not a promise of source access. [Source verification](SOURCE_VERIFICATION.md), [pipeline](DATA_PIPELINE.md), [thesis](INVESTMENT_THESIS.md).

Common period is UTC `[start,end)`. Flow aggregation sums days, stock aggregation takes a pinned boundary, ratio aggregation divides compatible sums. Zero requires verified completeness; missing is null. Every metric includes definition version, source lineage, exact/estimate/bound kind, observed/retrieved times, coverage and limitations. Financial precision follows [database policy](DATABASE_SCHEMA.md).

Availability codes: **A** saved observed data usable after import/rights validation; **P** provider-reported saved data, source-qualified and revisable; **B** bound/estimate only; **G** gated/unavailable until source/definition verified. Frequency below is observation frequency, not an SLA. MVP updates historical archives only by creating new versions; scheduling is opt-in.

| metric_id / priority | Definition and computation | Unit / frequency / source | Availability, limits and aggregation |
| --- | --- | --- | --- |
| network_transaction_count P1 | Count distinct successful transaction hashes by specified execution date, not receipts | count/day; SRC-BQ/indexer | G; define failed inclusions/contract scope; sum, dedup first |
| network_active_addresses P1 | Distinct specified role (signer or transacting account) within selected interval | addresses/day or interval; SRC-BQ | G; roles not interchangeable; daily distinct counts cannot sum to window unique users |
| network_new_accounts P1 | Successful account creation events under explicit direct/implicit-account policy | accounts/day; SRC-BQ | G; named/implicit creates need tested definition; not people |
| network_gas_fees_near P1 | Actual base-chain transaction gas charges, distinct from Intents product fees | NEAR/day; indexer/RPC outcome | G; RPC headers alone insufficient; sum exact raw costs |
| network_usage_growth P1 | (compatible current count/prior equal-window count−1)×100 | percent/window; derived | G; no missing/zero denominator; incomplete periods excluded |
| provider_intents_volume_usd P0 | Provider's daily gross cross-chain turnover, retained source-qualified | USD/day; SRC-LLAMA or SRC-DASHBOARD | P; definitions/revisions differ, no automatic dedup across providers; never sum both |
| intents_transaction_count P1 | Count distinct successfully executed swap IDs under documented provider universe | swaps/day; SRC-INTENTS | G for market-wide; short creation cohort is not full daily execution population |
| intents_average_size_usd P1 | Matching-universe volume / matching swap count | USD/swap/day; derived | G until definitions align; not volume divided by our collector conversion count |
| supported_network_count P1 | Count supported chain IDs in versioned official support list | networks/snapshot; official support API/docs | G; configuration coverage, not adoption; latest stock |
| integration_activity P2 | Executed activity by verified historical integration ID map | swaps/volume/day; provider export | G; collectors not integrations; mapping effective dates required |
| observed_near_purchases P0 | Sum positive wrap.near in successful token_diff with negative other asset, selected 90-day treasury-linked cohort | NEAR/day; SRC-BQ local longitudinal | A; acquisitions within pool, not all-market demand or proven fee-funded buybacks; sum Decimal |
| conversion_count P0 | Count canonical events satisfying observed_near_purchases definition | events/day; same | A; dedup account+intent/event under documented source key; not user swaps |
| treasury_payouts_near P0 | Matched successful native transfers from intents.near to three named wallets; exclude internal treasury hops | NEAR/day; local longitudinal | A; cash transfers, not accrual revenue/profit; matching scope/tolerance explicit. v1 aggregate (dimensions empty) and v2 per-recipient (dimensions.recipient = verified transfer receiver, one observation per named wallet) share the same matcher run: per day the three named-recipient v2 values must sum exactly to the v1 aggregate (enforced on delivery for the full-universe selection). v2 rows exist only in datasets rebuilt after NI-071 — operator archive rebuild, not a collector restart; older datasets report the v2 series honestly missing |
| treasury_payouts_near v2 comparison filter (NI-071) | The recipient dimension is the verified receiver of each matched transfer — the complete declared universe of the payout definitions; internal hops and non-treasury senders are excluded by the matcher quality rules | compared NEAR/day series; same matcher | A; the only added comparison dimension. No integrator/customer/collector classification is invented, and the provider `source` dimension stays single-value and never reconcilable (cross-source sums forbidden) |
| treasury_payout_count P0 | Count distinct matched transfer actions under payout definition | payouts/day; same | A; receipt-action identity, not tx count; sum |
| provider_gross_fees_usd P0 | Provider-reported Intents protocol+distribution gross fee definition | USD/day; SRC-LLAMA/SRC-DASHBOARD | P; not revenue retained by NEAR; source revisions and common Dune lineage |
| effective_gross_fee_bps P0 | 10,000 × compatible provider gross fees / volume | bps/day/window; derived | P; ratio of sums, not average tariff; zero denominator null |
| provider_reported_revenue_usd P1 | Provider's wallet-based reported captured revenue under exact adapter version | USD/day if entitled; SRC-LLAMA/DUNE | G for approved daily app series; separately named provider measure, not independently attributed protocol accrual revenue |
| protocol_revenue_usd P0 gate | Economically attributable gross revenue retained by defined protocol entity after distribution/rebates under chosen recognition basis | USD/day; reconciled fee/allocation ledger | G; missing allocation/cutoff/fee provenance; do not substitute gross fees or cash payouts |
| protocol_profit_usd P2 | Protocol revenue minus explicitly defined costs/incentives in same recognition basis | USD/day/window; operator economics | G; costs unknown; do not label revenue profit |
| protocol_capture_rate P0 gate | 100 × attributable protocol revenue / compatible gross generated fees | percent/day/window; derived | G; matching units/time/universe; cash sweeps may lag, no hard daily 0–100 clip hiding mismatch |
| revenue_per_transaction_usd P1 | Compatible protocol revenue / corresponding executed swap count | USD/swap/window; derived | G; denominator universe must align |
| protocol_revenue_growth P0 gate | Revenue change over equal complete windows using same definition/currency | percent/window; derived | G; no inference of sustainability from one rise |
| estimated_purchase_usd P0 | Σ daily observed_near_purchases × specified daily price; start-of-day baseline, end-of-day alternative | USD/day/window; longitudinal + SRC-PRICE | B; valuation estimate, not execution consideration; missing price→missing dollar value |
| near_price_usd P0 supporting | Saved provider NEAR/USD point at explicit timestamp, no inferred fill | USD/NEAR/day; SRC-PRICE | P; policy/precision/price timestamp retained; stock, not additive |
| total_supply_near P0 | total_supply from finalized indexed/RPC block header at selected boundary/hash | NEAR/boundary; SRC-NEAR-RPC + saved checks | A; four exact window boundary values; daily future series requires fresh verified data |
| net_supply_change_near P0 | Closing total_supply − opening total_supply over identical boundary window | NEAR/window; derived | A; exact boundary difference; no ordinary purchase subtraction |
| issuance_lower_bound_near P0 | Documented positive supply changes plus verified simultaneous burn, less conservative tolerance | NEAR/window; local supply | B lower; 6/297 headers audited, not full gross issuance |
| burns_lower_bound_near P0 | Documented negative supply changes plus verified simultaneous burn, less conservative tolerance | NEAR/window; local supply | B lower; not exact gas burn total |
| issuance_near P1 gate | Complete gross mint amount from all relevant protocol events/headers | NEAR/day/window; archival/indexer | G; do not use configured annual inflation instead of realized issuance |
| burns_near P1 gate | Complete actual token destruction with exact protocol event coverage | NEAR/day/window; archival/indexer | G; purchases/staking/treasury receipts are not burns |
| fee_funded_buybacks_near P0 gate | Reconciled executed conversion attributable to earned fees under documented mixed-pool accounting | NEAR/day/window; provenance ledger | G for full 90 days; use separately named narrow equivalent below |
| strict_fee_conversion_equivalent_near P0 | Conservative short-window inventory lower-bound value mapped at average actual conversion rates | NEAR-equivalent/window; local provenance | B model; 27 Oct–2 Nov only, fee execution subset 1–2 Nov; not physically tagged tokens |
| purchases_to_net_supply_pct P0 | 100 × observed purchases / positive net supply increase, matched window | percent/window; derived | A; scale context, not deflation/capture rate; net≤0→unavailable comparison |
| purchases_to_issuance_upper_pct P0 | 100 × observed purchases / strictly positive issuance lower bound | percent upper bound/window; local supply | B upper; rounding outward, not an exact share |
| treasury_balance_near P0 | Native account amount at block hash; report locked separately | NEAR/snapshot; SRC-NEAR-RPC | A saved 4 Nov point; not cumulative revenue or permanently removed supply |
| collector_concentration_hhi P1 | Sum squared shares of observed purchases by collector account in fixed cohort | index0–1/window; longitudinal | A; execution-account concentration, not customer concentration; unsummable daily values |
| ecosystem_application_activity P1 | App contract activity under a versioned app/contract classification | count/volume/day; indexed events | G; classification coverage and bots must be stated |
| ecosystem_contribution_share P1 | App's attributable compatible activity / same-universe total | percent/window; derived | G; no arbitrary recipient→business-source mapping |
| ecosystem_growth P1 | Change in a defined ecosystem activity metric over complete equal windows | percent/window; derived | G; no generic composite growth score |

## Publication rules

P0 means implement the metric or its explicit honest unavailability/gate, not fabricate its values. Core usable charts use A/P/B metrics with appropriate labels. P1 network/ecosystem additions require actual verified history first. Preserve source-qualified definitions rather than silently replacing one provider with another. Source disagreement and bound quality must propagate through charts, insight contexts, model readiness, public claims and exports.

A metric-definition change increments version and forces new prepared datasets/chart definitions where affected. A source-only observation revision creates a new dataset version with unchanged definition version and a changed-date report. Do not use the old name “buybacks” indiscriminately for observed_near_purchases. All additions need formula/unit/time/source/quality tests and an explicit explanatory limitation.


## NI-083 descriptive history extension

The saved-history operator preparation emits existing immutable provider volume
and gross-fee metric definitions over their actual source-specific coverage,
with `dimensions.source` preserved. It does not relabel gross fees as revenue or
splice providers. Missing pre-history and absent dates generate missing delivery
points, while source-reported fee zeros remain observations with an explicit
quality note. The full prepared source files and their recorded manifest hashes
are bound through NI-028 inputs; generated records stay local.

The research summary computes **10,000 × sum(gross fees) / sum(volume)** on the
intersection of observed dates of the same qualified source. A zero denominator
or empty intersection yields null. This is a descriptive effective gross fee
rate, not protocol capture, tariff, margin or causal effect. Whole-range volume
and fee subtotals can cover different dates; matched subtotals and day counts are
shown separately for the ratio. Complete-month/quarter comparisons require all
calendar days in both series; clipped edge buckets remain partial. No fitted
model, retention estimate or attribution gate changes. See the
[extension audit](verification/ni-082/README.md) and
[backend verification](verification/ni-083/BACKEND.md).
