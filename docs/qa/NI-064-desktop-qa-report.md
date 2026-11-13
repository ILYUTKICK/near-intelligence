# NI-064 — desktop accessibility and performance QA report

Task: [NI-064](../TASKS.md) (Epic 13 — Quality and Security, P0). Desktop-only
scope per the 8 November 2026 user override: **no mobile viewport/device/touch
passes were run or authorized**. Every check below ran against the REAL stack
( disposable loopback PostgreSQL 18 + the real FastAPI gateway with the
synthetic-ES256 provider transport + the production `next start` bundle + the
real NI-058 export worker) booted by the [NI-063 harness](../../apps/web/e2e/harness/stack.py) —
the primary API is never mocked. All fixtures are visibly synthetic.

## Documented test environment

- Machine: operator workstation, macOS ARM64 (Apple Silicon), Docker-free
  native run; Chromium (Playwright build v1254, `@playwright/test` 1.65.0),
  viewport **1440×900** (the documented desktop baseline), single serial worker.
- Stack: production `next build` + `next start`, real FastAPI gateway,
  disposable PostgreSQL 18.6, one approved synthetic dataset (14 daily rows)
  and the NI-064 performance fixtures (366-day synthetic dataset; one
  200-block / 20-chart-reference document created through the real principal
  bootstrap and document service).
- Date of the recorded runs: 10–11 November 2026. Performance numbers are
  local-run measurements on the machine above; per [TESTING_STRATEGY](../TESTING_STRATEGY.md)
  budgets are validated on documented conditions, not inferred from shared
  CI runners, so the perf suite is deliberately **local-only** (its
  `*.perf.ts` pattern does not match the shared e2e config).

## 1. axe scans — zero serious/critical gate

Suite: `apps/web/e2e/accessibility/axe-core-surfaces.spec.ts`
(`@axe-core/playwright` 4.14.0, axe-core 4.14.0 — added per [DEPENDENCIES.md](../DEPENDENCIES.md)).

Scanned surfaces (each asserts ZERO serious/critical violations):

| Surface | Result |
| --- | --- |
| Landing `/` | PASS |
| Thesis `/research` | PASS |
| Methodology `/methodology` | PASS |
| Data explorer `/data` | PASS (after the fix in §4.4) |
| Chart detail with resolved data | PASS |
| Models `/models` | PASS |
| Login `/login` | PASS |
| Workspace home / My Research / Saved Charts | PASS |
| Research editor with the 200-block / 20-chart synthetic document | PASS |

Lower-impact findings: none recorded by the runs above (axe reported no
moderate/minor violations on these surfaces beyond the fixed serious one).
One **serious** violation was found and fixed in-boundary (§4.4).

## 2. Keyboard journeys (real focus assertions)

Suite: `apps/web/e2e/accessibility/keyboard-navigation.spec.ts`. All steps
assert actual focus targets (`toBeFocused`), not just the absence of
violations. Desktop 1440×900, keyboard-only interactions.

- Skip link is the first Tab stop with the token focus ring actually drawn
  (`outline-width: 2px` under real keyboard focus).
- The workbench toolbar is reachable backwards from the paper (Shift+Tab walk
  through the outline pane to the Insert block trigger; the walk records its
  full focus path on failure).
- Insert menu: keyboard open, ArrowDown navigation to an item, Enter insert,
  live-region announcement ("Block inserted…"); inserted divider undone.
- Slash menu: "/" in the canonical empty document opens the positioned menu
  (after the §4.2 fix), ArrowDown + Enter inserts and announces, Escape closes
  with focus kept in the editor. **Playwright note (recorded honestly):**
  Playwright's synthetic `keyboard.type` events bypass Chromium's editing
  pipeline on this build (no `beforeinput`/`input` events at all), so the e2e
  drives the trigger through `keyboard.insertText`, which produces the same
  `beforeinput` pipeline a physical keystroke does.
