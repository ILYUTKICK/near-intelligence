# NI-075 desktop design verification

11 November 2026

The NI-074 atlas was opened in Chrome at 1280 × 720 and all 23 entries were selected through its screen switcher. The application screenshots below come from the production Next.js build running against the disposable NI-063 PostgreSQL and FastAPI stack. The browser used 1280 × 800 for the screenshots and 1440 × 900 for the Playwright suite. Documents, accounts, saved selections and live datasets in that stack are synthetic fixtures. The published historical claim in Overview and Research comes from the NI-014 registry.

## Implemented screens

| Surface | Routes and screenshots |
| --- | --- |
| Overview and original thesis | [Overview](overview.jpg), [Research](research.jpg). The fifteen section links and H1–H4 anchors are present. |
| Data explorer | [Overview](data.jpg), [Network Activity](network.jpg), [Intents & Adoption](intents.jpg), [Revenue & Fees](revenue.jpg), [Token Economics](token-economics.jpg), [Ecosystem](ecosystem.jpg). |
| Chart library and detail | [Library](chart-library.jpg), [No search results](chart-library-no-results.jpg), [Chart detail](chart.jpg), [Plot and exact values](chart-plot.jpg), [Category chart detail](chart-category-detail.jpg), [Gated chart](chart-unavailable.jpg). |
| Methods and models | [Methodology](methodology.jpg), [Model catalog](models.jpg), [Unpublished run boundary](model-run.jpg). |
| Auth | [Sign in](login.jpg), [Create account](signup.jpg). |
| Research workspace | [Home](home.jpg), [My Research](my-research.jpg), [No matching documents](my-research-no-results.jpg), [Editor](editor.jpg), [Revision history](history.jpg), [Frozen revision](frozen-revision.jpg). |
| Owned chart selections | [Saved Charts](saved-charts.jpg), [No matching charts](saved-charts-no-results.jpg), [Saved chart detail](saved-chart-detail.jpg). |
| Account | [Profile](profile.jpg), [Settings](settings.jpg). |
| Dialogs | [Source provenance](source-dialog.jpg), [Custom range](range-dialog.jpg), [Chart destination](add-chart-dialog.jpg), [New document](new-document-dialog.jpg), [Export](export-dialog.jpg). |

The atlas's design-system screen is represented in the shared tokens and primitives. [Application design system](../../DESIGN_SYSTEM.md)

## Integration decisions

| Before | After | Why |
| --- | --- | --- |
| Library and category chart-detail screens had separate rendering code | One shared screen with route-specific breadcrumbs and URLs | Keep selection validation, chart metadata and recovery actions consistent |
| Custom date fields followed the chart and data table | Named range dialog with keyboard entry and focus return | Keep the dates accessible alongside the selection controls |
| Profile form called a missing same-origin route | Profile reads and saves through the existing verified private gateway and backend contract | Give the form a real persistence path |
| Editor properties used two narrow columns and frozen Tiptap content exposed an unnamed input | Stacked properties and a named read-only document | Keep full dates and identifiers readable and give the frozen paper its correct role |
| The preview showed draft and reduced-motion switches | Settings links to per-document recovery and displays the operating-system motion preference | Match the controls to the implemented behavior |

The integration branch starts from main at `630b4ed` and includes the NI-064 source commits. The NI-064 PR was merged into its stacked base after the base had reached main. [NI-064 PR #85](https://github.com/ILYUTKICK/near-intelligence/pull/85)

The application retains its pinned ECharts renderer palette and its fixed historical export path. The category previews use validated data from the registry and delivery API. The first two entries on each saved-chart page can resolve previews through the owned chart endpoint. [Chart system](../../CHART_SYSTEM.md)

## Verification

| Check | Result |
| --- | --- |
| Web lint, strict TypeScript and production build | ESLint passed with zero diagnostics. Next.js completed compilation, TypeScript and route generation. |
| Web tests and contrast | 531 tests passed across 50 files. All 22 configured contrast pairs passed. The lowest tested ratio was 4.92:1. |
| Python export tests | 22 tests passed, including the frozen renderer, exact chart values and ZIP boundaries. |
| Desktop Playwright | 17 tests passed. The research journey covered sign-in, chart selection, document editing and autosave, reopen, frozen revision, dataset outage, and a verified Markdown/CSV/SVG ZIP from the acknowledged revision. A second account was denied access to the document and export. |
| Visual browser checks | 35 screenshots. Zero horizontal overflow in 30 measured route captures and zero uncaught page errors. The checks included empty search results, unavailable data, chart tables, and dialog dismissal. Focus returned to the source, range, new-document, chart destination and export controls after Escape. |
| Profile browser check | An updated display name and time zone persisted across reload. A second account retained its own profile. |
| Accessibility | The axe scans found zero serious or critical violations. The synthetic 200-block editor recorded one moderate `landmark-unique` violation. Keyboard checks covered skip navigation, editing, chart ranges and exact values. |

The pull request tracks the CI checks for the integration branch. [PR #87 checks](https://github.com/ILYUTKICK/near-intelligence/pull/87/checks)

## Environment and limits

- Windows production QA ran from an isolated ASCII copy of the project. Webpack built the application. The local Turbopack run failed while starting a PostCSS process.
- Supabase login and signup transport were covered by the web tests. The browser workflow used the local synthetic ES256 provider handoff. Real confirmation emails and deployed environments are outside this verification.
- The archive and scheduled collection were outside the browser stack. Categories without an approved dataset and unpublished model runs render their available explanation.
