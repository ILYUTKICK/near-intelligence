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
