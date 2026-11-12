# NI-078 — Complete desktop research and chart presentation

Implemented 12 November 2026 by the ZCode A-role implementation subagent
(coordinator session `sess_9345ee4f-f534-4698-98d2-5809986ac4c3`), branch
`feat/ni-078-presentation`, worktree `/Users/ilyutkinn/Desktop/near-intelligence-a31`,
base `docs/ni-077-handoff-v2` (2787fd5). Claim recorded in `docs/TASKS.md`
before implementation; NI-064 stayed with its own owner (no claim taken over;
see "Coordination" below).

## Scope

The NI-075 desktop design is preserved: no token, typography, palette or
layout-system change. This task resolves the five NI-076 presentation
findings (D1–D5, all P2) and verifies the custom-range control end to end.

## Result summary

| Finding | Disposition | Evidence |
| --- | --- | --- |
| D1 — Research text-heavy | Resolved — compact H1–H4 assessment beside the opening evidence; all 15 sections intact | `screens/research-opening-after-1440.jpg`; measured below |
| D2 — Two explanatory figures absent | Resolved — CL-004 USD-window figure and CL-007 supply-scale figure render from the claim registry | `screens/research-figures-usd-after-1440.jpg`, `screens/research-figures-supply-after-1440.jpg` |
| D3 — Chart begins too low | Resolved — one title, compact metadata, one action/selection row; plot at y662 (was ~y703 at a taller viewport) | `screens/chart-loaded-after-1440x900.jpg`, `screens/chart-loaded-after-1280x800.jpg` |
| D4 — Saved card is a full detail view | Resolved — one title, one context line, lazy bounded previews for every card, exact values behind a disclosure | `screens/saved-charts-after-1440.jpg` |
| D5 — Editor chrome compresses the paper | Resolved — duplicate breadcrumb removed, one compact header, paper at y351 / text at y408 (was 386/442) | `screens/editor-after-1440.jpg` |
| Custom range | **Verified end to end — no defect found**; NI-076's failed automation is explained by input-event handling, see below | `apps/web/e2e/ni-078-custom-range.spec.ts` (passes) |

## Measured before/after

Before numbers are from the NI-076 review (`docs/verification/ni-076/README.md`,
screens at `/Users/ilyutkinn/Desktop/Near/output/ni-076-review/screens/`, PR #87
head 0b80bf2, 1440×1000 viewport). After numbers are measured by
`apps/web/e2e/ni-078-evidence.spec.ts` against the real harness stack (same
method: document-coordinate y of the element, page scrolled to top), recorded in
`screens/measurements.json`.

- **D1**: before ~5,017 words / 19,733 px height / 1 figure; after 5,476 words /
  21,414 px / **3 figures** — the additions are the compact assessment and the
  two recorded-evidence figures; the compact H1–H4 assessment begins at
  **y=882** (1440×900), i.e. inside the first viewport right after the opening
  figure and evidence basis. All fifteen thesis sections, definitions,
  limitations and anchors remain (asserted by `tests/ui/thesis.test.tsx`).
- **D3**: the plot's top edge is at **y=662 at 1440×900 and y=662 at 1280×800**
  (before: ~y703 at 1440×1000, i.e. below the 800px fold). The plot now shows
  ~240 px at 1440×900 and ~140 px at 1280×800 on first paint — a meaningful
  part of the chart is inside the first viewport at both documented sizes.
- **D4**: the first card's plot starts at **y=593** and a full card is
  **717 px** tall (before: plot ~y669 plus an always-open exact table per
  card). Every card renders the same bounded preview; exact values are one
  disclosure away.
- **D5**: the paper panel starts at **y=351** and the first editable text at
  **y=408** (before: 386/442), with exactly **1** breadcrumb trail (workspace
  header; the page-level duplicate is removed — before: 2).

## Custom range — verified end to end, no defect confirmed

`apps/web/e2e/ni-078-custom-range.spec.ts` reproduces the NI-076 scenario on
the real stack (production Next.js + real FastAPI + disposable PostgreSQL) and
passes: open the actual dialog → fill the native date inputs (2026-01-03 →
2026-01-15) → click **Apply range** →

1. the replace-state URL resolves to `start=2026-01-03&end=2026-01-15`;
2. the fetched view re-resolves the requested window (exact table shows the
   requested window's persisted value);
3. a **reload preserves** the selection (the URL is the persistence);
4. the sign-in continuation carries `start=2026-01-03`;
5. saving through the real UI and reopening the saved chart preserves the
   custom window, and the compact Saved Charts card shows
   `2026-01-03 – 2026-01-15 (UTC, end exclusive)`.

Disposition: no product defect was reproduced, so nothing was "fixed".
Code reading and the passing reproduction point to the NI-076 observation
being an automation artifact: the date values only reach React state through
the inputs' `change` events, and an automation that sets input values (or
types partial dates) without a completed change event leaves the draft state
empty, so Apply legitimately re-applies the current selection. Human/Playwright
`fill()` input (proper events) works, and validation rejects unsupported
ranges with an inline reason instead of clamping (covered by
`tests/ui/chart-library.test.tsx`).

## Implementation notes

- **D1** — `app/(public)/research/page.tsx` gains a server-rendered
  "Hypothesis assessment at a glance" block (real `#h1`–`#h4` anchor links,
  statuses restated verbatim from `thesis.question.hypotheses`); no API
  dependency, no client JS.