- Keyboard block reorder (Mod-Alt-ArrowUp/Down, the keyboard alternative to
  drag): the focused block moves, document order flips and restores, and the
  polite live region announces the move (after the §4.3 fix).
- Chart source drawer: the pinned-context `<details>` toggles from the
  keyboard (context hash visible), Escape inside the chart node returns
  selection to the editor (NI-042 contract), and the chart's source dialog
  opens from the keyboard and returns focus to its trigger on Escape.
- Dialog traps: the Add-hypothesis dialog and the Export dialog keep focus
  inside across repeated Tab presses and return focus to their triggers on
  Escape. (The evidence-link dialog is reachable only from a hypothesis card;
  it is exercised by the NI-063 journey, which also covers the evidence
  panel's keyboard entry navigation and focus return — recorded, not
  re-implemented here.)

## 3. Chart data without hover

Suite: `apps/web/e2e/accessibility/chart-data-table.spec.ts` (NI-033 contract
at the documented desktop viewport):

- The exact-values table renders every covered day with the original decimal
  strings (no rounding, no zero-fill); the region is a labeled, keyboard-
  focusable scroll region (`tabindex=0`) and takes focus without a pointer.
- Range presets operate from the keyboard (focus + Enter, `aria-pressed`,
  URL round-trip anchored to the pinned selection end), and the table follows
  with exactly the covered window's rows; units survive the change.
- The manual "Accessible summary" details expands from the keyboard.
- The editor's chart node embeds the same hover-free exact table for its
  pinned dataset and its table region is keyboard reachable.

## 4. In-boundary fixes recorded (found by this QA)

1. **Slash menu never opened in a real browser (P0 editor blocker).**
   `prosemirror-view`'s DOM-diff input path only invokes `handleTextInput`
   when the edited parent already contains a text child, and its keypress
   path does not cover normal caret typing — so typing "/" into an empty
   paragraph (the canonical EDITOR_SPECIFICATION trigger) never reached the
   plugin. The canonical empty document additionally has NO top-level blocks
   in editor state (`content: []`), so no empty paragraph even exists to
   resolve into. Fix (`slash-menu.ts`): the plugin now listens for the
   `beforeinput` DOM event (cross-browser text-insertion signal) with the
   same trigger conditions plus the empty-document case, keeping the
   `handleTextInput` path; `insertBlock` now replaces the single "/" trigger
   paragraph so the slash never stays behind. Regression tests:
   `tests/editor/slash-menu.test.ts` (jsdom drives the beforeinput handler on
   a real editor; the real typing path is the e2e keyboard suite).
2. **Keyboard block operations were silent for screen readers.** The
   Mod-Alt-Arrow move, Mod-Shift-d duplicate and Mod-Shift-Backspace delete
   shortcuts ran inside ProseMirror without any live-region announcement
   (only the toolbar buttons announced). Fix: an `editor-operation-announce`
   bridge event (`ui-bridge.ts`) carries the same copy the toolbar paths
   announce to the shell's polite live region (`commands.ts`,
   `editor-shell.tsx`).
3. **Export dialog did not return focus on Escape.** It is opened from a
   plain controlled button (not a Radix `DialogTrigger`), so Radix had no
   opener to restore. Fix: the workbench passes a return-focus ref and the
   dialog's `onCloseAutoFocus` focuses the Export button.
4. **`/data` category cards failed axe `label-content-name-mismatch`**
   (serious, 5 nodes): the accessible name "Open data category: …" did not
   contain the visible text "Open category". Fix: `aria-label="Open category:
   {label}"` (visible text is now part of the name; test updated).
5. **Editor chart value fixtures:** the perf fixture's first-day value is
   asserted against the performance dataset's own day map (the significant-
   digit formatter trims trailing zeros; the exactness contract itself stays
   with the NI-033 unit tests incl. the 31-digit case).

## 5. Recorded NI-024 regressions — disposition

All three recorded regressions were reproduced from source, fixed in-boundary
and closed with regression tests (first commit of this task):

