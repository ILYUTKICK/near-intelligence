# Information architecture

Canonical product name: NEAR Intelligence. Labels and routes below override the earlier `product-plan` route proposal. Navigation is data-driven with `{label,href,group,icon,priority,enabled}`; desktop and mobile use one registry.

## Public navigation

| Label | Route | Content / authentication |
| --- | --- | --- |
| Overview | `/` | Landing, conditional thesis and selected real metrics; public |
| Research | `/research` | Canonical published long-term thesis with H1–H4 and evidence anchors; public |
| Data | `/data` | Data explorer overview: the five categories below with live availability or honest explanations; public (NI-015) |
| Data category | `/data/[category]` | `network`, `intents`, `revenue`, `token-economics`, `ecosystem`; same analytical components as workspace; public (NI-015) |
| Data chart | `/data/[category]/[chartId]` | Chart detail through the same shared implementation as `/charts/[chartId]`, mounted under the category; public (NI-015) |
| Chart library | `/charts` | Search/category catalog of every registered chart with its honest data status; public (NI-034) |
| Chart | `/charts/[chartId]` | Shareable public chart detail with validated selection URL; public |
| Methodology | `/methodology` | Definitions, sources, diagnostics and reproduction; public |
| Models | `/models` | Catalog of published model runs with the honest "no published model yet" empty state; public (NI-054) |
| Model run | `/models/[runId]` | One published run: limits and prohibited labels before any coefficient, recorded values verbatim, mechanical question/readiness, manifest download with offline verify pointer; public (NI-054) |
| Sign in | `/login` | Email/password sign-in and registration links |
| Sign up / recovery | `/signup`, `/reset-password`, `/auth/callback` | Provider auth flows |

Use `/research#h1` through `#h4`, `/methodology#sources` and `#reproduce` as stable editorial anchors. The research route (NI-014) additionally exposes fifteen thesis-section anchors (`#executive-summary`, `#question`, `#ecosystem`, `#intents-mechanism`, `#adoption`, `#revenue-generation`, `#revenue-capture`, `#token-economics`, `#econometrics`, `#alternative-explanations`, `#risks`, `#scenarios`, `#assessment`, `#limits`, `#sources-reproducibility`); the hypothesis anchors live inside `#question`. Unpublished model runs never resolve publicly.

## Workspace sidebar

| Group | Label | Route | Priority |
| --- | --- | --- | --- |
| Workspace | Home | `/workspace` | P0 |
| Workspace | My Research | `/workspace/research` | P0 |
| Workspace | Saved Charts | `/workspace/saved-charts` | P0 |
| Data Explorer | Network Activity | `/workspace/data/network` | P0, show availability |
| Data Explorer | Intents & Adoption | `/workspace/data/intents` | P0 |
| Data Explorer | Revenue & Fees | `/workspace/data/revenue` | P0 |
| Data Explorer | Token Economics | `/workspace/data/token-economics` | P0 |
| Data Explorer | Ecosystem | `/workspace/data/ecosystem` | P0 shell with honest gaps |
| Analytics | Econometric Models | `/workspace/models` | P0 published runs; P1 embedding |
| Account | Profile | `/workspace/profile` | P0 |
| Account | Settings | `/workspace/settings` | P0 |

Research editor route: `/workspace/research/[documentId]`. Model detail links to the public read-only model; private arbitrary execution is excluded. No dead chart entries for unverified metrics; an empty category explains why and links to definitions.

## Context and orientation

Data query parameters: `start=YYYY-MM-DD`, `end=YYYY-MM-DD` exclusive, `frequency=day`, `dataset_version=latest|UUID`, `source_id`, and chart-specific allowed filters. Units are part of chart/metric contracts; a unit switch resolves a valid alternative metric, never relabels the same values. Saved chart IDs and document IDs stay out of public URLs. Filter changes use replace-state; navigation to a new chart pushes history.

Chart detail URLs (`/charts/{chart_id}`) carry the validated selection exactly as NI-034 implements it: `version` pins the immutable definition version, `start`/`end` the half-open UTC window within the definition version's bounded ranges, `dataset_version=UUID` pins a historical dataset (absent/`latest` resolves the newest approved one), and `filters` is a JSON object whose keys and values must come from that chart version's closed filter schema. Only these parameters are ever forwarded to the chart API; anything else in the URL — and any value failing validation — is dropped with a visible honest reason and never sent. Range and filter changes rewrite the URL with replace-state, so the chart version/range survive back/forward navigation. The library route `/charts` uses `q` (search), `category` (one of the five registry categories) and an opaque `cursor`. The model catalog route `/models` (NI-054) uses only the opaque `cursor`; the run detail `/models/{run_id}` takes no query parameters, and an unknown, unpublished or malformed run identity is one generic 404 with no existence leak.

Implemented public data explorer (NI-015): `/data` renders the five explorer categories with per-category availability derived live from one bounded catalog request; `/data/[category]` lists each category's registered charts through the same `GET /api/charts?category=…` filter as the library, or renders the category's recorded explanation when nothing is registered; `/data/[category]/[chartId]` renders the chart detail through the same selection-URL gates, catalog API, renderer and sign-in continuation as `/charts/{chart_id}` — the serialized selection is identical, so an identical selection URL resolves to an identical view request and the same pinned values. The explorer categories group the registry's closed category values, which stay canonical: `intents` ← `activity`, `revenue` ← `fees` + `treasury`, `token-economics` ← `supply`; `network` and `ecosystem` have no registered charts yet and state that honestly ("availability varies by source", "empty until source validation"), and `model` charts stay in the chart library and model section. A chart requested under a category it does not belong to is answered with the 404 boundary. The `/data` routes carry no URL parameters of their own: anything present is dropped with a rendered note and never forwarded.

Public-to-private actions preserve a short-lived internal pending action with chart ID/version/range/filter context, never serialized private document content or arbitrary redirect URLs. After authentication show a destination picker; insertion occurs only after server validation and explicit destination choice. Breadcrumbs: Workspace → My Research → document title; Data → category → chart.

At ≥1280px editor shows outline, paper and tools; 768–1279px uses a collapsible outline and drawer tools; below 768px one pane plus accessible drawers. Sidebar is a modal drawer on mobile with focus restoration. Error boundaries preserve the shell; session expiry preserves local unsaved text and returns to the same permitted internal route.
