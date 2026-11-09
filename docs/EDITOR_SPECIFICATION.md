# Investment research editor

Tiptap core/ProseMirror with React custom node views; no custom rich-text engine. [Architecture](ARCHITECTURE.md), [database](DATABASE_SCHEMA.md), [API](API_SPECIFICATION.md). P0 single-author optimistic concurrency; P2 collaboration deferred.

## Canonical schema

EditorDocument: `{schema_version:1,type:"doc",content:BlockNode[]}`. Every top-level node has `attrs.block_id:UUID`; heading nodes carry level1–3; rich text allows paragraph/text/bold/italic/link/bullet/ordered list with depth≤3. Internal paragraph/list children do not require top-level block IDs. Arbitrary HTML, iframe, executable code, unsupported marks or remote image fetch nodes are rejected. P0 no image uploads.

| Type / priority | Persisted attributes | Interaction and acceptance |
| --- | --- | --- |
| paragraph P0 | block_id; standard bounded rich-text content | Edit/paste sanitized text and marks; keyboard/IME/undo preserved |
| heading P0 | block_id, level1–3, text content | Outline/navigation uses stable IDs, not mutable text slugs |
| liveChart P0 | block_id, chart_definition_version_id, mode live/snapshot, selection, observed_dataset_version_id, snapshot_id? | Canonical ChartView node; hover/tap/table/range/filter/source/refresh; no embedded provider logic. Save resolves immutable context |
| dataTable P0 | block_id, columns (key,label,type,unit?), rows or dataset/table_ref | Small authored table or approved dataset projection; max1k cells; formulas not executable; big data uses reference and pagination |
| insight P0 | block_id, insight_id, type, classification, body, context, authored_at, modified_at, hypothesis_id? | Context-preserving observation/hypothesis/risk/conclusion; structured metadata accessible |
| hypothesis P0 | block_id, hypothesis_id, statement, assessment, authored_at, modified_at | Editable hypothesis with linked evidence counts; status manually authored with rationale |
| evidence P0 | block_id, evidence_id, hypothesis_id, classification, target_kind,target_id,explanation | Link to insight/chart block/public model/citation; target validated, no dangling private IDs |
| risk P0 | block_id, title, body, related_hypothesis_id? | Explicit counterargument card, no algorithmic probability score |
| divider P0 | block_id | Semantic separator; keyboard delete/reorder |
| modelResult P1 | block_id, model_run_id, dataset_version_id, interpretation rich text | Immutable published run; coefficients/diagnostics read-only, narrative editable |

Citation attributes use a structured `{artifact_id|source_id,url?,label,locator?,accessed_at?}` object with a server-approved immutable artifact where possible; external URL-only citations are marked weaker and never a substitute for missing dataset provenance. Context contains chart/model and inspected selection/dataset definition hashes as in API. User/owner ID is server-derived, not trusted editor attrs.

**Implemented contracts (NI-046):** the typed annotation contracts for these four node families live in `apps/api/src/near_api/insights/schemas.py` (`InsightInput`/`Insight`, `HypothesisInput`/`Hypothesis`, `EvidenceInput`/`Evidence`, `RiskInput`, frozen `ResolvedContext`/`ModelContext`) and are published in the OpenAPI components for the generated TS client; the enum values and the rich-text body grammar are derived from the canonical validator above (one authoritative schema), not re-declared. `authored_at`/`modified_at` are persisted node attributes whose values the server authors when an annotation is created or mutated (inputs reject client-supplied timestamps and any owner field; entity ids are allocated once — uuid4 semantics, never content-derived — and persist unchanged across revisions so outline anchors and evidence links survive text edits). Convenience REST mutations of these nodes arrive with NI-047/NI-048/NI-049 and reuse these models.

## Persistence and revisions

The complete JSON is canonical. Each save creates an immutable document_versions row plus validated document_blocks/insights/hypotheses/evidence projections atomically. Insights endpoints are convenience editors of this same JSON, not a second database text source. See schema for composite FKs.

Autosave after 1s idle, max5s while typing; manual Save immediate. Retain dirty buffer during pending save; only mark revision content clean if its captured editor state matches acknowledged payload. Changes typed while request runs remain dirty. Use If-Match with last revision and an idempotency key per payload. Do not enqueue unlimited writes: at most one in flight, latest subsequent state coalesced. On 409 stop autosaving, preserve local version, show conflict options; never silently overwrite.

