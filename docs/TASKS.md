# Implementation backlog

**Mandatory execution entry point: [PLAN.md](../PLAN.md).** Choose work only through that plan and TEAM_PLAN.md assignments. This file is the sole registry for task statuses, dependencies, claims, acceptance criteria and verification evidence.

Version 1.0 • 5 November 2026. **All application tasks are TODO; none are implemented by this documentation delivery.** Implementation requires user approval. P0 blocks MVP release, P1 is a strong enhancement, P2 is deferred. S≈one bounded small change, M≈several coordinated modules, L≈complex integration/research work; these are relative effort, not day estimates. Dependency IDs refer to verified task completion; a forward numeric dependency is intentional where a later epic supplies a service. See [roadmap](IMPLEMENTATION_ROADMAP.md).

Every task includes description, priority, dependencies, implementation steps, expected modules, acceptance, tests, complexity and status. Steps listed with semicolons are sequential within that task. Before starting, read its epic specification and the relevant API/schema/security contracts. Mark BLOCKED only with an explicit missing input/dependency; mark DONE only after all acceptance and required checks pass. No P1/P2 work displaces an uncompleted P0 critical path.

## EPIC 01 — Repository Foundation

Specification: [ARCHITECTURE.md](ARCHITECTURE.md).

### NI-001 — Initialize repository and pin tooling

- **Epic:** 01 — Repository Foundation
- **Priority:** P0
- **Dependencies:** —
- **Complexity:** M
- **Status:** IN_PROGRESS
- **Claimed by:** Codex / Python requirements and judge setup
- **Execution role:** A
- **Started at:** 2026-11-05T18:34:46+03:00
- **Scope:** User authorized repository/collaborator setup, then a Python requirements baseline and judge deployment instructions. Python dependencies are now pinned/tested; frontend/workspace runtime tooling remains pending. Do not mark the full NI-001 DONE for this subset.
- **Repository setup result:** Private ILYUTKICK/near-intelligence created; main pushed; BkycnocTbI accepted the invitation; active write access verified through the collaborator-permission API. User explicitly selected documentation/mockups only; raw research remains local and excluded from the published history.
- **Repository setup verification:** Approved-path/history audit, secret-pattern scan, git diff --cached --check, preserved original artifact hashes, successful remote push and invitation API response. Runtime/toolchain acceptance criteria have not been performed.
- **Handoff:** Repository and Python dependency setup are complete. No active file claim remains after this subset; the next role-A agent may resume the remaining frontend/workspace/runtime criteria. NI-001 stays IN_PROGRESS until all its acceptance criteria pass.
- **Dependency setup started at:** 2026-11-05T18:57:15+03:00
- **Branch/worktree:** feat/ni-001-python-requirements; /Users/ilyutkinn/Desktop/Near

**Description:** Create the first maintainable project envelope without changing saved research or design artifacts. Implementation begins only after user approval.

**Implementation steps:** Inventory files and ignore generated caches/secrets; initialize Git if still absent; select supported Node/pnpm/Python/uv versions; add root workspace metadata and exact tool pins; record dependency/license evidence.

**Expected files/modules:** package.json; pnpm-workspace.yaml; .node-version; .python-version; requirements.in; requirements.txt; .gitignore; README.md; docs/DEPENDENCIES.md; docs/JUDGE_SETUP.md

**Acceptance criteria:** Clean bootstrap preserves archive bytes; no real secrets or raw private files staged; declared runtime versions are installed and compatible.

**Testing requirements:** Clean-directory dependency/tool preflight; compare pre/post archive hashes; review ignore rules with representative raw and generated files.

**Python dependency result:** requirements.in, hash-pinned requirements.txt, .python-version and contributor/judge instructions prepared. Fresh macOS ARM64 CPython3.13.3 install/import/pip-check and synthetic scientific/plot smoke passed; Linux x86_64/manylinux2.28 binary wheel target install passed (not Linux runtime execution). Full application/container/data reproduction is not implemented or claimed.

### NI-002 — Create web and API runtime skeletons

- **Epic:** 01 — Repository Foundation
- **Priority:** P0
- **Dependencies:** NI-001
- **Complexity:** M
- **Status:** TODO

**Description:** Establish typed frontend/API boundaries with actual runnable health paths and reproducible dependencies.

**Implementation steps:** Initialize Next App Router and strict TS; initialize FastAPI/Pydantic project with settings; pin resolved pnpm/uv locks; migrate requirements.in declarations into pyproject.toml, export root requirements.txt from the frozen uv.lock and verify parity; provide native run scripts; smoke-check scientific dependency wheels on selected Python.

**Expected files/modules:** apps/web/package.json; apps/web/tsconfig.json; apps/api/pyproject.toml; apps/api/src/near_api/main.py; pnpm-lock.yaml; apps/api/uv.lock

**Acceptance criteria:** Both services boot with documented commands; missing required configuration fails with readable errors; no collector or model starts on boot.

**Testing requirements:** Fresh frozen installs; frontend build/typecheck; API liveness request; import smoke for pandas/NumPy/SciPy/statsmodels.

### NI-003 — Create database roles and initial schema migrations

- **Epic:** 01 — Repository Foundation
- **Priority:** P0
- **Dependencies:** NI-002
- **Complexity:** L
- **Status:** TODO

**Description:** Create the initial identity/role/migration foundation; later domain tasks add their own dataset, chart, document, model and export tables.

**Implementation steps:** Define users/profile and DB session base; create Alembic baseline; configure separate runtime/migration/operator roles and transaction-local identity; add DB-only Compose service and initial identity indexes.

**Expected files/modules:** apps/api/src/near_api/db/; apps/api/alembic/; docker-compose.yml

**Acceptance criteria:** Empty database upgrades; users/profile ownership works; runtime cannot bypass RLS; no automatic ingestion. Domain-specific FKs/current-version constraints are verified in their owning tasks.

**Testing requirements:** Real PostgreSQL upgrade/down/up; two-user RLS smoke; invalid FKs, numeric overflow and transaction rollback cases.

### NI-004 — Establish OpenAPI generation and typed clients

- **Epic:** 01 — Repository Foundation
- **Priority:** P0
- **Dependencies:** NI-002
- **Complexity:** M
- **Status:** TODO

**Description:** Keep one executable contract for Python boundaries and TypeScript consumers.

**Implementation steps:** Define common errors, selections, decimal-string and quality schemas; expose OpenAPI; generate TS client; add reproducible generation/drift check scripts; document endpoint evolution.

**Expected files/modules:** apps/api/src/near_api/schemas/; packages/shared-types/; scripts/generate-api.*

**Acceptance criteria:** Generated client compiles; decimal values remain strings; unknown fields fail; no independently maintained duplicate DTOs.

**Testing requirements:** Contract fixtures for success/error/null/bound data; generation twice produces identical files; TS strict compile.

### NI-005 — Add baseline CI and developer checks

- **Epic:** 01 — Repository Foundation
- **Priority:** P0
- **Dependencies:** NI-001, NI-002, NI-003, NI-004
- **Complexity:** M
- **Status:** TODO

**Description:** Make contributor commands executable and distinguish app correctness from documentation validation.

**Implementation steps:** Wire lint/typecheck/unit/integration commands; add isolated PostgreSQL CI; check relative docs links/task metadata; protect credentialed provider calls from PR CI; document actual commands.

**Expected files/modules:** .github/workflows/checks.yml; package.json; apps/api/tests/; CONTRIBUTING.md

**Acceptance criteria:** Fresh CI installs frozen locks and runs checks without provider secrets; no production/raw archive mutation; failing contract drift blocks merge.

**Testing requirements:** Run the workflow locally or in CI; intentionally invalid schema/client sample fails the appropriate check, then remove it.

## EPIC 02 — Design System

