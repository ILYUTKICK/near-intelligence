# Design system

NI-099 implements the owner's approved **A / Comic Lab** desktop identity. The
warm paper, emerald mint, ink outlines and compact offset shadows are shared
across public research, the private workspace and native interaction controls.
The canonical three-node graph wordmark is the product logo. TRACE is the
approved mascot and appears on Overview, auth, workspace Home and the actual
empty Saved Charts state. It never stands in for missing observations.

This supersedes the NI-075 editorial appearance only. All route, ownership,
source/metric, financial-definition, revision-pin and export contracts remain.

## Application tokens

| Token | Value | Use |
| --- | --- | --- |
| color.canvas | #FFFDF6 | Warm ivory page |
| color.surface | #FFFFFF | Reading paper and native dialogs |
| color.surface-muted | #EEF5EF | Quiet secondary surface |
| color.text | #10231C | Ink text and outlines |
| color.text-secondary | #46594F | Readable secondary copy |
| color.action / color.action-hover | #00E5A0 / #00D393 | Mint primary actions and selected navigation |
| color.on-action | #10231C | Ink labels on mint; never white |
| color.accent / color.accent-hover | #006E4E / #00553D | Dark readable links and text accents |
| color.on-accent | #FFFFFF | Text on existing dark accent/danger fills |
| color.sage | #C9FAE7 | Pale mint contextual highlights |
| color.yellow / color.lavender | #FFE27A / #DACBFF | Supporting editorial/research notes |
| color.panel-border / color.control-border | #10231C | Outlined cards and controls |
| color.border | #CAD8CF | Quiet dividers within content |
| color.focus | #007B58 | Visible keyboard focus |
| color.warning / color.danger | #8A5C2B / #973E36 | Labeled warning and error text |

The frozen ECharts palette and render version stay unchanged. No scientific
series or old export is recolored by a page-level theme. `pnpm --filter web
check:contrast` parses the actual tokens and checks text, primary/hover action,
note surfaces, boundaries and focus. Small text needs 4.5:1 contrast; essential
control boundaries/focus need 3:1. Semantic states always retain text/icons.

Rubik is the display family, Golos Text is the interface and writing family,
and IBM Plex Mono is used for tabular figures. All are self-hosted through
`next/font/local`, with original OFL licenses and provenance in
[font notes](../apps/web/src/styles/fonts/LICENSE-NOTES.md). `--font-serif`
remains a compatibility alias to Rubik for existing heading components, while
the editor's paragraph body uses Golos Text. The logo uses its canonical vector
wordmark. Headings remain bold and readable; labels and prose carry a quieter
weight. Public page titles use the existing fluid scale; workspace PageIntro
titles use 36/42 px on desktop so document and chart content lead. Body is 16/26 px,
UI 14/20 px, metadata 12/18 px, and writing 17/28 px. Research prose is around
72 characters per line, with tabular lining numerals in tables/metrics.

Use the 4 px spacing scale. Paper cards have 16 px corners, controls 12 px,
and dialogs 20 px. Card/control outlines are 2 px. Paper cards use a compact
4 px neutral hard shadow and overlays 6 px. Primary controls have an offset
3 px shadow, a 44 px target and ink labels on mint. Quiet dividers remain 1 px.
The desktop workspace sidebar is 234 px, with the existing editor outline and
properties pane widths. Public content retains the existing 1280 px cap.

NI-100 applies [Unslop by Damir Sokolovsky](https://heydamir.design/unslop)
(CC BY 4.0) as a light polish of this approved identity. TRACE, the graph logo,
font families and the comic outline/shadow signature stay. The main continue
card keeps the strongest frame; secondary Home cards use the existing neutral
border with no offset shadow. Checklist states use the shared line icons and
explicit Complete/To do text. Existing documents make Continue research the
primary action and Create document secondary; first use keeps creation primary.
The desktop workspace topbar is 64 px high, with 44 px controls. Its private
label is quiet text. Public active navigation is neutral, while private selected
navigation retains mint. Overview has two hero actions; How it works remains
available in the footer. Section order, destinations and scientific/chart data
presentation are unchanged. Existing responsive layout rules are retained;
new mobile adaptation and device checks are outside this pass.

## Component contracts

Buttons primary/secondary/quiet/destructive; inputs/select/date range; dialog/drawer; nav item; disclosure; toast/status; tabs; source badge; quality badge; metric summary; chart frame; accessible data table; block handle/menu; evidence card; version banner; autosave indicator. Every component specifies default/hover/focus/disabled/pending/error. Disabled controls explain prerequisites with nearby text; tooltip alone is insufficient. Inline status for save/freshness is persistent; toasts only confirm brief actions.

ChartFrame includes title, definition/source action, selection toolbar, units, last observed/retrieved timestamps, mode, quality, accessible summary/table, plot and contextual actions. Avoid dashboards made of unrelated KPI cards; group charts by the economic question. Display measured quantities with compact formatted values and exact tooltip/table values; never drop the bound/estimate label when formatting.

## Responsive and input behavior

Breakpoints: <768 phone single column, 768–1279 tablet/collapsed tools, ≥1280 full editor panes. Public sections stack naturally; app sidebar becomes focus-trapped drawer with safe-area padding. Tables may scroll inside a labeled region; whole page must not overflow. Document toolbar wraps/overflows into an accessible menu.

Phone inputs use ≥16px font to prevent zoom, touch-action chosen per control, hover styles behind `(hover:hover)`, safe-area bottom padding, `100dvh` with fallback for full-height layout. Do not disable page zoom. Charts retain vertical page scrolling; horizontal brush/pan is explicit, not a scroll trap. Essential values available through table/tap and keyboard, not hover.

Buttons give 120 ms transform feedback on pointer press, gated to a fine pointer and non-reduced motion. Keyboard navigation, editing and save status are immediate. Reduced motion disables press scaling.

## Accessibility verification

Landmarks, skip link and heading hierarchy; persistent labels; aria-live polite for save errors/status without announcing every keystroke; dialog focus entry/escape/return; keyboard block insertion and up/down reorder alternatives; source details usable without hover. Chart descriptions/table include missing values and units. Never use apparent precision or an unlabeled confidence gauge as visual authority. Desktop keyboard/screen-reader acceptance remains applicable. Historical responsive behavior is retained; new mobile development and device passes are outside NI-099.