Server validates 2 MiB/200 top-level blocks, unique IDs, nesting/marks, filtered charts, public data visibility, same-owner snapshots, same-document private links and all dependencies. Title rename also creates a version, ensuring export title/content attribution are consistent. Empty document is valid. Revision pin creation and projections are a single transaction.

Schema migrations are explicit pure version→version transforms with fixture tests and a new revision. Old revisions remain immutable; unsupported versions open read-only with a recovery download and actionable message. Never reinterpret unknown nodes and discard their content.

## Live versus fixed evidence

A live working chart may query newest approved data and show “updated since last save”. The chart's inspected/observed version is submitted and validated when saving; save pins exactly that version. If new data arrives between inspection and save, preserve the inspected version and indicate newer available data, rather than changing evidence silently. The revision's resolved_contexts map contains dataset/chart/metric/renderer versions, filters, selected dates and context hash for every chart.

Opening a historical revision or exporting never resolves latest. Reopening the current working document can show live data alongside a saved-version badge; existing insight contexts always retain their own inspected pins. Explicit P1 Freeze changes mode and creates a private snapshot; unfreezing is a new document revision. Delete/revoke a referenced private snapshot is blocked while referenced. Missing frozen artifacts are a reconstruction error, not a reason to substitute current data.

## Block operations and focus

Insert via slash menu, toolbar or library at selected top-level position; moving a block updates order, preserves ID/insights; duplicate allocates new block and entity IDs and rewrites internal relationships only within the copied set. A duplicated single evidence block may still link to its existing hypothesis in the same document. Deleting a hypothesis/insight/chart target requires explicit linked-evidence removal or rejection; UI previews affected links.

After insertion focus first editable field; atomic chart node selected with keyboard and properties toolbar. Up/down reorder buttons announced through polite status. Outline follows heading IDs. Escape exits chart controls to editor without discarding input. Test undo/redo across node insertion/deletion and prevent chart React updates replacing the ProseMirror selection. Prototype IME/paste and chart event handling before broad integration (NI-038).

## Templates, duplication and export

P0 start empty. P1 template headings: Executive Summary, Investment Hypothesis, Adoption Evidence, Revenue Analysis, Token Economics, Econometric Results, Risks, Conclusion. No fabricated paragraphs or numerical placeholder claims. Public duplication clones a specified public release into new private IDs and retains attribution/data/model pins. Public subsequent edits do not mutate copies.

P0 export uses the exact acknowledged document revision; renders all block types to Markdown with static chart files, CSV and evidence/model citations. Unknown/unrenderable nodes fail explicitly. P1 PDF uses the same frozen intermediate representation; no screenshot of the live editor. [Export tasks](TASKS.md) define verification, and [chart system](CHART_SYSTEM.md) defines static rendering.

## Implemented editor state (NI-039, 2026-11-08)

The three-pane research editor lives at `apps/web/src/features/editor/` and serves
`/workspace/research/[documentId]`. State of this step, without changing the contracts above:

- **Layout.** ≥1280px shows outline / paper / context tools (collapsible); 768–1279px uses a
  collapsible inline outline and the tools drawer; below 768px the paper is the only pane and
  outline/tools open as drawers, one at a time. Block toolbar (move up/down, duplicate, delete)
  covers every structural operation with keyboard shortcuts (`Mod+Alt+↑/↓`, `Mod+Shift+D`,
  `Mod+Shift+Backspace`); reorder results are announced through a polite live region.
- **Insert set.** paragraph, heading 1–3, bullet/ordered list, dataTable, risk, divider — via
  the toolbar menu or the "/" slash menu (typing "/" in an empty top-level text block; choosing
  an item replaces that block). `liveChart`/`insight`/`hypothesis`/`evidence` authoring flows
  arrive with NI-041/NI-047/NI-048/NI-049; all four families already load, render, serialize and
  take part in every structural operation.