Specification: [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

### NI-006 — Implement design tokens and typography

- **Epic:** 02 — Design System
- **Priority:** P0
- **Dependencies:** NI-002
- **Complexity:** S
- **Status:** TODO

**Description:** Translate the ivory/forest/editorial direction into centralized accessible styling.

**Implementation steps:** Create semantic CSS variables and spacing/type scales; choose licensed self-hosted fonts/fallbacks; wire theme in app shell; measure actual text/control contrast.

**Expected files/modules:** apps/web/src/styles/tokens.css; apps/web/src/app/layout.tsx; font assets/license notes

**Acceptance criteria:** No page-specific arbitrary palette needed; hero/body/UI typography scales at phone/desktop; token contrast meets documented roles.

**Testing requirements:** Build and focused visual review at360/1440; automated contrast checks for used combinations; font-failure fallback inspection.

### NI-007 — Build accessible interaction primitives

- **Epic:** 02 — Design System
- **Priority:** P0
- **Dependencies:** NI-006
- **Complexity:** M
- **Status:** TODO

**Description:** Create the small reusable control set needed across the product.

**Implementation steps:** Add selected shadcn primitives; implement buttons/input/select/dialog/drawer/menu; define pending/disabled/error/focus states; use44px touch targets and persistent labels.

**Expected files/modules:** apps/web/src/components/ui/

**Acceptance criteria:** Keyboard operation and modal focus/return work; pending controls prevent duplicate submit; errors retain input; no unnecessary UI kit imports.

**Testing requirements:** Keyboard component integration tests for dialog/menu/forms; axe checks; manual touch-target review.

### NI-008 — Create public and workspace layout shells

- **Epic:** 02 — Design System
- **Priority:** P0
- **Dependencies:** NI-007
- **Complexity:** M
- **Status:** TODO

**Description:** Implement one configurable navigation source for desktop and mobile.

**Implementation steps:** Create canonical route registry and public header/footer; add workspace grouped sidebar/breadcrumbs; implement mobile drawer and content width breakpoints; keep workspace auth hook pluggable.

**Expected files/modules:** apps/web/src/lib/navigation.ts; apps/web/src/components/layout/

**Acceptance criteria:** All labels/paths match IA; no Strategy/Portfolio routes; mobile has no page overflow; current route and skip navigation accessible.

**Testing requirements:** Route-registry assertions; keyboard drawer/focus tests; responsive visual checks at360/768/1440.

### NI-009 — Build common data and async states

- **Epic:** 02 — Design System
- **Priority:** P0
- **Dependencies:** NI-007
- **Complexity:** S
- **Status:** TODO

**Description:** Make missing, stale and failed data distinct from verified zero throughout UI.

**Implementation steps:** Implement quality badge, skeleton, empty/unavailable/error panel, retry and persistent save status; map typed quality codes; provide accessible explanatory copy.

**Expected files/modules:** apps/web/src/components/data-state/

**Acceptance criteria:** Partial/stale/bound states retain units/date/limitations; an empty array never automatically renders zero; status is not color-only.

**Testing requirements:** State matrix component tests including null and true zero; screen-reader status review; no fabricated production fixture values.

### NI-010 — Create chart frame and source drawer

- **Epic:** 02 — Design System
- **Priority:** P0
- **Dependencies:** NI-006, NI-007, NI-009
- **Complexity:** M
- **Status:** TODO

**Description:** Provide consistent analytical framing before wiring rendering.

**Implementation steps:** Implement title/units/range/mode/freshness/actions slots; source/definition drawer; accessible summary/table region; responsive toolbars; no provider-specific fetch in component.

**Expected files/modules:** apps/web/src/features/charts/ChartFrame.tsx; SourceDrawer.tsx

**Acceptance criteria:** One frame supports public/editor/export metadata; source timestamps and bounds never disappear on small screens; controls keyboard reachable.

**Testing requirements:** Component checks with synthetic clearly labeled states; focus/overflow tests; source link sanitization.

## EPIC 03 — Public Website

Specification: [UI_SCREEN_SPECIFICATIONS.md](UI_SCREEN_SPECIFICATIONS.md).

### NI-011 — Create public editorial routes and mechanism section

- **Epic:** 03 — Public Website
- **Priority:** P0
- **Dependencies:** NI-008, NI-004
- **Complexity:** M
- **Status:** TODO

**Description:** Build the real public reading surface and conditional economic value-chain explanation.

**Implementation steps:** Create landing/research/methodology route shells using reviewed prose; add activity→fees→revenue→conversion→retention/supply diagram as semantic HTML; create stable section anchors.

**Expected files/modules:** apps/web/src/app/(public)/; public content module

**Acceptance criteria:** Pages render server-side without login; mechanism differentiates purchases and burns; no fake metrics or unfinished buttons.

**Testing requirements:** Anonymous route smoke; heading/anchor/link checks; mobile reading-width and keyboard review.

### NI-012 — Bind landing to approved findings and metrics

- **Epic:** 03 — Public Website
- **Priority:** P0
- **Dependencies:** NI-011, NI-029, NI-033
- **Complexity:** M
- **Status:** TODO

**Description:** Turn landing into an evidence-bearing introduction with source-qualified real values.

**Implementation steps:** Select at most3 meaningful metrics; fetch shared analytical services; add for/against findings with CL citations; implement unavailable/stale fallback and workspace/research CTAs.

**Expected files/modules:** apps/web/src/app/(public)/page.tsx; features/public-research/

**Acceptance criteria:** Every quantitative landing value links definition/dataset; archive dates visible; no live badge without refresh evidence; CTAs reach correct destinations.

**Testing requirements:** API-to-render integration against saved approved input; unavailable-source case; claim citation trace and responsive review.

### NI-013 — Publish methodology and reproduction content

- **Epic:** 03 — Public Website
- **Priority:** P0
- **Dependencies:** NI-011, NI-026, NI-029, NI-051
- **Complexity:** M
- **Status:** TODO

**Description:** Expose technical methods and limitations so a reviewer can assess the data before trusting results.

**Implementation steps:** Render provider/definition/cleaning/readiness sections; link sanitized manifests and actual source code; show access/rights restrictions; mark commands available only after implemented.

**Expected files/modules:** apps/web/src/app/(public)/methodology/; content/methodology.*

**Acceptance criteria:** Page covers source limitations and exact periods; short attribution/supply bounds explicit; no unsupported guarantee of public raw access.

**Testing requirements:** Reference/download permissions checks; follow one source→transform→metric path; verify command labels against available tooling.

### NI-014 — Create public thesis with claim registry

- **Epic:** 03 — Public Website
- **Priority:** P0
- **Dependencies:** NI-011, NI-029, NI-051
- **Complexity:** L
- **Status:** TODO

**Description:** Present the complete original conditional thesis rather than marketing copy.

**Implementation steps:** Implement fifteen sections and H1–H4 status/rationale; bind CL-001–CL-009 to pinned evidence; include contrary quantity/supply/price findings; leave model section explicitly pending until NI-070 finalization.

**Expected files/modules:** apps/web/src/features/public-research/; apps/api/src/near_api/publications/

**Acceptance criteria:** All claims have source/version/scope; three-window quantities and bounds accurate; public content cannot include private editor metadata.

**Testing requirements:** Independent claim-value audit; public projection allowlist tests; stale/insufficient-data assessment cases.

### NI-015 — Deliver public analytics explorer

- **Epic:** 03 — Public Website
- **Priority:** P0
- **Dependencies:** NI-033, NI-034, NI-011
- **Complexity:** M
- **Status:** TODO

**Description:** Allow anonymous exploration using exactly the shared chart/query implementation.

**Implementation steps:** Wire canonical public data/category/chart routes; synchronize validated selection in URL; render source/quality/table; route save/add actions through safe auth continuation.

**Expected files/modules:** apps/web/src/app/(public)/data/; apps/web/src/app/(public)/charts/

**Acceptance criteria:** All five categories have real available charts or honest explanations; identical public/private queries give same pinned values; unsupported filters not ignored.

**Testing requirements:** Anonymous chart journey; URL/back navigation tests; API equality checks and invalid range/filter recovery.

## EPIC 04 — Authentication

Specification: [AUTHENTICATION_SECURITY.md](AUTHENTICATION_SECURITY.md).

### NI-016 — Configure managed authentication environment

- **Epic:** 04 — Authentication
- **Priority:** P0
- **Dependencies:** NI-002
- **Complexity:** M
- **Status:** TODO

**Description:** Establish Supabase identity configuration without creating a custom password store.

**Implementation steps:** Configure dev identity provider with asymmetric keys, verification and callback allowlist; validate env schema; document project setup and recovery templates; separate dev/prod secrets.

**Expected files/modules:** apps/web/src/lib/auth/; apps/api/src/near_api/settings.py; .env.example

**Acceptance criteria:** Provider issuer/audience/algorithm match tested config; no service-role credential in normal browser path; placeholders fail safely.

**Testing requirements:** Settings validation; provider development-project smoke; inspect built frontend for server secrets.

### NI-017 — Implement same-origin login and cookie lifecycle

- **Epic:** 04 — Authentication
- **Priority:** P0
- **Dependencies:** NI-016, NI-007
- **Complexity:** L
- **Status:** TODO

**Description:** Provide registration/login/logout/recovery with server-readable sessions and safe return navigation.

**Implementation steps:** Implement auth handlers/pages, PKCE/state callback, HttpOnly cookie rotation and CSRF; refresh server-side; preserve short-lived chart action context; generic auth errors.

**Expected files/modules:** apps/web/src/app/api/auth/; apps/web/src/app/(auth)/

**Acceptance criteria:** Email verification/recovery works; browser JS receives no tokens; external redirects rejected; logout clears caches/cookies and revokes refresh.

**Testing requirements:** Provider-backed dev E2E; CSRF/open-redirect/expired link tests; cookie attribute inspection at production-like TLS origin.

### NI-018 — Verify JWT and bootstrap application principal

- **Epic:** 04 — Authentication
- **Priority:** P0
- **Dependencies:** NI-016, NI-003
- **Complexity:** M
- **Status:** TODO

**Description:** Make the API authenticate independently of gateway trust.

**Implementation steps:** Implement bounded JWKS cache and allowlisted signature verification; validate iss/aud/exp/nbf/sub; bootstrap users/profile from verified subject; reject disabled local users.

**Expected files/modules:** apps/api/src/near_api/auth/; apps/api/src/near_api/users/

**Acceptance criteria:** Forged/wrong-provider tokens fail closed; UUID owner never comes from request body; unknown kid retries JWKS once only.

**Testing requirements:** Signed test JWT matrix and JWKS outage/rotation cases; verify bootstrap cannot create arbitrary subjects.

### NI-019 — Enforce request-scoped ownership and RLS

- **Epic:** 04 — Authentication
- **Priority:** P0
- **Dependencies:** NI-018, NI-003
- **Complexity:** L
- **Status:** TODO

**Description:** Centralize authorization for all private repositories and nested references.

**Implementation steps:** Add principal-aware transaction/repository helpers; set transaction-local DB identity; define policies/composite ownership checks; standardize absent/not-owned404; limit operator role.

**Expected files/modules:** apps/api/src/near_api/db/security.py; repositories/; alembic policies

**Acceptance criteria:** Pooled connections cannot retain another user identity; runtime role cannot bypass policies; private list/search scoped before pagination.

**Testing requirements:** Alice/Bob reads/writes/searches; pooled transaction reset; malicious owner field and cross-owner FK probes.

### NI-020 — Verify authentication recovery and session boundaries

- **Epic:** 04 — Authentication
- **Priority:** P0
- **Dependencies:** NI-017, NI-018, NI-019
- **Complexity:** M
- **Status:** TODO

**Description:** Close login/session edge cases before private workflows depend on them.

**Implementation steps:** Implement session endpoint/cache clearing; handle revoked refresh and disabled users; preserve editor memory draft on expiry; test same-origin final routing and rate guards.

**Expected files/modules:** apps/web/src/features/auth/; apps/api/tests/auth/; apps/web/e2e/auth.*

**Acceptance criteria:** Account switching clears private state; invalid credentials nonenumerating; token expiry window documented; recovery cannot expose previous user content.

**Testing requirements:** Two-browser session tests; expiry-during-action; logout/cache bleed; rate limit and JWKS failure tests.

## EPIC 05 — Workspace Shell

Specification: [USER_JOURNEYS.md](USER_JOURNEYS.md).

### NI-021 — Protect workspace routes and shell

- **Epic:** 05 — Workspace Shell
- **Priority:** P0
- **Dependencies:** NI-008, NI-020
- **Complexity:** M
- **Status:** TODO

**Description:** Connect the existing layout to authenticated navigation without relying on UI for resource ownership.

**Implementation steps:** Add server session gate and safe redirect; render grouped nav/account menu; retain active route and mobile focus; display auth errors separately from source errors.

**Expected files/modules:** apps/web/src/app/workspace/layout.tsx; features/workspace/

**Acceptance criteria:** Anonymous user reaches login safely; authenticated pages use private no-store requests; route gate does not replace backend ownership.

**Testing requirements:** Anonymous/authenticated route tests; internal returnTo preservation; mobile drawer keyboard check.

### NI-022 — Implement owner-scoped home aggregation API

- **Epic:** 05 — Workspace Shell
- **Priority:** P0
- **Dependencies:** NI-019, NI-004
- **Complexity:** M
- **Status:** TODO

**Description:** Return research continuation data with bounded queries and independent public indicator failures.

**Implementation steps:** Build recent document/chart/insight projections using current revisions; cap lists at5; include workflow counts and selected shared indicators; avoid N+1 and private caching.

**Expected files/modules:** apps/api/src/near_api/workspace/; schemas/home.py

**Acceptance criteria:** No other user rows/counts leak; stale/unavailable indicator does not fail entire home; progress measures work completion only.

**Testing requirements:** Two-user empty/recent lists; query-count bound; one failing indicator and deleted-target cases.

### NI-023 — Build My Research and recent-item views

- **Epic:** 05 — Workspace Shell
- **Priority:** P0
- **Dependencies:** NI-021, NI-037
- **Complexity:** M
- **Status:** TODO

**Description:** Give users a usable entry point to persisted documents.

**Implementation steps:** Implement title search/updated sort/pagination; create/rename/delete actions with pending/error retention; link to document IDs; show first-use research explanation.

**Expected files/modules:** apps/web/src/app/workspace/research/page.tsx; features/documents/list/

**Acceptance criteria:** Lists only owner documents; rename/delete respect revision; no synthetic sample docs in production; create navigates to persisted editor.

**Testing requirements:** Browser create/list/search/rename/delete; two-user and stale-revision cases; responsive list review.

### NI-024 — Build research-focused workspace Home

- **Epic:** 05 — Workspace Shell
- **Priority:** P0
- **Dependencies:** NI-021, NI-022, NI-023, NI-035
- **Complexity:** M
- **Status:** TODO

**Description:** Help users resume research without creating another oversized metric dashboard.

**Implementation steps:** Render greeting/create/continue; recent docs/charts/notes; checklist progress; ≤3 contextual indicators and explorer links; separate empty states.

**Expected files/modules:** apps/web/src/app/workspace/page.tsx

**Acceptance criteria:** Fresh user can create and returning user resume within two actions; no confidence/conviction score; failed indicators do not hide documents.

**Testing requirements:** First-use and returning-user E2E; keyboard action order; source outage and mobile checks.

### NI-025 — Implement profile and minimal settings

- **Epic:** 05 — Workspace Shell
- **Priority:** P0
- **Dependencies:** NI-020, NI-021
- **Complexity:** S
- **Status:** TODO

**Description:** Provide useful account preferences and honest privacy controls.

**Implementation steps:** Add me read/update API; validate display name/timezone; settings for local draft clearing/session/logout; document operator-assisted deletion; avoid absent billing/team controls.

**Expected files/modules:** apps/api/src/near_api/users/routes.py; workspace/profile/; workspace/settings/

**Acceptance criteria:** Only verified subject profile editable; timezone changes display only; local draft deletion explicit; no editable user ID or false account-deletion success.

**Testing requirements:** Profile validation and ownership; timezone UTC calculation invariance; clear-draft/logout UI checks.

### NI-072 — Add lightweight private research organization

- **Epic:** 05 — Workspace Shell
- **Priority:** P1
- **Dependencies:** NI-023, NI-040, NI-062
- **Complexity:** M
- **Status:** TODO

**Description:** Help users organize growing document lists after the basic create/search/resume workflow is reliable.

**Implementation steps:** Choose bounded private document tags and favorite flag rather than folders/teams; add ownership-indexed metadata migration/API; add list filters and keyboard controls; keep organization outside scientific content unless explicitly exported as metadata.

**Expected files/modules:** apps/api/src/near_api/documents/organization.py; migration; apps/web/src/features/documents/list/

**Acceptance criteria:** Tags/favorites are private, searchable and owner-scoped; no document evidence/hash is silently rewritten; empty/deleted tag filters recover; core lists remain fast.

**Testing requirements:** Alice/Bob tag-filter isolation; duplicate tag normalization; pagination/sort behavior; metadata edit does not change frozen research/export.

## EPIC 06 — Data Infrastructure

Specification: [DATA_PIPELINE.md](DATA_PIPELINE.md).

### NI-026 — Verify provider capability, entitlement and rights

- **Epic:** 06 — Data Infrastructure
- **Priority:** P0
- **Dependencies:** NI-001
- **Complexity:** M
- **Status:** TODO

**Description:** Close operational data feasibility beyond the documentation-only source inspection.

**Implementation steps:** Review source register; record exact endpoint/auth/quota/history/terms; perform one bounded approved probe per needed adapter; identify allowed refresh source and raw redistribution constraints; preserve stopped collectors.

**Expected files/modules:** docs/SOURCE_VERIFICATION.md; apps/api/src/near_api/ingestion/capabilities/; sanitized probe artifacts

**Acceptance criteria:** Chosen P0 sources have explicit access/coverage/limits/rights evidence or remain BLOCKED with OQ ID; no cloud/paid/bulk request without authorization.

**Testing requirements:** Validate capability schemas/probe response; inspect secret redaction; verify caps and stop flags prevent disabled calls.

### NI-027 — Import existing archives read-only

- **Epic:** 06 — Data Infrastructure
- **Priority:** P0
- **Dependencies:** NI-003, NI-026
- **Complexity:** M
- **Status:** TODO

**Description:** Reuse real saved research without treating its aggregate scope as complete raw-chain data.

**Implementation steps:** Inventory required manifests/artifacts; verify byte hashes; sanitize credential-bearing metadata; import source lineage and aggregate/raw roles; preserve original files; record licensing visibility.

**Expected files/modules:** apps/api/src/near_api/ingestion/archive.py; tests/fixtures/archive/

**Acceptance criteria:** Archive bytes unchanged; manifest identifies precise cohort/date scopes and partial audits; no missing source silently replaced by a fixture.

**Testing requirements:** Import same archive twice idempotently; bad hash/missing input rejected; compare source and stored metadata.

### NI-028 — Implement immutable dataset staging and publication

- **Epic:** 06 — Data Infrastructure
- **Priority:** P0
- **Dependencies:** NI-027
- **Complexity:** L
- **Status:** TODO

**Description:** Create atomic versioned data delivery and reproducible artifact storage.

**Implementation steps:** Add dataset/artifact/observation migrations; build canonical hashing/manifest builder; persist staged observations/artifacts; validate dataset membership; publish approved active pointer in one transaction; retain superseded versions.

**Expected files/modules:** apps/api/src/near_api/datasets/; storage/; CLI dataset commands

**Acceptance criteria:** Failed validation cannot change active data; identical semantic input deduplicates appropriately; old versions and hashes remain queryable.

**Testing requirements:** Crash-before-publish and transaction rollback tests; concurrent publish lock; revised history creates new version without mutating old.

### NI-029 — Implement exact metric computations and quality

- **Epic:** 06 — Data Infrastructure
- **Priority:** P0
- **Dependencies:** NI-028
- **Complexity:** L
- **Status:** TODO

**Description:** Centralize the real P0 amounts and explicit unavailable metric definitions.

**Implementation steps:** Implement purchases/payouts/price estimate/supply change/bounds and source-qualified fees/volume; use Decimal; validate periods, denominators and quality propagation; emit registered definitions.

**Expected files/modules:** apps/api/src/near_api/metrics/; metric registry; tests/metrics/

**Acceptance criteria:** Historical CL amounts reconcile; missing≠zero; purchases not deducted from supply; lower-bound ratio reported upper-bound; unavailable revenue remains null.

**Testing requirements:** Independent event aggregation including duplicate/failure/internal transfer; UTC boundary and price-gap cases; compare saved summary totals exactly.

### NI-030 — Add one bounded scheduled refresh adapter

- **Epic:** 06 — Data Infrastructure
- **Priority:** P0
- **Dependencies:** NI-026, NI-028, NI-029
- **Complexity:** M
- **Status:** TODO

**Description:** Demonstrate a genuinely regularly updated series with last-good reliability.

**Implementation steps:** Implement verified finalized-header or other approved low-cost adapter; enforce allowlist/budgets/locks/checkpoints; validate/publish new version; schedule opt-in; display source freshness and failure.

**Expected files/modules:** apps/api/src/near_api/ingestion/providers/; cli.py; deployment timer config

**Acceptance criteria:** At least one real approved refresh publishes valid data;429/auth failure retains last good; startup defaults disabled; legacy collectors remain stopped.

**Testing requirements:** Controlled HTTP failure/schema/pagination tests; bounded authorized live smoke and recorded fresh block hash/time; scheduler overlap test.

## EPIC 07 — Analytics and Charts

Specification: [CHART_SYSTEM.md](CHART_SYSTEM.md).

### NI-031 — Define versioned chart and metric registries

- **Epic:** 07 — Analytics and Charts
- **Priority:** P0
- **Dependencies:** NI-029, NI-004
- **Complexity:** M
- **Status:** TODO

**Description:** Make charts extensible through definitions instead of custom pages.

**Implementation steps:** Add metric/chart registry migrations; create immutable registry schemas and initial valid chart entries; bind metric definition UUIDs and units; define allowed ranges/filters/categories; include renderer version and source lineage.

**Expected files/modules:** apps/api/src/near_api/charts/registry.py; schemas/charts.py

**Acceptance criteria:** All chart metrics resolve; unsupported/unavailable metrics not advertised as live; adding a supported definition needs no new page implementation.

**Testing requirements:** Registry integrity tests; invalid filter/unit/metric references rejected; version increments do not modify old definitions.

### NI-032 — Deliver metrics, chart views and source APIs

- **Epic:** 07 — Analytics and Charts
- **Priority:** P0
- **Dependencies:** NI-031
- **Complexity:** M
- **Status:** TODO

**Description:** Expose one normalized selection/data contract to every UI context.

**Implementation steps:** Implement public catalogs/series/chart-view/dataset/source endpoints; resolve one approved dataset per request; validate range/filter/source; add bounded version-keyed caching.

**Expected files/modules:** apps/api/src/near_api/metrics/routes.py; charts/routes.py; datasets/routes.py

**Acceptance criteria:** Queries include decimal strings/quality/timestamps; latest excludes staged data; source details redact secrets; identical selections resolve consistently.

**Testing requirements:** API contract and filter fuzz cases; staged/approved visibility; cache-key collision checks; source outage with last-good behavior.

### NI-033 — Implement reusable interactive ECharts renderer

- **Epic:** 07 — Analytics and Charts
- **Priority:** P0
- **Dependencies:** NI-032, NI-010
- **Complexity:** L
- **Status:** TODO

**Description:** Render real daily/comparison/scatter data with consistent interaction and accessible alternatives.

**Implementation steps:** Create pure typed option builder; integrate modular ECharts and ARIA/SVG; implement date inspection/table/range; handle missing/bounds; lazy mount/cancel stale requests.

**Expected files/modules:** apps/web/src/features/charts/renderer/; ChartView.tsx

**Acceptance criteria:** Public/editor share renderer; exact values accessible without hover; missing gaps not interpolated; metadata/units survive range changes.

**Testing requirements:** Renderer/data-table integration; large decimal formatting; keyboard/touch range checks; lazy unmount/resource cleanup.

### NI-034 — Build chart library and detail navigation

- **Epic:** 07 — Analytics and Charts
- **Priority:** P0
- **Dependencies:** NI-033
- **Complexity:** M
- **Status:** TODO

**Description:** Provide discoverable analytical charts with validated selection URLs.

**Implementation steps:** Implement search/category/preview/detail; sync range/source filters; show definitions/quality; implement public action continuation payloads and pending UI.

**Expected files/modules:** apps/web/src/features/charts/library/; app chart routes

**Acceptance criteria:** Search/filter reflects catalog; chart version/range survives navigation; stale/unavailable states actionable; no arbitrary URL fetch fields.

**Testing requirements:** Browser search/open/back/range journey; unsupported query recovery; anonymous private-action auth continuation.

### NI-035 — Persist saved chart instances

- **Epic:** 07 — Analytics and Charts
- **Priority:** P0
- **Dependencies:** NI-019, NI-034
- **Complexity:** M
- **Status:** TODO

**Description:** Allow independent users to save and resume canonical analytical contexts.

**Implementation steps:** Add saved-chart migration; implement saved-chart API/repository and list/detail actions; validate chart/dataset/filter refs; idempotent create; mode/label edits; clear private cache on account changes.

**Expected files/modules:** apps/api/src/near_api/charts/saved.py; workspace/saved-charts/

**Acceptance criteria:** Save/reopen preserves definition/range/filters; live updates labeled; Bob cannot enumerate or attach Alice instances; removal leaves global definitions intact.

**Testing requirements:** Alice/Bob CRUD and nested-ref tests; duplicate-submit retry; range/mode validation; save→reopen E2E.

### NI-071 — Add advanced supported analytical filters

- **Epic:** 07 — Analytics and Charts
- **Priority:** P1
- **Dependencies:** NI-035, NI-043, NI-058
- **Complexity:** M
- **Status:** TODO

**Description:** Extend the small P0 selection set only where verified source dimensions support a meaningful economic comparison.

**Implementation steps:** Select one verified dimension such as treasury recipient or provider version; add its immutable mapping/filter schema; implement multi-selection and comparison with independent query keys; retain source/unit/coverage context in save, insight and export.

**Expected files/modules:** apps/api/src/near_api/charts/filter_registry.py; apps/web/src/features/charts/filters/; metric/definition versions

**Acceptance criteria:** No unsupported integrator/customer classifications; aggregate and filtered values reconcile within declared universe; old chart versions still render; filters persist across saved instances/documents/exports.

**Testing requirements:** Filter schema/API mismatch rejected; dimension sum/reconciliation; source-version mismatch; range/filter/save/reopen/export journey.

## EPIC 08 — Research Documents

Specification: [EDITOR_SPECIFICATION.md](EDITOR_SPECIFICATION.md).

### NI-036 — Implement canonical document schema and revision service

- **Epic:** 08 — Research Documents
- **Priority:** P0
- **Dependencies:** NI-019, NI-028, NI-004
- **Complexity:** L
- **Status:** TODO

**Description:** Create one authoritative versioned JSON document and atomic relational projections.

**Implementation steps:** Add document/version/block/insight/hypothesis/evidence projection migrations and composite FKs; define editor schema and all P0 node attrs; validate IDs/private/public refs/limits; implement revision CAS transaction/content hash/pins interface; regenerate block projections.

**Expected files/modules:** apps/api/src/near_api/documents/schema.py; service.py; projections.py

**Acceptance criteria:** Invalid content creates no partial revision; old content immutable; same-document evidence links and owner rules enforced; empty doc valid.

**Testing requirements:** Schema fixtures for each block; duplicate/dangling IDs; transaction rollback; concurrent CAS race; projection round-trip.

### NI-037 — Implement document CRUD and version endpoints

- **Epic:** 08 — Research Documents
- **Priority:** P0
- **Dependencies:** NI-036
- **Complexity:** M
- **Status:** TODO

**Description:** Expose real create/list/rename/delete/save/reopen operations.

**Implementation steps:** Add API routes and pagination; create first empty revision; version title changes; implement idempotent create/save and ownership checks; version detail and deletion constraints.

**Expected files/modules:** apps/api/src/near_api/documents/routes.py; tests/documents/

**Acceptance criteria:** If-Match required;409 never overwrites; not-owned IDs404; deletes remove private child projections/jobs while retaining shared scientific data.

**Testing requirements:** Alice/Bob endpoint matrix; missing If-Match; idempotency timeout-after-commit; list ordering and deletion FK tests.

### NI-038 — Prototype Tiptap custom block integration

- **Epic:** 08 — Research Documents
- **Priority:** P0
- **Dependencies:** NI-002, NI-009, NI-031
- **Complexity:** M
- **Status:** TODO

**Description:** Validate the editor choice against financial node interactions before broad UI implementation.

**Implementation steps:** Integrate core editor in isolated route/test; build chart atomic node view and one insight card; test selection, IME, paste, undo and nested controls; record decision outcome.

**Expected files/modules:** apps/web/src/features/editor/prototype/; docs/DECISIONS.md

**Acceptance criteria:** Typing and undo survive React node updates; chart controls escape to editor; no custom rich-text engine; failure triggers explicit ADR before dependent implementation.

**Testing requirements:** Browser IME/paste/selection/undo checks; mount/unmount lifecycle; node schema serialization/reload test.

### NI-039 — Build editor layout and block operations

- **Epic:** 08 — Research Documents
- **Priority:** P0
- **Dependencies:** NI-038, NI-037, NI-007
- **Complexity:** L
- **Status:** TODO

**Description:** Deliver the three-pane research editor and complete P0 block interactions.

**Implementation steps:** Create outline/paper/context tools; implement insert/remove/reorder/duplicate/headings/table/risk/divider; keyboard alternatives; stable IDs/remap links; responsive drawers.

**Expected files/modules:** apps/web/src/features/editor/; workspace/research/[documentId]/

**Acceptance criteria:** All P0 structural operations serialize valid schema; duplicate/delete preserve or explicitly update evidence links; mobile supports one-pane editing.

**Testing requirements:** Browser keyboard/drag/duplicate/undo/reopen; outline accuracy; reference deletion confirmation and responsive checks.

### NI-040 — Implement autosave, manual save and conflict recovery

- **Epic:** 08 — Research Documents
- **Priority:** P0
- **Dependencies:** NI-039
- **Complexity:** L
- **Status:** TODO

**Description:** Prevent data loss during network failures, concurrent tabs and session expiry.

**Implementation steps:** Implement1s idle/5s max save scheduling; one in-flight request; coalesce later content; CAS/idempotency; truthful saved status;409 recovery download/new-copy flow; memory draft/session recovery.

**Expected files/modules:** apps/web/src/features/editor/persistence/; document query hooks

**Acceptance criteria:** Acknowledging older payload never clears newer dirty edits; network timeout retry cannot duplicate revisions; no silent last-write-wins; unsaved content recoverable.

**Testing requirements:** Two-tab race; offline/reconnect; expired auth; timeout-after-commit; typing-during-save and unload warning tests.

## EPIC 09 — Chart Embedding

Specification: [EDITOR_SPECIFICATION.md](EDITOR_SPECIFICATION.md).

### NI-041 — Implement Add Chart to owned research

- **Epic:** 09 — Chart Embedding
- **Priority:** P0
- **Dependencies:** NI-040, NI-033
- **Complexity:** M
- **Status:** TODO

**Description:** Connect explorer/library selection to persisted document blocks.

**Implementation steps:** Build owned destination picker/Create New; implement revision-checked chart insertion API; capture inspected definition/dataset/range/filter context; handle retry/conflict and return link.

**Expected files/modules:** apps/api/src/near_api/documents/chart_blocks.py; apps/web/src/features/charts/add-to-research/

**Acceptance criteria:** One confirmation appends one valid block; owner validated; source change does not silently alter inspected evidence; duplicate retry idempotent.

**Testing requirements:** Public→login→destination flow; Bob/private snapshot probe; double submit/concurrent revision cases; reopen inserted chart.

### NI-042 — Complete interactive chart node behavior

- **Epic:** 09 — Chart Embedding
- **Priority:** P0
- **Dependencies:** NI-041
- **Complexity:** M
- **Status:** TODO

**Description:** Make embedded charts inspectable while preserving editor focus and local note context.

**Implementation steps:** Reuse chart renderer for node view; add range/filter/definition/source/refresh/Add Insight controls; show live/saved/changed badges; isolate chart control events from text selection.

**Expected files/modules:** apps/web/src/features/editor/nodes/LiveChart.tsx

**Acceptance criteria:** Same chart definition behaves consistently in explorer/editor; range changes are explicit document edits; chart failures do not disable prose editing.

**Testing requirements:** Keyboard/touch node interaction; range filter save/reopen; missing source; editor focus/undo regression.

### NI-043 — Freeze resolved evidence on every document revision

- **Epic:** 09 — Chart Embedding
- **Priority:** P0
- **Dependencies:** NI-042, NI-028
- **Complexity:** L
- **Status:** TODO

**Description:** Guarantee that old research and exports reconstruct exactly the data inspected at save.

**Implementation steps:** Complete server pin resolution and context hashing; validate observed versions; persist chart/metric/renderer pins; historical reader never queries latest; mark live changes on working view.

**Expected files/modules:** apps/api/src/near_api/documents/context_resolver.py; dataset pin tests; historical viewer

**Acceptance criteria:** Source revision leaves old document/context hashes unchanged; no silent latest substitution; missing pinned artifact produces reconstruction error.

**Testing requirements:** Publish new dataset after save and compare old revision/chart CSV; race between preview/save; source definition version mismatch.

### NI-044 — Add explicit snapshot management UX

- **Epic:** 09 — Chart Embedding
- **Priority:** P1
- **Dependencies:** NI-043, NI-035
- **Complexity:** M
- **Status:** TODO

**Description:** Expose convenient freezing/browsing independently of mandatory save-time pins.

**Implementation steps:** Implement snapshot create/list/read/delete with immutable selection/context; Freeze/Compare to Live controls; prevent referenced deletion; show owner-scoped storage metadata.

**Expected files/modules:** apps/api/src/near_api/charts/snapshots.py; apps/web/src/features/charts/snapshots/

**Acceptance criteria:** Snapshot remains fixed through refresh; same-owner FK enforced; referenced snapshot cannot disappear; no change to existing revisions.

**Testing requirements:** Two-user snapshot matrix; freeze→refresh→compare; deletion409 for referenced snapshot; content hash regeneration.

### NI-045 — Implement template and public research duplication

- **Epic:** 09 — Chart Embedding
- **Priority:** P1
- **Dependencies:** NI-040, NI-050, NI-014
- **Complexity:** M
- **Status:** TODO

**Description:** Create reusable starting structure and independent private copies with retained attribution.

**Implementation steps:** Add eight-section empty-content template; clone explicit publication revision; allocate new block/insight/hypothesis/evidence IDs; rewrite internal links; preserve public pins and source attribution.

**Expected files/modules:** apps/api/src/near_api/documents/templates.py; publications/duplicate.py; template picker

**Acceptance criteria:** Public source unchanged after private edits; no private editorial metadata copied; idempotent retry returns same copy; links remain valid.

**Testing requirements:** ID remap graph test; template save/reopen; public copy/edit isolation; unavailable source publication and permissions.

## EPIC 10 — Insights and Evidence

Specification: [FEATURE_SPECIFICATIONS.md](FEATURE_SPECIFICATIONS.md).

### NI-046 — Define structured insight and evidence node contracts

- **Epic:** 10 — Insights and Evidence
- **Priority:** P0
- **Dependencies:** NI-036, NI-038
- **Complexity:** M
- **Status:** TODO

**Description:** Centralize the typed research annotations shared by editor/API/projections.

**Implementation steps:** Implement four insight types, three evidence classifications, hypothesis/risk schema and chart/model contexts; author timestamps server-side; generate TS validation types.

**Expected files/modules:** apps/api/src/near_api/insights/schemas.py; editor node schema; generated client

**Acceptance criteria:** Context contains selected range/filters/dataset and stable IDs; no trusted client owner field; rich-text content bounded/sanitized.

**Testing requirements:** Schema matrix including unsupported classifications/context; timestamp handling; canonical JSON round-trip and generated client compile.

### NI-047 — Persist context-preserving chart insights

- **Epic:** 10 — Insights and Evidence
- **Priority:** P0
- **Dependencies:** NI-046, NI-040, NI-043
- **Complexity:** M
- **Status:** TODO

**Description:** Allow observations/risks/conclusions to survive chart refresh and document reopen.

**Implementation steps:** Implement insight convenience API as document revision mutation; chart/editor insight form; store original inspected context; modify/delete with explicit reference cleanup.

**Expected files/modules:** apps/api/src/near_api/insights/service.py; apps/web/src/features/editor/insights/

**Acceptance criteria:** An insight stays tied to original data after live refresh; saves update canonical JSON/projections atomically; owner and revision checked.

**Testing requirements:** Create/edit/reopen after new dataset; Bob reference denial; deleting linked insight with/without cleanup;409 conflict.

### NI-048 — Implement hypothesis blocks and assessments

- **Epic:** 10 — Insights and Evidence
- **Priority:** P0
- **Dependencies:** NI-047
- **Complexity:** M
- **Status:** TODO

**Description:** Let researchers state an independent question and record an authored evidence assessment.

**Implementation steps:** Add hypothesis CRUD through revision service; create/edit card and statement/assessment controls; link stable ID to outline/context tools; distinguish editorial assessment from objective confidence.

**Expected files/modules:** apps/api/src/near_api/evidence/hypotheses.py; editor/nodes/Hypothesis.tsx

**Acceptance criteria:** Untested/insufficient/mixed states available; no automated support badge from missing metrics; existing evidence references remain valid on text edit.

**Testing requirements:** CRUD/reopen; assessment state matrix; same-document FK and deletion reference tests.

### NI-049 — Implement evidence relationships and classifications

- **Epic:** 10 — Insights and Evidence
- **Priority:** P0
- **Dependencies:** NI-048
- **Complexity:** M
- **Status:** TODO

**Description:** Connect supporting, contradicting and uncertain artifacts to hypotheses without dangling references.

**Implementation steps:** Add evidence APIs and typed target resolver; validate chart/insight same revision or public model/citation; store explanation; enforce deletion/remap rules; never infer causality from classification.

**Expected files/modules:** apps/api/src/near_api/evidence/links.py; editor/nodes/Evidence.tsx

**Acceptance criteria:** For/against evidence can coexist; cross-document private links rejected; no unvalidated polymorphic target ID; projections match canonical content.

**Testing requirements:** Dangling/cross-owner/cross-doc target tests; duplicate/remap; historical revision preserves prior relationship; unknown model/citation.

### NI-050 — Build evidence navigation and research context panels

- **Epic:** 10 — Insights and Evidence
- **Priority:** P0
- **Dependencies:** NI-049, NI-042
- **Complexity:** M
- **Status:** TODO

**Description:** Make the connected argument inspectable in the editor instead of scattered notes.

**Implementation steps:** Add per-hypothesis evidence list/counts; click-through to chart/insight source context; risk/counterargument panels; Add Insight from explorer after destination selection; keyboard/focus behaviors.

**Expected files/modules:** apps/web/src/features/editor/evidence/; context panels

**Acceptance criteria:** User can trace hypothesis→contrary evidence→pinned chart→source and back; current selection changes do not rewrite original insight context.

**Testing requirements:** Complete J4 browser flow; opposing evidence case; keyboard navigation/return focus; save/reopen linked graph.

## EPIC 11 — Econometric Models

Specification: [ECONOMETRIC_METHODOLOGY.md](ECONOMETRIC_METHODOLOGY.md).

### NI-051 — Implement model dataset readiness gate

- **Epic:** 11 — Econometric Models
- **Priority:** P0
- **Dependencies:** NI-026, NI-029
- **Complexity:** M
- **Status:** TODO

**Description:** Choose an admissible empirical question before fitting rather than manufacturing revenue data.

**Implementation steps:** Add model definition/run migrations and typed registry; build calendar-aligned prepared table; profile missing/zero/bound data and policy/source changes; enforce project nobs/parameter rules; select true-revenue or explicitly named proxy spec; record OQ-02 risk.

**Expected files/modules:** research/models/readiness.py; model configs; readiness report

**Acceptance criteria:** No gross-fee/payout proxy passes as protocol_revenue; gaps/exclusions explicit; short attribution dataset rejected for daily long-run inference.

**Testing requirements:** Real archive readiness report; missing/zero/nonadjacent days; lower-bound outcome rejected; reproducible reason codes.

### NI-052 — Implement fixed deterministic econometric estimator

- **Epic:** 11 — Econometric Models
- **Priority:** P0
- **Dependencies:** NI-051
- **Complexity:** L
- **Status:** TODO

**Description:** Fit one defensible real-data association with declared transformations and covariance.

**Implementation steps:** Create registered spec/config and pure design builder; implement positive log/difference or justified alternative; explicit intercept/control/rank checks; OLS/HAC settings; no arbitrary user code.

**Expected files/modules:** research/models/fit.py; configs/gross_fee_activity_v1.json; apps/api research CLI

**Acceptance criteria:** Same input/config/lock reproduces fitted values within tolerance; mechanical fee-volume limitation attached; no p-value-driven search or invented coefficients.

**Testing requirements:** Synthetic known-behavior estimator tests separate from actual archive run; rank failure, zero policy and HAC config serialization.

### NI-053 — Generate diagnostics, robustness and interpretation artifacts

- **Epic:** 11 — Econometric Models
- **Priority:** P0
- **Dependencies:** NI-052
- **Complexity:** L
- **Status:** TODO

**Description:** Make the model assessable beyond a single coefficient or high R².

**Implementation steps:** Produce sample/exclusion table, CI/SE/results, ADF/KPSS settings, residual/ACF/Ljung–Box and heteroskedasticity/influence checks; limited prespecified sensitivity; authored economic interpretation/limits.

**Expected files/modules:** research/models/diagnostics.py; research/reports/<run>/

**Acceptance criteria:** All defined diagnostics and failed/undefined-test reasons included; source/price/covariance sensitivity reported; causal/sustainability claims bounded.

**Testing requirements:** Compare diagnostic outputs to direct statsmodels calls; deliberately nonstationary/mechanical synthetic cases; inspect real run report for omissions.

### NI-054 — Publish reproducible model artifacts and APIs

- **Epic:** 11 — Econometric Models
- **Priority:** P0
- **Dependencies:** NI-053, NI-004, NI-028
- **Complexity:** L
- **Status:** TODO

**Description:** Expose only reviewed immutable results that reviewers can actually rerun offline.

**Implementation steps:** Write full data/code/lock/config/design/result manifests; implement research verify --offline; add operator publication gate and public definition/readiness/run/manifest APIs; build public model page.

**Expected files/modules:** apps/api/src/near_api/research/; research/reports/; apps/web model routes

**Acceptance criteria:** Clean offline reproduction succeeds on permitted inputs; unpublished/failed runs never look like results; endpoint access triggers no fit/provider call; actual statistics replace pending placeholder only here.

**Testing requirements:** No-network reproduction with exact data hashes/stat tolerance; missing input/lock rejection; public unpublished404; API output complete.

### NI-055 — Add model-result block to private research

- **Epic:** 11 — Econometric Models
- **Priority:** P1
- **Dependencies:** NI-054, NI-039, NI-050
- **Complexity:** M
- **Status:** TODO

**Description:** Embed immutable statistical results with editable interpretation while keeping estimation fixed.

**Implementation steps:** Implement modelResult node/view/serializer and Add Model picker; validate published run/dataset pin; show coefficient/diagnostic summary and source link; render export fallback.

**Expected files/modules:** apps/web/src/features/editor/nodes/ModelResult.tsx; backend schema/export mapper

**Acceptance criteria:** Block always references exact published run; editing prose cannot change coefficients; source revision does not refit; model context preserved.

**Testing requirements:** Insert/save/reopen/export; unpublished run rejected; changing data pointer leaves old result unchanged; keyboard selection.

## EPIC 12 — Research Export

Specification: [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

### NI-056 — Create frozen document export representation

- **Epic:** 12 — Research Export
- **Priority:** P0
- **Dependencies:** NI-043, NI-050, NI-054
- **Complexity:** M
- **Status:** TODO

**Description:** Translate an acknowledged immutable revision into a complete export plan.

**Implementation steps:** Read owned exact version; validate all pins/citations; map every P0 block into deterministic intermediate representation; include title/author/date/source/model references and data-table specs.

**Expected files/modules:** apps/api/src/near_api/exports/ir.py; schemas/export.py

**Acceptance criteria:** No latest-data lookups; all required references resolvable; unsupported/missing block fails with detail; title/content correspond to same revision.

**Testing requirements:** Mutate current document/source after request and compare frozen IR; every block mapper; missing artifact and cross-owner cases.

### NI-057 — Render static chart assets from frozen contexts

- **Epic:** 12 — Research Export
- **Priority:** P0
- **Dependencies:** NI-056, NI-033
- **Complexity:** M
- **Status:** TODO

**Description:** Reuse chart data/options for portable exported evidence.

**Implementation steps:** Add pinned Node ECharts SSR renderer with typed stdin schema; Python subprocess without shell/network; generate SVG plus normalized CSV/hash; enforce timeout/size and safe filenames.

**Expected files/modules:** apps/web/scripts/render-charts.mjs; apps/api/src/near_api/exports/charts.py

**Acceptance criteria:** Export series/units/quality equal frozen view; no arbitrary remote/HTML code; renderer version/hash recorded; corrupt input fails safely.

**Testing requirements:** Compare chart CSV to pinned series; subprocess timeout and injection/path traversal; SVG safe output and no-network test.

### NI-058 — Deliver Markdown ZIP export jobs and download

- **Epic:** 12 — Research Export
- **Priority:** P0
- **Dependencies:** NI-057, NI-040
- **Complexity:** L
- **Status:** TODO

**Description:** Provide one reliable complete MVP export rather than several incomplete formats.

**Implementation steps:** Add export-job/idempotency/audit migrations as needed; implement owned queued export jobs/lease/retry/TTL; generate research.md/assets/CSV/manifest ZIP; status polling/download; exclude private filesystem paths and sanitized secret-bearing metadata.

**Expected files/modules:** apps/api/src/near_api/exports/; export worker CLI; editor Export dialog

**Acceptance criteria:** User downloads exact revision with charts/notes/sources/model refs/timestamps; Bob cannot poll/download; expired artifacts return typed state; late edits do not affect bundle.

**Testing requirements:** Unzip full research export and validate hashes/links; worker crash/retry idempotency; owner matrix; edit-during-export and expiry.

### NI-059 — Implement PDF export from frozen representation

- **Epic:** 12 — Research Export
- **Priority:** P1
- **Dependencies:** NI-058
- **Complexity:** M
- **Status:** TODO

**Description:** Add a polished static report without diverging from evidence used by Markdown.

**Implementation steps:** Choose maintained PDF renderer after license review; use frozen IR/static chart assets; paginate headings/tables/figures and source appendix; inspect rendered pages; preserve manifest reference.

**Expected files/modules:** apps/api/src/near_api/exports/pdf.py; PDF templates

**Acceptance criteria:** PDF contains correct attribution/date/pins and no clipped charts/tables; no live screenshot fetching; only enabled after Markdown path passes.

**Testing requirements:** Render representative short/long report pages and visually inspect all; compare source/data references to ZIP; failure and private download checks.

### NI-060 — Design revocable read-only sharing

- **Epic:** 12 — Research Export
- **Priority:** P2
- **Dependencies:** NI-058, NI-062
- **Complexity:** M
- **Status:** TODO

**Description:** Plan later explicit publication of user research without making private UUID URLs public.

**Implementation steps:** Define consent/snapshot/revocation/expiry and access-token hashes; perform threat model; add separate publication projection only after P0 completion; update schema/API/docs before implementation.

**Expected files/modules:** docs/sharing design ADR; future sharing module

**Acceptance criteria:** Sharing never exposes live private drafts or historical versions by default; revocation and asset permissions specified; user explicitly opts in.

**Testing requirements:** Threat-model review and future unauthorized/token-expiry/revocation tests; no P2 implementation before all P0 gates.

## EPIC 13 — Quality and Security

Specification: [TESTING_STRATEGY.md](TESTING_STRATEGY.md).

### NI-061 — Add business/data integration regression suite

- **Epic:** 13 — Quality and Security
- **Priority:** P0
- **Dependencies:** NI-035, NI-050
- **Complexity:** M
- **Status:** TODO

**Description:** Verify financial and research invariants across DB/API/editor boundaries.

**Implementation steps:** Create independent event oracles; cover exact sums/internal hops/failed receipts/missing data/bounds; test revision projections and prepared-dataset membership; isolate all fixtures from production.

**Expected files/modules:** apps/api/tests/integration/; apps/web tests/; CI test data

**Acceptance criteria:** Invariant suite catches double counting and source mutation; fixture labels explicit; no tests alter archives or access paid providers.

**Testing requirements:** Run focused suite against real PostgreSQL; exact monetary assertions; document graph and API-contract regressions.

### NI-062 — Complete adversarial ownership and security audit

- **Epic:** 13 — Quality and Security
- **Priority:** P0
- **Dependencies:** NI-020, NI-058, NI-061
- **Complexity:** L
- **Status:** TODO

**Description:** Prove that users and untrusted content cannot cross private resource boundaries.

**Implementation steps:** Exercise every private endpoint family with Alice/Bob; nested refs/export/download/RLS pools; CSRF/JWT/cache/XSS/SSRF/path limits; verify no secrets in builds/logs/public manifests; close findings.

**Expected files/modules:** apps/api/tests/security/; apps/web/e2e/security/; security review report

**Acceptance criteria:** Zero unauthorized reads/writes/downloads; safe404 behavior; no private cache bleed or executable content; unresolved critical/high flaws block release.

**Testing requirements:** Full attack matrix; JWT/JWKS and cross-tab account tests; malicious rich text/tooltip/file names; production secret scan.

### NI-063 — Verify complete research workflow end to end

- **Epic:** 13 — Quality and Security
- **Priority:** P0
- **Dependencies:** NI-058, NI-054, NI-015, NI-024
- **Complexity:** M
- **Status:** TODO

**Description:** Test the actual product outcome across browser, API, data and persistence.

**Implementation steps:** Automate anonymous claim trace→login→save chart→create doc→add chart/insight/contrary evidence→reopen→export; inspect DB version and ZIP hashes; add source-outage branch.

**Expected files/modules:** apps/web/e2e/research-workflow.spec.ts; test harness

**Acceptance criteria:** Journey uses real services/persisted state and approved saved data, not mocked primary API; export and reopened document match expected context; failed source remains explicit.

**Testing requirements:** Playwright full-stack run on isolated DB/auth/storage; verify downloaded assets and DB revision; repeat for second user isolation.

### NI-064 — Verify accessibility, responsiveness and performance

- **Epic:** 13 — Quality and Security
- **Priority:** P0
- **Dependencies:** NI-009, NI-039, NI-063
- **Complexity:** M
- **Status:** TODO

**Description:** Validate usability of the core research flow across input devices and document sizes.

**Implementation steps:** Run axe/keyboard/screen-reader/touch checks at360/768/1440; inspect chart table and editor IME/reorder; measure PRD budgets with200 blocks/20 refs/366 points; fix bottlenecks.

**Expected files/modules:** apps/web/e2e/accessibility/; performance fixtures; QA report

**Acceptance criteria:** No core-flow accessibility blocker or page overflow; chart data accessible without hover; measured budgets pass or documented limits revised with justification.

**Testing requirements:** Real-device mobile pass when available; keyboard/screen reader review; documented staging performance run and lazy-chart mount checks.

### NI-065 — Plan advisory integrity checks and optional AI tools

- **Epic:** 13 — Quality and Security
- **Priority:** P2
- **Dependencies:** NI-062, NI-063
- **Complexity:** M
- **Status:** TODO

**Description:** Add future evidence assistance without making an LLM the source of facts.

**Implementation steps:** Specify deterministic metadata checks separately from interpretive judgments; define evidence-bound tool outputs and citation rules; maintain no-LLM workflow; update feature/API/ADR before implementation.

**Expected files/modules:** docs/integrity design ADR; future optional assistant module

**Acceptance criteria:** Missing citation/pin can be verified; contradiction/causality commentary advisory; no invented data/coefficient/source; P0 works without AI credentials.

**Testing requirements:** Future tool-contract and prompt-injection/evidence-grounding tests; verify optional outage cannot affect research editing/export.

## EPIC 14 — Deployment and Hackathon Demo

Specification: [DEPLOYMENT.md](DEPLOYMENT.md).

### NI-066 — Package portable local and production runtimes

- **Epic:** 14 — Deployment and Hackathon Demo
- **Priority:** P0
- **Dependencies:** NI-005, NI-030, NI-057
- **Complexity:** M
- **Status:** TODO

**Description:** Create immutable app images and a fresh-machine onboarding path without auto-starting collection.

**Implementation steps:** Add production Dockerfiles/web/API/export runtime; finish Compose profiles/env validation/readiness; include Node renderer and Python locks; restrict volumes/network/roles; document alternative native setup; implement the real clean-clone sequence in docs/JUDGE_SETUP.md using frozen Python/frontend locks, auth/config/migrations and an explicitly permitted input bundle.

**Expected files/modules:** Dockerfiles; docker-compose.yml; deployment/; README.md

**Acceptance criteria:** Fresh setup boots/migrates with documented commands; exact images reproducible; collectors off by default; API internal and persistent artifacts mounted; judge setup is tested on Linux/container runtime, not inferred from wheel availability.

**Testing requirements:** Clean build/Compose smoke; readiness/migration failure; inspect image secrets and renderer availability; scheduler disabled check.

### NI-067 — Deploy staging and production with safe configuration

- **Epic:** 14 — Deployment and Hackathon Demo
- **Priority:** P0
- **Dependencies:** NI-066, NI-062, NI-063
- **Complexity:** L
- **Status:** TODO

**Description:** Publish the authorized product at a real TLS origin with verified identity/data behavior.

**Implementation steps:** Resolve hosting/domain/budget/region; provision only after authorization; configure secrets/callbacks/TLS/DB roles/storage; backup before migrations; roll out immutable commit; enable only approved refresh.

**Expected files/modules:** deployment configs; release report; production env schema

**Acceptance criteria:** Final-origin auth/cookies work; data/source refresh real; private APIs not public-cached; health/logs safe; no synthetic primary metrics; rollback documented.

**Testing requirements:** Staging full workflow/security smoke then production bounded smoke; callback/expiry tests; provider failure leaves editing usable.

### NI-068 — Verify backups, restore and operational monitoring

- **Epic:** 14 — Deployment and Hackathon Demo
- **Priority:** P0
- **Dependencies:** NI-067
- **Complexity:** M
- **Status:** TODO

**Description:** Ensure published evidence and private research survive an operational failure.

**Implementation steps:** Configure DB/artifact offsite backup coherence; restore into isolated environment; verify hashes/owner/pins; add alerts for lag/job/error/storage; rehearse image rollback and active dataset pointer rollback.

**Expected files/modules:** deployment/backup/; monitoring rules; restore report

**Acceptance criteria:** Actual measured restore meets documented target or revised approved objective; no missing referenced artifacts; no credentials/private content in monitoring.

**Testing requirements:** Restore real test data and pinned model/export; compare manifests/RLS; simulate failed source, stuck lease and disk alert.

### NI-069 — Run hackathon demo and reviewer reproduction

- **Epic:** 14 — Deployment and Hackathon Demo
- **Priority:** P0
- **Dependencies:** NI-068, NI-064, NI-070
- **Complexity:** M
- **Status:** TODO

**Description:** Demonstrate the evidence-first investment workflow and independent reproducibility.

**Implementation steps:** Write five-to-seven-minute walkthrough; show supporting/contrary finding and unavailable metric; run new-user editor/export; reviewer reruns model offline; capture actual commit/URLs/results and limitations.

**Expected files/modules:** docs/DEMO_RUNBOOK.md; release evidence; research report bundle

**Acceptance criteria:** Demo works on deployed product; judge can inspect real sources and rerun permissible model; no fictitious numbers or hidden access barriers; all P0 tasks verified.

**Testing requirements:** Rehearse from clean browser and separate offline environment; verify source and ZIP hashes; record unresolved external judging/data risks and actual docs/JUDGE_SETUP.md commands/runtime/input hashes from a clean clone.

### NI-070 — Finalize and publish original research release

- **Epic:** 14 — Deployment and Hackathon Demo
- **Priority:** P0
- **Dependencies:** NI-014, NI-054, NI-013, NI-061
- **Complexity:** L
- **Status:** TODO

**Description:** Replace pending model sections with actual verified findings and a reviewed complete investment thesis.

**Implementation steps:** Audit fifteen sections/H1–H4/CL registry; insert actual model outputs/diagnostics and honest status; confirm rights/attribution/date/repository links; publish immutable content/evidence manifest; update landing and methodology.

**Expected files/modules:** research/reports/; publication seed/release manifest; public research content

**Acceptance criteria:** All claims cite versioned inputs/calculations; contrary evidence preserved; model run reproducible; no claim true protocol revenue unless gate passed; no private content or restricted raw artifact leakage.

**Testing requirements:** Independent source-to-claim review; publication visibility/license checks; rerun all cited calculations/model; public page/source link audit.
