# Long-history research protocol — NI-082

This protocol is a proposed extension of the current evidence, not a longer
approved dataset, fitted result or investment recommendation. Existing 90-day
claims remain pinned to their original scope. No raw archive, collection script
or newly downloaded dataset is published by this document.

## Research structure

Use three explicit clocks rather than one misleading universal date selector:

1. **Network context:** the available indexed NEAR history, with separate source,
   definition and precision limits. Indexed supply is not a replacement for exact
   chain-boundary supply or the incomplete gross issuance/burn audit.
2. **Intents business history:** all available comparable provider-reported volume
   and gross fees. These describe adoption and gross monetization, not accrued
   protocol profit. Use each series' actual coverage and the genuine common
   window; never pad earlier unavailable fees with zeros.
3. **Token-capture mechanism:** actual observed purchases, cash receipts, retention,
   outflows and burns/locks under a versioned address/event definition. Its shorter
   verified window remains visible beside the longer context. More volume/fee
   observations cannot establish longer conversion provenance or retention.

## Regime and source timeline

- The official [Intents introduction](https://near.org/blog/introducing-near-intents)
  is dated 10 November 2024 and describes a beta launch. This dates the official
  introduction; it does not establish the first comparable observation for every
  metric or authorize backfilling absent history.
- The official [Q2 2026 account](https://near.org/blog/the-state-of-near-q-2-2026),
  dated 8 July 2026, says the fee switch was activated at the end of February 2026.
  This is a project-reported milestone, not an independently reconciled chain
  activation timestamp or an automatically exogenous treatment date.
- The saved fee provider metadata classifies treasury ProtocolRevenue before
  23 February 2026 and HoldersRevenue afterwards. That precise classification
  date must not silently be equated with the official approximate activation
  date, a burn event, an immutable commitment or the start of gross fees.
- Record documented fee-rate/distribution/front-end/incentive/accounting changes
  and source adapter changes before choosing segments. Unknown changes remain
  unknown; source code's configured start is not proof of response coverage.

Primary documentation was read on 13 November 2026. No market data endpoint,
cloud SQL, authenticated provider service or stopped collector was invoked.

## Dataset preparation and quality gates

- Preserve original bytes, retrieval provenance, hashes and the current 90-day
  artifact identities. Longer files are a separate source-qualified candidate
  dataset version. Do not edit or silently widen v1 model/specification windows.
- Parse numeric source values as exact decimals. Retain UTC half-open ranges and
  distinguish successful zero-valued observations from missing records, absent
  pre-history and unknown coverage. Preserve gaps and provider revisions.
- Separate provider snapshots; never average or sum DefiLlama and Dashboard as
  independent confirmations. Their common upstream lineage remains a limitation.
- A saved historical chart is the provider's as-of snapshot of past values, not
  a point-in-time vintage archive. Do not imply a look-ahead-free trading backtest.
- Keep source start/end, complete-day cutoff, gaps/duplicates, unusual/zero values,
  adapter scope and historical schema/version uncertainty in a quality manifest.
- Do not silently substitute NearBlocks' indexed price field for the registered
  CoinGecko price basis. Verify unit, construction, zeros and overlap first; any
  alternative price basis needs its own named sensitivity/definition.
- No daily allocation of monthly captured revenue. A calendar-closed month can
  still be revisable or wallet-timing-based; the in-progress month is separate.

## Staged analysis

First publish only permitted, quality-checked descriptive evidence: complete
calendar-month/quarter volume and fee histories, same-source effective gross-fee
rate, rolling 30/90-day summaries with overlap stated, source disagreement and
regime annotations. Partial quarters/months are not compared with full ones as
if equally covered. Do not claim two complete annual comparison windows when
less than 730 days exist for the selected metric. Aggregate reported gross fees
are not a measured protocol retention/capture rate.

Then extend the token mechanism independently. Define treasury/address membership
as of each period and distinguish fixed-cohort versus changing-scope views. Do
not select today's surviving collectors and project them backwards as the full
historical market. Reconcile inflows, conversions, inter-wallet transfers, opening
and closing stock and outflows without counting stages twice. Cash sweep timing
is not accrual recognition, and cash receipts are not net profit after costs.

Only after quality/definition checks should an immutable extended model spec be
registered. The existing [readiness policy](../../../research/models/configs/readiness_gate_policy_v1.json)
sets a 365-day long-run threshold, but passing a length threshold is not sufficient
for long-run inference. Preserve calendar-adjacent differences, strict positivity,
rank/sample requirements and preregistered diagnostics. Report zero/gap exclusions;
do not insert epsilons or difference across absent days. Do not search dates,
controls or lags for a desired significant result. A longer gross-fee/volume proxy
still cannot prove attributable revenue, price impact, sustainable capture or a
causal adoption effect.

## Long-term case and falsification

Separate historical measurement from a forward conditional case. The forward
case should expose assumptions about adoption, retained fee share, costs and
incentives, conversion policy and durable retention/burn/lock behavior. Present
sensitivity, not fitted probabilities, unsupported price targets or annualized
extrapolation of one favorable month. Governance discretion and token holders'
lack of a guaranteed cashflow claim must remain explicit.

Evidence that strengthens the case: independently reconciled economic receipts,
stable capture through different conditions after costs, and verifiable retention
or actual burns/locks under known rules. Evidence that weakens it: adoption growth
without corresponding retained economics, fee compression/incentives consuming
receipts, concentration/scope artifacts or later treasury spending reversing
accumulation. Positive total-supply growth alone does not estimate market selling
pressure or disprove every liquid-supply/value-capture effect.

## Bounded missing-input handoff

A collection proposal must name each missing series, verified source/schema,
requested UTC window, allowed fields, rate/byte/query-cost caps, retention and
rights, credentials and stop conditions. Only then request any missing approval.
No open-ended full-chain crawl, collector restart or paid/cloud job follows from
this protocol. Reuse the saved candidate history first; the current audit is not
permission to manufacture a daily net-revenue series or expand collection.