- **Stable IDs.** every top-level node carries an immutable `block_id`; a ProseMirror plugin
  allocates ids for Tiptap-normalized nodes (empty document, Enter split — which copies attrs and
  would duplicate the id) and never remaps them. Duplicates allocate NEW block and entity ids;
  references pointing outside the copied set are preserved (a duplicated single evidence block
  still links to its existing hypothesis/chart target).
- **Delete with links.** deleting a hypothesis/insight/liveChart that other blocks link to opens
  an explicit confirmation naming the dependent evidence/insight/risk blocks; confirming removes
  target and dependents together so a revision can never contain a dangling reference. Unlinked
  blocks delete directly and are undoable.
- **Serialization.** the Tiptap JSON ↔ canonical transform (list-name mapping, empty inline
  content, optional-null attr omission, ordered-list `start`/`type` stripping) is validated by a
  client mirror of the NI-036 validator whose issue paths/reasons are cross-verified to agree
  with `apps/api` `parse_document`; invalid or unsupported stored content opens a read-only
  recovery view with the raw content for download, never a partial render.
- **Editing depth.** dataTable cells (strings only — decimal precision stays exact, bounds
  mirrored) and risk titles are editable; rich-text bodies of annotation cards render read-only
  until the NI-047/NI-048/NI-049 forms. Saving was deliberately NOT implemented in that step:
  autosave, manual save and conflict recovery are NI-040 and are now implemented (see the
  "Implemented save service" section below); the NI-039 "saving arrives with NI-040" note is
  gone from the header, replaced by the truthful save-status line.
- **Known manual steps.** IME/paste/selection behavior needs operator browser checks (jsdom
  cannot emulate composition), carried over from the NI-038 record.

## Implemented save service (NI-040, 2026-11-08)

The persistence paragraph above is implemented in `apps/web/src/features/editor/persistence/`
and wired into the NI-039 workbench; contracts are unchanged:

- **Scheduling.** Autosave fires after a 1s idle window and at a hard 5s ceiling while typing
  continues; manual Save (toolbar button or Mod+S) is immediate and cancels the pending
  timers. Content is captured when a save fires, not per keystroke; the loaded (already
  validated) content is adopted as the acknowledged baseline, so the editor's own
  normalization of an empty document never produces a phantom revision and content equal to
  the baseline never saves.
- **One request in flight; coalescing.** A change during a pending request is coalesced;
  the acknowledgement re-evaluates the captured state and only an exact match with the
  acknowledged payload marks the revision clean — changes typed while the request ran stay
  dirty and are scheduled (immediately after a manual save, else after the idle window).
- **CAS/idempotency.** Every attempt sends `If-Match: "<revision>"` and a client-generated
  UUID `Idempotency-Key`. A retry after an unknown-outcome (transport) failure reuses the
  SAME attempt (and key), so a committed save replays the original 201 instead of
  duplicating a revision; an explicit new decision (conflict overwrite) starts a fresh key.
- **Truthful status.** The header shows one honest state: all changes saved (with the UTC
  saved-at time and revision), unsaved with the autosave schedule, saving, offline queue
  ("changes are held in this tab…"), saving paused after a conflict, or a typed error with
  the content retained. The unload warning covers every unacknowledged state.
- **Conflict recovery.** A 409 REVISION_CONFLICT stops autosaving and opens an explicit
  dialog naming the server's current revision (from the typed `current_revision` detail)
  against the editor's held revision. Options: overwrite the server version (CAS against
  the reported revision, only through the dialog button), load the server version
  (discards local edits, explicitly labeled), download the local copy (JSON, no API
  needed), save a copy as a new document (POST /documents + first revision, then
  navigation), or keep editing (autosave stays paused, status bar keeps the review entry).
  A raced overwrite that 409s again re-surfaces the dialog with the fresh revision.
- **Offline queue and errors.** A transport failure retains the attempt with its
  idempotency key, reports the held state honestly, and retries on the browser `online`
  event or the explicit Retry button; newer edits coalesce behind the retained attempt.
  401/404/413/422 are typed errors that keep the content; editing resumes scheduling only
  where editing can fix the failure (validation/size), not auth or deletion.
