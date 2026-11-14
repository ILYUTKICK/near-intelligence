# NI-079 — Final integrated local release acceptance

**Status:** IN_PROGRESS (evidence accumulates here; the task is DONE only when every applicable gate below is recorded as passed or explicitly blocked).

**Release candidate:** `feat/ni-079-release-acceptance` — `596c36e` (owner landing copy revisions) + `4c493b0` (NI-090 VPS preparation record) on top of main `13e9d0c` (PRs #100, #101 merged). Claim: 2026-11-14T15:32:44+03:00, ZCode role-A coordinator, interactive owner chat session, worktree `/Users/ilyutkinn/Desktop/near-deploy`.

**Environment:** macOS ARM64 (Darwin 25.6.0), Node v24.22.2 (node@24 keg-only), pnpm 12.16.1 (corepack), uv / CPython 3.13 (`apps/api/.venv`, frozen), PostgreSQL 18.6 (Homebrew, disposable clusters), Docker 29.9.2 + Compose v5.6.1.

## Gate matrix

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| A1 | Offline API suite | **PASS** | `python -m unittest discover -s apps/api/tests` with node@24-first PATH: **exit 0, 849 tests, OK (skipped=312, DB-gated)**. First runs exposed two environment/test issues, both resolved before the recorded run: (1) the Node chart-renderer subprocess tests fail when a non-node@24 binary shadows the PATH prefix (both system node and keg-only node@24 are v24.22.2 here; PATH order is decisive) — toolchain rule recorded; (2) `test_insights.test_07` still expected a 367-day selection to exceed the Selection bound — fixed in `194eb79` to the 730-day NI-083 contract (test-only change; A2–A4 ran on the pre-fix tree whose runtime files are identical). |
| A2 | Full disposable-cluster DB suite (26 patterns) | **PASS** | `scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` (thread caps 1): **exit 0, 571 tests ok, 31 module summaries OK, zero failures/skips** |
| A3 | Web unit suite (serial) | **PASS** | `pnpm --filter web test --maxWorkers=1`: **66 files / 681 tests pass, exit 0** |
| A4 | Production build | **PASS** | `pnpm --filter web build`: exit 0 (static prerender + dynamic server routes) |
| A5 | lint / typecheck / contracts / doc-links / contrast / client-secrets / uv lock | **PASS** | below |
| B1 | Real-stack workflow e2e (public→chart→login→saved→research→insight→evidence→save/reopen→ZIP) | **PASS (synthetic leg)** | `pnpm --filter web exec playwright test --config e2e/playwright.config.ts`: **26 passed, exit 0, 2.6 min** — the NI-063 journey covers the full workflow incl. outage and export on the real loopback stack. The real-data leg of the end-to-end trace is Gate G2. |
| B2 | Alice/Bob denial + source-outage editing | **PASS (synthetic leg)** | covered by the same e2e run (journey outage step, two-user denial specs) and the DB-suite ownership matrix (A2). |
| C1 | Real research data import (stage→validate→approve→publish) | **PASS** | 2026-11-14, deployment DB (near-deploy, localhost:15433): NI-027 `python -m near_api.ingestion.archive` imported the machine-local archive as `near_operator` — **380 files / 155,529,116 verified bytes / all 8 declared cohorts / 29 documented runs**, batch manifest sha256 `fbaf3fbea19db4fea1b63a90e2ab2716fec8abf1e74fe86cc32d59f777a8630c`, batch id `4f73ae5d-c0c4-4d66-b2fe-9d112929cab8`. Import shape note: the importer classifies by the first path segment after the manifest's common leading directory, so the batch was built from a byte-identical temp copy of the 8 cohort directories (the archive root contains Finder `.DS_Store` junk that belongs to no cohort); the archive content hash over all non-junk files is **identical pre/post import (`cca74075027003b90e…`)** — zero archive bytes changed. NI-029 emission (`.local/ni079_emit_manifests.py`, the recorded reconciliation inputs): `metrics.flows.daily` 1710 observations + `metrics.windows.snapshot` 35 observations, 4 lineage inputs each, pipeline `ni079-release`, code commit `5f2b0be`. NI-028: `datasets stage` → both **validated** in one transaction (`70d8d056-…` / `454b6eee-…`, version 1), `datasets publish` → active pointers switched. Delivery verification: `/api/charts` lists the catalog; `intents-volume` v2 reports `data_status: available`; `/api/research/history` **200** (was 503); `/api/charts/intents-volume/view?definition_version=1&start=2026-10-01&end=2026-11-04&dataset_version=latest` returns 34 points; without an approved filter value the periods answer the honest multi-variant unavailable reason, with `filters={"source":"SRC-LLAMA"}` **34/34 points carry values (e.g. 2026-10-01 = 125036685, quality ok)**. |
| C2 | Real-data provenance/rights/quality audit | **partial PASS (compute leg)** | `NI_REAL_ARCHIVE_ROOT=…/research python -m unittest discover -s apps/api/tests -p test_metrics_real_archive.py`: **7 real-archive reconciliation tests OK** (buy total, fee bps at storage scale, payout matching, supply values, treasury balance, USD estimates, emitted manifests vs summaries — all reconcile exactly with the saved archive; 6 DB-gated cases skip outside a cluster). Source provenance/rights statuses come from the shipped NI-027 cohort registry transcription (documented/unverified, never invented). |
| D1 | Real deterministic model fit + publish gate | pending | — |
| D2 | Offline reproduction of the published run | pending | — |
| E1 | Permitted-source refresh last-good evidence (1 guarded request, OQ-03) | pending | — |
| F1 | Container/migration rehearsal on RC images | pending | — |
| F2 | Local backup/restore + rollback rehearsal | pending | — |
| G1 | Desktop keyboard/accessibility/performance | pending | — |
| G2 | Extended chart acceptance incl. one real chart end-to-end (input→metric→API→plot→saved revision→ZIP/PDF) | pending | — |

## Gate A5 — fast static gates (2026-11-14, this worktree, RC head)

| Check | Command | Result |
|-------|---------|--------|
| lint | `corepack pnpm --filter web lint` | 0 problems |
| typecheck | `corepack pnpm --filter web typecheck` | clean |
| contracts | `corepack pnpm check:contracts` | OpenAPI and TypeScript are current |
| doc-links | `corepack pnpm check:doc-links` | OK — 1029 relative links resolve |
| contrast | `corepack pnpm --filter web check:contrast` | all token contrast checks passed |
| client-secrets | `corepack pnpm --filter web check:client-secrets` | exit 0 |
| uv lock | `uv lock --check --project apps/api` | OK |

Notes: root `check:contrast` / `check:client-secrets` wrappers fail with exit 127 under corepack-shimmed PATH because the root scripts shell out to a bare `pnpm`; the underlying workspace scripts pass (recorded command above is the workspace-scoped equivalent).

## Gate C/D/E — real-data prerequisites (operator scope)

The deployment DB (`near-deploy`, localhost:15433) currently holds the registered registries (20 metric definitions, 14 chart definitions, 6 documented sources seeded 2026-11-14) and **no approved datasets** — delivery endpoints answer the honest 503/unavailable states. Gates C/D/E require the owner's machine-local research archive and one operator decision (permitted-source refresh authorization); recorded here as they land, never fabricated.

**Archive import preparation (2026-11-14):** a strict `shasum -a 256` manifest was generated over the machine-local archive `/Users/ilyutkinn/Desktop/Near/research` (395 files incl. macOS Finder junk). Dry-run findings against the shipped NI-027 cohort registry (`archive_cohorts.json`): byte verification passes; the batch is rejected only because root-level `.DS_Store` files (11) belong to no cohort directory. The importer scopes its extra/missing-file tree comparison to the manifest's common leading directory, so the sanctioned import shape is **per-cohort manifests** (each manifest covering one cohort directory). Plan: import chart-relevant cohorts (`near-treasury`, `near-supply`, `near-weekly`, `near-dollar`, `near-longitudinal`, `near-pilot`, `near-provenance`) via `python -m near_api.ingestion.archive` as `near_operator` into the deployment DB, then `python -m near_api.metrics build` (NI-029) and `python -m near_api.datasets stage-from-import → validate → publish` (NI-028) per the recorded DATA_PIPELINE.md contract. No archive byte is modified; the archive tree hash is recorded before/after.
