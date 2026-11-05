# Open questions and explicit assumptions

No answer is inferred from user silence. These questions do not prevent writing this documentation; several gate later ingestion/publication/deployment. Roles below are ownership suggestions, not assigned people. No provider outreach was sent.

| ID | Question / required evidence | Default and decision gate | Owner / affected tasks |
| --- | --- | --- | --- |
| OQ-01 | Can we obtain and publish a daily economically attributable revenue/allocation ledger, with historic fee policy, cash/accrual timing, costs and redistribution permission? | No verified daily protocol revenue. Preserve gaps; no capture-rate/whole-flow fee attribution until reviewed. Separate existing limited provenance evidence. | Research/data; NI-026, NI-051, NI-070 |
| OQ-02 | Will judges accept a transparent reproducible proxy association while H1/H4 remain unresolved, or require true protocol-revenue econometrics? | Product requirements prefer true revenue analysis; limited model allowed only with explicit caveats and judging risk, never substitute labels. No supplied competition deadline/rubric beyond prompt. | Product/research; NI-051–NI-054, NI-069–NI-070 |
| OQ-03 | Which provider account, quota, backfill allowance and cost cap are approved for refreshing data? | All collection disabled; preserve existing STOP markers. Low-cost finalized RPC header first candidate, operational probe pending. | Data/ops; NI-026/NI-030 |
| OQ-04 | Hosting provider, budget, domain and region? | Portable VM app + managed PostgreSQL/Supabase Auth baseline; no account purchase/provisioning. Recheck vendor limits before deployment. | Ops/product; NI-066–NI-068 |
| OQ-05 | Team size, delivery deadline and actual engineering capacity? | Dependency roadmap and S/M/L complexity only; no invented dates/velocity. Cut P1/P2 if constrained, keep integrity/security gates. | Product; all phases |
| OQ-06 | Final public language, author/team attribution, repository URL and final visual-reference selection? | Specification/content contracts in English; English UI default, attribution required before publish. Use existing SVGs as inspiration. No new i18n system for MVP. | Product/design; NI-006, NI-014, NI-070 |
| OQ-07 | Privacy/retention/data residency policy and operator-assisted deletion contact? | Private by default; no sharing/analytics text. Draft retention targets in security/deployment require owner confirmation before public use. | Product/ops; NI-025, NI-062, NI-067 |
| OQ-08 | Exact historical mapping of affiliate recipients, collectors, token wrappers and business revenue channels? | No mapping beyond verified effective-date evidence; collector ≠ integration/customer. 1cs_v1 assets not automatically onchain wrapper aliases. | Research/data; NI-027/NI-029/NI-051 |
| OQ-09 | Which installed runtime/dependency versions pass web/editor/scientific compatibility and licenses? | Choose supported versions in bootstrap, pin locks, test Tiptap custom nodes and ECharts renderer. No guessed “latest” version numbers. | Engineering; NI-001/NI-002/NI-038 |
| OQ-10 | What complete gross issuance/burn series is available without resuming stopped archival audit? | Preserve lower bounds and exact net supply; do not restart 291 missing requests automatically. | Research/data; NI-026/NI-029 |
| OQ-11 | Does the public adapter's revenue definition match intended economic entitlement and current dashboard cutoff? | Keep provider reported revenue separate and unresolved reconciliation; independent attribution still required. | Research; NI-026/NI-051/NI-070 |

## Decisions already made, not awaiting preference polling

Use a modular monorepo, managed authentication, immutable evidence, Tiptap/ECharts, strict server ownership, Markdown MVP export, public H1–H4 thesis and no P2 features before core. Explicit save-time pins are P0 despite advanced snapshots being P1. These are justified in [DECISIONS.md](DECISIONS.md). Reopen them only for concrete conflicting evidence or a user constraint.

Before application work, the user must explicitly approve implementation as requested in the original brief. The final documentation report stops at that boundary; it does not request provider access or commit to costs. Subsequent agents can work on approved independent foundation tasks while operational questions remain gated, but cannot treat elapsed time as access/budget approval.
