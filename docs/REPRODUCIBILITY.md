# Research reproducibility

Two layers: existing offline descriptive analyses already in the directory, and the future versioned application/model pipeline. Never describe planned commands as currently installed. Source rights may limit public raw download; retain sanitized manifests and permitted reproduction paths.

## Existing offline analyses

Run from repository root in a disposable copy because scripts rewrite derived outputs in place. Inspection found the four primary analyze.py scripts use stdlib; optional plotting needs matplotlib and is not required for recomputing amounts. Record `python3 --version` and hash inputs first. No new API key/cloud job is needed for the saved-input path.

| Purpose | Existing command | Inputs / derived output |
| --- | --- | --- |
| 90-day conversions/payouts | `python3 research/near-longitudinal/scripts/analyze.py` | data/flows_90d_raw.json and weekly collector scope; analysis/summary.json, payout matches and issues |
| Daily USD sensitivity | `python3 research/near-dollar/scripts/analyze.py` | longitudinal saved outputs plus data/coingecko.json, llama_* and dashboard records; analysis/daily.json and summary.json |
| Net supply and lower bounds | `python3 research/near-supply/scripts/analyze.py` | saved headers/indexed boundaries and prior observations; analysis/summary.json; incomplete gross audit remains incomplete |
| Treasury retention scope | `python3 research/near-treasury/scripts/analyze.py` | saved FastNear history/RPC/governance; data/summary.json and reconciliations |
| Small provenance sample | `python3 research/near-provenance/scripts/audit_sample.py` | saved API sample and receipt traces; analysis/sample_summary.json |
| Full saved creation cohort | `python3 research/near-provenance/scripts/audit_cohort.py` | 23 saved API pages/cohort and incoming events; analysis/cohort_summary.json |
| Inventory bounds | `python3 research/near-provenance/scripts/inventory_bounds.py` then same command with `--exact-integer-only` | saved matched fees and reconciled ledgers; expanded/strict inventory summaries |
| Collector route bounds | `python3 research/near-provenance/scripts/collector_routes.py` | saved matched ledgers/treasury paths; route artifacts |
| Final provenance summary | `python3 research/near-provenance/scripts/summarize.py` | preceding generated summaries; analysis/final_summary.json |

Inspect each script's read paths before execution: not every legacy script is a reusable pure function, and some depend on earlier generated outputs. Saved manifests live in the respective research directories and record raw hashes/job/source metadata. Existing final findings are linked from [thesis](INVESTMENT_THESIS.md). These commands reproduce saved-input accounting, not new complete-market data or statistical regressions.

**Do not run** fetch scripts, archival header collection, cloud SQL or stopped account-balance collectors as part of offline reproduction. Do not remove STOP_PUBLIC_COLLECTION. In particular the supply audit must continue to report 6/297 verified headers; no offline calculation can invent missing gross issuance/burn. Do not rerun Explorer collection requiring the former token.

## Dependency baseline

The root [requirements.txt](../requirements.txt) now contains a tested hash-pinned Python dependency set; [DEPENDENCIES.md](DEPENDENCIES.md) records platforms and checks. This does not include the unshared research code/data. NI-002 will make pyproject.toml/uv.lock the declaration/lock source and export the pip-compatible file, keeping one exact version source. A published model must record its actual Python patch, dependency lock/hash and input manifests; installing packages alone does not reproduce a model.

## Future reproducibility bundle

Each approved dataset bundle includes manifest schema version, dataset UUID/key/version, UTC scope and cohort, raw artifact names/byte hashes, source URLs/query IDs/SQL hashes, source cutoff/retrieved times, original units/decimals, cleaning/matching rules, metric definition versions, code commit, dependency lock hash, config and canonical transformed-data hash. Include quality/coverage/revisions/known exclusions/license restrictions.

Canonical JSON uses UTF-8, normalized key ordering and deterministic separators, decimal strings unchanged, UTC timestamps with explicit Z, sorted records by defined primary key; no volatile wall-clock field participates in the content-addressed semantic hash. Raw-byte SHA hashes still cover exact original responses. Manifest metadata and semantic data hash are separate. Identical content may be deduplicated within a dataset key; retrieval records remain separate lineage.

Dataset immutability: only staged artifacts mutate; approved dataset bytes/rows never do. Re-fetch revisions create a new version/supersedes relationship. Content hash is integrity evidence, not an authenticity guarantee or a substitute for source trust. Signed/provider-authenticated receipts are not assumed available.