1. **Sidebar alias prefetch 404s** — the workspace registry pointed the Data
   Explorer and Analytics entries at the never-implemented `/workspace/data/*`
   and `/workspace/models` aliases. Fixed in `lib/navigation.ts` (entries now
   target the implemented public routes `/data/*` and `/models`; exactly one
   explorer/catalog implementation exists) and reconciled in
   [INFORMATION_ARCHITECTURE.md](../INFORMATION_ARCHITECTURE.md). Tests:
   unit (no alias hrefs; exact implemented targets) and e2e (every sidebar
   link resolves < 400 on the production server, which is exactly what Next
   prefetches).
2. **`Button asChild` Children.only crash** — the slot path rendered
   `{pending ? spinner : null}` next to the child, so Radix Slot always
   received multiple children and crashed. Fixed (`button.tsx`): the slot
   path renders exactly one child and announces pending via `aria-busy` on
   the anchor. Tests: real slotted next/link renders with button styling;
   pending + asChild stays renderable with no injected spinner sibling.
3. **Global unlayered anchor color** — the unlayered `a { color }` rule in
   `tokens.css` overrode every layered utility (cascade layers lose to
   unlayered CSS regardless of specificity), which had forced an inline-style
   workaround on the workspace Continue link. Fixed: the anchor rule moved
   into the Tailwind v4 `base` cascade layer, the workaround was removed, and
   the e2e asserts the Continue link's computed foreground is the layered
   `text-on-accent` (and its background the accent token).

## 6. Performance vs PRD budgets

Suite: `apps/web/e2e/performance/document-performance.perf.ts` (local-only
config; measurements from the documented environment above, synthetic 200-block
/ 20-chart-ref document and 366-day dataset on the real stack).

