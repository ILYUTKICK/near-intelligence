# Information architecture

Canonical product name: NEAR Intelligence. Labels and routes below override the earlier `product-plan` route proposal. Navigation is data-driven with `{label,href,group,icon,priority,enabled}`; desktop and mobile use one registry.

## Public navigation

| Label | Route | Content / authentication |
| --- | --- | --- |
| Overview | `/` | Landing, conditional thesis and selected real metrics; public |
| Research | `/research` | Canonical published long-term thesis with H1–H4 and evidence anchors; public |
| Data | `/data` | Default available category and chart catalog; public |
| Data category | `/data/[category]` | Same analytical components as workspace; public |
| Chart | `/charts/[chartId]` | Shareable public chart detail; public |
| Methodology | `/methodology` | Definitions, sources, diagnostics and reproduction; public |
| Model | `/models/[modelId]` | Published model runs/readiness/results; public |
| Sign in | `/login` | Email/password sign-in and registration links |
| Sign up / recovery | `/signup`, `/reset-password`, `/auth/callback` | Provider auth flows |

Use `/research#h1` through `#h4`, `/methodology#sources` and `#reproduce` as stable editorial anchors. Unpublished model runs never resolve publicly.

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

Public-to-private actions preserve a short-lived internal pending action with chart ID/version/range/filter context, never serialized private document content or arbitrary redirect URLs. After authentication show a destination picker; insertion occurs only after server validation and explicit destination choice. Breadcrumbs: Workspace → My Research → document title; Data → category → chart.

At ≥1280px editor shows outline, paper and tools; 768–1279px uses a collapsible outline and drawer tools; below 768px one pane plus accessible drawers. Sidebar is a modal drawer on mobile with focus restoration. Error boundaries preserve the shell; session expiry preserves local unsaved text and returns to the same permitted internal route.
