# UI screen specifications

All routes in [information architecture](INFORMATION_ARCHITECTURE.md) use [design tokens](DESIGN_SYSTEM.md). Screens share loading/empty/error/stale/unavailable semantics and ownership. P0 first; P1 affordances appear only once implemented. No dead buttons or fake live statistics.

## Public screens

| Screen | Layout and content | Actions / state acceptance |
| --- | --- | --- |
| Overview `/` (NI-086) | Approved Comic Lab hero and TRACE artwork; one curated featured publication; three data-direction cards; Read→Inspect→Build workflow; compact methodology band; green workspace CTA | Blog/research/data/methodology/workspace links work with keyboard; historical coverage qualification; no duplicate financial/claim tables; page remains available during API outage |
| Research `/research` | Reading column plus sticky section outline; executive summary, question, ecosystem, Intents, adoption, revenue generation/capture, token economics, econometrics, alternatives, risks, scenarios, assessment, limits, references | Citation opens evidence/source panel; chart opens pinned detail; model opens run; duplication CTA (NI-045) rendered only when a release is actually published for the slug — anonymous visitors get the sign-in continuation, signed-in users the pinned-version duplicate dialog; no release, no affordance. Research date/release version fixed; unresolved H1/H4 clearly labeled |
| Public Data `/data`, `/data/[category]` | Five category tabs/sidebar; question headline; concise availability statement; range/filter controls; selected chart rows with definitions and source panel | Browse/search/view/save/add/insight; private actions invoke login + destination choice. Empty category explains data gap; failure uses last good with stale badge |
| Chart detail `/charts/[chartId]` | Title/definition, unit and quality; plot plus accessible data table; pinned/latest mode and source/updated times; methodology link and related charts | Dates/allowed filters, inspect values, refresh, Save/Add to Research/Add Insight. Unsupported URL selection gives recoverable validation error; source gap is not zero |
| Methodology `/methodology` | Editorial sections: providers, collection/cleaning, metric catalog, model specs/diagnostics, limitations, reproduction recipe/repository | Jump links, sanitized manifest downloads; restricted raw data states explain retrieval requirements. No terminal command presented as implemented before it exists |
| Model `/models/[modelId]` | Research question and readiness first; published run picker; specification/sample/exclusions; coefficient/CI table; diagnostics and model charts; interpretation, limitations, reproduction | Inspect/download manifest; P1 Add Model. Rejected readiness shows reasons and no coefficient placeholder; no automatic scientific execution |
| Login `/login` | Compact form, email/password labels, recovery/signup links, preserved internal action summary | Submit pending/error/retry; generic invalid credentials; keyboard/password-manager friendly; session-success returns to allowed action |
| Signup `/signup` | Name optional, email/password, validation and terms links when policy exists | Check-email confirmation; avoid enumeration. No claimed successful private save before user authenticates |
| Reset `/reset-password`, callback `/auth/callback` | Request email or valid-session new-password form; callback status | Expired/invalid callback recovery; no token in displayed URL/logs; provider errors sanitized |

## Workspace screens

Shared shell: persistent group sidebar on desktop; top breadcrumb/title/account; right content workspace; mobile nav drawer. Data, charts and models have workspace routes that reuse the public analytical screens and preserve the cabinet shell. Unauthorized session redirects through safe auth with local editor buffer handling.

