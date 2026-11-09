# Testing strategy

No application or econometric test suite currently exists. This specification defines required checks after approval; documentation validation alone cannot establish runtime correctness. [Acceptance requirements](FEATURE_SPECIFICATIONS.md), [task backlog](TASKS.md).

## Test layers and highest-value cases

| Layer | Scope | Required examples |
| --- | --- | --- |
| Unit — Python | Metric transforms, periods, matching, quality, readiness | Exact yocto sums; duplicated receipt does not double count; failed execution excluded; missing vs zero; USD denominator alignment; lower/upper bounds remain bounds |
| Unit — TypeScript | Editor schema/IDs, selection serialization, token formatting | Duplicate/remap evidence targets; canonical filter hash; 24-decimal display without precision loss; invalid persisted node rejected |
| Integration — PostgreSQL | Actual migrations/RLS/transactions/repositories | Two-user CRUD, nested version ownership, CAS race, no partial revision projections, pooled identity reset, staged dataset never latest |
| API contracts | Pydantic/OpenAPI/generated client | Every endpoint family, 401/404/409/422/428, pagination before owner leakage, unknown fields/filters rejected |
| Data integration | Saved provider responses and controlled HTTP fakes | Pagination exhaustion, 429 Retry-After, partial day, revised history, conflicting duplicates, price gap, provider schema change; no real paid provider in CI |
| Editor browser | Typing/keyboard/drag/chart nodes/autosave | Save/reopen; IME; focus after reorder; local undo; timeout-after-commit idempotency; two-tab conflict; expired session recovery |
| Full E2E | Real web/API/DB with isolated provider/auth test setup | Anonymous thesis→chart→login→save→document→insight→opposing evidence→export; verify stored version and downloaded hashes |
| Quantitative | Fixed real dataset + frozen config/code/locks | Rebuild design matrix; exact sample/exclusions; compare coefficient/SE/CI tolerances; diagnostics and interpretation present; short/missing/nonstationary samples fail/readiness explain |
| Accessibility/UI | Automated checks + keyboard/screen reader review | Dialog traps/return focus, contrast, chart table, editor toolbar/outline, reduced motion, desktop viewport (1440px baseline) |
| Operations | Build/staging/backup/restore | Fresh migration, readiness before traffic, failed provider leaves editing functional, artifact backup restore, image rollback |

## Financial and research invariants

Never test financial integrity by asserting that the UI matches its own fixture strings. Independently aggregate known event inputs with duplicate/internal-treasury-transfer/failure cases and compare exact raw totals. Include an event near UTC midnight and a payout whose matching receipt is on the next date. Distinguish daily cash receipts from accrual data. Ensure dataset revisions leave old document/model/export hashes unchanged.

Use real legacy saved outputs as regression evidence only after confirming source hashes and scope. Values in [thesis](INVESTMENT_THESIS.md) are historical observations, not fabricated expected model coefficients. Synthetic data are useful for known statistical behavior tests, but must never reach published research. A mechanically constructed fee=volume×rate synthetic case should prove the interpretation warning, not “discover” causality.

Model reproducibility compares canonical prepared-data bytes and manifest hashes exactly. Numerical estimates use pinned environment and declared tolerance (initial rtol 1e-8, atol 1e-10 for fitted statistics, adjusted only with documented cross-BLAS evidence); no byte-for-byte promise for PNG/OS-dependent render metadata. Statistical nonsignificance is a valid output. Reject parameter/model selection that seeks significance without disclosure.

## Release gates

NI-012 HTTP integration (`apps/api/tests/test_landing_integration.py`) runs via
`scripts/run-db-tests.py --suite landing` after the frozen web build. It starts
real production Next.js and FastAPI processes on loopback, uses the unprivileged
`near_app` connection for delivery and `near_operator` for staging/publication,
and compares visible HTML article text (excluding React script payloads) with
the API's exact decimal strings. It verifies no-approved-data and stopped-API
states on the same running web process. CI uses only labeled synthetic data.
An explicit `NI_LANDING_ARCHIVE_ROOT` selects the saved-input emission path and
checks the consumed archive hashes before/after; missing inputs fail the run
instead of substituting fixtures. This is HTTP/SSR integration evidence;
keyboard, responsive and screen-reader release checks remain separate.

