# User journeys

Routes: [information architecture](INFORMATION_ARCHITECTURE.md). Contracts: [API](API_SPECIFICATION.md). Each flow must be exercised with real persisted state, not only screenshots.

## J1 — Reviewer follows the public thesis (P0)

Anonymous user opens `/`, selects Read the Research, reads executive summary and H1–H4 findings. Selecting a quantitative citation opens source details with period, units, definition, quality and dataset ID. Open Chart navigates to `/charts/[chartId]` with that pinned dataset; Model opens a published run and its reproduction manifest. No login is required. An unresolved hypothesis has an insufficient-data explanation, never a supported badge. Acceptance: reviewer traces one supporting and one contradicting claim to a saved source/calculation and can download permitted reproduction assets. Tests: publication projection excludes private content; stale and unavailable sources remain intelligible.

## J2 — Explore and save a chart (P0)

User opens Data, selects Intents & Adoption or Token Economics, sets valid dates and inspects a point/table. Save Chart prompts login when anonymous, preserving only the chart context. Authenticated user confirms Save and sees it in Saved Charts. The server uses the verified owner, validates chart version/filters and stores the instance. A later source refresh updates a live saved-chart view with a badge; it does not alter old document evidence. Failed saves show Retry without a false success toast. Tests: source labels persist, duplicate submit is idempotent, Bob cannot read Alice's saved chart.

## J3 — Create private research and add a chart (P0)

User chooses Create New Research from Home/My Research, supplies a title, receives an empty document and editor URL. P1 adds the eight-section template choice. In the explorer, Add to Research opens a picker of this user's documents plus Create New. Confirming resolves the latest approved data to an immutable version, appends one chart block with a unique block ID in a revision-checked transaction, and links back to the document. If it changed concurrently, fetch latest and request retry; never overwrite existing prose. Acceptance: reopen preserves chart/range/source pin and interactive live controls. Tests: incorrect owner/reference, double-click and concurrent edits.

## J4 — Attach insight and opposing evidence (P0)

User inspects chart/model context, chooses Add Insight and records type `observation|hypothesis|risk|conclusion`, classification `supporting|contradicting|uncertain`, text and optional hypothesis. Server freezes the inspected context (including selected date interval, dataset and filters), associates the document/block, and saves atomically with its revision. A hypothesis has text and evidence links; classification is editorial, not a statistical confidence score. Evidence may be an insight or pinned chart/model reference. Changing the chart view later does not rewrite the insight. Tests: preserve original context after refresh, show orphan/reference warning on proposed block removal, reject cross-document private references.

## J5 — Edit, save and recover (P0)

User types, inserts/removes/duplicates/reorders blocks and follows the outline. After 1s idle, autosave submits content with the last revision via If-Match. UI moves Dirty → Saving → Saved only on acknowledgment; max wait 5s while typing. Network loss shows Unsaved and keeps an in-memory recovery buffer. Reconnection retries the same idempotency key unless content changed. A 409 opens a conflict dialog: reload remote after downloading local recovery JSON, or save the local copy as a new private document. No silent last-write-wins. Session expiry asks for login while preserving this tab's buffer. Refresh/tab-close warns if unsaved; persistent browser recovery is opt-in because it stores sensitive research locally. Tests include reload, expired auth, timeout-after-commit and two tabs.

## J6 — Inspect reproducible econometrics (P0)

User opens Models; sees specification, admissible data and limitations before results. Open a published run to inspect sample, coefficients/intervals, diagnostics, exclusions and mechanical-relationship warning. Download manifest/source instructions; execute the fixed recipe offline. No arbitrary code or paid request is triggered by opening the page. If readiness fails, show exact reasons and the limited alternative analysis, never fabricated coefficients. P1 Add Model to Research stores the immutable run ID with an interpretation note. Test both publishable and rejected runs.

## J7 — Export the evidence used (P0)

From editor, choose Export → Markdown bundle. Server first saves/validates the current content, pins live references in that revision, and enqueues export using its exact version ID. Poll job status; download ZIP containing research.md, chart SVG/PNG assets, CSV data, model references and manifest.json. User receives failed-reference details if an input cannot be reconstructed; no export claiming complete evidence is produced silently. Edit-after-request does not change the export. Job/download are owner-protected and expire. P1 PDF follows the same manifest. Tests: unzip and inspect source links, compare chart CSV hashes to revision, denial for Bob, private response no-store.

## J8 — Duplicate public research (P1)

Authenticated user chooses Duplicate into Workspace. The server clones an explicit immutable public revision under a new owner and new document/block/insight/hypothesis IDs, rewrites internal links, preserves public dataset/chart/model pins, and stores attribution to the source release. It excludes private editorial notes. Idempotent retry returns the same copy. Changes in the copy cannot mutate the public release. Test the ID remap and subsequent independent edits.

## J9 — Source failure and revision (P0)

Operator ingestion receives an error/revised historical observation. On failure, last successful approved dataset stays active; API exposes freshness lag and provider error class without credentials. On revision, build a new immutable version, compare affected dates and publish only after validation. Existing research revisions/models remain pinned. Live views show “data revised” with old/new version links. Test 429, timeout, partial pagination and changed metric definition.