For document revision, include editor schema/content hash, publication source if copied, every chart definition/renderer/metric version, selection/filter/mode, exact dataset pin and context hash, insight/evidence metadata and model run references. Snapshots reconstruct the same evidence; live mode is merely a working-view resolution policy.

## Deterministic model commands — implemented subset and remaining plan

Implemented so far (offline research commands; the archive is opened read-only and reports are written only to the operator-provided output directory):

```sh
uv sync --project apps/api --frozen
# NI-051 readiness gate (decides which empirical question is admissible):
uv run --project apps/api python research/models/readiness.py \
    --archive-root /path/to/research --configs-dir research/models/configs \
    --out-dir research/models/reports
# NI-052 fixed deterministic estimator (same specification, unchanged):
uv run --project apps/api python -m near_api.research fit \
    --archive-root /path/to/research --out-dir research/models/reports \
    --code-commit <git sha>
# equivalent standalone research entry point:
uv run --project apps/api python research/models/fit.py \
    --archive-root /path/to/research --out-dir research/models/reports \
    --code-commit <git sha>
# NI-053 diagnostics/robustness/interpretation battery over the same fit:
uv run --project apps/api python -m near_api.research diagnostics \
    --archive-root /path/to/research --out-dir research/reports/<run> \
    --code-commit <git sha>
# equivalent standalone research entry point:
uv run --project apps/api python research/models/diagnostics.py \
    --archive-root /path/to/research --out-dir research/reports/<run> \
    --code-commit <git sha>
```

The estimator refuses to fit unless the gate verdict for the bound specification (`research/models/configs/gross_fee_activity_v1.json` with settings in `research/models/fit_configs/gross_fee_activity_v1_fit.json`) is `READY`/`READY_WITH_LIMITS`. The diagnostics battery binds the same specification (`research/models/diagnostics_configs/gross_fee_activity_v1_diagnostics.json`), re-runs the estimator and records the sample/exclusion table verbatim, ADF/KPSS with preregistered fixed lag settings, residual ACF/Ljung–Box/Breusch–Pagan/Cook's distance, the preregistered sensitivity presets (HAC maxlags 3/14, alternate provider source, alternate price basis) and a template-rendered bounded interpretation; every defined diagnostic is present or undefined/failed with a recorded reason. Exit codes are 0 success, 4 contract/policy failure, 2 usage. The same inputs/config/lock render a byte-identical manifest on one platform; fitted floats compare under the documented tolerance (rtol1e-8/atol1e-10). The real-archive fit and diagnostics runs are operator-side evidence, not repository content.

## Operator publication gate and offline verification — implemented (NI-054)

Publication is an operator CLI flow, never a browser route (API_SPECIFICATION: "Creating datasets/models/publications uses the operator CLI, not a browser POST API"). The gate lives in `apps/api/src/near_api/research/` and is pure-file work until the final database write:

```sh
# 1. Verify a run bundle offline (no network, no database, no re-fit):
uv run --project apps/api python -m near_api.research verify \
    --bundle research/reports/<run> --offline
# The bundle directory holds fit_manifest.json (NI-052), diagnostics_report.json
# (NI-053), readiness_report.json (NI-051) and publication_approval.json.
# A passing verification prints the canonical SHA-256 of the three manifests.

# 2. Record the operator approval binding those exact hashes
#    (publication_approval.json: approval_type model_run_publication_approval,
#    decision "approve", reviewer, review_reference, approved_artifacts{...}).

# 3. Publish — verify runs again, then the run is written once:
uv run --project apps/api python -m near_api.research publish \
    --bundle research/reports/<run> \
    --database-url <near_operator psycopg URL>
```

The verifier checks, fail-closed and offline: bundle completeness and artifact types; the approval binding (decision `approve`, non-empty reviewer and review reference, and the approved SHA-256 matching the canonical rendering of every manifest — the reviewed bytes and the published bytes must be identical); the data manifest (one archive state pinned by name/SHA-256/bytes identically across fit, diagnostics and readiness artifacts); the code manifest (one recorded commit); the lock manifest (the recorded `apps/api/uv.lock` hash must match this checkout); config identity (every recorded spec/fit/diagnostics/policy hash must match the committed preregistered file, so a run publishes only under the checked-in configs); cross-manifest identity (one specification, one sample window and size, one gate verdict shared with the readiness report); the design manifest (declared columns, row count equal to the sample, finite rank/condition, exact-decimal and float64 design hashes); the result manifest (finite coefficients bound to the declared columns, ordered 95% intervals containing the estimates, and the diagnostics report's rebuilt coefficient table equal to the fit manifest's under the declared tolerances); diagnostics completeness (every declared diagnostic present exactly once with a status or an undefined reason, the reported sensitivity presets exactly the preregistered ones — no surfing, template-rendered interpretation only); limitations attached verbatim to both artifacts; and the reproduction tolerances. A served bundle (from `GET /api/model-runs/{run_id}/manifest`) verifies with the same command — `verify --bundle <downloaded manifest.json> --offline` — so a reviewer re-checks the published artifact without any operator tooling.

