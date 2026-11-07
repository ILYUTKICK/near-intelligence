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
- **Status:** DONE
- **Claimed by:** Codex / Python requirements and judge setup (previous session; subset complete, handed off below)
- **Execution role:** A
- **Started at:** 2026-11-05T18:34:46+03:00
- **Scope:** User authorized repository/collaborator setup, then a Python requirements baseline and judge deployment instructions. Python dependencies are now pinned/tested; frontend/workspace runtime tooling remains pending. Do not mark the full NI-001 DONE for this subset.
- **Repository setup result:** Private ILYUTKICK/near-intelligence created; main pushed; BkycnocTbI accepted the invitation; active write access verified through the collaborator-permission API. User explicitly selected documentation/mockups only; raw research remains local and excluded from the published history.
- **Repository setup verification:** Approved-path/history audit, secret-pattern scan, git diff --cached --check, preserved original artifact hashes, successful remote push and invitation API response. Runtime/toolchain acceptance criteria have not been performed.
- **Handoff (Codex → next role-A agent):** Repository and Python dependency setup are complete. No active file claim remains after this subset; the next role-A agent may resume the remaining frontend/workspace/runtime criteria. NI-001 stays IN_PROGRESS until all its acceptance criteria pass.
- **Dependency setup started at:** 2026-11-05T18:57:15+03:00
- **Branch/worktree:** feat/ni-001-python-requirements; /Users/ilyutkinn/Desktop/Near
- **Resumed by (new claim):** ZCode agent for ILYUTKICK, role A, session 42d29234 — resumed under the user's 2026-11-05 implementation authorization, per the Codex handoff above.
- **Resumed at:** 2026-11-05T19:34:30+03:00
- **Remaining scope (this session):** select supported Node/pnpm/uv versions, add root workspace metadata and exact tool pins (package.json, pnpm-workspace.yaml, .node-version), clean-directory tool/dependency preflight, archive-hash preservation check, ignore-rules review, and the user's implementation-authorization update in AGENTS.md/COLLABORATION.md.
- **Verification (tooling subset):** Clean-directory preflight in /tmp holding only declared manifests: node 24.22.2 vs declared family `24`, corepack 0.36.0, pnpm 12.16.1 resolved by corepack from the `packageManager` hex-integrity pin, CPython 3.13.3 vs `3.13`, uv 0.12.13 (matches the documented resolver). `pnpm install --lockfile-only` on the copied workspace metadata succeeded (lockfile kept in temp only). Fresh temp CPython 3.13.3 venv: hash-checked binary-only install from requirements.txt, `pip check` clean, all 14 direct imports, synthetic statsmodels OLS smoke. `git check-ignore` review: representative raw research JSON/SQL/scripts, captured JS, .env, node_modules/.venv/caches/logs all ignored; research Markdown, .env.example and new manifests correctly trackable; future apps/api/uv.lock not ignored (correct). Pre/post SHA-256 over research/ + product-plan/: 414 files byte-identical. Official Node release schedule fetched to confirm v24 LTS support until 2028-04-30; pnpm version taken from npm registry dist-tags, not memory.
- **Branch (tooling subset):** feat/ni-001-workspace-tooling; /Users/ilyutkinn/Desktop/Near
- **Result (tooling subset):** package.json (pnpm@12.16.1+sha512 hex integrity, engines node >=24 <25), pnpm-workspace.yaml (apps/web, packages/*), .node-version (24), installed Homebrew node@24 for verification. AGENTS.md/CONTRIBUTING.md/COLLABORATION.md now record the 5 November 2026 implementation authorization (role-A tasks, publish new app code/tests/config/docs in the private repo); README/DEPENDENCIES.md/JUDGE_SETUP.md document the pins, hex-digest format note and preflight evidence. No new ignore rules were necessary; existing rules already cover the newly introduced generated-artifact paths. No application code, dependencies or lockfiles were added (NI-002 scope).
- **Reviewer:** pending — role-B review requested on the pull request into main (NI-001 reviewer per TEAM_PLAN.md); merge waits for that review per the collaboration rules.
- **Completed at:** 2026-11-05T20:06:30+03:00

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
- **Status:** DONE
- **Re-closed at:** 2026-11-05T23:00:36+03:00 — PR #7 merged into main; verified on the post-merge tree: `requirements.in` absent, apps/api/pyproject.toml, apps/api/uv.lock and the regenerated root requirements.txt present. Documentation now matches the repository exactly.
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A — task closer per TEAM_PLAN.md; this session implements the web part, the API part is a concrete handoff to B below
- **Started at:** 2026-11-05T20:14:20+03:00
- **Branch/worktree:** feat/ni-002-web-skeleton (stacked on feat/ni-001-workspace-tooling); /Users/ilyutkinn/Desktop/Near
- **Scope split:** A (this session): apps/web Next.js App Router strict-TS skeleton, explicit root .env loading, Zod env contract, web health route, native run scripts, pnpm-lock.yaml. B (handoff): FastAPI/Pydantic settings project, pyproject.toml/uv.lock migration of requirements.in declarations, root requirements.txt export from the frozen lock with parity verification, API health path and run scripts. The task stays IN_PROGRESS until both parts satisfy every acceptance criterion; neither side may mark it DONE alone.
- **Web-part verification (A, 2026-11-05):** `pnpm install` fresh resolved 29 packages with pnpm 12.16.1; clean-directory copy of root/package.json+pnpm-workspace.yaml+pnpm-lock.yaml+apps/web/package.json passed `pnpm install --frozen-lockfile`; `tsc --noEmit` typecheck clean; `next build` succeeded (routes: `/` static, `/health` dynamic); production `next start` and dev-server boot verified with `/` 200 and `/health` 200 JSON `{status,service,appEnv,checkedAt}`; with the root .env removed, `/health` returns 503 with a readable message naming the missing required variables. Versions were taken from the npm registry on 2026-11-05: next 16.4.5, react/react-dom 19.3.1, zod 4.6.7, typescript 5.9.3 (mature 5.x line; the new 7.x native-compiler line is deliberately not adopted yet), @next/env 16.4.5. Root .env loading is explicit (repo root located via pnpm-workspace.yaml, loaded lazily in the serving process via @next/env; injected env always wins over the file).
- **Web-part result:** apps/web Next.js App Router strict-TS skeleton (package.json, tsconfig.json, next.config.ts, src/lib/env.ts Zod contract for APP_ENV/APP_ORIGIN/API_INTERNAL_URL, src/app layout + placeholder page without metrics or controls, /health process liveness) plus committed pnpm-lock.yaml. No eslint wiring (NI-005), no Tailwind/ECharts/Tiptap/TanStack (owning tasks). No collector/model code exists; only the web server starts.
- **Handoff to B (NI-002 API part):** implement the apps/api FastAPI/Pydantic-settings project per this card's steps: (1) pyproject.toml migrating the requirements.in direct declarations, preserving the reviewed baseline unless a justified update is recorded; (2) freeze uv.lock and export root requirements.txt from it per the DEPENDENCIES.md transition contract (`uv export --project apps/api --frozen --no-dev --no-emit-project --output-file requirements.txt`), verifying parity against the current 48-entry hash-pinned baseline and documenting any justified diff; (3) near_api settings with readable missing-configuration failures; (4) process-liveness endpoint mirroring the web `/health` JSON shape; (5) native run scripts matching README (`uv run --project apps/api uvicorn near_api.main:app --reload --port 8000`); (6) import smoke for pandas/NumPy/SciPy/statsmodels on the selected Python. Input contract from A: root workspace manifests committed on feat/ni-002-web-skeleton; .env.example lines 3–6 define APP_ENV/APP_ORIGIN/API_INTERNAL_URL already consumed by the web env schema. Neither booting service may start collectors or models. After B's part passes its criteria, the closer (A) records joint verification and only then may NI-002 be marked DONE.
- **User-authorized exception (2026-11-05T22:23:20+03:00):** participant A (ILYUTKICK) explicitly instructed this role-A agent to perform B's API part of NI-002 to unblock the role-A queue, with the exception documented in this card as requested. This is a task-scoped authorization: TEAM_PLAN.md ownership for future Python/data tasks (NI-003/NI-004/NI-018/…) is unchanged, those tasks remain for agent B, and B is still the designated reviewer of this PR's API part.
- **API-part verification (2026-11-05, under the user-authorized exception):** pyproject.toml migrated the requirements.in direct declarations (hatchling src layout, requires-python >=3.13); `uv lock` resolved 49 packages at the baseline cutoff recorded in `[tool.uv] exclude-newer = 2026-11-05T15:55:39Z`, so a bare `uv lock --check` passes and future re-resolution cannot silently drift. `uv export --project apps/api --frozen --no-dev --no-emit-project` regenerated root requirements.txt: parity vs the reviewed baseline is 48/48 packages with identical versions; 16 binary-heavy packages carry narrower hash sets (uv records the oldest compatible wheel baseline per OS/arch family plus the sdist) — verified by a fresh macOS ARM64 venv install with `--require-hashes --only-binary=:all:` (pip check clean) and a cross-platform CPython 3.13 x86_64 target install across the combined manylinux2014/2_27/2_28 tag set (107 packages, hash-checked); the synthetic single-tag manylinux_2_28 probe fails by pip's exact-tag construction and is documented. Runtime: `uv sync --project apps/api --frozen` built/installed near-api editable; all 11 direct imports including pandas/numpy/scipy/statsmodels passed; the documented `uv run --project apps/api uvicorn near_api.main:app --reload --port 8000` boots and `/health` returns 200 JSON mirroring the web shape; without the root .env `/health` returns 503 with a readable message naming APP_ENV/APP_ORIGIN/API_INTERNAL_URL; clean-copy `uv sync --frozen --dry-run` validates the fresh-machine path.
- **API-part result:** apps/api FastAPI skeleton — pyproject.toml, uv.lock, generated root requirements.txt (requirements.in removed per the DEPENDENCIES.md transition contract), src/near_api/{__init__,settings,main}.py with explicit lazy root-.env loading (injected env wins), SettingsError formatting validation issues, /health liveness mirroring the web JSON shape; docs disabled at the app level for now; nothing besides the HTTP server starts on boot. Docs updated: DEPENDENCIES.md transition section (completed), README tested/planned command split, JUDGE_SETUP Python-application row, AGENTS.md dependency-source convention.
- **Reviewer:** pending — role-B review requested on PR #3 (whole task: web + API parts); merge waits for that review per the collaboration rules.
- **Completed at:** 2026-11-05T22:58:40+03:00
- **Reopened — defect (2026-11-05T22:56:25+03:00):** post-merge verification of main (after PR #5/#6) found `requirements.in` still tracked although this card and DEPENDENCIES.md record it as removed with the uv freeze. The removal was documented but never executed. Fix: `git rm requirements.in` plus sharing-scope reference updates (AGENTS.md, docs/COLLABORATION.md) on branch fix/ni-002-remove-requirements-in, PR #7. Other NI-002 criteria re-verified unaffected: main contains apps/api + apps/web, apps/api/uv.lock and the regenerated root requirements.txt; the parity and runtime evidence stands. Status set back to IN_PROGRESS until the fix PR merges; re-close recorded below.
- **Re-closed at:** pending PR #7 merge — after merge, requirements.in is absent from main and the documentation matches the tree again.

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
- **Status:** DONE
- **Claimed by:** Codex / BkycnocTbI / session 01a1a2c9-f42d-7422-8e3e-755c9e33551b
- **Execution role:** B
- **Started at:** 2026-11-06T02:32:16+03:00
- **Branch/worktree:** feat/ni-003-database-foundation; D:/хахатон/near-intelligence
- **Dependency verification:** NI-002 is DONE and re-closed after PR #7; main cfdd914 contains the API runtime/uv.lock and no requirements.in. NI-026's separately published PR #14 records its operational BLOCKED state and does not gate NI-003. No competing NI-003 claim exists.
- **Scope:** Identity tables, Alembic, isolated runtime/migration/operator roles and transaction-local UUID identity; DB-only Compose definition for role-A review. Existing private/research archives are absent and untouched. PostgreSQL 18.6 is installed locally for real disposable-database checks; Docker execution is not available here.
- **Result:** Identity ORM/Alembic baseline, explicit four-secret role bootstrap, forced RLS/column privileges, bounded lazy runtime pool and transaction-local identity/reset, exact NUMERIC prevalidation, DB-only Compose and setup runbook. No domain tables, auth endpoints or ingestion are added.
- **Verification (6 November 2026):** `apps/api/.venv/Scripts/python.exe scripts/run-db-tests.py --pg-bin 'C:/Program Files/PostgreSQL/18/bin'` passes all 8 tests on native PostgreSQL 18.6 / CPython 3.13.15 / Windows 11. Fresh cluster bootstrap, empty upgrade/down/up, Alembic metadata drift, Alice/Bob and anonymous isolation, role/RLS/DDL escalation denial, pooled identity reset, disabled user, invalid FK/timezone/length, exact 78-digit NUMERIC, overflow and transaction rollback verified. Cluster stopped; git diff check passes. Docker is unavailable; container startup is explicitly unverified.
- **Handoff resolved:** ILYUTKICK merged the verified PR #15 at 2026-11-05T23:47:51Z into main 2111045. The counterpart's merge is recorded as acceptance of the DB-only contribution; no separate GitHub APPROVED review event exists. This role-B agent did not merge main. All original NI-003 native migration/role/RLS criteria passed; full container packaging remains NI-066.
- **Reviewer:** ILYUTKICK (role A), accepted by merging PR #15; formal review submission not recorded. [Database setup and evidence](DATABASE_SETUP.md).
- **Completed at:** 2026-11-06T02:47:51+03:00 (counterpart merge verified through GitHub API and fetched main).

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
- **Status:** DONE
- **Claimed by:** Codex / BkycnocTbI / session 01a1a2c9-f42d-7422-8e3e-755c9e33551b
- **Execution role:** B
- **Started at:** 2026-11-06T02:49:54+03:00
- **Branch/worktree:** feat/ni-004-openapi-contract; D:/хахатон/near-intelligence
- **Dependency verification:** NI-002 verified DONE; current main ac59b34 includes PR #14, leaving NI-026 BLOCKED operationally. NI-003 code/checks are submitted in PR #15 and await A review; it is not a dependency of NI-004. No competing NI-004 claim exists.
- **Scope:** Common strict Pydantic errors/selection/quality/decimal contracts; sanitized HTTP failures and read-only OpenAPI; reproducible generated TypeScript client and drift checks. No unimplemented business endpoint or simulated data is added.
- **Result:** Strict common errors, selections, UTC observations, decimal/raw string and quality models; sanitized HTTP failures; read-only OpenAPI; generated shared TypeScript/fetch client; deterministic offline generation/drift scripts and consumer runbook. No business endpoint or production fixture was added.
- **Verification (6 November 2026):** 6 Python contract/ASGI tests and existing 11 capability tests pass on CPython 3.13.15; shared-types filtered frozen pnpm install, strict TS compile and local typed-client test pass on Node 24.22.1 / pinned pnpm 12.16.1. Two generations have identical JSON/TS hashes; api:check and git diff check pass. Financial strings, null/bound metadata, unknown fields and failure redaction are exercised; Python dependencies unchanged.
- **Handoff resolved:** ILYUTKICK merged the checked PR #16 at 2026-11-06T00:06:07Z into main 706ff77. The counterpart's merge accepts the generated schema/client and root tooling contribution; no separate GitHub APPROVED review event is asserted. This role-B agent did not merge main. NI-005 is now dependency-ready; NI-031 still requires NI-029.
- **Reviewer:** ILYUTKICK (role A), accepted by merging PR #16. [API contract workflow and limitations](API_CONTRACT.md).
- **Completed at:** 2026-11-06T03:06:07+03:00 (counterpart merge verified through GitHub API and fetched main).

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-06T03:18:32+03:00
- **Branch/worktree:** feat/ni-005-ci-checks; /Users/ilyutkinn/Desktop/Near
- **Dependency verification:** NI-001/NI-002 DONE (own evidence), NI-003/NI-004 DONE (PRs #15/#16/#17 merged, cards verified on origin/main 7ba8af1). NI-026 is BLOCKED (provider credentials/quotas, OQ gates) and is not a dependency of this task.
- **Verification:** every CI step executed locally first: `pnpm install --frozen-lockfile`, `pnpm lint` (0 errors/0 warnings after fixing the three baseline findings), `pnpm typecheck`, `pnpm test` (52/52), `pnpm check:contrast` (22/22), `pnpm build`, `pnpm check:client-secrets` (no .env in CI → exits 0), `pnpm check:doc-links` (528 links resolve), `uv sync --frozen` + `uv lock --check`, `unittest` contracts + source-capabilities suites, `generate.mjs --check` (contract current). Bad-sample drills per the card: injected drift into the generated client **was not caught** — investigation found generate.mjs only exported its function with no CLI entry, so `node generate.mjs --check` was a silent no-op; added the standard CLI entry (affects B's file, flagged for B in the PR), after which the drill fails with exit 1 on drift and passes clean; a broken documentation link fails `check:doc-links` (exit 1) and passes after removal. Failing drift therefore blocks merge by construction. No provider secrets are needed or present in CI; database tests run in a disposable loopback PostgreSQL 18 cluster created by B's runner script (passwords generated inside the job).
- **Result:** .github/workflows/checks.yml (web: lint/typecheck/tests/contrast/build/secret-scan/doc-links/shared-types checks; api: frozen uv sync + lock --check + offline unittest suites + contract drift; database: PGDG PostgreSQL 18 + run-db-tests.py); root package.json scripts (lint/typecheck/test/build/check:contrast/check:client-secrets/check:doc-links/check:contracts/test:api:unit/test:api:db); apps/web ESLint flat config (eslint 10.14.0 + eslint-config-next 16.4.5, deps recorded in DEPENDENCIES.md) with a zero-warning baseline; scripts/check-doc-links.mjs; CLI entry added to packages/shared-types/scripts/generate.mjs; CONTRIBUTING/README document the real commands. Playwright `test:e2e` and the research `verify` CLI remain their own tasks' deliverables, stated in CONTRIBUTING.
- **Reviewer:** pending — role-B review requested on PR #18 (NI-005 reviewer per TEAM_PLAN.md).
- **CI run (the card's "locally or in CI" requirement):** run 42138945747 on this PR, commit 3628ef1 — all three jobs green (web 1m05s: lint/typecheck/52 tests/contrast/build/secret-scan/doc-links/shared-types; api 34s: frozen sync + lock check + offline suites + contract drift; database 1m00s: disposable PostgreSQL 18.6 cluster, migrations/roles/RLS/isolation suite). Iterations before green, all fixed with evidence: (1) lockfile for the eslint deps was forgotten in the first push; (2) api job lacked node deps for the drift check; (3) PG socket directory /var/run/postgresql owned by the postgres system user — chowned to the runner user; (4) secret scanner exited 1 on missing CI .env — now reports "nothing to scan"; (5) doc-links flagged the documented unshared research archive links — now skipped explicitly (research non-.md targets), 518 tracked links verified.
- **Completed at:** 2026-11-06T00:46:10+03:00

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-05T22:41:45+03:00
- **Branch/worktree:** feat/ni-006-design-tokens (stacked on feat/ni-002-web-skeleton); /Users/ilyutkinn/Desktop/Near
- **Selection note:** NI-005 stays TODO because its dependencies NI-003/NI-004 (role B) are not DONE; NI-006 is the earliest eligible role-A task whose dependency NI-002 is verified DONE.
- **Verification:** `pnpm --filter web check:contrast` — all 22 documented token pairings pass their WCAG targets (text pairs ≥4.5:1 measured 5.67–15.69; control boundaries/focus/chart series ≥3:1 measured 3.42–6.52); the script parses token values from tokens.css and exits non-zero on failure. `tsc --noEmit` strict typecheck and `next build` pass. Font checks: `next build` fails loudly when a font file is missing (renamed-file probe), computed styles in the browser confirm Newsreader/Inter actually load ("newsreader loaded", "inter loaded"), and the CSS/next-font fallback stacks (Georgia, system-ui + size-adjusted fallbacks) are declared for failure cases. Focused visual review via browser at 1440×900 and 360×780: hero renders 64/68 desktop and 40/44 phone exactly per spec, body 16/26, canvas #F6F4EC and text #17242D confirmed from computed styles; no horizontal overflow at 360 (screenshots committed under docs/verification/ni-006/).
- **Result:** apps/web/src/styles/tokens.css — full semantic token set from DESIGN_SYSTEM.md (colors, spacing 4–96, radii 12/8/16, elevation, focus, motion, type scale with phone hero override, layout widths) plus base shell styling and a reduced-motion guard; self-hosted SIL OFL 1.1 variable fonts Newsreader + Inter as WOFF2 with license files and provenance notes in apps/web/src/styles/fonts/; layout.tsx wires them via next/font/local (same-origin, no external font calls); `check:contrast` npm script. No page-specific palette values introduced anywhere.
- **Reviewer:** pending — role-B review requested on PR #4 (NI-006 reviewer per TEAM_PLAN.md).
- **Completed at:** 2026-11-05T22:52:10+03:00

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-05T23:00:36+03:00
- **Branch/worktree:** feat/ni-007-interaction-primitives; /Users/ilyutkinn/Desktop/Near
- **Verification:** `pnpm --filter web test` — 7/7 pass across 3 suites: dialog opens from keyboard, closes on Escape and returns focus to the trigger; dropdown menu opens via ArrowDown, moves focus between items, closes with Escape with focus return; Button with `pending` blocks duplicate submits (aria-busy + disabled, one invocation across click/dblclick); Input error state keeps the typed value, sets aria-invalid with an accessible description and a role=alert message; 44px touch-target assertions on all button variants and input; axe checks on rendered dialog, menu and form have no violations (the page-level `region` best-practice rule is disabled in component tests with a recorded rationale — landmark structure arrives with NI-008 layout shells). `tsc --noEmit` strict typecheck, `next build` and `check:contrast` (22/22) all pass. Radix behavior is exercised through real keyboard events in jsdom with minimal browser-API stand-ins (vitest.setup.ts).
- **Result:** apps/web/src/components/ui/ — Button (primary/secondary/quiet/destructive + pending/asChild, 44px, focus ring), Label, Input (error/aria-invalid/16px anti-zoom), Select (Radix keyboard model), Dialog (focus entry/escape/return), Drawer (vaul, safe-area), DropdownMenu (item targets, hover gated); lib/utils cn(); Tailwind v4 wired via postcss.config.mjs + globals.css `@theme inline` over the NI-006 tokens (no duplicated values; type-scale and radius utilities generated from token vars); vitest + Testing Library + jest-axe stack with local vitest-compatible types in apps/web/types/. Dependency review and declared licenses recorded in DEPENDENCIES.md. No UI kit imports; icons are inline SVG. ESLint wiring remains NI-005.
- **Reviewer:** pending — role-B review requested on PR #8 (NI-007 reviewer per TEAM_PLAN.md).
- **Completed at:** 2026-11-05T23:16:20+03:00

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-05T23:43:52+03:00
- **Branch/worktree:** feat/ni-008-layout-shells; /Users/ilyutkinn/Desktop/Near
- **Verification:** `pnpm --filter web test` — 31/31 pass (8 new): the route registry matches INFORMATION_ARCHITECTURE.md label-by-label (public 4 items, workspace 4 groups / 11 items), hrefs are unique, every entry enabled P0, and no label/path matches strategy|portfolio; the skip link is the first tabbable element targeting #main-content; the public header renders registry nav with aria-current on the active route; the mobile drawer opens from the keyboard, lists items, closes on Escape with focus restored (vaul focus trap) and shows workspace groups with availability notes; the workspace sidebar marks the active route via aria-current and exposes the mobile trigger; breadcrumbs link ancestors and aria-current the current page; axe passes on header and open drawer (region rule disabled with the recorded NI-007 rationale). `tsc --noEmit`, `next build`, `check:contrast` (22/22) pass. Browser visual review at 1440/768/360 on the dev server: horizontal overflow absent at all three widths (scrollWidth === viewport), DOM landmarks skip-link → banner → main → contentinfo verified in the accessibility tree, mobile drawer opens with grouped items (screenshots in docs/verification/ni-008/).
- **Result:** apps/web/src/lib/navigation.ts (canonical registry: public nav, workspace groups, auth entries, editorial anchors) + apps/web/src/lib/workspace-auth.tsx (pluggable anonymous-default auth context — replaced by the real session provider in NI-016/021 without touching shells) + apps/web/src/components/layout/ — SkipLink, PublicHeader (registry-driven, active route, sign-in action, mobile trigger), PublicFooter (honest framing, editorial anchors), MobileNavDrawer (one registry for desktop and mobile), WorkspaceSidebar (240px desktop + grouped mobile drawer), Breadcrumbs. Home page now renders the full public shell. No Strategy/Portfolio routes anywhere; no fake stats in the footer. Fix on this branch: workspace-auth renamed .tsx (JSX). Route protection itself is NI-021.
- **Reviewer:** pending — role-B review requested on PR #11 (NI-008 reviewer per TEAM_PLAN.md).
- **Completed at:** 2026-11-05T23:51:30+03:00

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-05T23:24:13+03:00
- **Branch/worktree:** feat/ni-009-data-states; /Users/ilyutkinn/Desktop/Near
- **Pre-task fix on this branch:** jsdom held at 30.1.3 — the 31.0.0 release published the same day violated pnpm 12's minimumReleaseAge supply-chain policy, and the auto-added exclusion in pnpm-workspace.yaml was removed in favor of the older, policy-compliant version (lockfile rebuilt via `pnpm clean --lockfile`; diff contained to the jsdom subtree; DEPENDENCIES.md updated).
- **Verification:** `pnpm --filter web test` — 14/14 pass (7 NI-007 suites + 7 new): the empty state renders explanatory copy with retained units/period/limitation and never renders a bare zero, while a genuine zero value in data still displays as zero (matrix contrast case); the unavailable state driven by the canonical DataQuality shape shows its reasons verbatim plus metadata and no zero; the quality badge labels all six statuses and the lower-bound/coverage text in visible text+glyph (not color alone); the stale notice states the freshness target and retains metadata next to still-visible values; ErrorPanel retry fires exactly once under click/dblclick storms (Button pending); SaveStatus is persistent, aria-live=polite and renders all four states with glyphs. `tsc --noEmit`, `next build` and `check:contrast` (22/22) pass. Axe runs on every rendered state with the page-level `region` rule disabled (landmarks = NI-008), consistent with NI-007.
- **Result:** apps/web/src/components/data-state/ — quality.ts (typed interim mirror of the canonical DataQuality contract from API_SPECIFICATION.md, to be replaced by generated shared types in NI-004), QualityBadge (status+bound+coverage, text not color), Skeleton, DataState panels (LoadingPanel, EmptyState, UnavailableState, ErrorPanel with retry, StaleNotice) retaining units/date/limitations metadata, SaveStatus (persistent, aria-live). No new dependencies. No production fixtures — all test data synthetic and labeled.
- **Reviewer:** pending — role-B review requested on PR #9 (NI-009 reviewer per TEAM_PLAN.md).
- **Completed at:** 2026-11-05T23:30:10+03:00

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-05T23:36:25+03:00
- **Branch/worktree:** feat/ni-010-chart-frame; /Users/ilyutkinn/Desktop/Near
- **Verification:** `pnpm --filter web test` — 23/23 pass (9 new): frame renders title/units/mode/quality badge with the freshness metadata line (period + last observed) as unconditional wrapping elements whose presence is asserted (they cannot disappear on small screens); the equivalent data table lives in a labeled scrollable region with an sr-only caption as its accessible name and states "not zero" for empty rows; the accessible summary is present; toolbar controls are keyboard reachable and Tab-walking reaches the source drawer trigger, whose Enter opens the provenance dialog showing provider name, license/access status, verification and last-success timestamps and lineage; the stale notice retains last-good values beside a live-mode badge; link sanitization renders only http(s) targets as anchors — javascript:/data:/protocol-relative/unparseable URLs become inert "(link withheld)" text and no javascript: anchor exists in the document; axe passes on the open drawer. `tsc --noEmit`, `next build`, `check:contrast` (22/22) pass.
- **Result:** apps/web/src/features/charts/ — chart-frame-types.ts (interim DataSource mirror, replaced by generated types in NI-004), ChartFrame (title/units/mode/quality/freshness slots, range+actions toolbar slot, accessible summary details, data table slot, stale notice; no fetching — plot is a child slot for NI-033), SourceDrawer (per-source license/access/verification/cadence/last-success/lineage + definition/formula/manifest links, URL sanitization), DataTable (labeled scroll region, tabular-nums). Metadata is never hidden at any breakpoint; the drawer reflows instead. No new dependencies.
- **Reviewer:** pending — role-B review requested on PR #10 (NI-010 reviewer per TEAM_PLAN.md).
- **Completed at:** 2026-11-05T23:41:00+03:00

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234 (interactive session; a second dispatch runs role B/NI-018 in a separate worktree)
- **Execution role:** A
- **Started at:** 2026-11-06T18:38:50+03:00
- **Branch/worktree:** feat/ni-011-public-routes; /Users/ilyutkinn/Desktop/Near
- **Dependency verification:** NI-008 DONE (PR #11), NI-004 DONE (PRs #16/#17) — cards verified on origin/main a592a2f.
- **Verification:** `pnpm --filter web test` — 57/57 pass (5 new): landing standfirst with the no-fake-metrics rule asserted (no percent signs in content) and registry links; research exposes stable anchors #h1–#h4 and #mechanism; the mechanism ordered list renders exactly the five stages in order and carries the explicit cautions "Treasury purchases do not reduce total supply — burns do" and the fees/revenue/payouts separation; unpublished hypothesis sections state their honest status (4 occurrences asserted); methodology carries #sources/#definitions/#collection/#reproduce including the intentional archive-gap sentence; axe passes on all three pages. Anonymous route smoke on the dev server: /, /research, /methodology (+anchor variants) all HTTP 200 with id="h1"/id="mechanism" present in served HTML. Browser visual review 1440×900 and 360×780: no horizontal overflow, active nav item highlighted, serif headings, stage cards render (screenshots in docs/verification/ni-011/). `tsc --noEmit`, `eslint` (0 warnings), `next build` (static routes /, /methodology, /research) pass.
- **Result:** apps/web/src/app/(public)/ — layout (public shell), page.tsx (landing with standfirst, links, mechanism teaser), research/page.tsx (standfirst, mechanism section, thesis outline with stable anchors h1–h4/limits), methodology/page.tsx (four sections incl. #sources/#reproduce); old root page.tsx removed into the group. apps/web/src/features/public-research/ — content.ts (typed reviewed copy, deliberately metric-free) + MechanismFlow.tsx (semantic ordered value chain with purchases≠burns cautions). No fake metrics, no live claims, no dead controls anywhere.
- **Reviewer:** pending — role-B review requested on PR #19; CI runs on this PR (web job).
- **Completed at:** 2026-11-06T19:00:20+03:00

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
- **Status:** IN_PROGRESS
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-05T23:59:52+03:00
- **Branch/worktree:** feat/ni-016-auth-environment; /Users/ilyutkinn/Desktop/Near
- **Verification:** web config matrix — 39/39 tests pass (8 new): publishable values accepted; placeholder values (substring detection, e.g. https://REPLACE_PROJECT...) fail readably naming the variable; a service-role-shaped key in the browser slot is rejected; HS256 is rejected with the asymmetric-algorithm message; http JWKS URLs rejected; each missing/placeholder server variable is named in one readable error; short signing secrets rejected; origin list parsing verified. API side verified by the recorded `uv run` matrix: valid config parses (allowed_redirect_origins split+validated), HS256/placeholder-in-URL/non-URL origin/http JWKS/short secret each rejected readably; /health stays independent of auth provisioning (separate AuthSettings). Secret-leak guard: build with synthetic non-production secrets in .env — `check:client-secrets` scans the client bundle (14 files) and finds nothing; positive control (injected leak file) fails with exit 1 naming the variable and file; .env restored afterwards. `tsc --noEmit`, `next build`, `check:contrast` (22/22) pass. Built-frontend inspection is automated by the script (no manual grep claims).
- **Result:** apps/web/src/lib/auth/config.ts (public/server split: browser path reads only NEXT_PUBLIC_* publishable values; placeholder/HS256/service-role/https guards with readable AuthConfigError), apps/web/scripts/check-client-secrets.mjs + `check:client-secrets` npm script (server-secret leak scanner with positive-control verification), apps/api/src/near_api/auth_settings.py (AuthSettings with asymmetric-only algorithm, https JWKS, placeholder rejection, origin parsing; cached getter independent of /health), docs/AUTHENTICATION_SECURITY.md "Dev identity provider setup" section — operator checklist for the dev Supabase project (asymmetric keys, callback allowlist, generated signing secrets, recovery templates) explicitly marked as a user handoff step, .env.example format notes.
- **Reviewer:** pending — role-B review requested on PR #12 (NI-016 reviewer per TEAM_PLAN.md).
- **Completed at:** 2026-11-06T00:07:20+03:00
- **Handoff (user):** create the dev Supabase project per the AUTHENTICATION_SECURITY.md checklist (requires the operator's Supabase account); values go into the local .env only. The provider round-trip smoke is NI-017/NI-020 and needs this project.
- **Reopened — acceptance gap (2026-11-06T03:07:15+03:00, role-B dependency review):** the original NI-016 testing requirements below include a provider development-project smoke. Its recorded verification covers configuration/synthetic tests and explicitly leaves the actual project to the user; no real smoke evidence is supplied, and this fresh checkout has no .env. Moving that check to NI-017/NI-020 did not change the original NI-016 criterion. The previous code/test results and A's claim are preserved; B does not take over NI-016. DONE is restored by A after recording real dev-project issuer/audience/asymmetric-key matching and bounded provider smoke evidence. Secrets/tokens stay local; only sanitized outcome/time/config identity may be recorded. This gate prevents premature NI-018 implementation.

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-06T00:14:47+03:00
- **Branch/worktree:** feat/ni-017-auth-gateway; /Users/ilyutkinn/Desktop/Near
- **Scope note:** this session implements the offline-implementable part (gateway handlers, signed HttpOnly cookie lifecycle, CSRF, login UI, mocked-provider test suite). The provider-backed dev E2E (real sign-up/verification round trip, cookie attributes at production-like TLS) stays an open criterion until the user completes the NI-016 Supabase handoff; the task must not be marked DONE before it.
- **Verification (offline part):** `pnpm --filter web test` — 52/52 pass (13 new, provider mocked via stubbed fetch): CSRF minting returns a readable double-submit cookie; login with minted token sets a signed HttpOnly SameSite=Lax session cookie (Path=/, Secure deferred to production via APP_ENV), rotates the CSRF cookie, and carries only the publishable apikey to the provider; safe internal returnTo preserved verbatim while https://evil / protocol-relative / backslash targets collapse to "/"; cross-origin, missing origin, missing/mismatched CSRF, malformed body and missing fields all reject 403/400 **before any provider call**; wrong password and unknown email return the identical generic 401 message (anti-enumeration); 429/503 map honestly; logout verifies the signed pair, calls provider logout?scope=global, clears both cookies (Max-Age=0) even when the provider is unreachable (honest 503 body), and succeeds without a session; callback rejects missing/invalid link parameters pre-provider, sanitizes external return targets to internal paths on success, maps expired links to a generic expired flag and sets HttpOnly cookies on a valid exchange. `tsc --noEmit`, `next build` (routes: ƒ /api/auth/{csrf,login,logout}, ƒ /auth/callback, ○ /login), `check:contrast` (22/22) pass.
- **Result (offline part):** src/lib/auth/session.ts (HMAC-signed cookie payloads, timing-safe comparisons, session encode/decode with expiry check, CSRF mint/verify, safeInternalReturnTo), src/lib/auth/provider.ts (three documented Supabase Auth REST calls via fetch with publishable apikey only; generic ProviderAuthError mapping; no tokens/passwords logged), gateway routes /api/auth/{csrf,login,logout} + /auth/callback, (auth)/login page + LoginForm (fresh CSRF per attempt, pending state, generic errors, server-validated redirect target). ADR-level choice recorded here: the provider SDK was deliberately not added — three REST calls with explicit cookie control keep the audit surface small; revisit only if a provider feature (OAuth, magic links) requires it.
- **Open criteria (blocking DONE):** provider-backed dev E2E — real sign-up → verification email → callback → session round trip; cookie attribute inspection at a production-like TLS origin (Secure on); recovery flow never exposing previous user content (NI-020 overlaps). Unblocked by the user's NI-016 Supabase handoff.
- **Provider round trip + logout revocation A/B (2026-11-06, real dev provider `athvdjlaovigvffmksbi`):** real login via the gateway returned 200 with a signed HttpOnly session cookie; the stored access JWT was cryptographically verified against the provider JWKS (ES256, exact iss/aud, sub UUID, role authenticated). **Logout revocation A/B proof**: refresh grant live before logout → gateway logout → same refresh grant rejected with `refresh_token_not_found`. The round trip exposed and fixed two real defects: (1) GoTrue logout requires the Bearer access token — `revokeSession` sends the Bearer header, revocation failures are honest 503s; (2) the auth config did not load the root .env — `ensureRootEnvLoaded` is called by both auth loaders. Record restored: the original documentation was pushed to the already-merged feat/ni-017-auth-gateway and missed main; the fixes themselves were in main via PR #22.
- **Operator decision + E2E closure (2026-11-06, 21:41+03:00):** the operator chose friction-free entry for the dev project and demo: **"Confirm email" disabled** in the dev Supabase project (production re-enables verification per the spec — recorded in AUTHENTICATION_SECURITY.md) and **Anonymous sign-ins enabled**. Implemented and verified end to end: signup flow (`confirmation_sent`/`session` paths), and **demo sign-in** — POST /api/auth/demo creates a real anonymous provider session (own sub, full RLS ownership, optional email stored as a display label in user_metadata only, never verified, never authenticating); the login page carries a clearly labeled Demo block. Operator performed the flow in a browser ("вошёл"); the session path was reproduced server-side (csrf 200 → demo 200 session). Verified: 67/67 web tests, lint 0 warnings, build, contrast 22/22.
- **Deferred criteria (recorded, not silently dropped):** email-confirmation/recovery link E2E — intentionally deferred with the operator's confirm-email-off decision; recovery flow itself is NI-020/NI-020-adjacent scope and needs SMTP or the default-link fragment handling when re-enabled. Production-TLS Secure-cookie inspection belongs to NI-067. Provider SDK choice unchanged. POST /api/auth/signup (origin+CSRF guards, publishable-key REST call, 422 already-registered surfaced helpfully, 429/503 mapped honestly) + (auth)/signup page and form (fresh CSRF, pending, confirmation-sent state, auto-confirm session path) + login↔signup links. Tests: 6 new cases (63/63 total). The real-email E2E below needs this flow merged first.
- **Reviewer:** pending — role-B review requested on PR #13 (NI-017 reviewer per TEAM_PLAN.md; B also owns the NI-018 server-side verification that consumes these cookies).
- **Reviewer:** pending — role-B review requested on PR #22 (NI-017 reviewer per TEAM_PLAN.md).
- **Completed at:** 2026-11-06T21:41:44+03:00 — with the operator's confirm-email-off decision and demo sign-in E2E recorded above; email-verification/recovery E2E deferred with that decision (recovery returns in NI-020 scope), production-TLS inspection in NI-067.

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
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch
- **Execution role:** B
- **Started at:** 2026-11-06T18:43:55+03:00
- **Branch/worktree:** feat/ni-018-jwt-verification; /Users/ilyutkinn/Desktop/near-intelligence-b
- **Operator dispatch note (2026-11-06T18:43:55+03:00):** participant A (ILYUTKICK) explicitly instructed this role-B agent to implement NI-018 now and provided the machine-local environment handoff (docs/DEV_ENVIRONMENT.md, untracked operator file): the dev Supabase project exists, JWKS serves ES256 (GoTrue v2.197.0), and the operator verified a real gateway round trip (login → HttpOnly cookie → ES256 verification against the dev JWKS → logout revoking refresh) on 6 November 2026. The upstream provider smoke that NI-016's reopening demanded therefore exists as recorded operator evidence; NI-016's own DONE/review stays with A and is unchanged. The earlier "do not start before the provider smoke exists" condition is satisfied by that handoff; committed tests still use only local synthetic keys and mocks (no provider calls, no real account tokens in Git), with at most a bounded local smoke against the operator's dev project as explicitly allowed by the dispatch.
- **Dependency audit (6 November 2026):** NI-003 is verified DONE after PR #15. NI-016's original real-provider smoke is unfulfilled and has been reopened under A's existing claim. NI-018 remains unclaimed/unstarted until that dependency is genuinely DONE; no local test key or fake account substitutes for the upstream acceptance evidence. Other available P0 role-B tasks require the blocked data/auth chain. No provider call or account creation was attempted by B.
- **Verification (2026-11-06, this claim):** 1) `uv run --project apps/api python -m unittest discover -s apps/api/tests -p "test_*.py" -v` — 47 tests OK (skipped=11, exactly the DB cases that require the isolated cluster). 2) `uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` — PostgreSQL 18.6 disposable loopback cluster on this machine: `test_database.py` 8/8 OK (NI-003 suite stays green) and `test_auth_bootstrap.py` 4/4 OK, no skips. 3) `uv lock --check --project apps/api` — OK; no dependency changes (PyJWT[crypto]/httpx were already declared and locked). 4) Bounded real-provider smoke allowed by the dispatch — exactly one HTTPS GET of the operator dev project JWKS (host athvdjlaovigvffmksbi.supabase.co) through `JWKSCache`: the served ES256 EC key parses and resolves as a usable PyJWK; no key material or token recorded. No token round trip was performed (no dev-account credential exists on this machine); the sign-up/login/refresh E2E remains with NI-017/NI-020 (role A). 5) CI updated: the api job now runs `test_jwt_verification.py`; the database job runs both DB suites through the unchanged disposable-cluster runner contract.
- **Result:** apps/api/src/near_api/auth/ — `__init__.py`, `jwks.py` (bounded JWKS cache: 600 s TTL, 32-key maximum, 1 MiB fetch bound, trusted-URL-only fetcher, unusable documents fail closed, exactly one refresh on unknown kid then fail closed), `verification.py` (configured asymmetric algorithm enforced in the header before any key lookup — alg=none/HS256 never reach the JWKS; exact issuer and strict single audience; exp/nbf/iat verified with zero leeway; `sub` must be a canonical lowercase UUID v4; JWT `jku`/`x5u` never read or fetched), `principal.py` (`bootstrap_principal` upserts app.users/app.user_profiles from the verified subject inside a transaction-local near_app context, rejects `disabled_at` rows fail closed, returns Principal; `get_principal` FastAPI dependency derives identity only from the verified token, maps failures to generic 401/403 with no detail leak, and builds the runtime engine lazily from DATABASE_URL). Tests: apps/api/tests/test_jwt_verification.py (18 offline tests: cache TTL/size/single-retry, full rejection matrix — forged, wrong issuer/audience, expired, future nbf, missing exp/sub, HS256, alg=none, unconfigured asymmetric, non-UUID/non-v4 subjects, malformed kid, garbage, unknown kid single retry, jku/x5u ignored, JWKS outage — plus dependency 401/403/200 mapping and request-body identity-override rejection) and apps/api/tests/test_auth_bootstrap.py (4 cluster tests: idempotent upsert writes only the verified subject, runtime cannot insert another subject (42501), disabled user rejected fail closed with state-dependent recovery, pooled identity never retains another user). Tooling/docs: scripts/run-db-tests.py now executes both DB suites; .github/workflows/checks.yml api job gained the JWT suite; AUTHENTICATION_SECURITY.md records the implemented behavior, DATABASE_SETUP.md the NI-018 consumer and runner scope, apps/api/README.md the module entry. Acceptance criteria: forged/wrong-provider tokens fail closed (matrix), UUID owner never comes from a request body (verified-subject-only bootstrap + dependency test), unknown kid retries JWKS once only (cache test). No provider credentials, tokens or research data were committed.
- **Reviewer:** pending — role-A review requested on the NI-018 pull request (per TEAM_PLAN.md). Status stays IN_PROGRESS until that review; no criterion is knowingly unmet.

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
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #2
- **Execution role:** B
- **Started at:** 2026-11-06T19:36:47+03:00
- **Branch/worktree:** feat/ni-019-rls-ownership at /Users/ilyutkinn/Desktop/near-intelligence-b (from origin/main 0080576)
- **Verification (2026-11-06, this claim):** 1) `uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` — PostgreSQL 18.6 disposable loopback cluster: 21 integration tests OK across the three discovered suites (`test_database.py` 8, `test_auth_bootstrap.py` 4, new `test_ownership_rls.py` 9), no skips; the run includes empty upgrade→downgrade→upgrade plus the Alembic metadata drift check over the new migration. 2) `uv run --project apps/api python -m unittest discover -s apps/api/tests -p "test_*.py" -v` — 56 tests OK (skipped=20, exactly the cluster-dependent cases). 3) `uv lock --check --project apps/api` — OK, no dependency changes. 4) `pnpm check:doc-links` — 537 links resolve. The Alice/Bob matrix on the cluster: two-user CRUD/search/delete isolation; owner scoping applied before pagination (25-row scoped pages with owner-scoped counts, literal wildcard search, page-bound rejections); nested version/block access resolved only through the owned parent chain; cross-owner probes return 42501 (RLS WITH CHECK, column-grant denials) and 23503 (composite FKs); pooled identity reset verified on the private tables (same backend pid, cleared identity, no residue after rollback or a session-level leak); runtime denied SET ROLE/DDL/TRUNCATE/row_security=off; operator denied read/write on private content with purge-by-delete only (users-table cascade); `near_public` denied everything on schema app; disabled owner loses private rows fail closed and recovers when re-enabled.
- **Result:** `apps/api/alembic/versions/0002_private_documents.py` — private document chain per DATABASE_SCHEMA.md (documents, document_versions, document_blocks) with composite same-owner FKs (document→version→block, deferred current-version pointer), enabled+forced RLS, `app.identity_is_active()` in every private policy, immutable versions/blocks for the runtime role (no UPDATE grant), operator purge DELETE (USING(true), no SELECT implied) and no policies for near_migrator/near_public; `apps/api/src/near_api/db/models.py` mirrors the migration for the drift check. `apps/api/src/near_api/db/session.py` — user_transaction verifies app.current_user_id() matches the verified subject right after set_config (fail closed). `apps/api/src/near_api/db/security.py` — `verified_owner_id` (payload owner fields rejected), `owner_scope`, `one_or_not_found`/`ResourceNotFound` (absent = not-owned = one 404 shape), `scoped_page` (owner predicate is a required argument applied before LIMIT/OFFSET with an owner-scoped count; page bounds default 20/max 100), `principal_transaction`. `apps/api/src/near_api/repositories/documents.py` — reference owner-scoped repository (create/get/list/search/rename/delete + compositional nested version/block access). `scripts/db/010-roles.sql` — optional `near_public` login (CONNECT only, nothing on schema app) when DB_PUBLIC_PASSWORD is set; without it the bootstrap is unchanged, so the DB-only Compose contract is untouched. `scripts/run-db-tests.py` provisions the role, exposes NI_TEST_PUBLIC_URL and discovers the new suite. Docs updated: DATABASE_SETUP.md (ownership helpers, roles, verified results), AUTHENTICATION_SECURITY.md (implemented NI-019 paragraph), apps/api/README.md. Acceptance criteria: pooled connections cannot retain another user identity (asserted identity + reset tests on the private tables), runtime role cannot bypass policies (42501 matrix incl. row_security=off, SET ROLE, DDL), private list/search scoped before pagination (scoped_page requires the owner predicate). Scope note: the private tables were created here because the acceptance criteria require real nested references and cross-owner FK probes; the scientific/global tables, saved charts, snapshots and insight/hypothesis/evidence projections remain migrations of NI-028/NI-031/NI-035/NI-036, and document content/CAS/projection services remain with NI-036. No provider calls; no real identities or research data.
- **Reviewer:** pending — role-A review requested on the NI-019 pull request (per TEAM_PLAN.md). Status stays IN_PROGRESS until that review; no criterion is knowingly unmet.

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-06T21:41:44+03:00
- **Branch/worktree:** feat/ni-020-session-boundaries; /Users/ilyutkinn/Desktop/Near
- **Dependency verification:** NI-017 DONE (PR #22, operator E2E recorded), NI-018 DONE (PR #21), NI-019 DONE (PR #23) — cards on origin/main cead969.
- **Scope note (operator decision 2026-11-06):** email confirmation is disabled on the dev provider, so the email-verification leg is deferred with that decision; recovery flow, session boundaries (session endpoint, refresh rotation, revoked refresh, disabled users, rate guards, JWKS failure) and expiry documentation are this session's scope. Editor-draft preservation and cross-tab signals are wired where those surfaces exist (workspace/editor tasks).
- **Verification:** `pnpm --filter web test` — 79/79 pass (5 new): the gate layout redirects anonymous/expired sessions to /login (redirect digest asserted), renders the shell for a valid HMAC-signed session without leaking tokens into markup (access/refresh token absence asserted); the workspace entry page contains no dead links to NI-023/NI-035 routes (queried); AccountMenu posts the CSRF-minted logout and routes to /login, surfacing provider-side revocation failures honestly via role=alert; axe passes on the gated shell. `tsc --noEmit`, `eslint` 0 warnings, `next build` (ƒ /workspace behind the gate) pass. Route protection never replaces backend ownership: the cookie is the HMAC boundary, private API requests re-verify server-side (NI-018/019).
- **Result:** apps/web/src/app/(workspace)/layout.tsx (server gate via cookies()+decodeSessionCookie, redirect to /login, force-dynamic for private no-store semantics, WorkspaceSidebar + AccountMenu wiring), (workspace)/workspace/page.tsx (honest entry page), components/layout/AccountMenu.tsx (sign-out with fresh CSRF, pending state, honest failures). The gate is the UI boundary only — resource ownership remains server-side.
- **Reviewer:** pending — role-B review requested on PR #29; CI runs on this PR.
- **Completed at:** 2026-11-06T23:20:40+03:00
- **Verification:** `pnpm --filter web test` — 74/74 pass (7 new): session endpoint returns subject+expiry for a valid signed cookie, clears expired/tampered cookies with 401, answers 401 with no cookie and sets nothing; refresh rotation exchanges the refresh token provider-side and re-signs the cookie with the NEW refresh token, clears the session honestly on revoked/expired refresh (401), and keeps the cookie through provider outages (503, no fake rotation); per-IP sliding-window guard allows exactly 5 attempts/min and blocks the sixth while other IPs are unaffected; disabled users fail closed through the NI-018 bootstrap; JWKS/provider outage cases covered in both existing and new suites. `tsc --noEmit`, `eslint` 0 warnings, `next build` (ƒ /api/auth/{session,refresh} added) pass. Rate guard counts hostile requests too (pre-auth rejections consume the bucket) — the pre-provider rejection matrix resets its bucket per case with a recorded rationale.
- **Result:** apps/web/src/app/api/auth/session/route.ts (HMAC-cookie boundary, honest three-way answer), apps/web/src/app/api/auth/refresh/route.ts (provider refresh rotation, revoked → 401+clear, outage → 503 cookie kept), apps/web/src/lib/auth/rate-limit.ts (sliding-window per-IP guard wired into login/signup/demo/refresh at 5-10/min, single-instance note for NI-067), wired into login/signup/demo routes; expiry window documented in AUTHENTICATION_SECURITY.md (observed provider default 3600s). Deferred with rationale: editor-draft preservation and cross-tab cache signals wire in when workspace/editor state exists (NI-021+); recovery-flow exposure checks return with recovery (needs SMTP decision); two-browser manual pass belongs to NI-064 staging verification.
- **Reviewer:** pending — role-B review requested on PR #24; CI runs on this PR.
- **Completed at:** 2026-11-06T22:05:30+03:00

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-06T22:51:34+03:00
- **Branch/worktree:** feat/ni-021-workspace-gate; /Users/ilyutkinn/Desktop/Near
- **Dependency verification:** NI-008 DONE (PR #11), NI-020 DONE (PR #24, session/refresh boundaries in main) — cards on origin/main a594f78.

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
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #3
- **Execution role:** B
- **Started at:** 2026-11-06T21:41:32+03:00
- **Branch/worktree:** feat/ni-022-home-aggregation at /Users/ilyutkinn/Desktop/near-intelligence-b (from origin/main cead969)
- **Verification (2026-11-06, this claim):** 1) `uv run --project apps/api python -m unittest discover -s apps/api/tests -p "test_*.py" -v` — 67 tests OK (skipped=25, exactly the cluster-dependent cases; `test_contracts.py` updated for the second implemented path). 2) `uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` — PostgreSQL 18.6 disposable loopback cluster: 32 integration tests OK across the four discovered suites (`test_database.py` 8, `test_auth_bootstrap.py` 4, `test_ownership_rls.py` 9, new `test_home_aggregation.py` 11), no skips. The NI-022 matrix: two-user isolation (Alice 25 documents vs Bob 2 → owner-scoped totals 25/2 and exactly 5 recent each, zero cross-owner rows/titles/ids); the `(updated_at DESC, id)` order pinned with staggered timestamps; summaries carry the live documents-row revision/current_version_id; deleting the newest document removes it from recent and totals with HTTP 200 (no 500, no 404); a fresh user gets a valid empty response (empty arrays, not null, `counts.documents=0`); a disabled account is 403 fail closed through the real `get_principal` chain with state-dependent recovery (200 after re-enable); the aggregation runs an identical bounded statement count for 25-row and 1-row homes (≤6 including the identity setup, expected 2 aggregation statements — no N+1); `Cache-Control: no-store` asserted on 200/401/403; `ResourceNotFound` maps to the one generic 404; the 401 matrix (missing/empty/malformed/basic/token headers) runs through the real dependency; pending sections forbid items at schema level (`maxItems: 0`) so fabricated placeholder data cannot validate. 3) `uv lock --check --project apps/api` — OK, no dependency changes. 4) `pnpm check:doc-links` — 539 links resolve. Known CI note: the `checks.yml` api step "Generated client matches the API contract" reports drift on this branch because the new route changes `app.openapi()`; regenerating `packages/shared-types` artifacts writes outside this dispatch's stated file boundary (packages/** is off-limits while role A works in the main checkout), so the one offline command (`node packages/shared-types/scripts/generate.mjs`) is left to the operator/role-A decision; `schemas/common.py` (shared models) is unchanged.
- **Result:** `apps/api/src/near_api/workspace/` — `aggregation.py` (`home_overview`: one `scoped_page` call — owner predicate applied before LIMIT/OFFSET, count over the same scoped statement, cap 5, stable `(updated_at DESC, id)`; deleted documents drop out of list and totals without an error) and `routes.py` (`GET /api/home`: identity only via `get_principal`, `principal_transaction` transaction-local identity, `Cache-Control: no-store` on every response). `schemas/home.py` — `HomeResponse` with `DocumentSummary`/`DocumentProgress`/`PendingHomeSection`/`HomeCounts` pinned to the API_SPECIFICATION home row; `recent_charts`/`recent_insights`/`indicators` are required `maxItems: 0` pending sections documented as arriving with NI-035 / NI-046-047 / NI-031-032 (per-indicator typed failures arrive with NI-031/NI-032); `DocumentSummary.progress` counters are documented zeros until the NI-036 revision service and NI-041/NI-046 block taxonomy define canonical projections; the operator-directed `counts.documents` extension is recorded in the spec's implemented note. `auth/principal.py` — public `get_runtime_engine` dependency separating engine wiring from identity verification. `contracts.py` — global `ResourceNotFound` handler producing the one generic 404 shape. `main.py` includes the workspace router (no import-time DB connection; `/health` stays DB-free). Route-path note: the dispatch prescribes `GET /api/home`; the spec row's `/workspace/home` under base `/api/v1` remains the same contract — any path alias is a review decision recorded in API_SPECIFICATION.md. Tests: `apps/api/tests/test_home_aggregation.py`; `scripts/run-db-tests.py` discovers the fourth suite; `test_contracts.py` OpenAPI paths assertion updated. Docs updated: API_SPECIFICATION.md (implemented note + counts extension), API_CONTRACT.md (implemented paths), apps/api/README.md. Acceptance criteria: no other user rows/counts leak (two-user matrix incl. HTTP level); stale/unavailable indicators do not fail the page (indicators are an honest empty section until NI-031/NI-032); progress measures work completion only. No provider calls; no real identities or research data.
- **Reviewer:** pending — role-A review requested on the NI-022 pull request (per TEAM_PLAN.md). Status stays IN_PROGRESS until that review; no criterion is knowingly unmet.

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A (owner/closer; the /me API is B's zone per TEAM_PLAN, implemented by this agent under the standing parallel-dispatch authorization, following B's established patterns)
- **Started at:** 2026-11-06T23:18:09+03:00
- **Branch/worktree:** feat/ni-025-profile-settings; /Users/ilyutkinn/Desktop/Near
- **Dependency verification:** NI-020 DONE (PR #24), NI-021 DONE (PR #29) — cards on origin/main cead969+.
- **Verification:** API — `pnpm check:doc-links` OK; unittest offline 117 OK (validation matrix: empty/control names, non-IANA timezones, oversized, payload-cannot-carry-subject); disposable-cluster run: 36 tests OK including 4 new profile round-trips through RLS (own-row update via profile_self, foreign profile unreachable, invalid timezone rejected by the DB CHECK, timezone display-only UTC invariant). Contract regenerated: /api/me in openapi.json + typed client (generate --check green); contract-path pins updated in test_contracts.py and test_home_aggregation.py. Web — /workspace/profile (GET fills via /api/me, PATCH saves with values retained on errors, honest load-error state, subject never rendered or editable) and /workspace/settings (session/logout via AccountMenu, drafts section stating the NI-038/040 arrival, operator-assisted deletion stated without faking success, no billing/team controls). 79/79 web tests, tsc/lint/build green (ƒ /workspace/profile, ƒ /workspace/settings). Local smoke: demo login via the gateway returned 200, but the browser GET/PATCH /api/me currently answers 401 — the profile form's same-origin fetch needs the gateway session-to-API forwarding that arrives with NI-032's API delivery (recorded deferral, not claimed as working). The API round trip itself is verified in the cluster tests with a real bearer (36 OK incl. 4 profile round-trips through RLS).
- **Result:** apps/api/src/near_api/users/routes.py (GET/PATCH /api/me — verified-principal ownership, pydantic+zoneinfo validation, DB CHECK as second layer, no subject in payloads), wired in main.py; apps/web (workspace)/profile + /settings pages with ProfileForm; settings states drafts-arrival and operator-assisted deletion honestly. No billing/team controls; the verified subject is never editable or displayed as an identity anchor.
- **Reviewer:** pending — role-B review requested on PR #31; CI runs on this PR.
- **Completed at:** 2026-11-06T23:40:20+03:00

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
- **Status:** DONE (probe executed within the operator authorization; SRC-NEAR-RPC carries explicit access/limits/rights evidence; the other nine sources remain documented-limited with OQ IDs)
- **Claimed by:** Claude agent for role B, dispatch #4 (continuation of the 2026-11-06 role-B work; prior session: Codex / BkycnocTbI / session 01a1a2c9-f42d-7422-8e3e-755c9e33551b)
- **Execution role:** B
- **Started at:** 2026-11-06T02:14:00+03:00 (re-claimed 2026-11-06T19:11:42+00:00 for the authorized bounded probe)
- **Branch/worktree:** feat/ni-026-provider-probe; /Users/ilyutkinn/Desktop/near-intelligence-b (git worktree; prior: feat/ni-026-provider-capabilities)
- **Authorization:** Participant B explicitly authorized role-B implementation and private-repository code/tests/config/docs publication on 6 November 2026. Raw historical archives remain excluded. Operator dispatch #4 (2026-11-06, verbatim): «оператор утвердил источник (OQ-03 RESOLVED, оформляется в PR #27): публичный NEAR mainnet RPC `https://rpc.mainnet.near.org` для finalized-header polling; лимит 1 запрос/мин, ≤1440/сутки; бюджет 0; ответ header-only с байт-капами твоего probe; on-chain header data публична. Это дословная авторизация оператора на ОДИН bounded-запрос».
- **Dependency verification:** main cfdd914 contains NI-001 DONE with tool/dependency evidence and NI-002 runtime/lock files. Clean checkout verified; no competing NI-026 claim or open PR found at start.
- **Scope:** Validate source capability records and fail-closed probe controls, refresh documentation/rights evidence, and perform isolated Windows Python compatibility verification. Provider credentials, approved quotas/budgets and the historical input archive are absent. Unresolved operational gates retain their OQ IDs.
- **Operator authorization (2026-11-06, resolves OQ-03):** participant A (ILYUTKICK) approved the recommendation: public NEAR mainnet RPC `https://rpc.mainnet.near.org` for finalized-header polling; 1 request/minute, ≤1440/day; budget 0 (free tier, no account/key); header-only responses with the implemented byte caps; on-chain header data is public, derived-metric publication permitted. Recorded in OPEN_QUESTIONS.md (OQ-03 RESOLVED). The bounded single probe is authorized to run; the blocker above is superseded by this record. Status moves to IN_PROGRESS for the probe + evidence step. OQ-01/OQ-08/OQ-10/OQ-11 retain the per-source attribution/history limitations. Historical files and hashes must come from an authorized archive-owner handoff, outside GitHub. Until evidence and a bounded approved probe exist this task is not DONE; downstream NI-027/NI-030 remain gated. (2026-11-06 addendum: the probe ran the same day and the task is DONE — see Verification below; NI-027's separate archive-handoff gate and NI-030's adapter work are unaffected.)
- **Result:** Immutable capability registry for ten sources and a single-use finalized-header probe with disabled defaults, evidence/approval/stop gates, byte caps, no redirect/retry and sanitized output. SRC-NEAR-RPC now records the operator authorization (endpoint `https://rpc.mainnet.near.org`, rights `approved`, rights/quota evidence URLs, no blockers) and the probe additionally returns `response_bytes`; the other nine sources stay disabled with OQ blockers. The authorized probe was executed exactly once. See [verification README](verification/ni-026/README.md) and [probe evidence](verification/ni-026/probe-evidence.md).
- **Verification (6 November 2026):** CPython 3.13.15/Windows 11, uv 0.12.13; frozen hash-checked binary installation and dependency check pass for 48 packages; offline lock check and generated-export parity pass; 14 imports and synthetic OLS/linear algebra/PNG plus missing-config `/health` 503 pass. Eleven capability/guard tests pass with mock transports; `git diff --check` passes. No real-data result is claimed.
- **Verification (probe, 2026-11-06, dispatch #4):** one real `POST https://rpc.mainnet.near.org` JSON-RPC `block finality=final` through the guarded `HeaderProbe`: HTTP 200, 18 496 bytes ≤ 65 536 approved cap, final height 223357966, hash `7gsbtD5R8A2hasDzVDXWF6hdnV6kKL4VW3Sg5QCXBwZo`, sanitized output only ([evidence](verification/ni-026/probe-evidence.md)). Offline re-checks on this branch: `unittest discover` 68 tests OK (12 capability/guard), `uv lock --check` OK, `pnpm check:doc-links` OK (553 links), `git diff --check` OK. No retry, pagination, second request, SQL, paid or bulk operation.
- **Completed at:** 2026-11-06T19:15:12+00:00
- **Reviewer:** ILYUTKICK (role A), pending on PR #14; narrow source changes only, no ignore-rule exception requested.

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
- **Status:** IN_PROGRESS (implementation complete on PR, awaiting role-A review; DONE withheld by dispatch instruction)
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #5
- **Execution role:** B
- **Started at:** 2026-11-06T22:40:00+03:00
- **Branch/worktree:** feat/ni-027-archive-import; /Users/ilyutkinn/Desktop/near-intelligence-b (git worktree; main checkout /Users/ilyutkinn/Desktop/Near stays with role A)
- **Authorization:** Operator dispatch #5 (2026-11-06, participant A ILYUTKICK): role-B work on NI-027 is authorized in the worktree; the authorized archive-owner handoff is local — the archive at /Users/ilyutkinn/Desktop/Near/research/ is READ-ONLY (no modify/delete/move), with the operator-generated hash manifest /Users/ilyutkinn/Desktop/near-archive-manifest.sha256 (380 files, 149 MB, SHA-256 per file, generated 2026-11-06). Original files are never copied into the database nor edited on disk.
- **Dependency verification:** NI-003 DONE (PR #15 merged, migration/role/RLS evidence in card); NI-026 DONE (PR #28 merged at main a594f78, probe evidence recorded). Branch created from origin/main a594f78; no competing NI-027 claim present.
- **Archive manifest verification (read-only):** `shasum -a 256 -c` against the operator manifest from /Users/ilyutkinn/Desktop/Near returned exit 0 with all **380/380 files OK** at session start (2026-11-06 ~22:40+03:00) and again **after every test run and disposable-cluster import** — archive bytes unchanged throughout. Cohort inventory: near-dollar, near-longitudinal, near-pilot, near-provenance, near-supply, near-treasury, near-weekly (all with internal manifest.json; internal checksum listings cross-checked against archive bytes on import) and revenue-dashboard (captured third-party material, no cohort manifest, never fabricated).
- **Result:** Migration `0003_archive_import` creates the operator-zone tables `app.sources` (SRC-* catalog subset of `data_sources`), `app.import_batches` (UNIQUE manifest_sha256 idempotency key), `app.imported_files` (path/sha256/byte_size/`file_role` raw|aggregate|provenance|editorial|script/`coverage_scope`/half-open UTC window/source FK/license visibility/sanitized ≤4 KiB metadata JSONB; file bytes never stored) and `app.source_runs` (documented retrieval lineage), all FORCE RLS with near_operator-only policies (near_app gets SELECT on `sources` only). `apps/api/src/near_api/ingestion/archive.py` implements the operator CLI `python -m near_api.ingestion.archive --archive-root --manifest --cohorts --database-url [--dry-run]`: strict manifest parsing, per-file byte verification BEFORE any content read, whole-batch rejection on hash mismatch/missing/extra/symlink/undeclared cohort/cohort-checksum divergence, deterministic conservative role classification (a file is `raw` only when the archive itself documents a saved response/export), credential redaction (JWT/bearer/userinfo/secret params) on every stored string, and a versioned cohort scope registry `archive_cohorts.json` transcribed from the cohort READMEs/manifests plus SOURCE_VERIFICATION.md (windows, partial-audit statements such as the 6-of-297 stopped supply audit and the unresolved weekly intent-hash mismatches, license visibility `unverified`). Models mirrored in `apps/api/src/near_api/db/models.py` for the Alembic drift check; docs updated in DATABASE_SCHEMA.md and DATA_PIPELINE.md.
- **Verification:** Unit `unittest discover -p test_archive.py`: 29 tests OK (manifest format/traversal/duplicates, verify-before-read ordering proof, internal-checksum divergence, registry contracts, redaction, classification, source attribution, extra-file-outside-covered-subtree). DB suites via `scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` (disposable loopback PostgreSQL 18 cluster): test_database 8 OK, test_auth_bootstrap 4 OK, test_ownership_rls 9 OK, test_home_aggregation 11 OK, **test_archive_import 9 OK** — import twice idempotent (second run changes=0, identical table state), bad hash / missing file / extra file each reject the WHOLE batch with zero rows written, stored metadata vs source manifest comparison, secret-marker and payload strings absent from every stored column, archive tree digest unchanged after both imports, two-user probe: both users read `sources`, both get 42501 on the import zone, non-operator credentials rejected, 0003 downgrade/upgrade round trip plus `command.check` clean. Full `unittest discover`: 106 tests OK (34 DB-skip without cluster env). `uv lock --check` OK; `pnpm check:doc-links` OK (557 links); `git diff --check` clean. End-to-end evidence on the REAL archive: `--dry-run` verified 380 files / 155 529 116 bytes / 8 cohorts / 29 documented runs; a disposable local cluster import succeeded twice (IMPORT 1 imported=True changes=418; IMPORT 2 imported=False changes=0; counts sources=8, import_batches=1, imported_files=380, source_runs=29; credential-pattern rows 0); manifest re-check 380/380 OK afterwards. No network/provider calls; no writes to the research directory.
- **Reviewer:** ILYUTKICK (role A), pending — review requested on the PR; DONE deliberately withheld per dispatch.

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
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #6
- **Execution role:** B
- **Started at:** 2026-11-06T23:24:00+03:00
- **Branch/worktree:** feat/ni-028-dataset-staging; /Users/ilyutkinn/Desktop/near-intelligence-b (git worktree off origin/main 3e38b71)
- **Verification (2026-11-07, this claim):** 1) `uv run --project apps/api python -m unittest discover -s apps/api/tests -p "test_*.py"` — 122 tests OK (skipped=44, exactly the cluster-dependent cases). 2) `uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` — PostgreSQL 18 disposable loopback cluster, 57 integration tests OK across all six discovered suites (test_database.py 8, test_auth_bootstrap.py 4, test_ownership_rls.py 9, test_home_aggregation.py 11, test_archive_import.py 9, new test_dataset_staging.py 16 = 6 offline canonical/manifest/period-grid/storage + 10 real-DB), no skips. The NI-028 matrix actually asserted: stage persists version+members+inputs+observations and validation in ONE transaction (committed status validated); publish approves and switches `active_datasets` atomically (supersedes/revision delta recorded; near_app reads approved data and observations through real RLS while its INSERT/UPDATE matrix is 42501); identical semantic input deduplicates to the same version id across JSON key order, decimal spelling (`10.50`), timestamp offset form and a different local input path (one version row per key); a revision stages as version 2, publishes with supersedes=v1 and changed=1, and v1 stays approved, byte-identical (hash + observations re-read) and queryable with both hashes in history; a window gap commits the version as `rejected` with an uncovered-period report while the active pointer stays on v1, publish of the rejected id is refused and the rejected row is trigger-frozen; simulated crash inside stage (fault-injected validation) and inside publish (fault-injected delta) plus a caller-rolled-back transaction around the internal core leave exactly zero new rows in all six tables; two threads publishing versions 2 and 3 concurrently across two engines both succeed serialized by the `pg_advisory_xact_lock` per dataset key (final pointer is one of them, all three versions approved, one pointer row); approved/rejected rows reject UPDATE via the immutability trigger, identity-column rewrites are refused by the column grant (42501), DELETE has no grant, and a staged→approved shortcut is rejected by the transition whitelist; `stage-from-import` runs the real NI-027 archive import on a synthetic two-cohort archive, reads observations from the re-verified aggregate (file_role aggregate → role normalized), publishes, deduplicates on re-run and refuses changed archive bytes with a verification error; the query API surfaces history hashes, active pointer, bounded observation pages and input storage keys; migration round trip drops/recreates all six tables and `alembic check` reports no metadata drift. 3) `uv lock --check --project apps/api` — OK, no dependency changes. 4) `pnpm check:doc-links` — all relative documentation links resolve. CLI contract smoke: `python -m near_api.datasets --help` lists stage/stage-from-import/validate/publish/show; bad credential → exit 5, wrong role → exit 5, unreadable manifest → exit 4. No network calls; no research archive bytes touched (synthetic fixtures only).
- **Result:** Migration `apps/api/alembic/versions/0004_dataset_staging.py` creates the DATABASE_SCHEMA.md dataset zone: `app.artifacts` (content-addressed, append-only, private-scope owner check), `app.dataset_versions` (UNIQUE(dataset_key,content_sha256) dedup key, UNIQUE(dataset_key,version), same-key supersedes composite FK, trigger-guarded status whitelist staged→validated→approved with frozen approved/rejected rows), `app.dataset_metrics`, `app.dataset_inputs` (raw/normalized/price/sql/config lineage; `ingestion_run_id` reserved for NI-030), `app.metric_observations` (half-open UTC periods, NUMERIC(78,30), missing/unavailable ⇔ NULL value with a reason, bound_kind iff value, canonical dimensions_hash, membership composite FK) and `app.active_datasets` (single approved pointer per key, same-key composite FK + approved-gate trigger); FORCE RLS with near_operator-only write policies, near_app read-only (private artifacts owner-scoped), no UPDATE/DELETE grants on append-only tables. `apps/api/src/near_api/db/models.py` mirrors the migration for the drift check. `apps/api/src/near_api/datasets/`: `canonical.py` (deterministic canonical JSON/decimal/timestamp forms, SHA-256 digests, duplicate-key/float rejection), `manifest.py` (strict prepared-manifest and stage-from-import binding parsing), `storage.py` (content-addressed artifact bytes written before the transaction), `service.py` (advisory-locked staging with in-transaction validation, digest re-derivation from persisted rows, membership/window/alignment/coverage gates, atomic publish with revision delta, query API for active/history/hashes/observations/inputs), `from_import.py` (NI-027 integration: observations read from re-verified imported aggregates, coverage-window containment, offline), `cli.py`/`__main__.py` (operator CLI with exit codes 0/3/4/5). `scripts/run-db-tests.py` discovers the new suite. Docs updated: DATA_PIPELINE.md (implemented datasets CLI leg), DATABASE_SCHEMA.md (implemented-zone interpretations), apps/api/README.md. Limitations: `metric_definitions` FK awaits NI-031 (metric ids are opaque registered identifiers until then); scheduled refresh, live adapters and the remaining `near_api.cli` verbs stay with NI-030; no browser route exposes these operator verbs; PR not merged, DONE pending role-A review.

**Description:** Create atomic versioned data delivery and reproducible artifact storage.

**Implementation steps:** Add dataset/artifact/observation migrations; build canonical hashing/manifest builder; persist staged observations/artifacts; validate dataset membership; publish approved active pointer in one transaction; retain superseded versions.

**Expected files/modules:** apps/api/src/near_api/datasets/; storage/; CLI dataset commands

**Acceptance criteria:** Failed validation cannot change active data; identical semantic input deduplicates appropriately; old versions and hashes remain queryable.

**Testing requirements:** Crash-before-publish and transaction rollback tests; concurrent publish lock; revised history creates new version without mutating old.
- **Reviewer:** pending (role A review on PR feat/ni-028-dataset-staging)

### NI-029 — Implement exact metric computations and quality

- **Epic:** 06 — Data Infrastructure
- **Priority:** P0
- **Dependencies:** NI-028
- **Complexity:** L
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #7
- **Execution role:** B
- **Started at:** 2026-11-07T00:27:00+03:00
- **Branch/worktree:** feat/ni-029-metrics; /Users/ilyutkinn/Desktop/near-intelligence-b2 (git worktree off origin/main c467e6b)

**Description:** Centralize the real P0 amounts and explicit unavailable metric definitions.

**Implementation steps:** Implement purchases/payouts/price estimate/supply change/bounds and source-qualified fees/volume; use Decimal; validate periods, denominators and quality propagation; emit registered definitions.

**Expected files/modules:** apps/api/src/near_api/metrics/; metric registry; tests/metrics/

**Acceptance criteria:** Historical CL amounts reconcile; missing≠zero; purchases not deducted from supply; lower-bound ratio reported upper-bound; unavailable revenue remains null.

**Testing requirements:** Independent event aggregation including duplicate/failure/internal transfer; UTC boundary and price-gap cases; compare saved summary totals exactly.
- **Verification (2026-11-07, this claim):** 1) `uv run --project apps/api python -m unittest discover -s apps/api/tests -p "test_*.py"` — 184 tests OK (skipped=54, exactly the cluster/handoff-dependent cases; with `NI_REAL_ARCHIVE_ROOT` set the 7 real-archive reconciliation tests execute instead of skipping). 2) `NI_REAL_ARCHIVE_ROOT=…/research uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` — PostgreSQL 18 disposable loopback cluster, 119 integration tests OK across all eight discovered suites (test_database 8, test_auth_bootstrap 4, test_ownership_rls 9, test_home_aggregation 11, test_archive_import 9, test_dataset_staging 16, new test_metrics 52 = 46 offline/real-archive + 6 real-DB, test_profile 10), no skips. The NI-029 suite asserted: the 19-definition registry is complete, deterministic (uuid5 identities), formula-bound and rejects unimplemented formulas; registration into `app.metric_definitions` (migration 0005) is idempotent and content-verified (an admin-tampered row makes registration refuse; the row is restored in cleanup); near_app of two different users reads all definitions including the NULL-source gated ones and gets 42501 on INSERT/UPDATE/DELETE; event aggregation collapses identical duplicates, quarantines conflicting payloads, excludes failed transfers/internal treasury hops/other-sender inflows/out-of-window rows, errors on unmatched or ambiguous withdrawals, is inclusive at exactly 300 s, buckets 23:59:59.999999Z vs 00:00:00Z into their own UTC days and rejects partition/timestamp mismatches; missing prices produce missing USD values (never zero) and unavailable window estimates listing the missing days; zero/negative denominators (volume, net supply, issuance lower bound) produce unavailable observations; the purchases/issuance ratio always carries bound_kind `upper` with the direction documented; net supply change is exactly closing−opening with purchases reported alongside and never deducted; protocol_revenue_usd/protocol_capture_rate/fee_funded_buybacks_near are null with OQ-01/OQ-08/OQ-11 reasons on every period; uncovered days with extract coverage are verified zeros; both emitted manifests parse through the strict NI-028 manifest parser and pass the membership/window/coverage gates; the synthetic saved-summary totals reconcile exactly (Decimal) against an independently computed expectation; the emitted manifests stage, publish and stay readable by two runtime users, and identical input re-stages as a deduplicated approved version. 3) Real-archive reconciliation (read-only): payout matching reproduces 3165/3165 matched pairs with zero issues and payout total 1405659.135989071036891726256814 NEAR; purchases aggregate to 524480.127692882832410490617319 NEAR over 54991 events; USD estimates reconcile exactly with the saved 90-day totals (start and end bases, full precision); fee bps reconcile at the NUMERIC(78,30) storage scale; supply stocks, net changes and conservative bounds reproduce the saved summary exactly; internal hops 502794 NEAR, other senders 7751.94972615998997116 NEAR and the 14 out-of-window 2026-11-04 transfers are excluded and reported; the real manifests stage and publish in the disposable cluster and the stored approved observations re-reconcile with the archive summaries. 4) `uv lock --check --project apps/api` — OK; `pnpm check:doc-links` — 563 links resolve. CLI smoke: `python -m near_api.metrics build --spec … --out-dir …` emits both manifests offline with exit 0 and exit 4 on contract violations. No network calls; the research archive was only read.
- **Result:** `apps/api/src/near_api/metrics/`: `registry.py` (19 immutable v1 definitions from METRIC_CATALOG with A/P/B/G availability, deterministic uuid5 identities, idempotent content-verified `register_definitions`), `events.py` (canonical NEAR event identity, duplicate collapse/quarantine, successful-execution-only transfers, payout matcher with recorded matcher version and 300 s tolerance, internal-hop/other-sender/failed/out-of-window exclusion, exact-arithmetic context decorator), `compute.py` (pure-Decimal formulas: purchases, conversion count, payouts, payout count, saved prices, USD estimates with exact_value preservation at the NUMERIC(78,30) scale, source-qualified provider volume/fees, ratio-of-sums fee bps, supply stocks/net change/conservative bounds, bound ratios with upper-bound propagation, gated nulls, verified zeros, coverage-proven zero policy), `inputs.py`/`loaders.py` (strict loaders for the real aggregate shapes: longitudinal flows extract, dollar daily series, supply summary, treasury snapshot), `emit.py` + `__main__.py` (`python -m near_api.metrics build` → prepared manifests `metrics.flows.daily` and `metrics.windows.snapshot` for the NI-028 staging pipeline). Migration `0005_metric_definitions.py` creates the append-only FORCE-RLS `app.metric_definitions` registry (nullable source_id reserved for gated definitions; the `dataset_metrics` FK stays with NI-031 as documented). `apps/api/src/near_api/db/models.py` mirrors it for the drift check; `scripts/run-db-tests.py` discovers the new suite. Boundary fix in `apps/api/src/near_api/datasets/canonical.py`: `decimal_string` now normalizes in a local context with at least the value's own digit count — the previous ambient-context rendering (28 significant digits) silently rounded values beyond that and made the NI-028 digest round trip context-dependent; existing NI-028 behavior and tests are unchanged. Docs updated: DATA_PIPELINE.md (stage-5 Compute leg), DATABASE_SCHEMA.md (metric definition registry zone), apps/api/README.md. Limitations: gated metrics stay null until OQ-01/OQ-08/OQ-11 evidence exists; strict_fee_conversion_equivalent_near is NI-051 scope and is not registered; window-level 90-day totals are range aggregates recorded in dataset quality metadata (only atomic 30-day windows and boundary stocks are observations); provider series remain source-qualified and revisable with no cross-source summation; live refresh stays with NI-030; PR not merged, DONE pending role-A review.

### NI-030 — Add one bounded scheduled refresh adapter

- **Epic:** 06 — Data Infrastructure
- **Priority:** P0
- **Dependencies:** NI-026, NI-028, NI-029
- **Complexity:** M
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #10
- **Execution role:** B
- **Started at:** 2026-11-07T02:12:00+03:00
- **Branch/worktree:** feat/ni-030-refresh-adapter; /Users/ilyutkinn/Desktop/near-intelligence-b2 (based on origin/main e69746b with feat/ni-031-registries b31c6cc merged so migration 0008 chains after 0007; parallel NI-031/NI-051 files untouched)
- **Verification (2026-11-07, dispatch #12 continuation):** 1) Full offline discovery `uv run --project apps/api python -m unittest discover -s apps/api/tests -p "test_*.py"` — 266 tests OK, 93 env-gated skips (cluster/live-archive only). 2) Disposable-cluster suite `uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` (run twice: once to validate the carried fixes, then with `NI_LIVE_SMOKE=1` for the smoke) — all twelve suites executed with no skips, 183 tests OK, including the refresh-adapter suite: lifecycle (publish + checkpoint + counters), supersede (next-day `added` delta and the new same-day `changed`/`added=0` case), unchanged height, height regression, 429/401/403 retention with honestly consumed attempts, schema failure with zero dataset rows, daily/minute budget refusals before any request, unapproved-source refusal, checkpoint resume across restart, scheduler-overlap refusal, two-user boundary (near_app read-only; each denial on its own connection), checkpoint-reset restaging honesty, and the migration 0008 round trip. 3) `uv lock --check --project apps/api` — OK; `pnpm check:doc-links` — 577 links resolve. 4) Bounded authorized live smoke (OQ-03, exactly ONE real request, no retries, inside the disposable cluster through the same guarded `run_once()` path the CLI invokes): request 2026-11-07T19:29:22.97Z → 19:29:28.68Z against `https://rpc.mainnet.near.org` (read from the `app.sources` registry row with `access_status='approved'`), HTTP 200 within the 65 536-byte cap, published dataset version `e0e1a6e4-9c82-403b-b355-008209e5f27e` (`content_sha256` `da3516ad9635f67f459b2c556e5215391a73bf8e3da61082e4d746ef450bfb05`); **final block height 223509484, hash `HvJDUUJqEERE5NkDBjegYLpRBBsyEjoBVofjPH6kQyFY`, header time 2026-11-07T19:29:25.737158Z (lag 2.9 s)**. The exact response byte size was validated in-run against the cap but the smoke's evidence print did not yet include it and the disposable-cluster artifacts are destroyed, so cap compliance (≤65 536; the run succeeded through validation) is recorded instead of an invented exact number; the smoke now reads the preserved raw artifact's `byte_size`, asserts it positive and within the cap, and prints it for future authorized runs. No other provider request was made by this dispatch.

**Description:** Demonstrate a genuinely regularly updated series with last-good reliability.

**Implementation steps:** Implement verified finalized-header or other approved low-cost adapter; enforce allowlist/budgets/locks/checkpoints; validate/publish new version; schedule opt-in; display source freshness and failure.

**Expected files/modules:** apps/api/src/near_api/ingestion/providers/; cli.py; deployment timer config

**Acceptance criteria:** At least one real approved refresh publishes valid data;429/auth failure retains last good; startup defaults disabled; legacy collectors remain stopped.

**Testing requirements:** Controlled HTTP failure/schema/pagination tests; bounded authorized live smoke and recorded fresh block hash/time; scheduler overlap test.

**Result:** `apps/api/src/near_api/ingestion/providers/finalized_header.py` — the single-shot adapter: OQ-03 budgets (1 request/minute, ≤1440/day) evaluated purely and enforced from persisted migration-0008 state before any network I/O; the endpoint comes only from the operator-managed `app.sources` registry (`access_status='approved'`, clean public HTTPS) — the code carries the source identifier, never the URL; `STOP_PUBLIC_COLLECTION` root/research markers gate the adapter exactly like the NI-026 probe; one streamed POST `block finality=final` per invocation with a 65 536-byte cap, identity-encoding rule, 10 s timeout, no redirects and no retry; strict sanitization through the probe's `FinalizedHeader` model (monotonic height, base58 hash, digit-string timestamp/supply); the persisted height checkpoint makes a lower advertised height a `height_regression` failure, an unchanged height publish nothing, and a higher height stage+publish dataset `near-finalized-headers` (metric `total_supply_near`, exact yoctoNEAR→NEAR via a precision-safe local context, raw response preserved as the source-qualified input artifact, revision delta recorded) in the same transaction that advances the checkpoint and counters — any failure retains the previous approved pointer and records `last_failure_at`/`last_failure_kind`/`consecutive_failures`; a failed or schema-invalid response is honestly counted as a consumed attempt. A session-level per-source advisory lock refuses scheduler overlap. `apps/api/src/near_api/ingestion/refresh.py` — the operator CLI (`python -m near_api.ingestion.refresh --once --database-url --storage-root [--repo-root] [--source]`) with exit codes 0/3/4/5 and JSON reports; nothing else imports or starts the adapter (no startup path, no HTTP handler). `apps/api/alembic/versions/0008_refresh_checkpoints.py` — the operator-owned checkpoint/counter zone: FORCE RLS with a single near_operator write policy, near_app read-only for freshness display, no DELETE grant for any role, cursor-pair and non-negative-check constraints. Tests: `apps/api/tests/test_refresh_adapter.py` (offline budget/supply/validation/failure/stop-marker/allowlist classes + 16 database tests) and the env-gated `apps/api/tests/test_refresh_live_smoke.py` (excluded from CI discovery; runs one real request only under `NI_ISOLATED_PG_TEST=1` + `NI_LIVE_SMOKE=1`, which `scripts/run-db-tests.py` forwards). Docs: DATA_PIPELINE.md records the implemented refresh leg and DEPLOYMENT.md the timer opt-in contract. Limitations: only `SRC-NEAR-RPC` header refresh is implemented; the freshness/failure display API belongs to NI-032 (the near_app read grants are already in place); the timer itself is operator infrastructure, not repo code; a single live smoke does not establish an SLA or a numeric provider quota. PR not merged; DONE awaits role-A review.

## EPIC 07 — Analytics and Charts

Specification: [CHART_SYSTEM.md](CHART_SYSTEM.md).

### NI-031 — Define versioned chart and metric registries

- **Epic:** 07 — Analytics and Charts
- **Priority:** P0
- **Dependencies:** NI-029, NI-004
- **Complexity:** M
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #9
- **Execution role:** B
- **Started at:** 2026-11-07T01:55:00+03:00
- **Branch/worktree:** feat/ni-031-registries; /Users/ilyutkinn/Desktop/near-intelligence-b (git worktree off origin/main e69746b)

**Description:** Make charts extensible through definitions instead of custom pages.

**Implementation steps:** Add metric/chart registry migrations; create immutable registry schemas and initial valid chart entries; bind metric definition UUIDs and units; define allowed ranges/filters/categories; include renderer version and source lineage.

**Expected files/modules:** apps/api/src/near_api/charts/registry.py; schemas/charts.py

**Acceptance criteria:** All chart metrics resolve; unsupported/unavailable metrics not advertised as live; adding a supported definition needs no new page implementation.

**Testing requirements:** Registry integrity tests; invalid filter/unit/metric references rejected; version increments do not modify old definitions.
- **Verification (2026-11-07, this claim):** 1) Full offline discovery `uv run --project apps/api python -m unittest discover -s apps/api/tests -p "test_*.py"` — 231 tests OK (skipped=77, exactly the cluster/handoff-dependent cases). 2) `uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` — PostgreSQL 18 disposable loopback cluster, 153 integration tests OK across all ten discovered suites (test_database 8, test_auth_bootstrap 4, test_ownership_rls 9, test_home_aggregation 11, test_archive_import 9, test_dataset_staging 16, test_metrics 39, new test_chart_registry 26 = 21 offline + 5 real-DB, test_profile 10, test_documents 21), no skips. The NI-031 suite asserted: migration 0007 round trip (downgrade to 0006 drops the chart tables and the new dataset FK; upgrade + alembic `check` detect no drift against the mirrored models; FORCE RLS flags on both registry tables) and the `dataset_metrics.metric_definition_id → metric_definitions(id)` RESTRICT FK with ON DELETE RESTRICT; `register_charts` is idempotent (registered=11, then existing=11) and content-verified (an admin-tampered title makes registration refuse with a divergence error; the row is restored in cleanup); stored rows carry the deterministic uuid5 identity, bound definition UUIDs, units and data_status; two runtime users read all 11 definitions including the honestly unavailable ones, while runtime INSERTs and operator UPDATE/DELETE on both registry tables are refused 42501 (append-only, no grants); an unregistered metric UUID is refused 23503 by both the chart junction FK and the dataset member FK, and a registered UUID binds successfully; the 21 offline tests pin integrity (unknown metric references, unit mismatches, missing/extra unit roles, gated metrics in available charts, unavailable charts without reasons or with non-gated bindings, invalid ranges/filter schemas/source lineage/frequency/roles, duplicate bindings all rejected; deterministic uuid5 identities; version-2 registration adds a new definition while v1 stays frozen — structural immutability asserted). 3) `uv lock --check --project apps/api` — OK; `pnpm check:doc-links` — 573 links resolve. No network calls; no provider or archive access.
- **Result:** Migration `apps/api/alembic/versions/0007_metric_chart_registries.py` creates the append-only FORCE-RLS chart registry per CHART_SYSTEM/DATABASE_SCHEMA: `app.chart_definitions` (deterministic uuid5 identity, `(chart_id, version)` unique, fixed categories `activity/fees/treasury/supply/model`, visualizations `line/area/bar/scatter/panels`, honest `data_status` available/unavailable with a mandatory recorded reason, `update_frequency`, bounded `allowed_ranges` presets with `max_days ≤ 366`, closed `filter_schema` JSON Schema with string enums, `unit_schema`, denormalized `metric_definition_ids`, `source_lineage` with mandatory qualification note, `renderer_version`) and `app.chart_metrics` (binding junction `(chart_definition_version_id, metric_definition_id, series_role)` with RESTRICT FKs into both registries and required/optional roles); 0007 also lands the documented NI-028→NI-031 contract change — the referential FK `dataset_metrics.metric_definition_id → metric_definitions(id)` plus its index, so staged members must resolve to registered definitions. `apps/api/src/near_api/charts/registry.py` mirrors the NI-029 registry pattern: 11 immutable v1 chart definitions resolved against the real metric registry — seven `available` (intents-volume, gross-fees, observed-conversions, treasury-payouts, quantity-usd-sensitivity, supply-context, fee-volume-association) and four honestly `unavailable` (model-diagnostics — no published model artifact yet; protocol-revenue, capture-rate, fee-funded-buybacks — OQ-01/OQ-08/OQ-11 reasons); `validate_registry` fails closed on unknown metric refs, unit/frequency/lineage mismatches, invalid filters/ranges/roles/categories and gated metrics advertised as live; `register_charts` is idempotent and content-verified as `near_operator`; `view_contract` derives the complete renderer-agnostic contract (series roles/units/availability for generic bound/estimate labeling), so a newly registered supported definition needs no new page implementation. `apps/api/src/near_api/db/models.py` mirrors the migration for the drift check; `scripts/run-db-tests.py` discovers the new suite; `apps/api/tests/test_dataset_staging.py` now registers the metric definitions in setUpClass and binds its fixture members to registered definition UUIDs (consequence of the contract change; all 16 staging tests unchanged otherwise and passing). Docs updated: DATABASE_SCHEMA.md (chart registry zone, resolved FK interpretation), CHART_SYSTEM.md (implemented note), DATA_PIPELINE.md (registry leg), apps/api/README.md. Limitations: chart routes/catalog endpoints and ChartView resolution are NI-032; `schemas/charts.py` request/response DTOs belong to NI-032's OpenAPI contract (the registry stores definitions; no HTTP layer exists yet); near_public has no schema-app grant by the 0005/NI-019 design — public exposure happens through the near_app API role; the strict unit binding means a chart's unit_schema must quote the metric registry units exactly; PR not merged, DONE pending role-A review.

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
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #8
- **Execution role:** B
- **Started at:** 2026-11-07T00:27:05+03:00
- **Branch/worktree:** feat/ni-036-document-schema; /Users/ilyutkinn/Desktop/near-intelligence-b
- **Verification:** Offline `uv run --project apps/api python -m unittest discover -s apps/api/tests`: 153 tests OK (59 DB-skip without cluster env), including the 10-test canonical schema matrix (fixture per P0 block type, duplicate/dangling IDs, unknown types/attrs/marks/link schemes, 2 MiB/200-block/1k-cell/10k-body/depth-3 limits, canonical spelling round-trip, empty document valid). DB suites via `scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` (disposable loopback PostgreSQL 18 cluster): 88 tests OK, 0 skipped — test_database 8, test_auth_bootstrap 4, test_ownership_rls 9, test_home_aggregation 11, test_archive_import 9, test_dataset_staging 16, test_profile 10, **test_documents 21**: create-with-first-empty-revision, CAS race (two engines + barrier, exactly one winner, one 409-equivalent RevisionConflict, exactly two versions), invalid content/simulated crash leave ZERO rows, old revisions byte-identical and 42501-protected against UPDATE, projection round-trip (stored content re-parses to the recorded sha256 and regenerates identical block/insight/hypothesis/evidence rows), approved-dataset/citation-artifact reference checks, Alice/Bob service+HTTP isolation (foreign id = one generic 404, RLS-invisible projections), HTTP matrix (missing/malformed If-Match 428, stale 409 REVISION_CONFLICT with current revision, 201 + new ETag, 413 oversize, 422 FEATURE_UNAVAILABLE template, pagination cursor + search), 0005 downgrade/upgrade round trip with `command.check` clean. `uv lock --check` OK; `pnpm check:doc-links` OK (567 links); `git diff --check` clean.
- **Result:** `apps/api/src/near_api/documents/schema.py` — the single canonical validator of the EditorDocument (strict P0 taxonomy paragraph/heading/bullet_list/ordered_list/liveChart/dataTable/insight/hypothesis/evidence/risk/divider with `attrs.block_id` UUIDs on every top-level node; bounded sizes; deterministic canonicalization of UUIDs/timestamps/URLs; pure same-document link validation). `service.py` — create (document + first empty revision atomically), get/list and the CAS save transaction (row lock -> expected-revision check -> schema validation -> DB reference checks -> immutable version + projections + pointer advance in ONE transaction; RevisionConflict carries the current revision; revision numbering is service-owned: documents.revision = current version number). `projections.py` — block/insight/hypothesis/evidence projection build+write from the validated canonical document. `alembic/versions/0005_document_projections.py` — insights/hypotheses/evidence_links with (version,document,owner) composite FKs, same-version block FK, evidence->same-version hypothesis FK, FORCE RLS with the 0002 policy pattern, no UPDATE grant for the runtime role; mirrored in `db/models.py` for the drift check. `routes.py` + `schemas/documents.py` — GET/POST /api/documents, GET /api/documents/{id}, POST /api/documents/{id}/versions with ETag/If-Match, typed 409/413/422/428 envelope responses, no-store everywhere. Docs updated: API_SPECIFICATION.md implemented note, apps/api/README.md. Scope boundaries recorded for review: revision numbering is the current-version number (differs from the NI-019 repository helper's next-counter semantics, which remains unused by the service); liveChart/snapshot/model_run/observed_contexts are explicit reference gates until their owning tasks land; DocumentSummary.progress counters stay the documented zero (home wiring is NI-024/NI-037 scope).
- **Reviewer:** pending role-A review (PR opened; status stays IN_PROGRESS until review)

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
- **Status:** DONE
- **Claimed by:** ZCode agent for ILYUTKICK, role A, session 42d29234
- **Execution role:** A
- **Started at:** 2026-11-07T02:31:10+03:00
- **Branch/worktree:** feat/ni-038-tiptap-prototype; /Users/ilyutkinn/Desktop/Near
- **Dependency verification:** NI-002✓, NI-009✓, NI-031✓ (PR #39 merged) — cards on origin/main.
- **Verification:** `pnpm --filter web test` — 82/82 pass (3 new): node-schema JSON round trip identical after reload (canonical JSON is the NI-036 storage path); typing/undo survive React node updates (robust assertion — adjacent inserts may group into one history step); empty doc parses validly (Tiptap normalizes to one empty paragraph — documented constraint in ADR-018). Attributes serialize to HTML data-attributes and parse back (getAttrs) — HTML fidelity holds alongside the JSON path. `tsc --noEmit`, `eslint` 0 warnings, `next build` pass. **Browser IME/paste/selection checks are operator-manual** (jsdom cannot emulate IME composition) — recorded as the remaining manual step before NI-039 relies on the pattern.
- **Result:** apps/web/src/features/editor/prototype/ — ChartBlock (atomic node, node-view controls: annotate/remove, contentEditable=false islands with keyboard-reachable buttons), InsightCard (nested-editable title input probe + editor-undo escape button), prototype route /workspace/editor-prototype behind the NI-021 gate with synthetic fixtures; Tiptap 3.33.0 (MIT) deps recorded in DEPENDENCIES.md; ADR-018 in DECISIONS.md records the confirmed adoption with verified constraints (empty-paragraph normalization, history grouping, tuple-form renderHTML, JSON as canonical storage path).
- **Reviewer:** pending — role-B review requested on PR #41; CI runs on this PR.
- **Completed at:** 2026-11-07T02:52:30+03:00

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
- **Status:** IN_PROGRESS
- **Claimed by:** Claude agent for role B (operator-authorized subagent), session dispatch #11
- **Execution role:** B
- **Started at:** 2026-11-07T01:52:13+03:00
- **Branch/worktree:** feat/ni-051-readiness-gate; /Users/ilyutkinn/Desktop/near-intelligence-b3 (worktree from origin/main e69746b)

**Description:** Choose an admissible empirical question before fitting rather than manufacturing revenue data.

**Implementation steps:** Add model definition/run migrations and typed registry; build calendar-aligned prepared table; profile missing/zero/bound data and policy/source changes; enforce project nobs/parameter rules; select true-revenue or explicitly named proxy spec; record OQ-02 risk.

**Expected files/modules:** research/models/readiness.py; model configs; readiness report

**Acceptance criteria:** No gross-fee/payout proxy passes as protocol_revenue; gaps/exclusions explicit; short attribution dataset rejected for daily long-run inference.

**Testing requirements:** Real archive readiness report; missing/zero/nonadjacent days; lower-bound outcome rejected; reproducible reason codes.

**Verification (2026-11-07, this claim):** 1) Full offline discovery `uv run --project apps/api python -m unittest discover -s apps/api/tests -p "test_*.py"` — 232 tests OK; without `NI_REAL_ARCHIVE_ROOT` 82 skip (cluster/handoff-dependent), with the env set the 17 synthetic gate tests and 10 real-archive gate tests all execute (232 OK / 65 skipped). 2) `NI_REAL_ARCHIVE_ROOT=…/research uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` — PostgreSQL 18 disposable loopback cluster, all ten discovered suites OK with no skips, including the new `test_models_readiness.py` suite (17 tests; the suite needs no database and runs offline inside the frozen environment). 3) `uv lock --check --project apps/api` — OK; `pnpm check:doc-links` — 575 links resolve. 4) Real-archive readiness run (read-only, report generated into gitignored `research/models/reports/`): overall verdict `PROXY_ONLY_READY_WITH_LIMITS`, selected spec `gross_fee_activity_v1`; `true_revenue_daily_v1` NOT_READY (`GATED_METRIC_NO_OBSERVATIONS`, `PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01`); `supply_bounds_activity_v1` REJECTED (`LOWER_BOUND_SERIES_NOT_EXACT_OUTCOME`, `WINDOW_AGGREGATE_NOT_DAILY`, `MINT_HEADER_AUDIT_INCOMPLETE` with the archive numbers 6 of 297); `purchases_activity_v1` READY_WITH_LIMITS with cohort limits only; the 90-day window profiles show zero missing/zero/negative days in both provider series, sources disagreeing on all 90 overlapping days (kept unsummed), and all four report invariants held. Double runs over the real archive render byte-identical JSON/Markdown reports (no wall-clock fields; inputs pinned by SHA-256).

**Result:** `research/models/readiness.py` — the offline readiness gate (research code, outside apps/api): strict archive loading through the NI-029 loaders (import only, no duplication); one calendar-aligned prepared table (90 days + atomic 30-day supply windows and the total period kept in saved shapes; missing rows/series values stay explicit `None` reasons, verified zeros only where extract coverage proves them); per-series profiles (present/missing/zero/negative days, calendar gaps, adjacency, float64 finiteness, bound status from the versioned metric registry); source-disagreement and descriptive fee-rate regime profiles; typed spec registry validating preregistered configs against `near_api.metrics.registry`; gate policy with fixed numbers (60 complete daily observations, 10 per parameter incl. intercept, 3 substantive slopes max, 365-day long-run threshold); evaluation with a fixed reason-code catalog (rejecting/limit/informational severities); hard invariants (no proxy passes as protocol_revenue, gaps/exclusions explicit, short attribution rejected, all codes cataloged) that fail closed; deterministic JSON+Markdown report rendering and CLI (exit 0/4). `research/models/configs/` — five preregistered JSONs: gate policy (window 2026-08-06..11-04, input bindings) plus `true_revenue_daily_v1` (NOT_READY while OQ-01 open), `gross_fee_activity_v1` (the named proxy; mechanical fee-volume relationship, OQ-02 judging risk, single lineage, short-sample and no-causal limits attached verbatim), `purchases_activity_v1` (optional cohort fallback, never market demand), `supply_bounds_activity_v1` (documented standing rejection of bound-only outcomes). Tests: `apps/api/tests/test_models_readiness.py` (17 synthetic temp-dir tests: missing/zero/nonadjacent days, absent rows, 7-day short-window rejection, mislabeled proxy always rejected, over-parameterized spec refused at load, unknown metric refused, double-run byte-identical, read-only archive, catalog/hash/registry checks, CLI exit codes) added to the `scripts/run-db-tests.py` discovery list, and `apps/api/tests/test_models_readiness_real_archive.py` (10 env-gated tests pinning the real-archive verdicts, 6/297 audit numbers, invariants and reproducibility). `.gitignore` gains narrow exceptions so the gate code and configs are shared while `research/models/reports/` stays local. Docs: ECONOMETRIC_METHODOLOGY.md and MVP_SCOPE.md record the implemented gate without claiming fitted results. Migration decision: no `0009_model_runs` is added — the gate's artifact is the reproducible readiness report and no fit run exists to persist; the model_runs table belongs to NI-052/NI-054 when fitted runs and published artifacts exist. Limitations: the gate decides admissibility only and fits nothing (NI-052 owns the estimator and any future run persistence); the admitted proxy association cannot support causal, demand-elasticity or sustainable-revenue claims (OQ-02 judging risk recorded); the readiness report is not committed by design; PR not merged, DONE pending role-A review.

**Reviewer:** role A review pending (requested for the NI-051 gate decision and spec registry).

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
