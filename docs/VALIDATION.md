# Documentation validation report

Delivery date: **5 November 2026**. Result: complete documentation foundation; application implementation has not started. The original request requires explicit approval before implementation, so no frontend components, backend services, migrations, app manifests, deployments or credentials were created.

## Files and structural checks

All **29 required files** are present: four root files (AGENTS.md, README.md, CONTRIBUTING.md, .env.example) and 25 requested docs. Four additional documentation files provide an index, repository audit, dated source verification and this validation report. Total: **33 new files**, of which 32 are Markdown and one is an environment-variable example. [Index](INDEX.md) lists the documentation; [README](../README.md) links entry points.

Automated validation checks required file existence, relative Markdown link targets, balanced code fences, consistent GFM table columns, all task metadata, unique task IDs, existing dependency IDs, acyclic dependencies, referenced task IDs and P0 dependency priorities. Historical numerical claims are checked against saved original JSON summaries. Final automated results are recorded below after execution.

Backlog contains **72 tasks across 14 epics**: 64 P0, 6 P1, 2 P2. All tasks are TODO. Every task has description, epic, priority, dependencies, implementation steps, expected files/modules, acceptance criteria, test requirements, complexity and status. Application task completion is not implied by documentation completion. The dependency graph contains no cycle, and no P0 task depends on a P1/P2 task.

## User-journey coverage review

| Journey | API/storage support | Implementation tasks |
| --- | --- | --- |
| Public claim → source/model | Publications, source/metric/chart/dataset/model APIs; immutable evidence manifests | NI-011–NI-015, NI-054, NI-070 |
| Explore → save chart | ChartView/Selection, saved_charts, owner verification | NI-031–NI-035, NI-016–NI-020 |
| Create research → add chart | Documents/versions/blocks, chart insertion CAS, pinned contexts | NI-036–NI-043 |
| Add insight → opposing evidence | Canonical insight/hypothesis/evidence nodes plus per-revision projections | NI-046–NI-050 |
| Edit → save/reopen/recover | Immutable JSON revisions, ETags/If-Match, idempotency and conflict UI | NI-036–NI-040 |
| Reproduce quantitative analysis | Prepared dataset + fixed model/code/config/lock manifest; published run API | NI-051–NI-054 |
| Export acknowledged evidence | Frozen IR, rendered chart/CSV assets, owner-scoped jobs/download | NI-056–NI-058 |
| Template / public duplication | Public release projection, private ID remapping, retained public pins | NI-045 (P1) |
| Failure / source revision | Ingestion state, last-good active pointer, new immutable versions and stale/revised quality | NI-026–NI-030, NI-043 |

Canonical navigation and priorities were reviewed across IA, screen specifications, feature requirements, API and tasks. The legacy Strategy/Portfolio concept is explicitly preserved as prior input and deferred. Current hypotheses H1–H4 are not conflated with old H1–H6. Save-time data pins are P0; explicit snapshot UX P1. Markdown ZIP is the P0 export, PDF P1, sharing P2. Public model results P0, model-result editor block P1. Missing protocol revenue remains a data gate, not a substituted measure.

## Actual offline reproduction verification

Executed in a disposable temporary copy of the research archive using the host Python interpreter. No fetch script, provider credential, network collection, cloud SQL or statistical model fit was invoked. Ten commands completed with exit code 0:

1. near-longitudinal analyze.py
2. near-dollar analyze.py
3. near-supply analyze.py
4. near-treasury analyze.py
5. near-provenance audit_sample.py
6. near-provenance audit_cohort.py
7. near-provenance inventory_bounds.py
8. near-provenance inventory_bounds.py --exact-integer-only
9. near-provenance collector_routes.py
10. near-provenance summarize.py

Five regenerated summary JSON objects (longitudinal, USD valuation, supply, treasury and final provenance) matched the corresponding saved original objects exactly. SHA-256 checks before/after confirmed all **407 pre-existing files** under research/ and product-plan/ were unchanged by verification. This demonstrates reproducibility of the existing descriptive saved-input analyses; it does not establish full economic attribution, a locked modern research environment or a fitted econometric result.

## Source review and remaining limits

Official NEAR/Intents, DefiLlama, Dune, CoinGecko, BigQuery and selected software documentation/source pages were browsed. [SOURCE_VERIFICATION.md](SOURCE_VERIFICATION.md) distinguishes documented capability, local historical evidence and untested operational access. No source's current authenticated entitlement, exact live quota, full history or commercial redistribution license is declared verified without evidence. Failed guessed URLs are not treated as working APIs.

Major unresolved gates: daily protocol-attributable revenue and historical allocation; provider rights/quotas/budgets; acceptance of limited proxy econometrics by judges; actual live-source refresh; runtime version compatibility; hosting/domain/region/privacy attribution. [Open questions](OPEN_QUESTIONS.md) and [risks](RISKS.md) assign consequences. No fictional production values or regression coefficients are supplied.

This validation is documentation and legacy-analysis QA. Runtime API correctness, migrations/RLS, auth provider configuration, editor interaction, numerical model fitting, accessibility, performance, exports, backups and deployed end-to-end behavior remain future task acceptance requirements. A specification cannot claim those tests have passed.

## Final automated result

All 29 required files exist. The final check verified 158 relative links, 72 unique fully specified tasks across 14 epics, valid task references, an acyclic 72-node dependency graph, no P0 dependency on deferred priorities, balanced code fences, consistent table columns and exact copied historical amounts/counts. **Zero validation errors.** This is a structural/consistency check, not a claim of implemented application behavior.