Publication writes one immutable row into `app.model_runs` (migration 0010): the content-derived `run_id` (UUIDv5 over the three manifest hashes — identical content is a no-op, a re-approval of identical content under a different approval is a conflict), the specification identity, the NI-051 gate verdict, the full manifest set as JSONB, the per-artifact SHA-256 map, the approval record and the denormalized identity columns re-asserted by CHECK constraints against the stored manifests. The table is published-only by CHECK, write-once (no UPDATE/DELETE grant for any role) and FORCE-RLS with `near_operator` as the only writer; a refused bundle reaches no database row, so unpublished, failed and rejected runs never look like results. Exit codes for `verify`/`publish`: 0 success, 4 gate/contract refusal, 2 usage.

Remaining planned (do not describe as working until implemented):

```sh
uv run --project apps/api python -m near_api.cli datasets build --config research/models/configs/intents_daily_v1.json --offline
uv run --project apps/api python -m near_api.cli research readiness --model gross-fee-activity-v1 --dataset <UUID>
```

The `near_api.cli` surface and dataset-UUID binding do not exist yet. Models for true protocol revenue are enabled only after their readiness gates pass. `--offline` rejects provider HTTP and cloud access, not merely omits an API key. The publication gate validates that artifact/code/lock/config inputs are all resolvable and pinned; redistribution licensing of the saved inputs remains an operator responsibility recorded on the dataset/source artifacts (NI-027/NI-028), not something a hash can prove.

Model bundle adds model version, sample/exclusions, transformed design, coefficient/SE/CI/test outputs, covariance/lag settings, diagnostics, interpretation/limitations, Python/OS/BLAS versions and seeds. Exact data hashes must match; fitted floats use documented tolerance (initial rtol1e-8/atol1e-10); rendering pixels/ZIP timestamps may differ while canonical values/pins match.

## Reviewer recipe and acceptance

1. Obtain an explicit published research release and permitted immutable input bundle; verify each hash and license/source note.
2. Check out exact code commit and install frozen lockfiles in an isolated environment; print environment metadata.
3. Run offline dataset builder and compare canonical data/design hashes, date coverage and exclusions.
4. Run the registered model/config, compare coefficient/SE/CI/diagnostics under stated tolerance; include unsuccessful readiness reports when applicable.
5. Reconstruct a document/export using its pinned contexts; verify chart CSV and source/model references.

If a provider forbids redistribution, supply the original query/API retrieval recipe and approved summary artifacts, clearly disclosing any entitlement/cost barrier. A supposedly independent reproduction that cannot access required inputs must be reported as limited, not passed. P0 should prefer publishable saved inputs so hackathon judges can actually rerun without paid credentials. NI-054 and NI-069 perform the clean-machine/offline and demo verification after implementation.

## Interactive document inspection — NI-042

The working editor reconstructs its observed dataset UUID through the owner-scoped chart-view endpoint. A successful range/filter edit preserves that dataset. Explicit Refresh asks for latest and adopts the returned UUID into the document. Whole-document save validates submitted inspection claims against the immutable registry, selection and approved dataset. Unchanged contexts, including their saved observation time, are copied verbatim on prose edits.

NI-043 resolves historical chart data and CSV through `documents.context_resolver.reconstruct_revision_chart`. It verifies the revision and context hashes, the chart, metric and renderer versions, and the pinned prepared-data digest against the manifest registry before delivery. This verifies the prepared PostgreSQL evidence using local rows. Independent reproduction from original source bytes still requires the separately authorized archive. Historical views omit the live ingestion checkpoint. Source catalog labels and links are informational. NI-056 can reuse the resolver when assembling the frozen export representation.

