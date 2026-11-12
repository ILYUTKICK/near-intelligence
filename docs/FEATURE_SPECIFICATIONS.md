# Functional feature specifications

Common requirements: owner from verified session; data quality/source/time visible; loading/empty/error/stale states; UTC half-open intervals; inputs validated. IDs below map to [tasks](TASKS.md) and [PRD](PRODUCT_REQUIREMENTS.md).

| Feature | Priority/dependencies | Implementation behavior and acceptance | Task IDs |
| --- | --- | --- | --- |
| F01 Landing | P0; design, public release | Hero and two CTAs; conditional mechanism, ≤3 selected metrics, findings for/against, workspace preview, reproduction/footer. Every number resolves to the published manifest; missing metrics show unavailable. | NI-011–NI-012 |
| F02 Public research | P0; evidence/metrics/model publication | Fifteen required editorial sections from executive summary to references; stable claim/hypothesis anchors; distinguish observation/estimate/scenario. No claim of fitted results before run exists. | NI-014, NI-070 |
| F03 Methodology | P0; registry/model recipe | Provider table, cleaning, definitions, assumptions, diagnostics, limitations and exact reproducibility recipe. A reviewer follows one full path offline. | NI-013 |
| F04 Explorer | P0; metric API/chart registry | Five categories; valid ranges, definitions, last observed/retrieved times; available metrics only; source/version compare. Identical public/private queries use identical service results. | NI-015, NI-031–NI-033 |
| F05 Chart library | P0; chart registry | Search title/description; category filter, preview/detail, save/add/insight actions. Unknown or unsupported filters return 422, never ignored. | NI-034–NI-035 |
| F06 Auth/profile/settings | P0; Supabase + API | Sign-up, verified email, login/logout/password recovery. Profile display name; settings timezone display preference; calculations remain UTC. Refresh invalid session safely; no email-as-owner trust. | NI-016–NI-020, NI-025 |
| F07 Workspace home | P0; document/saved APIs | Greeting, up to 5 recent documents/charts/insights, user-visible research checklist progress, ≤3 contextual indicators, create/continue/explore actions. Progress is workflow completion, not truth/confidence. | NI-021–NI-024 |
| F08 My Research | P0; document service | Title search, updated sort, create/rename/delete with confirmation and explicit irreversibility; private pagination; reopen editor. Hard deletion removes owned child metadata/jobs; public scientific inputs survive. | NI-036–NI-037 |
| F09 Editor | P0; typed schema + revision API | Text/heading/chart/table/insight/hypothesis/evidence/risk/divider; insert, reorder via keyboard/drag, duplicate with ID remap, delete with reference review, collapsible tools, autosave/conflict recovery. | NI-038–NI-040, NI-046–NI-050 |
| F10 Chart embedding | P0; immutable versions | Canonical chart reference + validated filters + explicit mode + save-time data pin. Interact/refresh/view sources/add insight; no duplicated plotting logic. | NI-041–NI-043 |
| F11 Evidence relationships | P0; insights/hypothesis schema | Link supporting/contradicting/uncertain evidence; same-document private references; pins preserve selected context; reject dangling block links or require explicit removal. | NI-046–NI-050 |
| F12 Statistical analysis | P0; readiness + locked recipe | Fixed operator-run models, reproducible published runs, full diagnostics/limits. Public sees published artifacts; user code execution and automatic model searching excluded. | NI-051–NI-054 |
| F13 Export | P0 Markdown; P1 PDF | Revision-bound ZIP with charts, notes, sources/timestamps/model refs, exact values and manifest. Expiring owner-only download; missing artifacts fail explicitly. NI-059 implemented the PDF format: the deterministic static report of the SAME frozen plan (attribution/pins, vector chart embeds from the NI-057 assets — no screenshots, exact-value appendix, source registries, provenance; `application/pdf` download of the same job lifecycle). | NI-056–NI-059 |
| F14 Snapshot UX | P1; P0 save pins | Explicit freeze/copy/browse snapshot and compare-to-live actions; immutable selection/config/hash. | NI-044 (implemented: freeze/browse/compare/delete with owner-scoped storage metadata; `copy` remains future scope) |
| F15 Templates/duplication | P1; editor/release projection | Empty P0; default eight-section template and public copy P1; new owner/private IDs and retained attribution. | NI-045 |
| F16 Model result block | P1; run API/editor | Immutable published run reference, coefficient table/diagnostics links plus editable interpretation. No recomputation on document load. | NI-055 |
| F17 Sharing | P2; frozen revision/security; required before deployment | Separate revocable read-only publication tokens and consent flow; no private URL acts as a share link. | NI-060 |
| F18 Integrity/AI | P2; proven core; required before deployment | Metadata rules can verify missing pins/citations. Interpretive checks advisory; identify evidence/context, allow dispute, no truth score. Deterministic tools supply every number; fully optional. | NI-065 |