| PRD budget (PRODUCT_REQUIREMENTS.md) | Measured | Verdict |
| --- | --- | --- |
| Public LCP ≤ 2.5 s (warm service) | **~0.1–0.2 s** (run-to-run 108–212 ms) | PASS |
| Document load ≤ 2 s for 200 blocks / 20 chart refs (warm service) | **~0.9–1.2 s** (923–1223 ms navigation → last block visible + editor interactive) | PASS |
| Chart series p95 ≤ 800 ms for 366 daily points at 10 concurrent clients | **p95 of the whole 10-request batch ≈ 0.15 s** (102–153 ms across 5 rounds; 366 real daily points per response) | PASS (recorded comparison: the PRD's p95 is per request; a full 10-request batch completing under the budget is the strictly harder condition. Local loopback, no network latency; staging-grade networking is a deployment concern) |
| Lazy mounting of 20 chart references (ARCHITECTURE limit) | **0 of 20 mounted near the document top; chart 16 of 20 mounts on scroll** | PASS (the IntersectionObserver deferral scales; dispose-on-unmount stays covered by the NI-033 unit tests) |
| No page overflow (acceptance criterion) | horizontal overflow **0 px** on landing, `/data`, and the 200-block editor at 1440×900 | PASS |

Additional recorded observations (no PRD budget; recorded for the record):

- Autosave round trip on the 200-block document (typing a sentence + the 1 s
  idle scheduler + POST + acknowledged new revision): **~2.5–3.1 s** wall
  clock, dominated by the deliberate 1 s idle scheduler and the editor
  serialization of 200 blocks; content confirmed acknowledged and restored
  byte-identically afterwards.
- Long tasks during editor load: 2 tasks totalling ~146 ms; during a full
  down-and-up scroll of the 200-block document: 3 tasks totalling ~239 ms
  (all under the 50 ms "long" threshold by only a small margin — no jank
  observed; nothing asserted against a budget because the PRD defines none).
- Cumulative layout shift during editor load and scroll: **0** (nothing
  shifts under the user).

Honest limits of the perf numbers: single machine, loopback networking, warm
service, one synthetic document/dataset; the "10 concurrent clients" are
concurrent requests from one test process, not ten distinct machines. The
budgets pass with an order of magnitude of headroom, so the recorded
conclusion — the PRD budgets hold at the documented limits (200 blocks, 20
refs, 366 points) with no revision needed — does not depend on these caveats.

## 7. Screen-reader review: automated approximation and operator remainder

Real screen-reader interaction (VoiceOver on macOS) is operator-manual by
environment. The automated approximation covers: ARIA roles/names/landmarks
(axe's `aria-usage` rule family), focus order and targets, live-region
announcements (asserted textually), dialog/`details` semantics, and the
labeled exact-value table alternative. **Recorded as still operator-side:**
(1) actual VoiceOver announcement quality/rhythm on the editor live region;
(2) real IME composition behavior in the editor (jsdom and Playwright
keyboard events cannot emulate CJK composition — recorded in the NI-038/039/040
cards as well); (3) physical-keyboard checking of the slash trigger
(the e2e covers the same production `beforeinput` pipeline through
`keyboard.insertText`).

## 8. Verdict

No core-flow accessibility blocker remains open: the one axe serious
violation and the three product bugs found by the desktop QA (slash trigger,
silent keyboard operations, export focus return) are fixed with regression
tests. Chart data is accessible without hover on public and editor surfaces.
All measured PRD budgets pass at the documented limits with no revision
needed. No mobile viewport/device/touch pass was performed or is claimed.


## 9. Completion verification — 13 November 2026

The owner reassigned completion to Codex `/root`. The current registry stays
**IN_PROGRESS** until the remaining actual human input/screen-reader checks
are recorded; neither a green axe run nor launching VoiceOver substitutes
for those results. Earlier sections are historical 10–11 November evidence.

### Source and environment

- Source baseline: main `1e276937e7b8f6572a0d141ea247c04ad7dfe4b7` (PR #97 merged).
- Production build: `QAEASxflg2LGXP7w_kyFU`, with the bounded corrections below.
- Runtime/test diff SHA-256 (excludes this documentation): `a794739541666deea8996f628355e1a6f8a57ea14b5610f88c139e131e3d5412`.
- Apple M2, 8 cores, 8 GiB RAM, macOS 26.6.2 (25G83), Node 24.22.2,
  pnpm 12.16.1, Python 3.13.5, PostgreSQL 18.6, Playwright 1.65.0.
- Explicit PATH prefix `/opt/homebrew/opt/node@24/bin` is required on this host:
  new login shells selected Node 22.22.3. That preliminary automatic run was
  interrupted and excluded from acceptance. The final runs pin Node 24.
- Desktop 1440×900, warm local production service, real FastAPI/PostgreSQL/
  worker with labeled synthetic auth transport/data. No provider calls,
  stopped collectors, deployment or mobile tests.

### Confirmed defects and corrections

1. Native Chrome first `/` in the canonical childless `content:[]` document
   inserted text without opening the menu. Backspace then `/` in the resulting
   empty paragraph worked. The old browser test's `keyboard.insertText` did
   not cover that native key route. A narrow initial-key handler now inserts
   one paragraph/slash through a normal undoable ProseMirror transaction and
   opens the menu. It accepts Shift-produced `/` on other layouts, preserves
   existing paragraph input, and excludes Ctrl/Alt/Meta, composing/keyCode229,
   and read-only editors. The real-stack regression asserts saved `content:[]`
   before `keyboard.press('/')`; native Chrome was also rechecked afterwards.
2. Twenty repeated editor charts produced one moderate `landmark-unique`
   finding: their exact-data regions shared the same name. Tables retain
   their region role, keyboard focus, exact-value caption and chart-title
   prefix; editor instances add a human `research block N` context, updated
   on insert/move. Historical chart regions use the same context. Regression
   tests verify repeated instances and movement; the 200-block browser axe
   scan now explicitly rejects `landmark-unique` as well.
3. The local LCP test now waits for settled network/paint before reading the
   latest buffered LCP candidate; the measured value remains its original
   `startTime`. Budgets are unchanged. Lower-impact axe logs include exact
   targets/help instead of only a count.

### Current results

| Check | Result |
| --- | --- |
| Accessibility + complete research journey | 18/18 pass on the final build; all public/private/editor scans have zero serious/critical and zero lower-impact findings |
| Initial slash unit regressions | 17/17 pass, including history/IDs/composition/modifier/read-only guards |
| Repeated table / historical / actual insert-and-move regressions | 40/40 pass |
| Performance | 6/6 pass; final measurements below |
| Final serial web unit/interaction run | 63 files / 666 tests pass; 20/20 save/conflict tests also passed in the isolated diagnostic run |
| Final lint/strict TS/build/contracts/contrast/doc links | Pass; 22 contrast pairs and 863 relative links |
| Native Chrome initial key | PASS: a newly created empty document opens slash menu on the first native OS slash event; choosing Paragraph removes the slash, prose saves as revision 3 |
| VoiceOver | Started through the actual macOS first-run dialog; output observation repeatedly timed out and no audio channel is available to this agent. Actual spoken-output review remains pending; no audible announcement-quality pass is claimed |
| System IME | Only ABC/Russian installed. Owner chose to perform the real IME test manually; no input method was added. Awaiting composition/commit/cancel/save/reopen result |

VoiceOver was returned to its original OFF state. Input-source configuration
remains ABC/Russian; the add-source dialog was canceled without adding one.
The final disposable native stack remains available for the owner's pending
manual check. Its temporary port/document identifiers stay local, not research
artifacts or production data.

| Final production-mode performance check | Measured | Budget/verdict |
| --- | --- | --- |
| Settled warm landing LCP | 144 ms | ≤2500 ms — PASS |
| Editor load, 200 blocks / 20 chart refs | 693 ms | ≤2000 ms — PASS |
| Lazy mounting | 0/20 near top; chart 16 mounts on scroll | PASS |
| Autosave, including typing + 1s idle + POST + acknowledgement | 1916 ms | Observational; save/restore verified |
| 366 points / ten concurrent requests, five rounds | 107, 99, 65, 85, 209 ms; batch p95 209 ms | ≤800 ms — PASS; local-batch caveat from §6 applies |
| Load long tasks / CLS | 1 task, 56 ms / 0.016 | Recorded observations |
| Full scroll long tasks / CLS / horizontal overflow | 1 task, 76 ms / 0.017 / 0 px | Overflow gate PASS |

Commands use the Node 24 PATH prefix above:

```sh
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm build
corepack pnpm --filter web test --maxWorkers=1
corepack pnpm --filter web exec playwright test --config e2e/playwright.config.ts e2e/accessibility e2e/research-workflow.spec.ts
corepack pnpm --filter web exec playwright test --config e2e/performance/playwright.perf.config.ts
corepack pnpm check:contracts
corepack pnpm check:contrast
```

The first full unit process overlapped a source edit and loaded the old Shift
handler with the new test; that failure was discarded and the final focused
17-case run passes. A later full run overlapped real-stack axe tests and had
three 5s save/conflict timeouts (663/666 passed); the unchanged save/conflict
file passed 20/20 alone. The final serial all-file run passed 63 files / 666 tests. Published-head CI
is recorded on the pull request. No timeout was increased and no
assertion was weakened to hide a failure.

### Remaining manual checklist

The owner has a prepared synthetic document in native Chrome. Record the
actual input method/browser and observed result:

- Compose text with an actual system IME and select/commit a candidate; start
  and cancel another composition. No duplicates, lost prior text or unwanted
  slash menu. Wait for the acknowledged save, reload, and compare the text.
- With VoiceOver, review Insert block/Export names, dialog announcement,
  keyboard trap and Escape returning focus to Export. The agent's native AX
  observations and automated tests are supporting evidence, not an audible
  screen-reader review.

No NI-064 DONE or deployment readiness is claimed while these results are
missing. NI-079 still owns final integrated release/data/model/container
acceptance, and NI-067 rechecks actual staging-machine performance later.