| Screen | Structure | Actions / required states |
| --- | --- | --- |
| Home `/workspace` | Research-context introduction; Create New/Continue; up to5 recent docs; small recent charts/notes; workflow progress checklist; no Data context section (owner NI-080 correction) | First-use explanation and create action instead of fake docs; deleted recent target resolves safely; Home does not render economic indicator cards |
| My Research `/workspace/research` | Title search, updated sort, document list with title/date/progress; create action | Empty document default; investment-v1 template choice (NI-045, keyboard-accessible, empty preselected). Rename and delete dialogs; pending save; pagination; 404 if inaccessible. No confidence scoring |
| Saved Charts `/workspace/saved-charts` | Search/category, saved instances showing range/mode/last resolved date, preview | Open, rename, remove, Add to Research; live changed-since-save badge; explicit snapshot badge P1; empty list directs to explorer |
| Network `/workspace/data/network` | Network question; only verified counts/fees; definitions distinguish signer/receiver/address semantics | Initial unavailable metrics remain listed in availability explanation, not fake KPIs. Show supply/header context only if relevant and labeled |
| Intents `/workspace/data/intents` | Provider volume and transaction definitions, observed cohort conversions; show series scope | Filter by approved source/category; cannot imply collector accounts equal users/integrators |
| Revenue `/workspace/data/revenue` | Gross provider fees, observed payouts and separate missing protocol revenue; explicit accrual/cash distinction | No daily capture rate without comparable daily revenue; provider differences visible, never averaged silently |
| Token Economics `/workspace/data/token-economics` | Supply boundaries/net change, purchases and lower-bound gross components | Compare same windows; label “scale comparison, not supply reduction”; exact/bounds never blended |
| Ecosystem `/workspace/data/ecosystem` | Available applications/integrations/concentration only after source validation | MVP may be informative empty state with data requirements. No collector-to-customer inference |
| Models `/workspace/models` | Same registered models/readiness/published runs, concise saved-document context | Open detailed run inside workspace; P1 insert model; private arbitrary reruns absent |
| Profile `/workspace/profile` | Display name, provider-managed identity info and timezone preference | Save/error; ID/email ownership not editable through profile. Account email/password changes through provider flows |
| Settings `/workspace/settings` | Display timezone, local draft controls, session/logout, data/privacy description, operator-assisted deletion process | Clear local drafts with confirmation; no unimplemented subscription/team/billing controls |

Implemented Home (NI-024): Create document immediately persists “Untitled
research” and opens its owned editor after acknowledgement; an uncertain retry
retains its idempotency key. Continue opens the most recently updated owned
document. The four workflow steps refer only to that document's current revision
(creation, heading, chart, insight); the checklist never rates a claim. Recent
notes are existing canonical saved insight projections, not a new insight
authoring flow. A focus/auth check hides private state until the account can be
checked again, and a different account discards pending continuation state.
NI-080 removes the Data context section and its economic indicator cards from Home; the canonical indicator API remains available without being rendered here.

## Research editor `/workspace/research/[documentId]`

Header: editable title, saved/dirty/saving/error state, last saved time, manual Save, Export. Left outline from headings; central paper contains typed blocks; right contextual panel switches Add Block/Chart Library/Properties/Sources/Insight/Model. Tool panels collapse. Desktop three-pane appears only when minimum paper width fits; tablet tools as drawer; phone full paper with one drawer at a time.

Block toolbar appears on keyboard focus as well as pointer hover. Slash menu has labeled types and shortcut hints. Reorder supports drag and Move Up/Down; duplicate assigns new IDs; delete handles dependent evidence explicitly. Heading outline remains accurate after undo and reorder. Chart controls do not hijack editor typing/selection. Nested charts/atomic cards are non-editable node views with accessible Edit Properties controls.

Context panels: chart library search/preview/select with insertion location; source drawer with definition/date/quality/provenance; insight form type/classification/text/hypothesis; hypothesis card linked for/against evidence; model panel published-only P1 insertion. Show contextual selected range and pin date before saving an insight.

Critical states: initial loading skeleton (paper shape); not-owned/absent same 404; invalid legacy schema read-only recovery path; unsaved network loss; 409 conflict dialog with download-local-copy option; chart data unavailable while text remains editable; session expiry with draft preserved; export queued/running/failed/ready/expired. No “saved” indicator until server revision acknowledgement.

## Reusable dialogs and drawers

Destination picker (owned document list/Create New); source details; evidence-link picker; delete/reference confirmation; data revised comparison; document conflict; export status/download. Every overlay has title, clear primary/cancel action, initial focus, Escape behavior and return-focus. A failed mutation retains input. Unavailable source does not disable editing unrelated prose. Validate the complete J1–J9 flows, not only individual screens.


