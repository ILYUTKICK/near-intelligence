# Implementation roadmap

**Execution entry point: [PLAN.md](../PLAN.md).** This roadmap provides context; task selection and progress follow the mandatory plan.

This documentation phase is complete only after [validation](VALIDATION.md). Application implementation requires explicit user approval. No team capacity/deadline supplied; complexity is relative, not a calendar promise. [Backlog](TASKS.md) is the executable sequence.

## Phase gates and dependency order

| Phase | Deliverables and task groups | Entry / exit gate |
| --- | --- | --- |
| 0 Research and feasibility | Repository audit, source register, conditional thesis and architecture (this delivery); future operational source/rights probe NI-026 and model readiness NI-051 | Preserve archive and stopped collectors. Exit requires selected usable sources, actual entitlement/budget/rights, and defensible empirical question. Documentation review alone does not close operational gates |
| 1 Foundation | NI-001–NI-005 repo/web/API/DB/client/CI contracts; NI-006–NI-010 tokens/components/layouts | User approves implementation. Exit clean install/build/migrations and shared types, reusable accessible shells; no fake financial data |
| 2 Public research structure | NI-011–NI-015 editorial pages, mechanism, methodology, thesis and public explorer | Can build reviewed prose/layout while data services develop. Final numerical bindings depend on Phase3 and model section on Phase6; do not mark public release complete from placeholders |
| 3 Data infrastructure | NI-026–NI-030 archive import, exact calculations, versioned datasets, approved refresh; NI-031–NI-035 chart registry/API/render/library | Pull minimal schema and source verification ahead of Phase2 numerical binding. Exit source-to-chart trace, last-good behavior and at least one actual approved refresh |
| 4 Investor workspace | NI-016–NI-020 auth/ownership and NI-021–NI-025 shell/home/settings; saved charts NI-035 | May run in parallel with Phase3 after API/auth contracts stabilize. Exit two isolated users, real persisted saved instances and usable Home |
| 5 Research editor | NI-036–NI-040 documents/schema/editor/CAS; NI-041–NI-043 chart insertion/pins; NI-046–NI-050 insights/hypotheses/evidence | Exit complete create→chart→insight→save→reopen; immutable evidence; no cross-user refs. NI-044/NI-045 explicit snapshots/templates are P1 after core passes |
| 6 Quantitative research | NI-051–NI-054 readiness, fixed models, diagnostics/reproduction/API; NI-055 P1 model embedding | Readiness question can be decided early with archive. Exit real publishable model rerun offline, honest unresolved H1/H4 where applicable; no substituted protocol revenue claim |
| 7 Final integration | NI-056–NI-058 P0 Markdown export; NI-061–NI-064 security/E2E/accessibility; NI-066–NI-070 deployment/backup/publication/demo | Exit all P0 gates in MVP_SCOPE, no fabricated data, final thesis includes actual executed findings/limits. PDF NI-059, advanced filters NI-071 and organization NI-072 P1; sharing NI-060 and integrity/AI NI-065 P2 |

Suggested phase labels preserve the prompt's narrative but **task dependencies take precedence**. Data feasibility, schema and auth boundaries are not postponed until after public pages are claimed functional. Quantitative exploration may start early, but publication waits for reproducibility and rights.

## Work that can proceed in parallel

For a concrete two-person allocation and handoff sequence, see [TEAM_PLAN.md](TEAM_PLAN.md). Original task dependencies and release gates remain authoritative.

These are coordination suggestions for future contributors, not a request to spawn agents in this documentation session. After NI-001–NI-005 freeze initial contracts: design/public layouts (NI-006–NI-015), data import (NI-026–NI-030), and auth/security (NI-016–NI-020) have distinct module ownership. Shared metric definitions/DTOs need one contract owner. After document version schema is fixed: editor UI and document API can proceed against generated contracts; chart renderer and export can share an explicit frozen ChartView schema. Quantitative model preparation can proceed from immutable imported datasets while workspace UI develops.

Avoid simultaneous schema/editor-format changes by multiple implementers. Metric registry, OpenAPI, document schema and model manifest each need a designated owner/reviewer. Branches integrate once their focused tests and contract generation pass; a parallel task cannot bypass a BLOCKED dependency.

## Critical path and cuts

Critical path: approval → runtime/schema foundation → source/rights + immutable dataset → chart API/render → owned document versioning → editor insertion/pins/insights → export/E2E/deploy. In parallel, source readiness → defensible model → offline verification → public thesis finalization joins the release path.

If time is constrained, drop P1 snapshot UX/templates/PDF/model embedding and P2 entirely. Reduce catalog to a few valid economic questions and use honest empty states for gated network/ecosystem metrics. Never cut authorization, save-time pins, original thesis, source provenance, actual model execution or the real refresh gate. If protocol-revenue data remain missing, use only the explicitly limited alternative analysis and disclose the external judging risk. If no defensible model or usable data rights exist, report P0 incomplete.

## Milestone evidence

Each phase exit records commit, completed task IDs, actual checks/artifacts, known gaps and next ready tasks. Tasks remain TODO until worked, BLOCKED only with specific unresolved dependency, DONE only after all task acceptance/tests. Research nonsignificance/contradictory results can satisfy a scientific task; inability to reproduce cannot. Final hackathon demo shows both a positive mechanism observation and a contrary finding, then a fresh user's independent evidence-backed document and exported bundle.
