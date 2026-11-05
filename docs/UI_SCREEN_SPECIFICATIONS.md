# UI screen specifications

All routes in [information architecture](INFORMATION_ARCHITECTURE.md) use [design tokens](DESIGN_SYSTEM.md). Screens share loading/empty/error/stale/unavailable semantics and ownership. P0 first; P1 affordances appear only once implemented. No dead buttons or fake live statistics.

## Public screens

| Screen | Layout and content | Actions / state acceptance |
| --- | --- | --- |
| Landing `/` | Simple nav; serif hero “The Investment Case for NEAR.”; supporting conditional thesis; ≤3 source-qualified metrics; activity→fees→revenue→conversion→retention/supply mechanism; findings for/against; workspace preview; reproducibility; repository/source footer | Read Research, Open Workspace; metric skeleton only during load, unavailable label on missing; observation date beside values, never “live” for archive |
| Research `/research` | Reading column plus sticky section outline; executive summary, question, ecosystem, Intents, adoption, revenue generation/capture, token economics, econometrics, alternatives, risks, scenarios, assessment, limits, references | Citation opens evidence/source panel; chart opens pinned detail; model opens run; P1 duplicate CTA. Research date/release version fixed; unresolved H1/H4 clearly labeled |
| Public Data `/data`, `/data/[category]` | Five category tabs/sidebar; question headline; concise availability statement; range/filter controls; selected chart rows with definitions and source panel | Browse/search/view/save/add/insight; private actions invoke login + destination choice. Empty category explains data gap; failure uses last good with stale badge |
| Chart detail `/charts/[chartId]` | Title/definition, unit and quality; plot plus accessible data table; pinned/latest mode and source/updated times; methodology link and related charts | Dates/allowed filters, inspect values, refresh, Save/Add to Research/Add Insight. Unsupported URL selection gives recoverable validation error; source gap is not zero |
| Methodology `/methodology` | Editorial sections: providers, collection/cleaning, metric catalog, model specs/diagnostics, limitations, reproduction recipe/repository | Jump links, sanitized manifest downloads; restricted raw data states explain retrieval requirements. No terminal command presented as implemented before it exists |
| Model `/models/[modelId]` | Research question and readiness first; published run picker; specification/sample/exclusions; coefficient/CI table; diagnostics and model charts; interpretation, limitations, reproduction | Inspect/download manifest; P1 Add Model. Rejected readiness shows reasons and no coefficient placeholder; no automatic scientific execution |
| Login `/login` | Compact form, email/password labels, recovery/signup links, preserved internal action summary | Submit pending/error/retry; generic invalid credentials; keyboard/password-manager friendly; session-success returns to allowed action |
| Signup `/signup` | Name optional, email/password, validation and terms links when policy exists | Check-email confirmation; avoid enumeration. No claimed successful private save before user authenticates |
| Reset `/reset-password`, callback `/auth/callback` | Request email or valid-session new-password form; callback status | Expired/invalid callback recovery; no token in displayed URL/logs; provider errors sanitized |

## Workspace screens

Shared shell: persistent group sidebar on desktop; top breadcrumb/title/account; right content workspace; mobile nav drawer. Public Data and Models link available without duplicating analytical logic. Unauthorized session redirects through safe auth with local editor buffer handling.

| Screen | Structure | Actions / required states |
| --- | --- | --- |
| Home `/workspace` | Greeting; Create New/Continue; up to5 recent docs; small recent charts/notes; workflow progress checklist; ≤3 contextual economic indicators; Explore link | First-use explanation and create action instead of fake docs; deleted recent target resolves safely; indicators can be unavailable independently |
| My Research `/workspace/research` | Title search, updated sort, document list with title/date/progress; create action | Empty document P0; P1 template. Rename and delete dialogs; pending save; pagination; 404 if inaccessible. No confidence scoring |
| Saved Charts `/workspace/saved-charts` | Search/category, saved instances showing range/mode/last resolved date, preview | Open, rename, remove, Add to Research; live changed-since-save badge; explicit snapshot badge P1; empty list directs to explorer |
| Network `/workspace/data/network` | Network question; only verified counts/fees; definitions distinguish signer/receiver/address semantics | Initial unavailable metrics remain listed in availability explanation, not fake KPIs. Show supply/header context only if relevant and labeled |
| Intents `/workspace/data/intents` | Provider volume and transaction definitions, observed cohort conversions; show series scope | Filter by approved source/category; cannot imply collector accounts equal users/integrators |
| Revenue `/workspace/data/revenue` | Gross provider fees, observed payouts and separate missing protocol revenue; explicit accrual/cash distinction | No daily capture rate without comparable daily revenue; provider differences visible, never averaged silently |
| Token Economics `/workspace/data/token-economics` | Supply boundaries/net change, purchases and lower-bound gross components | Compare same windows; label “scale comparison, not supply reduction”; exact/bounds never blended |
| Ecosystem `/workspace/data/ecosystem` | Available applications/integrations/concentration only after source validation | MVP may be informative empty state with data requirements. No collector-to-customer inference |
| Models `/workspace/models` | Same registered models/readiness/published runs, concise saved-document context | Open public detailed run; P1 insert model; private arbitrary reruns absent |
| Profile `/workspace/profile` | Display name, provider-managed identity info and timezone preference | Save/error; ID/email ownership not editable through profile. Account email/password changes through provider flows |
| Settings `/workspace/settings` | Display timezone, local draft controls, session/logout, data/privacy description, operator-assisted deletion process | Clear local drafts with confirmation; no unimplemented subscription/team/billing controls |

## Research editor `/workspace/research/[documentId]`

Header: editable title, saved/dirty/saving/error state, last saved time, manual Save, Export. Left outline from headings; central paper contains typed blocks; right contextual panel switches Add Block/Chart Library/Properties/Sources/Insight/Model. Tool panels collapse. Desktop three-pane appears only when minimum paper width fits; tablet tools as drawer; phone full paper with one drawer at a time.

Block toolbar appears on keyboard focus as well as pointer hover. Slash menu has labeled types and shortcut hints. Reorder supports drag and Move Up/Down; duplicate assigns new IDs; delete handles dependent evidence explicitly. Heading outline remains accurate after undo and reorder. Chart controls do not hijack editor typing/selection. Nested charts/atomic cards are non-editable node views with accessible Edit Properties controls.

Context panels: chart library search/preview/select with insertion location; source drawer with definition/date/quality/provenance; insight form type/classification/text/hypothesis; hypothesis card linked for/against evidence; model panel published-only P1 insertion. Show contextual selected range and pin date before saving an insight.

Critical states: initial loading skeleton (paper shape); not-owned/absent same 404; invalid legacy schema read-only recovery path; unsaved network loss; 409 conflict dialog with download-local-copy option; chart data unavailable while text remains editable; session expiry with draft preserved; export queued/running/failed/ready/expired. No “saved” indicator until server revision acknowledgement.

## Reusable dialogs and drawers

Destination picker (owned document list/Create New); source details; evidence-link picker; delete/reference confirmation; data revised comparison; document conflict; export status/download. Every overlay has title, clear primary/cancel action, initial focus, Escape behavior and return-focus. A failed mutation retains input. Unavailable source does not disable editing unrelated prose. Validate the complete J1–J9 flows, not only individual screens.