NI-080 owner correction (13 November 2026): Home omits Data context entirely.
Saved Charts Explore charts opens `/workspace/charts`; the explorer sidebar
opens `/workspace/data/[category]`. Shared category, catalog, chart-detail and
model screens retain their current workspace shell through internal navigation
and selection changes. Public entry points still use the public shell. Empty
Network Activity/Ecosystem states explain missing approved definitions rather
than inventing data.


NI-081 local public methodology design (13 November 2026): reader-facing editorial
hero and six-chapter index; human source families, metric meanings/limits,
preparation/version flow, chart inspection, interpretation limits and
reproducibility. Full source register/rights, exact technical validation,
readiness policy and real commands remain in native disclosures. Canonical
sources/definitions/collection/readiness/reproduce anchors remain; verify adds
the reader inspection path. Main prose contains no NI task codes or operator
backlog. Existing public palette and typography are retained.


NI-081 owner follow-up (13 November 2026) replaces the initial disclosure design:
remove all five public methodology technical appendices and their contents.
Do not convert them into open sections or hidden markup. Preserve the explanatory
six-chapter article, canonical reading anchors and visible evidence limitations;
the full source/metric/model/reproduction records remain internal documentation.


## Blog — NI-085, 14 November 2026

Public `/blog` uses the existing ivory/navy/green editorial design and links to
one real full research publication. Its card carries title, research question,
summary, topic/format, known release label and actual evidence scope; no fake
additional cards, authors, dates or financial figures. Data/methodology links
remain available. Blog replaces Research as the public navigation entry and
stays active while reading `/research`; that original article has a catalog
backlink and retains its full sections, claims and interactive history.
Curated future articles share a template with optional verified dates/authorship,
source sections and existing related-article links. Unknown article slugs have
a generic 404 with a route back to Blog. The original slug redirects to its
canonical `/research`; no private document appears by enumeration.

## Published model pages — readable presentation (NI-097)

The public /models catalog and /models/{run_id} result pages render through the NI-097
presentation layer (features/models/presentation.ts): the recorded run remains the single
source of truth, and a curated mapping exists only for the published
gross_fee_activity_v1 specification. The result page answers, in order: what the model
compares, what it found, what the numbers mean, which conclusions are allowed, and where
the diagnostics/method/reproduction live — via four keyboard-accessible tabs (Result /
Diagnostics / Specification / Reproduction). The summary surface rounds for display and is
marked as rounded; the recorded floats, every gate limit code, the admission reasons and
the verbatim specification/estimation/diagnostics/environment blocks stay reachable in the
Exact-coefficients, All-recorded-limitations and raw-verbatim disclosures. The finding text
is sign-aware: it is selected from the recorded slope's confidence interval, so a positive
finding is never presented for a negative or unresolved result. Unknown specifications get
an identity-preserving fallback built from their recorded fields. The manifest download,
Add to research and the anonymous sign-in continuation behave exactly as before.


## Comic Lab desktop implementation — NI-099, 22 November 2026

The owner-approved A / Comic Lab appearance replaces the earlier editorial
appearance across the existing routes. The canonical graph wordmark, Rubik /
Golos Text / IBM Plex Mono, ivory reading surfaces, mint actions, ink outlines
and neutral offset shadows come from the shared tokens/components. Public
and workspace navigation use a visible mint selected route. TRACE appears on
Overview, auth, the personal workspace's Continue panel and empty Saved Charts;
no chart/data/error view is replaced with an illustration.

Workspace Home retains its real owned document, progress and recent evidence
queries; the Continue panel becomes white paper, the research checklist is a
yellow supporting card, and recent insight notes are lavender. Public Overview
keeps its approved discovery sections and existing anchors. The Blog card uses
registered topic/question/release metadata in an outlined mint-cover layout.
The original publication/article content, scientific qualifications, existing
chart renderer and frozen export palette remain unchanged. Native forms,
menus, dialogs, saved cards, model panels and the editor share the same border,
control, paper and heading treatments. Existing loading/empty/error states,
keyboard semantics and ownership guards remain in use.

This is a frontend desktop redesign. No new mobile layouts, provider calls,
metric definitions, document schema or private-resource behavior are added.
