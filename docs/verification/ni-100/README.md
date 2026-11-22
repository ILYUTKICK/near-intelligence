# NI-100 — Unslop polish of Comic Lab

The owner requested Unslop after approving Comic Lab. This pass keeps the existing identity and applies polish to identified defects. Baseline: `6fd643c8b3407d207a80baaf71d6fec61c34c531`, with four passing CI jobs and the rendered [workspace](../ni-099/comic-lab-workspace.png) / [Overview](../ni-099/comic-lab-overview.png) evidence from NI-099.

Method: [Unslop by Damir Sokolovsky](https://heydamir.design/unslop), [@heydamir](https://x.com/heydamir), CC BY 4.0. The local installed skill, signs, tokens and visual references were read. This report credits the method; canonical NEAR Intelligence brand assets retain their existing separate license boundary.

## Direction

- **Product:** NEAR research where readers inspect sources and charts, then write an evidence-backed thesis.
- **Character:** Friendly, curious, precise.
- **World:** A research notebook with charts and source notes.
- **Moments:** Approved TRACE and the current research action; real data remains in its existing charts.
- **Signature:** Mint ink and the drawn Comic Lab outline, used selectively.

The direction comes from the already-approved identity and product. The current explicit request authorizes applying the polish; no replacement brand, new artwork or new feature is proposed.

## Audit

| Sign | Where it appears | Bounded correction |
| --- | --- | --- |
| Several equally bright surfaces compete | Home: mint Continue badge/buttons, solid yellow checklist, lavender notes and mint progress circles | Keep the main research card/TRACE as the visual focus; make supporting panels and progress states quieter |
| Multiple primary actions in the same workspace view | Home: Create document and Continue research both use primary treatment | Continue leads when a document exists; creation leads in the empty state |
| Vague app headline | Home: “Room for a clearer thesis.” | Name the research context and describe the actual next actions |
| Marketing-scale app titles | Shared PageIntro uses a 64px page scale or a 45.6px compact override | Bound workspace titles to the existing 36px/42px scale; keep display typography on public marketing views |
| A status styled like an action | Header: outlined Private workspace pill | Plain, legible status copy with the same meaning |
| A selected public link styled like another primary button | Public header: mint boxed active route | Quiet selected-route treatment with `aria-current` and focus preserved |
| Three adjacent hero actions | Overview: Read the research / Explore data / How it works | Keep two hero actions and preserve the workflow destination elsewhere in existing navigation |
| Several decorative emphasis conventions | Home: separate document icon, font glyph checklist circles, repeated badge/eyebrow emphasis | Use the existing line-icon language and only meaningful emphasis |
| Short strings end like paragraphs | Composed marketing headings/captions | Remove terminal punctuation from short owned UI strings; preserve actual sourced article text |

No glow/gradient text, fictitious testimonials, excessive motion or new feature claims were found in these surfaces. Existing motion is restrained press feedback; a loader may still communicate actual loading. No unsupported financial result or artificial number formatting is introduced.

## Retained decisions

This is the skill's light-polish mode. Rubik/Golos Text/IBM Plex Mono, approved TRACE/logo, mint/ivory/ink and purposeful Comic Lab outlines remain. Chosen Rubik display weight and the main card's drawn shadow are identity decisions, not generic defaults to erase. Current 44px control targets, visible focus, keyboard behavior and existing responsive code remain; no mobile work is included. Historical/synthetic data labels, exact decimal strings, scientific rendering and frozen exports take precedence over generic mock-data/chart advice.

## Pass record and verification

| Pass | Applied decision |
| --- | --- |
| 1. Spacing | Desktop workspace bar is 64px with the existing 44px controls. Checklist rows use 12px padding/gaps; redundant eyebrow space is removed |
| 2. Color | Home's supporting cards use existing white/neutral roles with no offset shadow. The main research card and selected action retain their brand emphasis. Public selected navigation is neutral |
| 3. Icons | Checklist check/circle states use the existing ProductIcon stroke system, alongside explicit Complete/To do labels. Removed the decorative document icon |
| 4. Copy | Research workspace names the context; descriptions name documents, charts and notes. Login uses Open your research workspace. Trimmed four owned section headings/captions; sourced research text is untouched |
| 5. Type | Workspace PageIntro is 36/42px on desktop; public display and editor paper scales/families remain. The selected Comic Lab display weight stays |
| 6. Layout | Feature/section order and proportions remain. Creation is secondary when a document can be continued; empty state keeps creation primary. Hero has two adjacent actions; How it works is retained in the existing footer |
| 7. Details | Privacy status is plain text. Supporting cards use neutral borders while the focal card retains its drawn frame; values, timestamps and scientific chart details are unchanged |
| 8. Visuals | Retained the exact approved TRACE and canonical logo. No visual was replaced or generated; no image prompt was written |
| 9. Motion | Existing restrained feedback, reduced-motion handling and purposeful loading states remain. No animation or dependency was added |

The focused 3-file UI run passed 25 tests; full web run (66 files / 682 tests) passed in 57.61s. Strict TypeScript, production build, contrast 28/28 and lint passed (four existing unused-variable warnings). Landing HTTP integration passed against real local API/PG, including publication/source bytes and API-outage behavior; its three owned heading expectations now match the punctuation polish. The client-secret command reports no root `.env` configured / nothing to scan, not a scan of production credentials.

Native Chrome confirmed login → demo workspace and the actual resulting action/panel hierarchy. The full desktop journey and final source/evidence record follow below. Existing baseline snapshots were reused; source was rendered once for the after-review, with no iterative restyling or new media.


## Final desktop acceptance

The full production-stack suite passed **25 scenarios, with one existing intentional D4 skip**, in **4.0 minutes**: Chromium desktop, one worker, no retries. The skip records the earlier NI-096 removal of the Save-chart action and was not introduced by this polish. The unchanged D5 paper gate measures **365 px** from the top and **535 px** visible at 1440×900; both chart viewports also pass. Public/private/editor axe scans report zero serious/critical and no lower-impact findings. Keyboard menus, focus return/traps and every sidebar destination pass.

The journey actually exercised chart selection/exact values → private document → prose/hypothesis/insight/evidence → save/reopen → source outage → frozen ZIP → manifest/member/revision hashes and repeated-download equality. Second-user denial, separate same-label visitors, logout/session rotation, public-copy ownership, custom ranges and revocable sharing passed. The stack uses real Next.js/FastAPI/PostgreSQL/RLS/export worker with synthetic provider transport and labeled fixture data. A separate manual review stack imports the existing saved historical archive; no new collection runs.

### Before / after evidence

| Before | After |
| --- | --- |
| [Workspace before](../ni-099/comic-lab-workspace.png) | [Workspace after](workspace.png) |
| [Overview before](../ni-099/comic-lab-overview.png) | [Overview after](overview.png) |

Additional passing-run captures: [login](login.png), [chart detail](chart.png), [editor saved context](editor.png), [editor layout](editor-layout.jpg). These files contain only the established synthetic fixtures, not raw historical archives or production users. No generation prompt/video was needed.

### Reproduce and review

Live local review: http://127.0.0.1:58346/ (cabinet: /login → Enter demo workspace). The saved-archive stack is left running. To recreate it, use the existing native harness procedure from NI-099 with an authorized local archive root; the handoff selects fresh loopback ports.

```sh
corepack pnpm build
corepack pnpm --filter web exec vitest run --maxWorkers=2
corepack pnpm --filter web exec playwright test --config e2e/playwright.config.ts
uv run --project apps/api --frozen --offline python scripts/run-db-tests.py \
  --pg-bin /opt/homebrew/opt/postgresql@18/bin --suite landing
```

Runtime data/services, metrics, editor schema, ownership, pins and frozen render/export palette are untouched; only the landing HTTP test's owned copy expectations change in the API tree. No new dependency, generated media, mobile adaptation, deployment or merge. Existing model/production-data/remote-provider acceptance belongs to its original tasks. Independent review skipped by user instruction 2026-11-09; root performed acceptance after the dedicated task agent's implementation.

Code/test digest relative to 6fd643c (sorted changed apps/web and apps/api/tests paths and bytes): `379e6fe4485d898767fe8f4e950059d18cec5d8fddba8087d4bd5afecb09e555`.

Final documentation check: 1,108 relative links resolve; whitespace check passes.
