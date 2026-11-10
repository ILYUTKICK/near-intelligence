# Original research release — content/evidence manifest (November 2026)

Immutable manifest for the NI-070 original research release. It pins the exact
bytes of every published release document, the versioned metric definitions the
published claims reference, and the recorded evidence base. Hashes are SHA-256
over the exact file bytes (UTF-8), as verified by the repository test
`apps/web/tests/release/release-manifest.test.ts`. If any listed document
changes, its hash changes and the release must be re-manifested — a manifest
entry that no longer matches the file it names is a publication failure, not a
metadata refresh.

## Published release documents

| Document | Bytes (size) | SHA-256 |
| --- | --- | --- |
| [original-research-release-2026-11.md](original-research-release-2026-11.md) | 28870 | `a74ab5f3968edfe2dd059eee7e1d6636c7f49e34c3ad84e9e4d97216f615636c` |
| original-research-release-2026-11.manifest.md (this file) | — | not self-hashed (a manifest cannot contain its own hash); its own integrity is anchored by the repository history and the verifying test, which recomputes every other entry |

## Versioned metric definitions referenced by published claims

Source of truth: the immutable v1 registry at
`apps/api/src/near_api/metrics/registry.py` (NI-029/NI-031; 19 definitions,
deterministic identities, append-only versioning). Availability codes: A saved
observed data, P provider-reported, B bound/estimate, G gated.

| metric_id | v1 availability | Published use |
| --- | --- | --- |
| `observed_near_purchases` | A | CL-001/CL-002 quantities; landing strip |
| `conversion_count` | A | CL-001 event count |
| `treasury_payouts_near` | A | CL-003 payout amount; landing strip |
| `treasury_payout_count` | A | CL-003 payout count |
| `estimated_purchase_usd` | B | CL-004 USD approximations (valuation estimate) |
| `near_price_usd` | P | CL-004 price marks |
| `provider_intents_volume_usd` | P | CL-004 provider volume; admitted proxy explanatory variable |
| `provider_gross_fees_usd` | P | CL-004 provider fees; admitted proxy dependent variable; landing strip |
| `net_supply_change_near` | A | CL-007 supply increase |
| `purchases_to_net_supply_pct` | A | CL-007 scale comparison |
| `issuance_lower_bound_near` | B | CL-008 lower bound |
| `burns_lower_bound_near` | B | CL-008 lower bound |
| `purchases_to_issuance_upper_pct` | B | CL-008 upper bound |
| `treasury_balance_near` | A | CL-009 saved balance point |
| `protocol_revenue_usd`, `protocol_capture_rate`, `fee_funded_buybacks_near` | G | gated; always null with recorded reasons (OQ-01/OQ-08/OQ-11) |

`strict_fee_conversion_equivalent_near` (CL-006) is a docs/METRIC_CATALOG.md
concept (B) recorded as not registered in the code registry; the public claim
renders it with that honest basis.

## Preregistered model artifacts (tracked)

| Artifact | Role |
| --- | --- |
| `research/models/configs/readiness_gate_policy_v1.json` | gate policy: window 2026-08-06..2026-11-04 (end exclusive); thresholds 60 complete days / 10 per parameter / max 3 slopes / intercept required / 365-day long-run minimum |
| `research/models/configs/true_revenue_daily_v1.json` | preferred revenue specification (NOT_READY while OQ-01 is open) |
| `research/models/configs/gross_fee_activity_v1.json` | the admitted named proxy specification with limitations and prohibited labels attached verbatim |
| `research/models/configs/purchases_activity_v1.json` | optional cohort fallback specification |
| `research/models/configs/supply_bounds_activity_v1.json` | documented standing rejection (bound-only outcomes) |
| `research/models/fit_configs/gross_fee_activity_v1_fit.json` | preregistered estimator settings: OLS, Newey–West HAC, Bartlett kernel, fixed maxlags 7, use_correction, use_t; reproduction tolerances rtol 1e-8 / atol 1e-10 |
| `research/models/diagnostics_configs/gross_fee_activity_v1_diagnostics.json` | preregistered diagnostics battery settings |
| `research/models/readiness.py`, `research/models/fit.py`, `research/models/diagnostics.py` | the gate, estimator and battery implementations (NI-051/052/053) |

Generated readiness/fit/diagnostics reports stay local by design
(`research/models/reports/`, `research/reports/<run-id>/`) and are not
repository content; no fitted real-archive artifact exists at publication time.

## Recorded evidence base (operator-recorded, hash-pinned on the operator machine)

| Evidence | Recorded values | Recorded in |
| --- | --- | --- |
| Real-archive readiness run | overall `PROXY_ONLY_READY_WITH_LIMITS`; per-spec verdicts and reason codes; 6/297 mint-header audit; byte-identical double runs | docs/TASKS.md NI-051 card (2026-11-07) |
| Real-archive metric reconciliation | 3,165/3,165 payout pairs, zero issues; payouts 1,405,659.135989071036891726256814 NEAR; purchases 524,480.127692882832410490617319 NEAR over 54,991 events; 502,794 NEAR internal hops excluded | docs/TASKS.md NI-029 card (2026-11-07) |
| Recorded input integrity | `flows_90d_raw.json` 3,147,156 bytes, SHA-256 `7680c5755c2efe5c1694544e68ede0f1f609c29b033ed5d9bdc62899e2024be8`; `near-dollar/analysis/daily.json` 62,432 bytes, SHA-256 `99fdb09823ff5dd80a46387f957bb6f54f71087abee87542e65cdd3f0674b8cd` | docs/TASKS.md NI-012 card (2026-11-08) |
| Estimator synthetic verification | known-coefficient recovery within atol 1e-10; direct-statsmodels equivalence 1e-15; 20 synthetic tests | docs/TASKS.md NI-052 card (2026-11-08) |
| Publication gate | 16 named fail-closed checks; write-once published-only storage; honest empty public catalog | docs/TASKS.md NI-054 card (2026-11-08) |

## Publication visibility rules anchored by this manifest

1. Every quantitative claim on the public pages traces to a recorded document,
   a tracked preregistered config, or a merged task card; the release adds no
   new numbers.
2. Contrary evidence is published with equal prominence (release report
   Section 5); negative verdicts (`NOT_READY`, `REJECTED`) are never softened.
3. No claim of true protocol revenue exists anywhere: the revenue gate (OQ-01)
   is open and the proxy-to-revenue prohibition is a hard gate invariant.
4. No private content: no document/revision/user identifiers, no credentials,
   no absolute local filesystem paths, no raw artifact bytes in any published
   document; the repository is referenced by checkout paths on public pages,
   never hyperlinked (NI-013 allowlist).
5. No raw-data downloads: saved raw inputs stay in the operator archive and are
   shared only through verified, hash-checked handoffs.
6. The real-archive fit run is pending operator execution; the public model
   catalog stays empty until a reviewed run is published through the NI-054
   gate. Unpublished, failed or rejected runs never look like results.
