# NI-076 — PR #87 desktop design review

Reviewed 11 November 2026 by Codex /root, with bounded read-only source comparison by /root/design_pr_audit.

## Result

PR #87 is running locally at **http://127.0.0.1:64932/** from exact head `0b80bf2fb0bbe884976123a4baf7a10576b61b87`. GitHub reports the owner already merged it as `1176f4a`; this review used the PR head in an isolated managed worktree. Existing authoring changes, the older localhost:13000 preview and atlas server were preserved.

The palette, serif/italic typography, original illustration, navigation and account layouts are close to NI-074. The main remaining gap is information hierarchy: Research is still mostly prose, and the complete chart renderer is too verbose when used inside saved cards and the editor. These are design/usability findings, not a claim that the product is ready for production.

## Local verification

- Cached frozen dependencies installed: `pnpm install --frozen-lockfile --offline`; `uv sync --project apps/api --frozen --offline`.
- `pnpm --filter web build` passed, including strict TypeScript verification. `pnpm --filter web check:contrast` passed all 22 pairs. `git diff --check` passed.
- Existing `apps/web/e2e/harness/stack.py` runs production Next.js, real FastAPI, disposable PostgreSQL 18 and the export worker. Only provider authentication transport is synthetic. No collectors, paid providers or cloud deployment were run.
- Actual desktop browser review at 1440 × 1000: Overview, Research, Data, Intents category, loaded chart, source dialog, Methodology, Models, Login, workspace Home, My Research, Saved Charts, editor, Profile and Settings.
- Saved a chart through the real UI/API/DB and reopened its preserved January selection. Sources dialog opened and closed. Editor reconstructed its pinned synthetic chart. Empty/unavailable states were inspected and are not treated as design failures merely for lacking data.
- The review stack contains explicitly synthetic NI-063/NI-064 QA datasets and a synthetic 200-block document. They are not fresh NEAR research. Original public claims remain historical Aug–Nov 2026 observations.
- Custom-range inputs accepted visible dates, but automated Apply returned to the old selection twice. This review does **not** certify that control; loaded-chart review used an explicit supported selection URL. Cause was not isolated, so this is a verification limitation requiring a focused manual check, not a confirmed new regression.
- No full unit/E2E rerun, keyboard accessibility certification, real Supabase login, two-user security audit or mobile pass is claimed here. NI-075 author checks remain separate evidence.

## Findings

Paths below are relative to `apps/web/src/` in the reviewed checkout. Screenshots are actual running-app captures under the local output directory linked below. All five findings are P2 presentation/usability issues.

| Before | After | Why |
| --- | --- | --- |
| **D1 — Research remains text-heavy.** DOM inspection found approximately 5,017 words, 19,733 CSS pixels of document height and one figure at 1440px width. Detailed H1–H4 cards are vertically stacked. Source: `app/(public)/research/page.tsx:110`, `:117`, `:341`. Evidence: `research.jpg`. | Add a compact assessment of H1–H4 near the opening evidence; keep all 15 original sections accessible below with a clear transition. | The original complaint about continuous prose is only resolved in the opening block. Preserve the full thesis while giving readers an overview. |
| **D2 — Two explanatory figures from the atlas are absent.** Only CL-002 purchases are charted; the USD estimate and purchases-versus-supply comparison remain prose/claim tables. Source: `app/(public)/research/page.tsx:83`, `:205`, `:221`; `features/public-research/RecordedPurchases.tsx:17`. | Add figures for the three USD windows (CL-004) and the scale of purchases versus positive net supply change (CL-007), referencing the recorded claims and exact definitions. | These explain why token quantity decline is not the same as USD demand decline, and why purchases do not cancel issuance. Keep estimates labeled and do not subtract purchases from supply. |
| **D3 — The chart begins too low.** Public detail repeats the long title, description, renderer/version, auth controls and frame metadata before the plot. At this viewport the custom-range plot begins around document y703. Source: `features/charts/library/detail-screen.tsx:191`; `features/charts/library/ChartDetailClient.tsx:163`; `features/charts/ChartFrame.tsx:69`. Evidence: `chart-loaded.jpg`. | Use one title, a compact action/selection row and shorter visible metadata; keep full provenance available in Sources. | A chart page should show a useful part of its chart immediately, including on an 800px-high desktop. |
| **D4 — Saved Charts uses a full detail view inside its card.** Title, period and mode repeat; the plot starts around y669 and an always-open exact table follows. Source: `features/charts/saved/SavedCharts.tsx:32`, `:68`, `:120`; `features/charts/renderer/ChartView.tsx:346`. Evidence: `saved-charts.jpg`. | Add a compact context to the shared renderer: one title, concise period, plot and source action; make exact data available through an accessible disclosure or detail. Use bounded/lazy previews consistently rather than only the first two entries. | Saved Charts should work as a comparable visual library. Preserve exact data access without making each card a long form. |
| **D5 — Editor chrome compresses the research paper.** Duplicate breadcrumbs, title/save and multiple operation rows place the paper surface near y386 and editable text at y442. Embedded chart adds a raw dataset UUID and more controls before the frame. Source: `features/editor/editor-shell.tsx:705`, `:772`, `:842`; `features/editor/blocks/live-chart.tsx:204`, `:212`, `:230`. Evidence: `editor.jpg`. | Consolidate persistent actions in a compact header; make block operations contextual; put technical identifiers under Properties. Keep visible pin/save state and explicit refresh. | The atlas allocated substantially more of the first screen to reading and writing. Fixture paragraph lengths are not counted as a product defect. |

Recommended order for the next design implementation task: D1/D2 research composition; shared chart presentation D3/D4; editor layout D5. These are proposed follow-up work, not implementation claims or a competing task registry.

## Evidence and preview

Screenshots: `/Users/ilyutkinn/Desktop/Near/output/ni-076-review/screens/`.

- `overview.jpg`, `research.jpg`, `data.jpg`
- `chart-initial.jpg`, `chart-loaded.jpg`, `chart-sources.jpg`
- `home.jpg`, `my-research.jpg`, `saved-charts.jpg`, `editor.jpg`
- `profile.jpg`, `settings.jpg`, `methodology.jpg`, `models.jpg`, `login.jpg`

NI-074 reference: `/Users/ilyutkinn/Desktop/Near/design/ni-074` and `/Users/ilyutkinn/Desktop/Near/output/ni-074/screens/`.

Public preview: http://127.0.0.1:64932/ . Synthetic workspace entry: http://127.0.0.1:64931/_ni063/session/alice?next=%2Fworkspace . This loopback-only helper belongs to the local QA harness and is not production authentication. Preview remains running for owner review; no cloud deployment or application code changes were made.
