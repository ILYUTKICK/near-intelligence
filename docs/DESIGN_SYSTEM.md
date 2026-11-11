# Design system

NI-075 applies the NI-074 desktop design to the application. Public pages use generous editorial compositions. Data and the private workspace use denser controls and the same paper, type and evidence styles. The original notebook illustration from NI-074 appears on the Overview, auth pages and workspace Home.

## Application tokens

| Token | Value | Use |
| --- | --- | --- |
| color.canvas | #F8F6EE | Main warm ivory background |
| color.surface | #FFFDFA | Reading paper, cards, dialogs |
| color.surface-muted | #F0EDE5 | Quiet neutral fill |
| color.text | #132C41 | Primary navy typography |
| color.text-secondary | #596B75 | Secondary descriptions, readable metadata |
| color.accent | #1C5B41 | Primary actions and links |
| color.accent-hover | #154632 | Hover/pressed action |
| color.sage | #E7EFDD | Selected rows and positive status surfaces |
| color.border | #E7E1D6 | Decorative divider |
| color.control-border | #79877C | Input boundaries on light surfaces |
| color.focus | #285F9A | Focus ring, ≥2px plus offset |
| color.warning | #8A5C2B | Stale/partial text with pale background |
| color.danger | #973E36 | Errors and opposing evidence, with label/icon |
| color.info-surface / color.chart-2 | #E8EEF2 / #3A6684 | Informational status surfaces and text |

Small text needs 4.5:1 contrast and control boundaries and focus rings need at least 3:1 where applicable. Statuses carry text and icons. Run `pnpm --filter web check:contrast` against the current tokens. The versioned ECharts palette stays fixed for reproducible exports. [Contrast check](../apps/web/scripts/check-contrast.mjs)

Newsreader with a true italic face serves editorial headings and the writing paper. Inter serves controls, chart metadata and data tables. Both are self-hosted. Desktop page titles use a fluid 42–64 px scale and the workspace uses a smaller title scale. Body text is 16/26 px, UI is 14/20 px, supplementary metadata is 12/18 px and document text is 17/28 px. Metrics and tables use tabular lining numerals. Long-form prose is set to about 72 characters per line. [Font provenance](../apps/web/src/styles/fonts/LICENSE-NOTES.md)

Use the 4 px spacing scale, 22 px paper corners, 10 px field corners and 24 px dialog corners. Buttons and status chips use rounded ends. Main actions retain 44 px controls and visible focus. Public content is capped at 1280 px. The private workspace sidebar is 216 px, with 154 px and 236 px for the editor outline and properties when both panes are open.

## Component contracts

Buttons primary/secondary/quiet/destructive; inputs/select/date range; dialog/drawer; nav item; disclosure; toast/status; tabs; source badge; quality badge; metric summary; chart frame; accessible data table; block handle/menu; evidence card; version banner; autosave indicator. Every component specifies default/hover/focus/disabled/pending/error. Disabled controls explain prerequisites with nearby text; tooltip alone is insufficient. Inline status for save/freshness is persistent; toasts only confirm brief actions.

ChartFrame includes title, definition/source action, selection toolbar, units, last observed/retrieved timestamps, mode, quality, accessible summary/table, plot and contextual actions. Avoid dashboards made of unrelated KPI cards; group charts by the economic question. Display measured quantities with compact formatted values and exact tooltip/table values; never drop the bound/estimate label when formatting.

## Responsive and input behavior

Breakpoints: <768 phone single column, 768–1279 tablet/collapsed tools, ≥1280 full editor panes. Public sections stack naturally; app sidebar becomes focus-trapped drawer with safe-area padding. Tables may scroll inside a labeled region; whole page must not overflow. Document toolbar wraps/overflows into an accessible menu.

Phone inputs use ≥16px font to prevent zoom, touch-action chosen per control, hover styles behind `(hover:hover)`, safe-area bottom padding, `100dvh` with fallback for full-height layout. Do not disable page zoom. Charts retain vertical page scrolling; horizontal brush/pan is explicit, not a scroll trap. Essential values available through table/tap and keyboard, not hover.

Buttons give 120 ms transform feedback on pointer press. Keyboard navigation, editing and save status are immediate. Reduced motion disables press scaling.

## Accessibility verification

Landmarks, skip link and heading hierarchy; persistent labels; aria-live polite for save errors/status without announcing every keystroke; dialog focus entry/escape/return; keyboard block insertion and up/down reorder alternatives; source details usable without hover. Chart descriptions/table include missing values and units. Never use apparent precision or an unlabeled confidence gauge as visual authority. Test actual screen reader and mobile interaction in NI-064.
