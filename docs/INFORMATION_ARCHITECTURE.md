# Information architecture

## Blog / research publications — implemented locally, 14 November 2026

The [publication brief](BLOG_PUBLICATIONS.md) is implemented through NI-085:

- `/blog` — public catalog of curated, actually available research articles.
- `/blog/[slug]` — shared article route for registered local editorial entries;
  an unknown or malformed slug produces the generic article 404.
- `/blog/near-thesis-2026-11` — permanent 308 alias to the original `/research`.
  The first catalog card links directly to `/research`, which remains canonical.

The full original article, fifteen sections, H1–H4/claim/evidence anchors, release
identity and interactive charts remain at `/research`. Blog is the primary
navigation label; it is active on both catalog/article routes and `/research`.
The article has a backlink to the catalog. A future real entry uses the curated
publication registry and shared article template, without copying the entire
original thesis route. No synthetic/demo/private publication populates Blog.
New articles do not silently rewrite earlier conclusions or pinned evidence.

Canonical product name: NEAR Intelligence. Labels and routes below override the earlier `product-plan` route proposal. Navigation is data-driven with `{label,href,group,icon,priority,enabled}`; desktop and mobile use one registry.

## Public navigation

| Label | Route | Content / authentication |
| --- | --- | --- |
| Overview | `/` | Product introduction, the featured research, data directions and `/#how-it-works` with links to the hypotheses, charts and workspace (NI-086, NI-088) |
| Blog | `/blog` | Public research-article catalog; active on article pages and `/research` (NI-085) |
| Original research | `/research` | First full article, canonical stable H1–H4/claim/evidence anchors; linked from Blog |
| Article | `/blog/[slug]` | Curated editorial article; first original-research slug aliases `/research`; unknown slug 404 |
| Data | `/data` | Data explorer overview: the five categories below with live availability or honest explanations; public (NI-015) |
| Data category | `/data/[category]` | `network`, `intents`, `revenue`, `token-economics`, `ecosystem`; same analytical components as workspace; public (NI-015) |
| Data chart | `/data/[category]/[chartId]` | Chart detail through the same shared implementation as `/charts/[chartId]`, mounted under the category; public (NI-015) |
| Chart library | `/charts` | Search and category filters over compact chart rows. Unavailable entries are labeled. Descriptions, units and availability reasons are on the chart detail (NI-034, NI-087). |
| Chart | `/charts/[chartId]` | Shareable chart detail with a validated selection URL, exact values and a Sources & definitions drawer (NI-088) |
| Methodology | `/methodology` | Definitions, sources, diagnostics and reproduction; public |
| Models | `/models` | Catalog of published model runs with the honest "no published model yet" empty state; public (NI-054) |
| Model run | `/models/[runId]` | One published run: limits and prohibited labels before any coefficient, recorded values verbatim, mechanical question/readiness, manifest download with offline verify pointer; public (NI-054) |
| Sign in | `/login` | Email/password sign-in and registration links |
| Sign up / recovery | `/signup`, `/reset-password`, `/auth/callback` | Provider auth flows |

Use `/research#h1` through `#h4`, `/methodology#sources` and `#reproduce` as stable editorial anchors. The research route (NI-014) additionally exposes fifteen thesis-section anchors (`#executive-summary`, `#question`, `#ecosystem`, `#intents-mechanism`, `#adoption`, `#revenue-generation`, `#revenue-capture`, `#token-economics`, `#econometrics`, `#alternative-explanations`, `#risks`, `#scenarios`, `#assessment`, `#limits`, `#sources-reproducibility`); the hypothesis anchors live inside `#question`. The approved Overview (NI-086) retains `/#evidence` and `/#findings` as compatible section destinations, with detailed source-qualified metrics and supporting/contrary claims remaining in the linked research/data pages. `/#mechanism` and `/#release-status` retain meaningful workflow/methodology entry points and links to the owning evidence/status sections. Unpublished model runs never resolve publicly.

The public header highlights Data on the explorer and chart library routes, and Models on the catalog and run routes. The workspace sidebar highlights the owning section on document, revision and saved-chart detail routes. Sign-in and registration share an account layout with links to each other and to Overview.

## Workspace sidebar

| Group | Label | Route | Priority |
| --- | --- | --- | --- |
| Workspace | Home | `/workspace` | P0 |
| Workspace | My Research | `/workspace/research` | P0 |
| Workspace | Saved Charts | `/workspace/saved-charts` | P0 |
| Workspace | Chart library | `/workspace/charts` | P0, direct catalog entry (NI-099) |
| Data Explorer | Network Activity | `/workspace/data/network` | P0, show availability |
| Data Explorer | Intents & Adoption | `/workspace/data/intents` | P0 |
| Data Explorer | Revenue & Fees | `/workspace/data/revenue` | P0 |
| Data Explorer | Token Economics | `/workspace/data/token-economics` | P0 |
| Data Explorer | Ecosystem | `/workspace/data/ecosystem` | P0 shell with honest gaps |
| Analytics | Econometric Models | `/workspace/models` | P0 published runs; P1 embedding |
| Account | Profile | `/workspace/profile` | P0 |
| Account | Settings | `/workspace/settings` | P0 |

