# NI-078 — Desktop research and chart presentation

The original implementation ran on 12 November 2026 at `d4c524f`. The 13 November integration updated PR #95 against `main` at `c56ec29`. Claims and acceptance are in [TASKS.md](../../TASKS.md).

| NI-076 finding | Result | Desktop evidence |
| --- | --- | --- |
| D1 — Research opening | The H1–H4 assessment links to all four full assessments. All 15 thesis sections remain. | [Before](../ni-075/research.jpg), [opening](screens/research-opening-after-1440.jpg), [assessment](screens/research-assessment-after-1440.jpg) |
| D2 — Missing figures | The CL-004 USD windows carry the estimate basis. The CL-007 supply comparison uses independent NEAR totals and links to CL-001 for observed purchases. Both figures use the recorded claim registry. | [USD windows](screens/research-figures-usd-after-1440.jpg), [supply scale](screens/research-figures-supply-after-1440.jpg) |
| D3 — Chart starts too low | One title, short metadata and a wrapping toolbar with sources, filters, range and private actions. The exact table stays visible without hover. | [Before](../ni-075/chart.jpg), [1440×900](screens/chart-loaded-after-1440x900.jpg), [1280×800](screens/chart-loaded-after-1280x800.jpg) |
| D4 — Saved cards repeat detail | One title, mode and context line per card. The shared renderer shows a bounded lazy preview and one exact-value disclosure. Previewing preserves the last-opened dataset. | [Before](../ni-075/saved-charts.jpg), [after](screens/saved-charts-after-1440.jpg) |
| D5 — Editor paper starts too low | One breadcrumb and a compact header. The paper shows the observation pin and save state. Properties and the chart disclosure contain the full dataset identifier. | [Before](../ni-075/editor.jpg), [after](screens/editor-after-1440.jpg) |

## Desktop measurements

The [NI-076 review](../ni-076/README.md) recorded baseline measurements at 1440×1000. Its original JPEGs were stored on the review machine. The committed NI-075 screenshots show the same pre-change revision (`0b80bf2`) at 1280×800 with separate synthetic selections and documents.

The [integration measurements](screens/measurements.json) come from `apps/web/e2e/ni-078-evidence.spec.ts` on a local production Next.js build, FastAPI and disposable PostgreSQL 18.6. The chart and workspace use isolated synthetic fixtures. The public figures use the existing historical claim registry. The test uses reduced motion, waits for the rendered SVG and writes captures to Playwright's output directory.

- **D1/D2** — The assessment starts at y882, after the opening evidence. The first viewport shows its top 18 px at 1440×900. A separate capture shows all four cards. The page has three evidence figures, up from one in the NI-076 review.
- **D3** — The plot starts at y596, with 304 px visible at 1440×900 and 204 px at 1280×800. NI-076 measured the earlier plot near y703 at 1440×1000.
- **D4** — The plot starts at y581 and all 208 px are visible at 1440×900. The card is 639 px tall. NI-076 measured the earlier plot near y669.
- **D5** — The paper starts at y351 and the first text at y408, with one breadcrumb. NI-076 measured y386 and y442 with two breadcrumbs.

## Custom range and regression checks

The actual date controls accept a new start and end. Apply resolves `[2026-01-03, 2026-01-12)` and the table excludes the end day. The selection survives reload, sign-in, save and reopen. The sign-in continuation carries both dates, the filter and the dataset version. The earlier Apply failure was not reproduced.

The local integration passed 199 targeted web tests, strict TypeScript, affected ESLint, production Webpack build, generated contracts and 22 contrast pairs. The saved-chart and snapshot suites passed 16 tests on disposable PostgreSQL 18.6, including a newer live dataset, unchanged preview metadata, first-open change notice, frozen exact values and a second user's 404.

Desktop Chromium verified Custom range, D1–D5, exact values and source focus, the NI-063 research and outage/export journey, and the two-user boundary. The NI-063 export still captures the acknowledged revision. The separate table and keyboard scenarios verify the observed dataset UUID inside the pin disclosure. Independent review covered the three conflict resolutions, shared renderer, preview semantics, keyboard access, pin presentation and captures.

The original branch recorded 551 web and 22 E2E passes on 12 November. Integration evidence above covers the current branch. Real Supabase login and deployment remain with NI-079.
