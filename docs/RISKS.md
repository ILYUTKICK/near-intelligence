# Risk register

Reviewed 5 November 2026. Owners are responsibility roles until team assignments exist; OQ links identify unresolved inputs. Severity is impact×likelihood assessment, not a quantitative probability.

| ID | Risk / severity | Detection and mitigation | Owner / release consequence |
| --- | --- | --- | --- |
| R01 | No daily attributable protocol revenue — Critical | Readiness gate rejects proxy relabeling; separate exploratory fee/activity model; seek executed allocation/recognition ledger | Research lead; H1/H4 remain unresolved, OQ-01/OQ-02; release incomplete if no defensible empirical model |
| R02 | Overstated fee-funded buybacks — Critical | Preserve observed purchases vs strict short-window modeled equivalent; no sample extrapolation; source-to-canonical-credit chain | Research/data lead; block unsupported claims |
| R03 | Positive quantity evidence mistaken for token supply reduction — High | ΔS=issuance−burns; ordinary purchases/treasury holding not burn; lower-bound tests | Research lead; block misleading token-economics chart/text |
| R04 | Provider revisions/common lineage — High | Immutable versions, compare source-qualified series, lineage graph, revised-date notices; do not call correlated providers independent | Data lead; stale/revised badges, rerun new versions explicitly |
| R05 | Rate limit/cost or stopped collector accidentally restarted — High | Disabled ingestion, source allowlist, per-call/day budget, pause markers, advisory lock, cloud bytes cap | Data/ops; block automation until OQ-03; preserve offline path |
| R06 | Redistribution/terms unknown — High | Capture license/terms evidence, sanitize archives, restrict raw downloads; favor permitted reproducible bundles | Product/research owner; block public raw release until OQ-01 |
| R07 | Cross-user access via nested references/export — Critical | Server predicates + RLS, same-owner composite refs, two-user tests for every route family/download | Backend/security; release blocker on any leak |
| R08 | Private content in caches/logs/public projection — Critical | no-store, clear client cache, publication allowlist, no document-text telemetry, privacy scan | Web/backend; release blocker |
| R09 | Autosave data loss or inconsistent relational projections — High | Revision CAS, one in-flight save, idempotency, atomic canonical JSON+projections, recovery conflict UI | Editor/backend; release blocker for failed persistence |
| R10 | Short/spurious regression/mechanical fees relation — High | Readiness/sample policy, stationarity diagnostics, difference sensitivity, limited predeclared controls, causal caveats | Quant lead; reject inadmissible model, publish contrary/nonsignificant findings |
| R11 | Snapshot/artifact loss prevents reproduction — High | Immutable artifacts, version pins, DB+artifact coherent backup, hash/restore drill | Data/ops; block claimed reproducibility |
| R12 | Scope overload (workspace+editor+research) — High | P0 first, 70 bounded tasks, cut P1/P2, narrow real chart catalog; no Strategy/Portfolio expansion | Product lead; OQ-05 deadline/capacity needed |
| R13 | Interactive chart node breaks rich-text editing — Medium/High | Tiptap proof-of-concept selection/IME/undo; atomic node views, keyboard controls; prototype gate | Frontend; NI-038 gates dependent editor work |
| R14 | Export renderer inconsistency/security — High | Shared frozen options/series, Node renderer without shell/network, sanitized SVG/ZIP paths, verify data hashes | Frontend/backend; Markdown path must pass before PDF |
| R15 | Legacy reproducibility not fully pinned — Medium | Preserve archive; run disposable-copy reproduction; record Python/version/source hashes; new locked pipeline | Research/data; no claim old scripts establish a modern lock |
| R16 | Auth/JWKS refresh/recovery misconfiguration — High | Staging final-origin cookies/callbacks, asymmetric verification, fail closed, known token-expiry window | Backend/ops; NI-020/NI-062 must pass |
| R17 | Mobile/accessibility gaps in chart/editor — Medium/High | Keyboard/table alternatives, tablet/phone drawers, touch/IME/real-device checks | Design/frontend; core journeys blocked if unusable |
| R18 | Unspecified hosting/backup/region policy — Medium/High | Portable baseline, actual budget decision, restore rehearsal and retention review | Ops/product; OQ-04/OQ-07 before production |

## Research limitation versus engineering defect

A genuine unsupported hypothesis, declining measured demand or nonsignificant regression is a result. An unlabeled missing series, hidden source disagreement, leaked private document or nonreproducible model is a defect. Do not optimize the product to make the investment thesis appear supported. The public assessment must change when evidence challenges it.

Reassess risks at each phase gate and after changes to providers, recognition policies, editor schema, auth, deployment or model specification. High-severity controls need test/artifact evidence, not a checklist tick.
