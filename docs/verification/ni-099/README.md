# NI-099 — Comic Lab desktop implementation

Verified locally on 22 November 2026 (Europe/Moscow), from `feat/ni-099-comic-lab`, based on main `3ff78b0b8e2d7556c5c2d096e3f3aa2b2373fd0d`. Coordinator: Codex `/root`; dedicated implementation agent: `/root/ni099_comic_lab`. Independent second acceptance remains waived under the existing owner instruction; the coordinator performed the checks below.

## Delivered behavior

The approved identity now renders in the actual Next.js application. The shared desktop shell, public/auth pages, workspace Home, chart/model views, editor, revision/share/export dialogs and account screens use Comic Lab foundations. These are native controls and existing data-backed views. The 58 design frames informed the presentation; they are not embedded as screenshots or introduced as 58 new routes.

| Before | After | Reason |
| --- | --- | --- |
| Editorial serif headings and thin neutral panels | Rubik headings, Golos Text prose, IBM Plex Mono values; outlined rounded paper panels | Match the approved identity and keep dense research readable |
| Earlier letter-based mark and research-desk art | Canonical three-node graph wordmark, matching favicon and exact approved TRACE | Carry the chosen brand into every shell and the main entry points |
| Dark primary fills | Mint actions with dark text; accessible dark green links | Preserve readable links and button labels |
| Neutral Home workflow cards | TRACE continue card, yellow progress checklist, lavender notes | Make the private research workflow easier to scan |

The existing Chart library route is also directly available in the workspace sidebar. API calls, metric/calculation definitions, editor schema, authentication, ownership and immutable research/export contracts are unchanged. Scientific chart rendering and the frozen export palette are unchanged.

## Assets and licenses

Canonical assets are under `apps/web/public/brand`; `trace-approved.png` preserves the supplied artwork and its original white background. Logo text is outlined vector geometry. No Near Cooking artwork was copied. The five WOFF2 faces are self-hosted via `next/font/local`; no font CDN is called at runtime. Their OFL texts, provenance and brand/code-license boundary are recorded alongside the assets and in THIRD_PARTY_NOTICES.

## Local verification

Commands use Node 24.22.2 and the repository-pinned pnpm 12.16.1 through Corepack. Frozen offline dependency installation succeeded. PostgreSQL 18.6 and the existing native disposable-stack harness were used; no Docker daemon was required.

| Check | Actual result |
| --- | --- |
| `pnpm lint` | Exit 0; four existing unused-variable warnings in category/model modules |
| `pnpm typecheck` | Pass |
| `pnpm --filter web exec vitest run --maxWorkers=2` | 66 files / 682 tests passed; 141.52 seconds |
| `pnpm build` | Final production build passed after the contrast fix; public, auth and workspace routes generated |
| `pnpm check:contrast` | 28 role pairs passed, including secondary text on both colored notes |
| `pnpm check:contracts` | OpenAPI and generated TypeScript are current |
| `pnpm check:client-secrets` | Exit 0, explicitly reports no root `.env` configured / nothing to scan; this is not a scan of production credentials |
| Desktop browser journeys | Full suite: 25 passed / one existing intentional skip in 3.2m; Chromium desktop, one worker, no retries |
| Documentation links / whitespace | Passed; final link count recorded in the task card; `git diff --check` clean |

The full unit suite passed before the final CSS-only secondary-color correction. That correction is covered by the final contrast check, production rebuild and browser scans. The final test-helper edits are covered by strict TypeScript, lint and the final desktop journeys. The subsequent editor-only spacing correction is covered by a fresh production build, focused ESLint and the complete desktop suite.

### Browser → API → database → export

The intended story is an English-speaking researcher opening the evidence, selecting a chart, adding it to a private research document, writing a hypothesis and evidence notes, saving/reopening the work, and exporting the acknowledged revision.

The automated desktop checks run at 1440×900 against the production Next.js build, real FastAPI gateway, disposable PostgreSQL with real migrations/RLS and the real export worker. Only the identity-provider transport is synthetic; signing, verification, ownership and session flows execute normally. The automated dataset and author text are explicitly synthetic fixtures, staged through the real pipeline.

