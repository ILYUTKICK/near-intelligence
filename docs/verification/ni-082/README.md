# NI-082 — Saved-history coverage audit and extension protocol

Audit date: 13 November 2026. Scope: read-only inspection of the owner's existing local research archive. No new data was requested, no stopped collector was restarted, no financial model was fitted, and no existing calculation, registry or dataset was changed. Raw records and the audit script remain local and ignored; this report contains sanitized coverage and source-quality findings only.

## Main finding

The earlier 90-day study selected a short window from files that contain substantially more provider-reported history. The saved DefiLlama snapshots contain **694 daily volume observations** and **543 daily gross-fee observations**, with **543 common consecutive calendar days, 10 May 2025–3 November 2026**. This is a candidate extension for descriptive activity and gross-fee research. It is not a validated long-run series of net revenue, fee-funded purchases, retained NEAR or token value capture.

The corresponding attributed onchain cohort remains 90 days. Comparable price coverage, definition stability, source disagreements, policy regimes and the existing attribution/supply gates still require explicit treatment before any long-run inference. Longer history alone does not change the NI-051 readiness decision or satisfy OQ-01.

## Saved coverage

The companion [long-history research protocol](LONG_TERM_PROTOCOL.md) defines the
three research horizons, documented launch/fee-policy regimes, dataset preparation,
staged analysis, falsification conditions and bounded missing-input handoff. It is
an extension design, not an approved dataset or fitted result. Coordinator review
completed on 14 November 2026 (Europe/Moscow); archive inspection occurred on 13 November.

Dates below are inclusive observation dates, UTC. Analysis windows must still use half-open periods `[start, end)`. A missing observation is never filled with zero.

| Saved archive input / series | Actual coverage | Rows / unique dates | Missing dates / duplicates | Permitted interpretation at this stage |
| --- | --- | --- | --- | --- |
| `near-dollar/data/llama_volume.json`, `totalDataChart` | 2024-12-10–2026-11-03 | 694 / 694 | 0 / 0 | Candidate provider-reported gross volume; not independent onchain adoption or revenue |
| `near-dollar/data/llama_fees.json`, `totalDataChart` (`dailyFees`) | 2025-05-10–2026-11-03 | 543 / 543 | 0 / 0 | Candidate provider-reported gross fees; 9 source-valued zeros require explicit handling |
| `near-dollar/data/dashboard_efficiency_record.json`, `intentVolumeSeries` | 2025-01-01–2026-11-03 | 665 / 665 | 7 / 0 | Separate provider-qualified volume history; do not merge with DefiLlama |
| Same dashboard input, `totalFeesSeries` | 2025-05-06–2026-11-03 | 541 / 541 | 6 / 0 | Separate provider-qualified fee history; do not merge with DefiLlama |
| Same dashboard input, `revenueSeries` | 2025-08–2026-11 | 16 / 16 months | No missing months / 0 | Monthly provider-labeled revenue only; November is in progress, leaving 15 closed calendar-month candidates |
| `near-dollar/data/coingecko.json`, `prices` | 2026-07-28T00:00–2026-11-04T12:29:50 | 101 / 100 | 0 / 1 duplicate calendar date | Short saved price window; November 4 has a midnight boundary mark and an intraday mark |
| `near-supply/data/nearblocks_charts.json` | 2020-07-21–2026-11-03 | 2,297 / 2,297 | 0 / 0 | Secondary-index supply/price history; units and historical methodology require validation before use |
| `near-longitudinal/data/flows_90d_raw.json`, conversion/coverage/quality/withdrawal dates | 2026-08-06–2026-11-03 | 90 distinct dates per kind | No missing dates within that window | Existing attributed 90-day cohort only; not a full-market or multi-year purchase/payout history |
| `near-supply/data/blocks_raw.json`, `daily_blocks` | 2026-08-05–2026-11-03 | 91 / 91 | No missing dates within that window | Opening boundary plus existing study boundaries; not a multi-year exact supply audit |
| `near-treasury/data/summary.json` | `[2026-10-05, 2026-11-04)` | 30-day summary | Not a daily longitudinal series | Point-in-time/short-window treasury evidence; not proof of persistent retention or locking |

The raw flows file has 6,812 kind/payload rows: 267 conversion rows, 90 coverage rows, 90 quality rows, 3,165 withdrawal rows and 3,200 native-context rows. Native context spans 91 dates through November 4; that extra context date does not extend the conversion or payout cohort. The block file has 111 rows: 91 daily boundary rows and 20 schema rows. Multiple rows on the same date in these files represent categories/events, not duplicate daily observations of one scalar metric.

## Quality and latest-period treatment

