# NEAR Intelligence — agent operating instructions

This is an evidence-first NEAR investment research product. **Before every task, read and follow the mandatory [PLAN.md](PLAN.md)**, then [README.md](README.md), [MVP scope](docs/MVP_SCOPE.md), [team assignments](docs/TEAM_PLAN.md), and the relevant specification. Current state: documentation and legacy research only. **Application implementation requires explicit user approval after this documentation phase.** Do not initialize services or migrations as part of preparing these specifications.

## Mandatory execution rule — follow PLAN.md only

- **Implement only an identified NI-task from [PLAN.md](PLAN.md).** No independent feature work, untracked tasks, skipped dependencies, or unilateral expansion of scope. Explicit user instructions take precedence; update the plan/backlog when they change the work.
- PLAN.md is the required execution entry point. [TASKS.md](docs/TASKS.md) is the sole status/dependency/acceptance registry; [TEAM_PLAN.md](docs/TEAM_PLAN.md) defines A/B ownership and handoffs. Do not maintain competing status lists.
- Before implementation, select the earliest eligible task for the assigned role whose dependencies are verified DONE. Announce its NI-ID; mark it IN_PROGRESS and record the real agent/session, role and start time in its TASKS.md card. Respect existing claims and unrelated changes. Work on one independent task at a time; distinct ready tasks may proceed in parallel.
- Do not take over another agent's IN_PROGRESS without an agreed handoff. A cross-boundary task is not DONE until both UI and backend contributions and its full acceptance checks pass. Record blockers and take another eligible task rather than bypassing prerequisites or inventing results.
- Keep P1/P2 deferred until P0 is complete and the work is within the user's authorized scope. Finishing one role's queue does not authorize expanding the product.
- Before DONE, record actual implementation results and verification evidence, update affected contracts/docs, and satisfy the task's original Definition of Done. Planning, screenshots, placeholders and untested code do not satisfy implementation criteria.
- Follow the existing user authorization boundary: a later explicit implementation/task instruction authorizes its scope without repeated confirmation. This documentation update alone does not start the application. Do not silently rewrite the plan to manufacture authorization or remove security/data-integrity requirements.

## Repository sharing scope

GitHub is authorized to contain documentation (including research Markdown findings) and visual mockups only. Raw research JSON/CSV/SQL, calculation/collection scripts and process state remain local and ignored. A fresh clone may therefore lack linked evidence artifacts and offline commands. Verify actual input availability; request an authorized data handoff when needed, never invent replacements or restart collectors. Do not remove these ignore rules or add/push research data without explicit user authorization.

## Architecture and map

Target: a modular FastAPI/Python backend, Next.js/React/strict TypeScript frontend, PostgreSQL, Supabase Auth, Tiptap, Apache ECharts, and a scheduled Python CLI using the backend's domain modules. No microservices, LLM dependency, collaborative editor, trading execution, or portfolio product in MVP. See [architecture](docs/ARCHITECTURE.md) and [decisions](docs/DECISIONS.md).

Existing `research/near-*` directories contain real saved evidence, SQL and offline analysis; `research/revenue-dashboard` contains captured third-party material. Preserve these. Existing `product-plan` contains an earlier product plan and SVG references. Its Strategy/Portfolio scope and H1–H6 numbering are superseded for the new product by these docs; do not modify or silently reinterpret it.

Planned paths: `apps/web` UI and same-origin auth gateway; `apps/api` domain/API/ingestion; `packages/shared-types` generated API client; `research/models` deterministic model specifications; `scripts` operator tooling; `.github/workflows` CI. These paths are specifications, not present implementations. [Audit](docs/REPOSITORY_AUDIT.md) is the starting inventory.

## Working conventions

- Choose and execute work only through [PLAN.md](PLAN.md), using TASKS.md dependencies/acceptance and TEAM_PLAN.md ownership. Preserve unrelated work; update status only after verified completion.
- Keep numerical definitions in the versioned metric registry; chart definitions reference metric IDs. Never duplicate fee, supply, currency, attribution or chart logic in pages.
- TypeScript strict; Python typed service boundaries; Pydantic request/response contracts; Zod for client validation. Generate TypeScript from OpenAPI; no independently maintained duplicate DTOs. Prefer explicit modules to speculative abstractions.
- Raw token amounts use integers/decimal strings, Decimal arithmetic and NUMERIC; never JavaScript Number for financial aggregation. API decimals are strings. UTC half-open periods `[start,end)` everywhere.
- Validate document JSON, nodes, filters, identifiers, sizes and ownership on the server. Do not accept `user_id` as authorization. Derive owner from a verified session; test access with two users.
- Every quantitative publication needs a source, definition version, dataset version, calculation and limitations. Missing is not zero; unavailable is not fake data. Fixtures stay isolated and visibly labeled.
- Purchases, fees, protocol revenue, treasury payouts, burns and issuance are different metrics. Treasury purchases do not reduce total supply. Preserve bounds as bounds. Never extrapolate sampled attribution to the full market.
- Live charts explicitly indicate latest data; every saved document revision pins the last observed dataset. Historical revisions, exports and model artifacts never silently refresh. See [reproducibility](docs/REPRODUCIBILITY.md).
- Do not restart stopped RPC collectors or remove `STOP_PUBLIC_COLLECTION`. Do not execute cloud SQL, paid providers or new bulk collection by default. Offline reproduction uses saved inputs. See [pipeline](docs/DATA_PIPELINE.md).
- Add a dependency only when required by a bounded task: compare existing tools, review maintenance/license, pin the resolved version, commit lockfiles, and record significant choices. No invented current package versions.
- Update API/schema/editor/metric docs and relevant ADR when behavior changes; update source verification dates after checking providers. Never describe a planned command as working.

## Commands, tests and Done

Currently available offline commands are in [REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md); they can rewrite legacy derived outputs, so reproduce in a disposable copy. Target application commands in [README.md](README.md) must first be created by foundation tasks.

Done means implemented acceptance criteria; appropriate unit/integration/E2E tests; two-user authorization checks for private resources; accessible loading/empty/error/stale states; no credentials or fabricated data; reproducible artifacts; updated docs/tasks; clean focused diff. Required checks are in [TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md). No application tests can currently be claimed to pass because there is no application.

Prohibited shortcuts: hardcoded financial results, mocked production charts, causal claims from correlation, silent source substitution, client-only ownership, public caching of private content, arbitrary user code execution, replacing preserved research, or marking blocked data gates DONE.
