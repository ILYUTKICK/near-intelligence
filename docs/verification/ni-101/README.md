# NI-101 — complete Comic Lab Unslop follow-up

Owner request, 23 November 2026. Source baseline34711a6, feature branch
`feat/ni-099-comic-lab`, PR105. Coordinator /root; dedicated implementation
agent /root/ni101_unslop. Acceptance is recorded below only after actual checks.
Independent review skipped by user instruction2026-11-09.

## Direction and audit

Uses [Unslop by Damir Sokolovsky / @heydamir](https://heydamir.design/unslop),
CC BY4.0, from the owner's installed skill. Light-polish mode retains the
approved Comic Lab direction; the owner explicitly requests proceeding.

- **Product:** NEAR research readers inspect evidence and authors write private theses.
- **Character:** playful, precise, approachable.
- **World:** a research desk with warm paper, ink and annotated evidence.
- **Moments:** TRACE at entry; actual source-qualified charts in analytical views.
- **Signature:** the approved drawn ink frame and compact hard shadow on focal content.

Baseline native Chrome inspection covers the five public tabs and opened
research editor on the existing NI-100 preview. Redundant arrows occur on
ordinary action links, including document creation; they add no destination
information. The editor repeats revision metadata, prints a raw ISO timestamp
and schema version in its main header, exposes a default block UUID, uses two
competing context headings and heavily outlines every toolbar operation.
Default chart-range prose describes URL/registry implementation instead of
the period being inspected. Save chart exists as an owned persistence component
but is absent from category/detail actions after NI-096.

Preserve meaningful move-up/down controls, disclosure directions and scientific
flow notation. Preserve source/definition access, invalid-selection warnings,
exact values, pin semantics, private ownership and unavailable-model explanations.
The owner explicitly reverses NI-096's Save chart removal for workspace explorer
cards and corresponding private detail pages. This does not change saved live
charts into frozen snapshots; those are different existing features.

## Nine passes

1. **Spacing:** consistent8px toolbar grouping; compact editor panes. Browser
   multi-unit charts reserve200px per unit panel plus64px for controls/legend,
   instead of compressing two panels into a240px category-card plot.
2. **Color:** quieter secondary editor borders and annotation metadata; preserve
   mint navigation/actions and the approved palette.
3. **Icons:** remove decorative arrows from public navigation/actions, article
   links, document creation, workspace actions, catalogs and model links. Keep
   actual reorder, disclosure, chart controls and scientific flow directions.
4. **Copy:** plain Blog/My Research headings, search labels, exact readable
   UTC/end-exclusive default periods and useful editor helper text. Missing-data
   cards state the actual availability/validation gate, with raw error details
   retained in a native disclosure. Missing, unsupported selection, authentication,
   permission and transport failures remain distinct.
5. **Type:** remove the italic Blog slogan; preserve Rubik/Golos/Plex families,
   the established workspace title scale and readable research paper.
6. **Layout:** group Share with history/export; replace floating/repeated chrome
   with one editor action area and one truthful save-state line.
7. **Details:** disclose schema/update metadata, block UUIDs and annotation
   context. Saved previews expose exactly one exact-values table under its
   keyboard disclosure. Browser comparison legends use one bounded scroll row;
   full series identities remain in tooltips and the exact table.
8. **Visuals:** canonical graph logo, TRACE and existing evidence remain. No
   generated imagery, replacement charts, invented observations or video.
9. **Motion:** retain existing short feedback/reduced-motion handling. No added
   loops, entrances, gradients or animation dependencies.

The scientific option builder, static export dimensions/palette and canonical
series, metric, dataset and document contracts are unchanged. Browser legend
presentation clones the option without mutating shared scientific output.

## Surface review

Native Chrome baseline/follow-up review covers Overview, Blog, Data, Methodology,
Models, demo entry, Home, My Research/open editor, Saved Charts, Chart library,
all five explorer subgroups, workspace Models, Profile and Settings. Public
charts/category routes are also checked through the catalog-driven browser test.
Meaningful controls and existing unavailable states remain reachable.

| Individual chart | Manual saved-archive observation / interaction |
| --- | --- |
| intents-volume | Historical volume resolves;90-day preset and Save chart succeed |
| observed-conversions | Two distinct-unit panels;30-day preset and Save chart succeed |
| quantity-usd-sensitivity |30-day range, end_of_day price basis, estimate labels and Save chart succeed |
| gross-fees |30-day preset resolves observed values/missing gaps honestly; Save chart succeeds |
| treasury-payouts |30-day range with two selected recipients renders separate series; Save chart succeeds |
| fee-volume-association |30-day SRC-DASHBOARD scatter resolves; Save chart succeeds |
| supply-context | Honest unavailable view: this isolated preview lacks the combined approved dataset; no substitute created |
| model-diagnostics | Registered unavailable definition; no reviewed model artifact invented |

The six successful saved selections use actual saved historical inputs in an
isolated database. The preview is not a restored production database. Its
supply/model gaps do not demonstrate a deployed regression or close a research
data gate. No provider transport or collector is contacted for this review.

## Verification

Final production build and strict TypeScript pass. Full sequential web unit suite:
66 files /685 tests pass,233.09s, one worker. ESLint has no errors; the three
pre-existing unused-variable warnings in ModelRunDetail remain. Contrast passes
28 token pairs; OpenAPI/generated TypeScript remain current. Client-secret check
reports no configured root .env/nothing to scan. The saved-chart/snapshot real
database and HTTP suites pass9+7+1 tests, including cookie/CSRF/ES256/RLS,
idempotent retry/reopen, frozen snapshot/compare, referenced deletion refusal
and second-user denial. Relative documentation links and whitespace pass.

Earlier runs exposed and corrected the duplicate saved-preview table, cramped
multi-panel axes and long-wallet legend. A stale period-copy expectation was
replaced with independent dataset metadata and exact half-open boundary checks;
the editor test now awaits actual initial selection readiness. An overlapping
unit/browser run also hit5s unit timeouts and a pending browser mutation; the
final sequential unit pass above has no increased timeouts or skipped tests.
Final desktop production-stack browser suite passes27/27, without skips or
retries, in3.3minutes on source `deb1546`. It includes the restored D4 saved-chart
keyboard/pin/source/two-user gate and a registry-driven matrix of every public
and private category/detail route. The complete research journey verifies
acknowledged revisions, exact decimal strings, source-outage prose saves,
reopened pins, frozen ZIP/member/manifest hashes and second-user denial.
Revocable sharing and separate same-label demo users pass. Automated transport
and research fixtures are synthetic and labeled; the API, Postgres/RLS and
export worker are real. Axe scans report zero serious/critical and no lower
impact findings on the tested public/private/editor surfaces.

Desktop measurements: D3 plot visible320px at1440×900 and1280×800; D4 saved
preview visible208px; D5 paper starts343px (<386px gate), with557px visible.
Exact machine-readable records: [D3](d3-measurements.json),
[D4](d4-measurements.json), [D5](d5-measurements.json).

All four GitHub CI jobs pass on code revision `deb1546`:
[run45158674892](https://github.com/ILYUTKICK/near-intelligence/actions/runs/45158674892).
The following delivery commit adds only this final report, task acceptance and
synthetic screenshots/viewport measurements; current-head checks are required
again before handoff. The source PR is
[105](https://github.com/ILYUTKICK/near-intelligence/pull/105).

## Before / after and local handoff

Baseline: [NI-100 workspace](../ni-100/workspace.png) and
[editor](../ni-100/editor-layout.jpg). This pass's after captures use only the
established synthetic test fixtures:
[Overview](overview.png), [workspace](workspace.png), [login](login.png),
[chart detail](chart.png), [Saved Charts](saved-charts.jpg),
[editor opening](editor-layout.jpg), [opened pinned context](editor.png).

Native final inspection confirms the distinguishing recipient labels and
bounded legend row, three restored save actions in Revenue cards, and concise
Token Economics unavailability. Review locally at http://127.0.0.1:56647/
or `/login` → Enter demo workspace. The existing saved archive is imported
into the isolated preview; supply-context's combined dataset and a published
model remain absent there. No production credentials/database are copied.

No deployment, merge, provider call, new collection, generated media, mobile work
or financial/model calculation is part of this task.
