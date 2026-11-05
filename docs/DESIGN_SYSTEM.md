# Design system

Premium editorial research interface: warm ivory surfaces, forest accents, calm charts and clear evidence. Existing SVGs in `product-plan` are visual references; written product scope and canonical routes prevail. No new image assets or component code are created in this phase.

## Tokens to implement

| Token | Value | Use |
| --- | --- | --- |
| color.canvas | #F6F4EC | Main warm ivory background |
| color.surface | #FFFEFA | Reading paper, cards, dialogs |
| color.surface-muted | #E9EEE5 | Quiet section/selection background |
| color.text | #17242D | Primary navy-charcoal typography |
| color.text-secondary | #4B5C54 | Secondary descriptions, readable metadata |
| color.accent | #214D3B | Primary action, links, series 1 |
| color.accent-hover | #173A2C | Hover/pressed action |
| color.sage | #DCE6D7 | Highlight fill only, dark text above |
| color.border | #D8DDD2 | Decorative border; not sole control boundary |
| color.control-border | #79877C | Input boundaries on light surfaces |
| color.focus | #285F9A | Focus ring, ≥2px plus offset |
| color.warning | #80521D | Stale/partial text with pale background |
| color.danger | #9B3B38 | Errors and opposing evidence, with label/icon |
| color.chart-2/3/4 | #5A7189 / #99662D / #86657E | Distinguishable secondary series |

Validate WCAG contrast using actual combinations; token values are proposals, not a completed audit. Small text needs 4.5:1; large text/control boundaries/focus ≥3:1 where applicable. Sage/border fills do not qualify as text colors. Opposing evidence uses descriptive text rather than red alone. **Audit status (NI-006, 2026-11-05):** all 22 documented role pairings pass their targets — run `pnpm --filter web check:contrast` ([apps/web/scripts/check-contrast.mjs](../apps/web/scripts/check-contrast.mjs)); measured values are in the NI-006 task record.

Typography: editorial hero/research title uses a self-hosted open-license serif candidate (Newsreader, **license/build check passed 2026-11-05** — SIL OFL 1.1, self-hosted WOFF2 in [apps/web/src/styles/fonts](../apps/web/src/styles/fonts) with provenance notes); app UI uses self-hosted Inter (SIL OFL 1.1). Avoid externally blocking font calls. Hero 64/68px desktop, 40/44px phone; page title 36/42; section heading 24/32; body 16/26; UI 14/20; metadata 12/18 only for supplementary content; document body 17/28. Tabular lining numerals for metrics/tables. Reading width 68–74ch, no dense full-width research prose.

Spacing scale px: 4,8,12,16,24,32,48,64,96. Surface radius 12; inputs/buttons 8; dialogs 16; no pill treatment for every element. Border 1px; elevation only for menus/dialogs, subtle 0 8px 32px rgba(23,36,45,.08). Primary button height44; icon targets ≥44×44; controls labeled. Desktop max width1280, public prose760; sidebar240; editor outline200/tools280; main document min560 when three panes fit.

## Component contracts

Buttons primary/secondary/quiet/destructive; inputs/select/date range; dialog/drawer; nav item; disclosure; toast/status; tabs; source badge; quality badge; metric summary; chart frame; accessible data table; block handle/menu; evidence card; version banner; autosave indicator. Every component specifies default/hover/focus/disabled/pending/error. Disabled controls explain prerequisites with nearby text; tooltip alone is insufficient. Inline status for save/freshness is persistent; toasts only confirm brief actions.

ChartFrame includes title, definition/source action, selection toolbar, units, last observed/retrieved timestamps, mode, quality, accessible summary/table, plot and contextual actions. Avoid dashboards made of unrelated KPI cards; group charts by the economic question. Display measured quantities with compact formatted values and exact tooltip/table values; never drop the bound/estimate label when formatting.

## Responsive and input behavior

Breakpoints: <768 phone single column, 768–1279 tablet/collapsed tools, ≥1280 full editor panes. Public sections stack naturally; app sidebar becomes focus-trapped drawer with safe-area padding. Tables may scroll inside a labeled region; whole page must not overflow. Document toolbar wraps/overflows into an accessible menu.

Phone inputs use ≥16px font to prevent zoom, touch-action chosen per control, hover styles behind `(hover:hover)`, safe-area bottom padding, `100dvh` with fallback for full-height layout. Do not disable page zoom. Charts retain vertical page scrolling; horizontal brush/pan is explicit, not a scroll trap. Essential values available through table/tap and keyboard, not hover.

Motion is restrained: 120–180ms opacity/color for menus/status; no animated KPI counters, autoplay data motion or decorative cryptocurrency gradients. Respect prefers-reduced-motion; errors/save status use no blocking transitions. Editor keystrokes/chart inspection should feel immediate; do not animate every pointer movement.

## Accessibility verification

Landmarks, skip link and heading hierarchy; persistent labels; aria-live polite for save errors/status without announcing every keystroke; dialog focus entry/escape/return; keyboard block insertion and up/down reorder alternatives; source details usable without hover. Chart descriptions/table include missing values and units. Never use apparent precision or an unlabeled confidence gauge as visual authority. Test actual screen reader and mobile interaction in NI-064.
