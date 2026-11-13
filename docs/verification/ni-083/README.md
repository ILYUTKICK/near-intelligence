# NI-083 — Interactive history and exact descriptive calculations

Local implementation and desktop verification, 14 November 2026 (Europe/Moscow).
Owner requested interactive research graphs and corrected calculations after the
[history audit](../ni-082/README.md). Git publication remains on hold.

## Delivered flow

Public `/research#interactive-history` → same-origin read-only history gateway →
FastAPI → approved canonical dataset artifacts → shared modular ECharts renderer.
The API does not read arbitrary local files. Explicit operator preparation in the
isolated preview imports the saved archive through NI-028 validation/publication.

- Real provider histories: 694 volume days and 543 gross-fee days for DefiLlama;
  Dashboard remains a separately selected, qualified source with its own gaps.
- Source/period controls, all-history/90-day/365-day presets and a bounded custom
  UTC half-open period. Range changes retain the original provider dataset pin.
- Exact hover values, timeline slider, drag navigation, Shift+wheel zoom and
  keyboard zoom/reset. Plot navigation leaves calculations, table and pins intact.
- The purchase chart retains its independently pinned original 90-day cohort;
  longer provider coverage never expands attribution. Different units use separate
  panels. Legend toggles hide/show a series while exact data remain accessible.
- Original categorical claim comparisons also render interactively through
  ECharts. Their recorded source strings and explanatory text remain visible;
  no synthetic daily series or fictitious dataset identity is constructed.
- Server-side Decimal totals and weighted effective gross-fee rate use matched
  dates. Monthly/quarterly tables expose coverage and partial periods; missing
  observations are explicit nulls, source-reported zeros remain identified zeros.

The independently recomputed historical purchase/payout/window totals match the
existing claims; no correction to those original amounts was needed. The long
history is a separate descriptive extension. It does not provide net revenue,
fee-funding attribution, permanent retention, a fitted model or a valuation.
Detailed calculations, provenance and backend commands: [BACKEND.md](BACKEND.md).

## Checks and evidence

- Production web build passed; build ID `gI08nOw4Da145y4CJcX9-`.
  The 371 source files (`.ts/.tsx/.py/.json/.css`, excluding Python bytecode)
  under web/API/shared-types source roots have combined SHA-256
  `1e7a2aa2b0d505a6164ce69b8cb6296ee7312a732637b3290c84f16bec1da23b`.
  Fingerprint encoding: sorted relative path, uint64 big-endian path byte length,
  path bytes, uint64 big-endian content byte length, content bytes per file.
- Focused frontend/renderer/recorded-figure/static-export run: **76/76 passed**
  across seven files. A first parallel run overlapped the production build and
  timed out in two 5-second cases; unchanged cases passed in the serial rerun.
- After the visible zoom-date status was added, focused history/chart tests:
  **29/29 passed**. Keyboard Enter verification then passed **26/26** chart tests.
- Web lint and production TypeScript check passed. Generated OpenAPI/TypeScript
  drift check passed. Backend focused integration **82/82**, contracts **7/7**.
- Real saved-input preparation/staging and API reconciliation succeeded. The
  first two isolated bootstraps rejected an unsupported optional snapshot member
  and uncovered missing fee dates; fixes omitted the unsupported snapshot and
  emitted explicit missing rows, preserving validation rather than bypassing it.
- Desktop browser at 1440×900: real plots rendered; mouse and keyboard zoom
  narrowed the visible dates, reset restored them, slider drag changed the view,
  and exact hover values appeared. Selecting 90 days changed counts to 90/90/90;
  source selection showed Dashboard 665/541/540 separately. Quarterly edge
  buckets stayed Partial. Legend selection removed the event-count line while
  retaining the purchase line and exact data table. No page-width overflow was
  visible. Unit axe checks passed; no new mobile verification was performed.
- Final local preview: `http://127.0.0.1:64769/research#interactive-history`.
  After correcting cohort metadata, browser rechecked the unchanged 694/543/543
  counts, zoom/reset and historical purchase cutoff `2026-11-04T00:00:00Z`.
  Its unknown retrieval timestamp remains null; runtime resolution time is not
  presented as fresh observation evidence. [Desktop proof](long-history-desktop.png).

Root logs are local under `/private/tmp/ni083-*.log`; machine-readable API and
calculation evidence and preview handoff live under ignored `.local/ni083*`.
These are not publication artifacts or available in a fresh clone. All 14
previously audited archive inputs rehashed unchanged. No provider request, cloud
SQL, collector restart, Git mutation or remote deployment occurred for NI-083.

## Limits retained

The 2,443 observed provider values have 333 explicit missing date/source slots
in the common calendar grid. Fees are not protocol net revenue. Sources share
lineage and differ; they are neither spliced nor averaged. Static exports omit
browser navigation and keep the existing deterministic renderer layout. Existing
definition v1 identities and 366-day bounds remain; provider-chart v2 permits
730 days. NI-079/research-model/refresh/deployment gates remain separate.