NI-024 Home integration runs with `scripts/run-db-tests.py --workspace-home-http`
after the production web build. It uses the real Next.js private gateway,
ES256 verification, RLS and disposable PostgreSQL to check first-use empty
sections, document create/save/reopen, current-version workflow projections,
Alice/Bob lists and an actual SQL error isolated to one contextual indicator.
The optional `NI_BROWSER_HANDOFF=1` retains that synthetic-only stack briefly
for native browser first-use/returning-user, keyboard and viewport checks.
Desktop responsive emulation is not physical-phone validation.

Every P0 user journey has one successful real persistence E2E and relevant failure branch. Every private route family has Alice/Bob tests including search, nested IDs and download. Every released metric has unit/definition/provenance/quality tests. Every model has input manifest, deterministic command and clean offline reproduction. Every chart has accessible data and missing/stale state. Markdown export is unpacked and validated against its revision, not just checked for HTTP200.

Performance budgets from PRD run on a documented staging machine/data/concurrency, not inferred from local dev. Limit 200-block documents, 20 chart references with lazy mounting, 366-day series; if budgets fail, optimize or lower documented limits rather than hiding failures.

## CI contract to implement

PR pipeline: frontend lint/typecheck/unit; Python Ruff/unit; PostgreSQL migration/integration; generated-client drift; docs relative-link/task validation; critical Playwright journeys. Release pipeline adds reproducible real-data model recipe (permitted inputs), artifact manifest checks, accessibility/performance checks, image scans and staging smoke/restore evidence. Separate expensive/credentialed provider probes from PR CI; require an explicit operator invocation and cap.

Tests run in isolated temp DB/storage/auth accounts. No tests mutate legacy research archives or restart stopped collectors. Test fixtures have visibly synthetic labels and production seed guards. Prefer focused regression tests for material business/security behavior; avoid snapshotting entire static pages or duplicating implementation formulas without an independent oracle.

NI-042 extends the existing `--chart-insertion-http` production integration with the owner-scoped chart-view query, exact old-pin values/hash, explicit range/filter save/reopen and replay, latest preview/adoption, old revision invariance, stale CAS, chart-delivery outage with successful prose save, and Bob denial. Web regressions exercise the actual Tiptap node, local drafts versus committed attrs, source-dialog focus return, a touch-pointer press/release activating Apply on the actual node, chart undo/redo with prose retained, late results after account/attribute changes, restored local chart drafts, and localized synchronous ECharts factory/setOption failures with table retention/retry. The node interaction test supplies only jsdom's missing Range geometry methods; it does not suppress thrown errors or claim real layout. [360px page-only Chrome evidence](qa/ni042-editor-chart-360.png) is synthetic and emulated, not a physical-phone release check.

The "Full E2E" row is implemented (NI-063): `pnpm --filter web build` then
`pnpm --filter web exec playwright test --config e2e/playwright.config.ts`
(after `playwright install chromium`) runs `apps/web/e2e/research-workflow.spec.ts`
at the documented 1440×900 desktop viewport. Its global setup boots the real
stack from `apps/web/e2e/harness/` — a disposable loopback PostgreSQL 18 with
the production roles, the real FastAPI gateway under the synthetic-ES256
provider transport used by every production HTTP suite here, the production
`next start` bundle, the real NI-058 export worker, and one approved synthetic
dataset staged through the real NI-028 pipeline — and its teardown removes the
cluster. The journey drives the actual browser through anonymous traces,
sign-in continuation, save chart, document authoring, the source-outage branch
and the export, verifies the downloaded ZIP (manifest hashes, research.md
links, exact decimal CSV) against the `app.document_versions` row read from
the disposable cluster, and repeats the private-resource denial for a second
user. Only the provider JWKS transport is synthetic; the primary API is never
mocked. CI runs the same journey in the `e2e` job of `.github/workflows/checks.yml`.

## Current user scope override — 8 November 2026

Remaining QA targets desktop. The user excluded mobile development/adaptation and mobile, touch, phone and tablet QA to reduce execution cost. Do not repeat mobile viewport/device screenshots or checks mentioned in historical task evidence; existing tests/code remain intact. Desktop keyboard/accessibility, exact data, two-user isolation, persistence, frozen revisions and export verification remain required. Run focused checks for changes and required integration gates; repeat broad suites only after relevant source changes, failures or unresolved concerns.
