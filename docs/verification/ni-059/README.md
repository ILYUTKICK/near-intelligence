# NI-059 PDF export — visual verification artifacts

Committed verification artifacts of the deterministic PDF export renderer
(`apps/api/src/near_api/exports/pdf.py`). Every PDF is visibly synthetic
("(fixture)" content) and was produced offline from the same fixtures the
test suite uses (`apps/api/tests/test_exports_pdf.py`).

| Artifact | Pages | Content |
| --- | --- | --- |
| `short-report.pdf` | 3 | Representative SHORT revision: every renderable block family once (paragraph/heading/bullet+ordered lists/hypothesis/risk/divider/authored table/evidence/chart) plus attribution block, registries, limitations, exact-value appendix and rendering provenance. |
| `long-report.pdf` | 9 | Representative LONG revision: 8 repeated sections (tables split across pages under repeated header rows), 2 charts, insight cards with pinned contexts, appendix and provenance. |
| `real-chart-report.pdf` | 3 | The REAL NI-057 Node ECharts SSR SVG (subprocess, byte-hashed request/script) embedded as vector art — grid, axes and the frozen series are visible on page 2; the provenance table carries the real renderer/script hashes. |

## How the pages were inspected (2026-11-11, implementation claim)

Every page of every artifact was rendered and viewed as a page image
(a PDF viewer rendering of each file, all pages), checking: attribution and
plan-identity block on page 1; pinned captions (chart definition version,
dataset version, resolved-at) under every figure; no clipped charts or
tables (tables split with repeated header rows; cells wrap, never truncate;
figures scale to the printable width with aspect preserved); the exact-value
appendix matches the CSV assets (missing values stay empty with their
recorded reason; the 32-digit decimal renders unwrapped); the registries and
limitations carry the recorded identities and reason codes.

Inspection method (2026-11-12, implementation verification): every page of
every artifact was rendered as a page image and inspected (a PDF rasterizing
viewer over the exact committed bytes — `pdftoppm`/`gs`/`mutool` do not exist
on the machine and the macOS command-line tools (`sips`, `qlmanage`) cover
only page 1, so the pages were rendered with a PDF viewer that draws each
page individually; 15/15 pages seen: short 3, long 9, real-chart 3). The
findings are recorded in the NI-059 task card. The coordinator performs the
final visual pass with a PDF viewer at acceptance; these artifacts make that
possible directly.

Regeneration (offline, disposable):

```sh
uv run --project apps/api python - <<'EOF'
import sys
sys.path.insert(0, "apps/api/tests")
sys.path.insert(0, "apps/api/src")
import test_exports_pdf as fx
from near_api.exports.charts import chart_render_request, render_chart_assets
from near_api.exports.pdf import render_pdf

plan = fx.short_plan()
open("docs/verification/ni-059/short-report.pdf", "wb").write(
    render_pdf(plan, fx.synthetic_render(plan)))
long_plan = fx.long_plan()
open("docs/verification/ni-059/long-report.pdf", "wb").write(
    render_pdf(long_plan, fx.synthetic_render(long_plan)))
plan_real = fx.short_plan(chart=False).model_copy(update={"blocks": (
    *fx.short_plan(chart=False).blocks, fx.renderer_fixtures.export_chart_block())})
result = render_chart_assets(chart_render_request(
    [b for b in plan_real.blocks if b.block_type == "liveChart"]), timeout=60.0)
open("docs/verification/ni-059/real-chart-report.pdf", "wb").write(
    render_pdf(plan_real, result))
EOF
```

The renderer is deterministic: rebuilding with the same inputs reproduces
byte-identical PDFs (test-enforced), so these artifacts equal what the
worker stores for the same frozen plans.

## NI-080 CI/main integration repair — 12 November 2026

The initial PR merge tree had two Alembic heads: organization `0014` and PDF
`0016`, both independently descended from `0012_export_jobs`. The original
`get_current_head()` failure was reproduced locally. Migration
`0018_merge_pdf_organization` now joins the two without altering either applied
parent. The existing export migration regression verifies upgrade from each
individual parent, combined schema/mirror, downgrade and re-upgrade.

Normal merges retain main `129262d` and the author's concurrent E2E format-start
fix `f7ef860`. The PDF renderer and the visual artifacts above are unchanged.
Local verification: PDF unit 27/27; real PostgreSQL export/IR integration 27/27;
production build, lint/types/contracts/docs (815 links)/contrast (22 pairs),
frozen lock and whitespace checks pass. The complete desktop Playwright run
passes 17/17, with synthetic auth/data over real web/API/PostgreSQL/worker,
including the frozen export and outage/owner-denial branches. Existing moderate
editor landmark finding is not hidden. Final-head GitHub required checks and
cross-PR migration-head integration are coordinated through NI-080; no deployed
or real-data release readiness is claimed by this repair.

## PR #93 repair verification (13 November 2026)

Rebuilt five synthetic reports with the frozen ReportLab 5.1.0 and svglib 2.4.0
runtime. Rendered and inspected all 20 pages with Poppler. The short and long
reports have 3 and 9 pages, the report with the NI-057 SSR chart has 3, the
model report has 2, and the wide table report has 3. The wide table starts on
the first page and repeats its column group and headers on continuation pages.
The model report puts the limitations ahead of the coefficients and prints the
same manifest path and SHA-256 verified in the Markdown ZIP. These checks used
temporary test outputs and synthetic source data.