Historical NI-064 decision (superseded by NI-080 below): the Data Explorer and Analytics sidebar entries previously carried the never-implemented aliases `/workspace/data/*` and `/workspace/models`, so the workspace sidebar prefetched 404s. They then targeted the implemented public routes (`/data/*`, `/models`); there is exactly one data explorer and one model catalog implementation.

The research editor opens at `/workspace/research/[documentId]`. Its Revision history link opens `/workspace/research/[documentId]/versions`. The optional `version` UUID selects a saved read-only revision with its pinned charts and CSV. Model detail stays in the workspace while displaying the same published read-only model; private arbitrary execution is excluded. No dead chart entries for unverified metrics; an empty category explains why and links to definitions.

## Context and orientation

Data query parameters: `start=YYYY-MM-DD`, `end=YYYY-MM-DD` exclusive, `frequency=day`, `dataset_version=latest|UUID`, `source_id`, and chart-specific allowed filters. Units are part of chart/metric contracts; a unit switch resolves a valid alternative metric, never relabels the same values. Saved chart IDs and document IDs stay out of public URLs. Filter changes use replace-state; navigation to a new chart pushes history.

Chart detail URLs (`/charts/{chart_id}`) carry the validated selection exactly as NI-034 implements it: `version` pins the immutable definition version, `start`/`end` the half-open UTC window within the definition version's bounded ranges, `dataset_version=UUID` pins a historical dataset (absent/`latest` resolves the newest approved one), and `filters` is a JSON object whose keys and values must come from that chart version's closed filter schema. Only these parameters are ever forwarded to the chart API; anything else in the URL — and any value failing validation — is dropped with a visible honest reason and never sent. Range and filter changes rewrite the URL with replace-state, so the chart version/range survive back/forward navigation. The library route `/charts` uses `q` (search), `category` (one of the five registry categories) and an opaque `cursor`. The model catalog route `/models` (NI-054) uses only the opaque `cursor`; the run detail `/models/{run_id}` takes no query parameters, and an unknown, unpublished or malformed run identity is one generic 404 with no existence leak.

Implemented public data explorer (NI-015): `/data` renders the five explorer categories with per-category availability derived live from one bounded catalog request; `/data/[category]` lists each category's registered charts through the same `GET /api/charts?category=…` filter as the library, or renders the category's recorded explanation when nothing is registered; `/data/[category]/[chartId]` renders the chart detail through the same selection-URL gates, catalog API, renderer and sign-in continuation as `/charts/{chart_id}` — the serialized selection is identical, so an identical selection URL resolves to an identical view request and the same pinned values. The explorer categories group the registry's closed category values, which stay canonical: `intents` ← `activity`, `revenue` ← `fees` + `treasury`, `token-economics` ← `supply`; `network` and `ecosystem` have no registered charts yet and state that honestly ("availability varies by source", "empty until source validation"), and `model` charts stay in the chart library and model section. A chart requested under a category it does not belong to is answered with the 404 boundary. The `/data` routes carry no URL parameters of their own: anything present is dropped with a rendered note and never forwarded.

Public-to-private actions preserve a short-lived internal pending action with chart ID/version/range/filter context, never serialized private document content or arbitrary redirect URLs. After authentication show a destination picker; insertion occurs only after server validation and explicit destination choice. Breadcrumbs: Workspace → My Research → document title; Data → category → chart.

At ≥1280px editor shows outline, paper and tools; 768–1279px uses a collapsible outline and drawer tools; below 768px one pane plus accessible drawers. Sidebar is a modal drawer on mobile with focus restoration. Error boundaries preserve the shell; session expiry preserves local unsaved text and returns to the same permitted internal route.


## NI-080 cabinet navigation correction — 13 November 2026

Owner feedback replaces the former public-route-only sidebar decision. The signed-in
cabinet now mounts the same shared screens at `/workspace/data`,
`/workspace/data/[category]`, `/workspace/data/[category]/[chartId]`,
`/workspace/charts`, `/workspace/charts/[chartId]`, `/workspace/models` and
`/workspace/models/[runId]`. These are implemented routes behind the workspace
session gate, not redirect aliases. Sidebar exploration, Saved Charts' Explore
charts, catalog search/category/pagination links and chart range/backlinks remain
inside the workspace shell. Public `/data`, `/charts` and `/models` routes retain
their public shells and the same canonical API/selection/rendering logic.
Network Activity and Ecosystem continue to state their actual data gaps; this
navigation correction does not create new metrics. Source documentation remains
an explicit public reference link.

Home no longer displays Data context or its indicator cards. Recent research,
saved charts/notes, Create/Continue and the research checklist remain. The Home
API's indicator contract is retained for existing consumers; it is not rendered
on the Home screen under the owner's new scope.