Implemented frozen export representation (NI-056): `exports.ir.build_export_ir` translates one owned, acknowledged immutable revision into the typed plan of `schemas/export.py` (`ExportIr`) — revision metadata (title/author/revision date/content hash), every P0 block with its pinned values, fully resolved frozen chart evidence (through the NI-043 resolver, so export series/units/quality equal the frozen view), data-table specs with exact decimal-string cells and the deduplicated source/model-run/citation references. The builder consults no latest pointer (verified by a test that refuses `resolve_latest_version` on the path), re-verifies every pin fail-closed (a missing pinned artifact, unresolvable dataset/model-run/citation reference or unsupported block raises a typed `ExportIrError` with details instead of substituting current data), adds no wall-clock field (building twice for the same revision yields identical canonical bytes via `export_ir_canonical_bytes`), and is produced only while the requested revision is the document's acknowledged current version — every title change creates a new revision, so title and content always describe the same revision. Rendering (static chart assets, ZIP delivery) stays with NI-057/NI-058.

Implemented chart asset rendering (NI-057): `exports.charts` invokes the pinned Node ECharts SSR renderer (`apps/web/scripts/render-charts.mjs`) as a subprocess (fixed ARGV list, no shell, strict typed stdin, timeouts and size caps), verifies the renderer identity, request hash and every asset hash, and re-scans every SVG for script/remote-reference content. Each chart exports a deterministic SVG plus a lossless CSV carrying the frozen view's exact decimal strings (missing points stay absent with their recorded reasons). `NEAR_CHART_RENDERER_NODE`/`NEAR_CHART_RENDERER_SCRIPT` are operator seams; the recorded identity (protocol id, echarts version, node version, script SHA-256, request SHA-256) travels into the ZIP manifest.

Implemented Markdown ZIP delivery (NI-058): the export job freezes the plan (above) at creation and the operator worker `uv run --project apps/api python -m near_api.exports.worker --database-url <near_app-url> --operator-database-url <near_operator-url>` delivers it — claim (`FOR UPDATE SKIP LOCKED`, lease, two-attempt cap with typed `lease_attempts_exhausted`), render (NI-057 assets + deterministic `research.md`), and a lease-guarded commit of the ZIP into the owner-scoped job row. The ZIP's `manifest.json` pins `bundle_format_version`, the plan identity (`plan_sha256` over `export_ir_canonical_bytes`, revision metadata), per-file SHA-256/byte sizes, the chart renderer identity record and the plan's recorded limitations; ZIP entries carry a fixed 1980-01-01 timestamp recorded in the manifest (no build-time clock). Verification of a downloaded bundle: unzip, recompute every manifest hash (`exports.bundle.verify_bundle`) and resolve every `research.md` asset link (`verify_research_links`) — the db-suite `test_exports_jobs.py` does exactly this end to end with the real renderer. Expiry is honest: a past-TTL artifact answers typed `expired`/410 even before `--sweep` persists the state and clears the bytes. Rebuilding the bundle from the same plan in the same environment is byte-identical; deflate bytes are not promised identical across zlib releases — verification is hash-validated extraction, not cross-environment byte identity. Scheduling stays operator-invoked: no daemon exists in MVP.

Implemented PDF delivery (NI-059): `format:"pdf"` runs the SAME frozen-plan machinery (creation-time plan freeze, idempotent replay, lease/retry, TTL, owner-scoped bytes) and the worker renders the deterministic static report with `exports.pdf.render_pdf` (ReportLab + svglib; dependency decision in [DEPENDENCIES](DEPENDENCIES.md)). Every NI-059 honesty rule carries over from the Markdown path: the renderer is a pure function of the frozen plan and the NI-057 boundary-verified assets — no latest pointer, no network, no browser and NO screenshot path anywhere (charts are the SSR SVGs embedded as vector drawings through svglib, so a figure can never fetch anything at view time); every value comes from the plan (the per-figure exact-value appendix renders the CSV asset verbatim — missing values keep their recorded reason, bounds stay bounds, numbers are never reformatted); attribution and pins (revision, content hash, plan SHA-256, chart-definition/dataset pins, renderer identity) are printed in the document so the PDF stays verifiable without the ZIP's manifest, which remains the reference record of the Markdown bundle of the same revision. The bytes are deterministic: ReportLab `invariant` mode, fixed document metadata (no wall-clock timestamps), the DejaVu TTFs bundled inside the frozen dependency set registered explicitly (the container ships no system fonts) and fail-closed glyph coverage — byte-identical double builds are test-enforced in `apps/api/tests/test_exports_pdf.py`. No clipped content: figures are scaled to the printable width with aspect preserved (an unembeddable asset is a typed failure, never a crop) and tables wrap/split under repeating header rows. A block the renderer does not understand, a malformed SVG or an uncovered glyph fails the job typed (`pdf_render_failed`/typed detail) instead of degrading the document.