| Boundary | Evidence |
| --- | --- |
| UI → API | Public trace, sign-in continuation and chart selection passed on the production bundle |
| API → database | Exact persisted decimal strings/dataset IDs and saved revision/context hash verified by the harness inspection endpoints |
| Mutation → reopened document | Prose, hypothesis, pinned insight and contradicting evidence survived reload; integrity findings cleared on the saved revision |
| Source outage → response | Latest lookup failed explicitly; pinned values remained available and prose continued saving |
| Export → artifact | Real worker returned a downloadable ZIP; revision/version/content hash matched DB; every manifest member hash and size verified; chart CSV retained exact values; repeat download was byte-identical |
| User ownership | Bob could not open Alice’s private research/export; same-label demo visitors received separate subjects, logout/rotation checks passed |
| Accessibility | Zero serious/critical axe violations and no lower-impact findings across the scanned public/private surfaces, including the 200-block / 20-chart editor; keyboard, focus trapping and sidebar targets passed |

Manual Chrome inspection additionally confirmed the real rendered logo/TRACE, login → demo workspace, the document editor and the Intents explorer with the saved historical archive. The final workspace was visually inspected after the contrast rebuild. This manual pass is a desktop review, not a new VoiceOver/IME or mobile acceptance run.

### Issues found and corrected

1. Real axe found secondary text on lavender at 4.03:1. Darkened the shared secondary token to `#46594F`, producing 4.98:1 on lavender and 5.86:1 on yellow; added both pairs to the contrast gate. No axe rule was disabled.
2. The long research journey assumed one autosave per user step and failed when normal typing produced revision 4 before it observed revision 3. The test now captures each acknowledged saved revision, requires subsequent mutations to advance it, and compares the exact final revision and hash with both the database and exported manifest. Full typed prose, including outage-time prose, remains required in the downloaded bundle. Production autosave behavior was not changed.
3. Full GitHub CI found that the long-title performance fixture placed the paper at 397 px, violating its existing <386 px threshold. Reduced workbench gaps from 16 to 8 px; the unchanged D5 test now measures 381 px, with 519 px of paper visible. A new local full-suite run 25 passed, one skipped. The existing D4 skip predates this task and records NI-096 removal of the Save-chart action; no new skip or weakened threshold was added.
4. The layered button regression now expects the approved `action`/`on-action` roles instead of the superseded dark-accent fill. It still checks actual computed foreground/background colors.

## Review locally

The live review stack was left running at `http://127.0.0.1:51574/`; cabinet entry is `/login`. Use an arbitrary example email label and “Enter demo workspace”; the existing demo flow creates a separate private visitor. This local stack uses the existing saved archive import for historical charts and the original 90-day cohort; it also retains the clearly identified harness/performance fixtures. It is not a restored production database and does not claim a published real model where none is staged.

To recreate this native preview after stopping it, build first, then run from the checkout with the existing local archive root:

```sh
corepack pnpm install --offline --frozen-lockfile
uv sync --project apps/api --frozen --offline
corepack pnpm build
NI_RESEARCH_ARCHIVE_ROOT=/path/to/approved/local/research \
  uv run --project apps/api --frozen --offline python apps/web/e2e/harness/stack.py \
  --pg-bin /opt/homebrew/opt/postgresql@18/bin \
  --handoff .local/ni099-preview.json --keep
```

The handoff prints newly selected loopback ports. This command uses an existing authorized local archive; it does not fetch provider data. Automated fixture-only reproduction omits `NI_RESEARCH_ARCHIVE_ROOT` and runs:

```sh
corepack pnpm --filter web exec playwright test --config e2e/playwright.config.ts
```

## Screenshots

- [Overview](comic-lab-overview.png)
- [Workspace Home](comic-lab-workspace.png)
- [Chart detail](comic-lab-chart.png)
- [Editor, saved pinned context and integrity](comic-lab-editor.png)
- [Editor layout with a long title](comic-lab-editor-layout.jpg)
- [Sign in](comic-lab-login.png)

Screenshots come from the passing production-build desktop tests; financial values and author documents in them are synthetic fixtures. Raw archive inputs, database files, sessions, traces and local process state are excluded from Git.

## Boundaries

No backend/schema/provider change, new collection, mobile adaptation, merge or deployment. Existing unrelated active tasks remain assigned as before. Real Supabase credential entry, a remote environment, all production data/model completeness and a new PDF-layout acceptance run are outside this desktop identity task. The existing frozen export/render contracts were retained and the ZIP research workflow was actually exercised as recorded above.

Code/asset/test content digest (sorted changed `apps/web` paths and bytes, excluding generated files): 40bffa695d78458b309bc9473a70c6c9055c4725cebc1dfa9eae8f59bbec92b8.