All four daily provider series in the first four table rows are ordered ascending and use midnight UTC timestamps. Their inspected value fields have no missing, malformed, nonfinite or negative values. Neither volume series nor dashboard fees contain zero values. DefiLlama fees contain nine zero-valued rows on May 13–16, 19–22 and 24, 2025. Preserve these as source-reported values with a quality note; do not certify economic zero, drop them silently, or take logarithms without a declared rule.

Dashboard volume is absent on March 8 and 15, April 21, 25 and 29, and May 4 and 14, 2025. Dashboard fees are absent on May 7, 10–12, 17 and 18, 2025. These absent dates remain missing. The starts and missing dates differ across sources and cannot be repaired by copying values from the other provider.

DefiLlama volume and fees were saved on November 4 at 12:31:32 UTC; the dashboard capture was saved at 12:32:56 UTC. Their last daily observations are November 3, so those daily buckets precede the retrieval day. This establishes calendar closure, not provider finality: later revisions remain possible, and a new snapshot must receive its own version. Dashboard monthly November 2026 is partial at capture; its `is_stale=0` label does not certify month completeness or economic accrual.

The CoinGecko file was saved November 4 at 12:31:32 UTC. It contains 99 midnight points before that date plus November 4 midnight and 12:29:50. Keep the midnight boundary mark when defining November 3 end-of-day valuation; exclude the intraday November 4 point from a closed-day panel. Treat boundary-price alignment separately from activity dates. There is no saved comparable CoinGecko history covering all 543 fee days or 694 volume days.

NearBlocks contains 2,297 non-null string values for each inspected field: `total_supply`, `circulating_supply` and `near_price`; they parse without malformed, nonfinite or negative values. Supply fields contain no zeros; `near_price` contains **85 zeros**. Do not interpret those prices as observed zero market prices. The manifest records archive creation on November 4 at 13:24:15 UTC, but no per-file retrieval timestamp was found in the inspected manifest. This index's units, historical supply/price definitions and revision behavior have not been validated for an expanded study. Its length does not authorize substitution for the existing canonical price marks or exact chain-boundary stocks.

The treasury summary is pinned to November 4, 11:31:03 UTC. It records 38 predecessor-history transactions, no unresolved child traces, five historical failure outcomes and no outgoing receipt actions in its specified 30-day window. These counters and historical records do not establish a continuous multi-year retention series. The supply archive's gross issuance/burn audit remains incomplete (6 of 297 headers); no uninspected remainder is assumed zero.

## Provider scope and comparability

Both saved DefiLlama responses identify `NEAR Intents` / `near-intents`, with `parentProtocol=parent#near-protocol`. The volume response links `NEAR Protocol` and `NEAR Intents`; the fees response additionally lists `Near Perps`. These are response metadata, not sufficient evidence that every historical observation has identical economic scope. Both breakdown arrays have the same number of rows as their main series and the stable keys `Near` → `NEAR Intents`; neither response contains a version key. Stable outer keys do not prove a stable calculation or included protocol universe.

The saved adapters declare version 1 and a Dune upstream. Volume uses `dune.near.dataset_near_intents_metrics`; fees combine the protocol-fee and fee datasets. The volume adapter declares a November 5, 2024 start, but the response begins December 10. The fee adapter declares a December 10, 2024 start, but the saved fee response begins May 10, 2025. These are explicit coverage mismatches, not evidence of zero activity before the first saved row. No backfill or zero-padding was performed.

The fee adapter defines gross fees as protocol plus distribution/affiliate fees. Its separate revenue labels are based on wallet sweeps and destination classifications. The `BUYBACK_START=2026-02-23` classification separates its protocol/holder-revenue labels; this saved provider date is not an independently verified activation timestamp or proof that every purchase was funded by fees. Provider-labeled revenue, gross fees, onchain conversions, treasury payouts and burns remain separate metrics. The adapter itself says purchased NEAR is not burned. Dashboard and DefiLlama share Dune lineage, so agreement would not supply independent confirmation.

A date-matched Decimal comparison of the saved daily values found:

| Comparison | Overlap days | Exact equal values | Differences ≤ USD 1 | Differences > USD 1 | Maximum absolute difference, USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dashboard volume vs DefiLlama volume | 665 | 0 | 94 | 571 | 50,816,582.2124849 |
| Dashboard fees vs DefiLlama fees | 538 | 0 | 17 | 521 | 140,840.89680366943 |

The USD 1 split is a diagnostic of magnitude, not an acceptance tolerance. These disagreements cannot all be described as decimal rounding. Their source/definition/revision causes remain unresolved; the audit neither declares corruption nor chooses a replacement source. Keep source-qualified parallel series, pinned snapshots and explicit disagreement. Do not average or sum them, or splice one into another to fill gaps.