P1 advanced supported analytical filters are implemented in NI-071; lightweight private tags/favorites in NI-072. They depend on verified source dimensions and completed P0 persistence/security, respectively. P2 scenario simulation, hypothesis monitoring, multichain expansion and collaborative editing require a separate approved design/ADR and bounded follow-on backlog after P0; they are excluded from this implementation roadmap.

**Implemented (NI-072, My Research organization):** My Research grows private organization controls that stay outside the scientific content: an accessible favorites toggle (`aria-pressed`) filtering the owner's list server-side, per-row tag chips that apply an exact server-side tag filter (AND across repeated tags), a tags edit dialog (comma-separated, bounded to 20 tags of 40 characters after the documented trim+lower normalization), and a per-row favorite toggle that updates optimistically and reverts with an honest error when the API refuses. Tag/favorite filters compose with title search inside one owner-scoped request; an empty or deleted tag filter is an honest empty state with a clear-filters recovery action, never an error. Keyboard: Up/Down arrows move between document rows in the API order and Enter opens the focused document link; every control stays in the plain tab order. Tagging/favoriting never creates a revision, never rewrites frozen evidence and never reorders the updated_at-DESC list (API_SPECIFICATION, NI-072 note); tags are private to the owning account and never shared vocabularies.

## Interaction contracts

All mutations disable duplicate submission while pending and use idempotency where creation can retry. A failed action retains user input and presents actionable error text. Save Chart creates an instance, not a new canonical chart. Add to Research chooses a private destination. Add Insight from a public chart is available after login and document selection. A missing document produces 404 for both absent and not-owned IDs.

## Content and scientific acceptance

Published thesis includes executive summary, question, ecosystem, cross-chain execution, adoption, revenue generation/capture, token economics, econometrics, alternatives, risks, scenarios, final assessment, limitations and references. Scenarios are textual/explicit assumptions in P0, not an unplanned simulator. Each H1–H4 assessment may be mixed or unresolved. Do not replace measured series with scenario output.

## Completion evidence

For each feature show acceptance in an automated domain/integration test and, when interactive, one relevant browser journey. Visual-only checks do not establish persistence or ownership. [Testing](TESTING_STRATEGY.md) specifies cross-feature failure tests; [UI screens](UI_SCREEN_SPECIFICATIONS.md) specifies all user-facing states.

## Owner release extension — 12 November 2026

All registered P1/P2 features are implemented and locally verified before deployment, rather than deferred behind the deployment P0 tasks. NI-060/065 must deliver actual features per TASKS; a design/ADR cannot satisfy them. Sharing creates an explicit frozen allowlisted publication with scoped assets and revocable/expiring hashed tokens; all private draft access remains owner-scoped. Integrity provides working deterministic checks without credentials, plus an optional explicitly enabled grounded adapter; external context transfer/provider spend still requires applicable permission. Interpretive output is advisory, never a numeric source or automatic research mutation. Preserve the existing design; verify plots, exact tables, pins, sources, ranges and export on all P1/P2 chart paths in NI-079. Other unregistered P2 concepts listed above remain excluded.