- **Recovery draft.** While content is unacknowledged, the latest captured state is written
  to `sessionStorage` (throttled to the idle window, also on unload) under a per-document
  key and cleared once the server acknowledges. On load, a differing draft is offered with
  an explicit Restore/Discard choice; a draft failing the canonical validation says why and
  offers discard only. Storage failures degrade honestly (no draft, autosave still active).

## NI-041 insertion integration

Confirmed Add Chart from a resolved public detail appends through the owned revision-checked endpoint and stores the inspected definition/dataset/range/filters with its frozen context. Canonical chart selections preserve registered source/recipient/price-basis dimensions as bounded strings; the server checks options against the immutable chart version. The client selection type is generated from OpenAPI. The liveChart node displays the inspected context on reopen and now renders interactively through NI-042 below. Subsequent prose saves carry unchanged server contexts forward verbatim. Explicit selection or pin changes submit the validated inspection context. Password and demo sign-in retain the internal pinned chart continuation, and document mutations/autosave supply Origin/CSRF through the same-origin gateway. [Synthetic insertion/reopen evidence](qa/ni041-chart-insertion-mobile.jpg) includes a saved text edit with the chart pin retained; it does not claim physical-phone release QA.

NI-041 review correction: retries are scoped to the concrete destination for chart insertion and document-version saves. Same-user focus checks hide/revalidate private action UI while retaining confirmed attempt state; identity changes discard it. Closing an uncertain insertion keeps its keys for retry, while acknowledged success followed by another confirmation starts a new intent.

## Implemented interactive chart node (NI-042, 2026-11-08)

`blocks/live-chart.tsx` now reuses the explorer's canonical `ChartView`, option builder, modular ECharts SVG runtime, exact-value table and Sources & definitions drawer. It loads the node's immutable definition/dataset/range/filters through the owner-scoped chart-view endpoint; opening, typing and saving prose never query latest or rewrite chart attrs. The block labels live policy separately from its saved observation and the frame's pinned historical data. Save status reports saved/unsaved document edits; adopting a different dataset also shows an explicit change badge.

Native range presets and a bounded custom UTC `[start,end)` range plus registered filter options inspect a prospective selection first. Apply/Refresh becomes one undoable node attribute transaction only after resolution succeeds and still matches the current node and account. Refresh explicitly requests latest for the same definition/range/filters and adopts the returned UUID. Errors leave the original pin intact. Definition ID/version, renderer, displayed dataset and context hash are inspectable.

Chart controls remain outside editable prose. Escape from a chart control selects the chart and returns editor focus; a source dialog handles its own first Escape and returns to its trigger. Typing, deletion/reorder and undo remain ProseMirror operations. Prospective edits keep the matching control DOM mounted; inactive Apply uses aria-disabled plus a no-op handler so acknowledging a successful edit does not blur its focused button. New inspection requests supersede pending reads through abort/generation checks. Async chart results are aborted/generation guarded and proposed edits commit only after reconciled identity/attrs checks, including an account suspension or Undo batched with a response. A loaded plot is keyed to its exact inspected context and is hidden if the node changes while reconstruction fails; stale data is never labeled with another selection. One account guard per chart-bearing document clears/hides chart UI during focus/auth/storage/visibility revalidation; a different verified subject must reopen the owner-checked document. Restoring a chart-bearing local draft into a chart-free document enables this guard from the CURRENT editor content.

Failures stay inside the chart: unsuccessful source queries do not dirty the node, and plot factory/setOption failures retain the exact data table and retry action. The shared renderer now gives its plot host an explicit 320px default height (or caller-supplied height), avoiding zero-height ECharts mounts. [Synthetic Chrome page-only evidence](qa/ni042-editor-chart-360.png) shows the real production renderer at CSS width 360px, measured document width 360px and plot height 320px, with internally scrolling data and retained prose. Native Chrome also verified prose typing/undo, source-dialog Escape focus return and an explicit preset saved as revision 9. This is desktop responsive emulation; physical-phone behavior remains NI-064. The synthetic browser fixture hold expired after these checks, so its automated integration was separately rerun without a hold.

## Frozen revision reader (NI-043)

Revision history lists the document's owned revisions newest first. Opening a revision loads its canonical paper read-only and resolves each chart through that revision and its saved block ID. The reader uses the shared renderer, exact table and source drawer. Download saved CSV uses the same frozen context. A reconstruction error stays inside the affected chart so the saved prose remains readable. Private requests are cancelled and cleared when the session is rechecked.