## What the archive can and cannot extend

- **Candidate extension now:** descriptive volume history over 694 days and gross-fee/volume comparisons on the 543-day common source-qualified window, after specifying coverage and regime treatment. These counts describe archived rows, not approved production datasets or fitted results.
- **Separate monthly sensitivity candidate:** 15 closed dashboard months, August 2025–October 2026, subject to revenue-definition and capture-attribution validation. Do not expand monthly values into synthetic daily observations.
- **Unresolved inputs:** longer comparable daily price marks; a reconciled and versioned definition history; longer attributed conversions/payouts and destination ownership/funding evidence; continuous retention/locking evidence; exact supply/issuance/burn evidence where required. NearBlocks is a lead for verification, not an approved substitute.
- **Inference remains gated:** the project's 365-complete-day long-run policy is a minimum gate, not proof of adequate effective observations, stable regimes, identified causality or net capture. A provider's row count cannot satisfy the missing attribution, supply or economic-definition gates.

## Integrity and reproducibility

Audit computations were bounded local reads of saved inputs. Decimal parsing preserved source values for numeric checks; UTC timestamps were checked for order, uniqueness, missing calendar dates and intraday endpoints. SHA-256 was calculated before and after the audit for all 14 files below; **all 14 were byte-identical**. All ten examined manifest-recorded input hashes matched their corresponding files. The four manifest hashes are themselves recorded below. This confirms local input integrity against these snapshots; it does not certify upstream economic correctness.

The audit script and machine-readable coverage summary are local ignored artifacts under `.local/ni082/`; no raw JSON/CSV, calculation script, account/event payload, credential or process state is included in this tracked report. A fresh checkout may lack the local archive and audit files. Reproduction requires the authorized archive-owner handoff described in the repository's [reproducibility policy](../../REPRODUCIBILITY.md); do not fetch replacements automatically.

| Archive-relative input | SHA-256 before = after |
| --- | --- |
| `near-dollar/data/llama_volume.json` | `e21e60e9f91adf49b672c6c799a9efded7d32abae4886450bd502bc22fdc293d` |
| `near-dollar/data/llama_fees.json` | `91090ea36c4378c961ada84a7621de0f31caa79970ef9443801c18f3bc48521b` |
| `near-dollar/data/coingecko.json` | `4b16232d15fe10cc9da623d98f564e82f823d1bb39524ef3b87a360617d9dc02` |
| `near-dollar/data/dashboard_efficiency_record.json` | `6d463c602dc4020f9fcf6dafbaad44de0dbb03dc16e84c50cbf7ea72535c433f` |
| `near-supply/data/nearblocks_charts.json` | `5788bbb59df305ad514a70ea394049cc957d3fd51ce9349cfe5c9d09289e75fa` |
| `near-longitudinal/data/flows_90d_raw.json` | `7680c5755c2efe5c1694544e68ede0f1f609c29b033ed5d9bdc62899e2024be8` |
| `near-supply/data/blocks_raw.json` | `d1a3434c24a24e6c83a136d9f526d46fb5a6491494e03ea9e1b9c29c94120a2c` |
| `near-treasury/data/summary.json` | `b52482f8ae7f26c20fa491fb54394c11bb856c3df95e38cd42f38b668f62fc25` |
| `near-dollar/manifest.json` | `8b46305a7479f6fc68ab19bdfa9dbf64795a79063d7e25e43c640f6db2bcb840` |
| `near-supply/manifest.json` | `3882fb8d60e685f809234c49edd123882bb270a41d564482d6ca313ed3cb7586` |
| `near-treasury/manifest.json` | `3463a09efef7ef8513f81d4467b2a7e3d06a2c232839b4e3a74b693aaefd92b0` |
| `near-longitudinal/manifest.json` | `55c5dd9e7596ab203755e0a8322a3eeb1e9bd282449d2400d8c206bb384aa703` |
| `near-dollar/data/llama_adapter.ts` | `4c1ecced73f89940ff7a8534154a15740cf57c4ddd76b3fb4928ee5d9c073a8d` |
| `near-dollar/data/llama_volume_adapter.ts` | `4843881598b47114bc54c297c9eb5e15e28815a2701ef4f44cbce884d8f43838` |

Related constraints: [source verification](../../SOURCE_VERIFICATION.md), [metric definitions](../../METRIC_CATALOG.md), [econometric methodology](../../ECONOMETRIC_METHODOLOGY.md), and preserved archive descriptions for [provider history](../../../research/near-dollar/README.md), [90-day onchain evidence](../../../research/near-longitudinal/README.md), [supply](../../../research/near-supply/README.md) and [treasury](../../../research/near-treasury/README.md).
