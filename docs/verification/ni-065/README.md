# NI-065 — PR #97 integration repair

Verified 13 November 2026 on macOS ARM64, Node 24.22.2, pnpm 12.16.1,
Python 3.13.5 and PostgreSQL 18.6. Repair starts at PR head `0bfc5d7`
and integrates `main` at `7ad89a0`. The owner's request is limited to fixing
PR #97; deployment and real provider calls were not performed.

## Corrected behavior

- Combined the gateway, editor imports, route inventory tests, DB discovery
  and generated contracts with the current snapshot/model/filter/publication/
  sharing/export implementation. Sharing keeps ADR-021; integrity uses ADR-022.
- Historical integrity accepts one valid `version_id`; malformed, duplicate
  and unknown query fields are refused before forwarding.
- The editor ties each report to its verified session, document, acknowledged
  revision and retry attempt. Pending, failed, aborted or mismatched checks
  cannot display old findings as current or claim a clean revision.
- Frozen chart contexts are verified against canonical pins, hashes, renderer
  and metric references. Frozen model contexts and published-run availability
  are checked. Missing dataset rows are unavailable; a revoked pin cannot
  make an older fallback look like a newer publication.
- The report cap is derived from 200 allowed blocks: four findings per block
  plus one map warning (801). The maximum corruption case is tested.
- Optional commentary checks ownership before adapter configuration, preserves
  complete numeric spellings when grounding, and returns typed failures for
  malformed configuration/context maps and overlong text. Selected model
  blocks carry their verified frozen context and bounded interpretation;
  unselected content and newer model results are never loaded into the prompt.
- The lexical numeric guard cannot fact-check the meaning of generated prose.
  Commentary stays advisory, disabled by default and read-only. Transport
  success/failure tests use `httpx.MockTransport`, with no external calls.

## Executed verification

All commands ran in the isolated PR worktree with frozen dependencies. `corepack
pnpm` selects the repository-pinned pnpm; plain system pnpm differs on this host.

| Check | Actual result |
| --- | --- |
| `corepack pnpm --filter web test --maxWorkers=1` | 63 files, 652 tests pass |
| Final panel/gateway rerun after the model finding labels | 22 tests pass |
| `uv run --project apps/api python -m unittest discover -s apps/api/tests -p 'test_*.py'` | 837 tests OK, 311 DB-gated skips; the separate cluster run covers DB tests |
| Final isolated adapter suite | 25 tests pass, no external transport |
| `uv run --project apps/api python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin` | 31 suites, 579 tests pass, zero skips |
| `corepack pnpm --filter web exec playwright test --config e2e/playwright.config.ts e2e/research-workflow.spec.ts` | 4 desktop Chromium scenarios pass on real PostgreSQL/FastAPI/production Next.js/worker |
| `corepack pnpm lint`, `corepack pnpm typecheck`, `corepack pnpm build` | Pass on final source |
| `corepack pnpm check:contracts`, shared-types typecheck/tests, `uv lock --check --project apps/api` | Pass |
| `corepack pnpm check:contrast`, `corepack pnpm check:doc-links` | 22 contrast pairs pass; documentation links resolve |
| `corepack pnpm check:client-secrets` | Command passes; no root `.env`, so it reports nothing to scan |
| `git diff --check` | Clean |

The browser journey now checks uncited chart → advisory with exact saved
revision → keyboard jump without a new revision → save a source-bearing
insight → automatic clean rerun on revision 5. It also verifies save/reopen,
source-outage prose editing, frozen ZIP export, Alice/Bob denial and private
publication copying. The primary API is not mocked. Only auth transport and
research input are visibly synthetic, following the existing loopback harness.
These runs prove application behavior, not real research results or provider
connectivity; final release acceptance remains NI-079.

The offline CI job now explicitly discovers `test_ai_adapter.py`; the DB job
preserves the union of all integrated suites and includes `test_integrity.py`.
GitHub checks for the published head are the remote CI record.