In the working editor, a successful range/filter edit or Refresh submits a typed observation with the save. A newer compatible publication can appear as “Newer approved data available” after the save while the chart continues to show the inspected version. Applying a new dataset requires explicit Refresh.

## Chart insight authoring (NI-047)

Add Insight from a saved chart opens a form with its exact dataset, UTC window, filters and observation time. The author chooses a type, classification, note and optional existing hypothesis. A public chart offers the same fields after sign-in and owned document selection. The confirmed public attempt retains the inspected version, note and retry key through a lost response.

Edit insight updates the saved annotation through the revision API and preserves its evidence context. Delete insight previews the affected evidence blocks and requires explicit confirmation to remove them in the same revision. The editor adopts the server-acknowledged revision when its local paper still matches the starting state. A stale CAS response leaves the draft open for recovery.

## Hypothesis authoring (NI-048)

Add hypothesis inserts a new card after the selected saved block, or starts an empty paper. The statement and the author's assessment can be edited on the saved card. Authors choose Untested, Supported, Mixed, Weakened or Insufficient data. The card lists evidence from the same revision separately. The outline selects the card by its stable block ID, and Properties shows its hypothesis ID. Historical papers keep their own text, assessment and evidence counts.

Edits keep the original IDs and author time, including when evidence already links to the hypothesis. Delete hypothesis, the block toolbar and keyboard deletion of a selected hypothesis use the same confirmation. Cleanup removes linked evidence blocks and clears hypothesis links from insights and risks while keeping their authored content. A stale revision keeps the draft and requires review before retrying. If the same hypothesis has changed, reopen its current revision before editing it.

The synthetic desktop smoke test created a card with Insufficient data, changed the statement and assessment to Mixed, and reopened revision 3 with the same hypothesis ID. [Desktop evidence](qa/ni048-hypothesis-desktop.jpg)

## Evidence links (NI-049)

Add evidence on a saved hypothesis opens the picker. The editor offers saved insight and chart targets from this research and paged public model runs or citations. The author selects Supporting, Contradicting or Uncertain and records an explanation. Different classifications can coexist on the same hypothesis. Counts describe linked evidence separately from the authored assessment.

Edit evidence link preserves its IDs while letting the author change the relationship. A stale save retains the explanation and requires review of the refreshed revision. If a private target changed or disappeared, the author explicitly selects a target again. Delete evidence link, the toolbar and keyboard deletion of a selected evidence block open the same confirmation. Removing the link leaves the hypothesis and target intact. Deleting a selected chart or insight with dependent evidence previews the affected links. Duplicating one evidence block allocates new IDs and keeps references to its existing targets. Reopening a historical revision retains its original links.

The synthetic desktop smoke test added a contradicting citation beside an existing supporting citation and reopened revision 4 with both links and the original Untested assessment. [Desktop evidence](qa/ni049-evidence-desktop.jpg)

## Evidence navigation and research context panels (NI-050)

The tools pane carries a read-only "Evidence and arguments" section (`evidence/evidence-panel.tsx`) next to Properties: per-hypothesis evidence lists with counts by classification (supporting/contradicting/uncertain) read from the owner-checked `GET /api/documents/{id}/evidence` surface, contradicting entries surfaced as the hypothesis's counterarguments, related risk blocks, and explicit empty states — missing evidence is never fabricated, and the classification wording stays editorial, never a confidence claim. The list is the server's saved-revision view; while the paper has unsaved edits the panel says so, and it refetches when the acknowledged revision changes.

Evidence entries navigate click-through to their target block in the paper (chart block by `block_id`, insight by entity id; public model/citation targets are reported honestly as outside the paper), after which the block's own pinned-context controls provide the source hop. A "Back to the evidence list" control and Escape (inside the panel) return keyboard focus to the originating entry. Navigation only moves the ProseMirror selection — it never rewrites block attributes, insight contexts or saved pins, and never dirties the document. The public explorer's Add Insight keeps its NI-047 destination-selection flow; the created insight freezes the inspected context exactly like the editor dialog and then participates in the same navigation graph.