- **D2** — `features/public-research/ResearchFigures.tsx` renders both figures
  consuming ONLY the typed `ClaimQuantity` objects of `content.ts` (values,
  scopes, bases and percentages are read from the registry objects; a unit
  mismatch fails loudly). One measurement unit per figure (USD figure / NEAR
  figure), zero-based bars, estimates labeled ("Estimate — valuation, not
  execution", "≈" plus sr-only "approximately"), purchases never subtracted
  from supply (recorded caution visible), no daily interpolation, no
  ChartView/dataset identifiers invented. `RecordedPurchases` now shares the
  same scope→period helper.
- **D3** — `ChartFrame`/`ChartView` accept `compact` (the frame does not
  repeat the page's h1); `ChartDetailClient` moves filters, custom range,
  refresh and the private-action continuations into the frame toolbar (one
  wrapped action/selection row); the long description stays available through
  "Sources & definitions" and the definitions panel. The exact-value table
  stays visible without hover on the detail page (the
  `chart-data-table.spec.ts` contract).
- **D4** — `SavedCharts` cards: one title, one context line (period + filters),
  mode badge; previews render for **every** card through the shared renderer
  (controlled `view`, no re-resolve) and fetch lazily per card via
  IntersectionObserver, honouring the session signal; exact values live behind
  the "Exact values and summary" disclosure (`discloseExactValues`). Rename,
  remove, search, pagination, snapshot badge unchanged.
- **D5** — the document page no longer renders a second breadcrumb row; the
  editor header carries title, revision/schema line, the truthful save state,
  revision-history/export and all pane toggles in one row; the operations row
  keeps document-level actions only; the embedded chart block shares one
  compact status row (mode, save state, observed-dataset id, newer-data
  notice) with the pin language still visible, and full technical identifiers
  moved under the Properties pane. Block actions keep their own stable row so
  keyboard focus never drops when the chart view resolves. Autosave, Mod+S,
  dialog return focus, outline/evidence panels and recovery views unchanged
  (NI-039/040/042/050 suites pass).

## Tests and checks (all passing on the committed head)

- Web unit/interaction suites: **551 tests** (`pnpm --filter web test`),
  including the extended/added `tests/ui/thesis.test.tsx` (compact-assessment
  block), `tests/ui/research-figures.test.tsx` (new: registry-exact values,
  estimate labels, single unit per figure, page placement, axe),
  `tests/ui/chart-library.test.tsx` (new D3 describe: one title, compact
  metadata, controls inside the frame toolbar, exact values visible),
  `tests/ui/renderer/chart-view.test.tsx` (new compact/disclosure describe),
  `tests/ui/saved-charts.test.tsx` (new card describe), editor suites
  (`live-chart`, `editor-workbench` D5 describes, NI-050 assertion updated to
  the compact pin wording). One transient parallel-load flake set
  (public-routes/axe) was rerun serially and passed; noted here for honesty.
- Lint (`pnpm lint`), strict TypeScript (`pnpm typecheck`), production build
  (`pnpm --filter web build`), `pnpm check:contracts` (OpenAPI/TS current),
  `pnpm check:doc-links` (807 links resolve), `pnpm check:contrast` (all 22
  pairs) — all pass.
- Real-stack E2E (`pnpm --filter web test:e2e`, disposable loopback
  PostgreSQL 18 + real FastAPI + production `next start` + export worker; only
  the provider JWKS transport is synthetic): **22 passed (3.1m)**, including
  the full NI-063 journey with save/reopen/outage/export, the two-user denial
  test, the NI-064 axe surfaces (editor with the 200-block synthetic document)
  and keyboard navigation suites, and the two new NI-078 specs above.
- Two-user/pin/export checks: covered by the passing journey (save → reopen →
  outage → acknowledged-revision export) and the second-user denial test;
  presentation-only changes, no data/auth/version/export behavior change.

## Screenshots

After captures in `docs/verification/ni-078/screens/` (JPEG, ≤150 KB each):
`research-opening-after-1440.jpg`, `research-figures-usd-after-1440.jpg`,
`research-figures-supply-after-1440.jpg`, `chart-loaded-after-1440x900.jpg`,
`chart-loaded-after-1280x800.jpg`, `saved-charts-after-1440.jpg`,
`editor-after-1440.jpg`, plus `measurements.json`. Before captures: the NI-076
review set at `/Users/ilyutkinn/Desktop/Near/output/ni-076-review/screens/`
(research.jpg, chart-loaded.jpg, saved-charts.jpg, editor.jpg).

## Remaining limitations

- No mobile pass (out of scope per the task card and the 8 November 2026
  desktop-only override).
- The saved-card exact-value disclosure keeps values accessible but closed by
  default; the detail page remains the hover-free surface for full tables.
- The editor "Add Insight" gating text moved one row earlier in the embedded
  chart block (presentation only); its `aria-describedby` wiring is unchanged.
- Remote-only checks (real Supabase login, deployment) remain with NI-079.

## Coordination

NI-064 remains IN_PROGRESS with its own owner; this task changed only
presentation code and adjusted two NI-063/NI-064-era e2e steps where the
commissioned layout change altered deterministic locators (the undo refocus
now targets a prose paragraph instead of the editor's center point, and the
pin-language text matches the compact wording). No NI-064 claim, fixture or
performance spec was modified beyond that step.
