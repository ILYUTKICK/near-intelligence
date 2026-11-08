# NI-012 final acceptance — 8 November 2026

Independent continuation reviewer: Codex delegated agent `/root/ni012_acceptance`,
role A, chat `01a1ba7d-239f-7483-b2d6-fc651744fe9b`. Reviewed the merged
restoration/integration from PR #66 on `feat/ni-012-final-acceptance` at base
`9d7abd2`, including the point-level missing-reason propagation and the real
Next.js → FastAPI → PostgreSQL test path. NI-011, NI-029 and NI-033 are DONE.

The three selected metrics consume the shared delivery service; decimal strings
remain intact, the fixed historical window is explicit, definition/dataset links
resolve to existing methodology anchors, and the four for/against claims consume
the thesis registry. Missing/ambiguous data stays unavailable and never becomes
zero. No live badge is rendered and absent archive timestamps remain unrecorded.

The fresh visual review found a long exact decimal extending beyond the phone
card. The bounded fix adds `overflow-wrap: anywhere` to its text and stacks the
observation definition list below the `sm` breakpoint. The coordinating Codex
agent `/root`, acting as role B, independently reviewed and approved both the
two-class source diff and the corrected mobile screenshot. This review is
separate from the delegated agent's review of the earlier continuation.

## Actual checks

Pinned Node 24.22.2, frozen API Python 3.13.3 and PostgreSQL 18.6; no dependency
change, provider request or collection command was needed.

- `pnpm --filter web exec vitest run tests/ui/landing-metrics.test.tsx tests/ui/public-routes.test.tsx --maxWorkers=2`: 2 files, 21 tests pass after the fix, including exact decimals, unavailable/empty/stale states, claim/CTA traces and axe checks.
- `pnpm --filter web build`: pass after the fix; `/` remains dynamic.
- `pnpm --filter web typecheck` and `pnpm --filter web lint`: pass after the fix.
- `pnpm check:contracts`: OpenAPI and TypeScript current.
- `pnpm check:doc-links`: pass, including this evidence document and the final task-card link.
- Original `apps/api/.venv/bin/python scripts/run-db-tests.py --pg-bin /opt/homebrew/opt/postgresql@18/bin --suite landing`: synthetic integration passes with 3/3 observed cards; no-approved-data → publication → rendered exact values → stopped-API fallback.
- The same original command with `NI_LANDING_ARCHIVE_ROOT=/Users/ilyutkinn/Desktop/Near/research`: post-fix pass, 1 test in 4.308 seconds, 2/3 observed cards. Gross fees stay unavailable because multiple dimension variants require an approved disambiguating filter. Both consumed source hashes remain unchanged:
  `7680c5755c2efe5c1694544e68ede0f1f609c29b033ed5d9bdc62899e2024be8`
  (longitudinal flows) and
  `99fdb09823ff5dd80a46387f957bb6f54f71087abee87542e65cdd3f0674b8cd`
  (daily analysis).

## Visual evidence

Native Chrome DevTools responsive inspection used the production build and the
same disposable saved-input server, with browser zoom normalized to 100%.
Populated and stopped-API states were inspected at 360 × 780 and 1440 × 900 CSS
pixels. A temporary local pause wrapper kept the test servers available for this
inspection; it and its temporary test file were removed after normal process and
database cleanup. Screenshots below contain only the page, captured with native
DevTools; no research input data files were committed.

- [Phone before](landing-mobile-before.png): exact decimal overflows the card at normal browser zoom.
- [Phone after](landing-mobile-after.png): every digit wraps inside the card; units, observation period, coverage and provenance remain visible.
- [Desktop](landing-desktop.png): full decimals, two-column metadata, dates and source links.
- [Phone API outage](landing-mobile-unavailable.png): typed unavailable state with no value or zero substituted.

This is browser/HTTP acceptance of NI-012. Physical phone, screen-reader and
whole-product keyboard/performance release checks remain in NI-064 and the
other release tasks; they were not claimed here.
