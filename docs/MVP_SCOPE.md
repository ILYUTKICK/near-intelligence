# Strict MVP scope

The application has not been built. P0 is the minimum hackathon product; P1 enhances it; P2 is deferred. [Task priorities](TASKS.md) are normative. No fixed hackathon deadline or team capacity was supplied; do not promise calendar completion.

## P0 commitments

Public landing, full original thesis, methodology and public data explorer; shared source/metric/chart registries; daily historical analytics from saved real data; scheduled refresh for at least one approved reliable source; visibly historical fallback for any failed source. Working Supabase login, private workspace/home, saved charts, document CRUD, Tiptap editor, text/heading/chart/table/insight/hypothesis/evidence/risk/divider blocks, Add Chart, Add Insight, typed context, server ownership, autosave/reopen and reproducible published quantitative analysis. Markdown bundle export is the single reliable MVP export.

P0 live charts use canonical versioned definitions and mutable “latest approved dataset” resolution, with explicit observation/retrieval timestamps. Every document revision freezes the exact dataset resolved at save; reopening the working document in live mode may show newer data with a change badge, but historical revision/export uses the pin. This minimum pin is P0 integrity infrastructure, despite the original priority list placing advanced chart snapshots at P1. An explicit snapshot creation/browsing UX is P1.

At least one regularly refreshed real series is needed for the challenge. The saved archive alone is insufficient for a “live dashboard” release. Refresh starts only after provider entitlement, scope, quotas and data quality pass. No stopped mass collectors are restarted by the product.

## Research feasibility gate

Preferred P0 model: activity versus a comparable daily protocol-attributable revenue series. This series is not currently established. NI-051 evaluates readiness before fitting; never relabel gross fees or treasury payouts as protocol revenue.

Fallback: execute a reproducible exploratory time-series association using explicitly provider-reported daily gross fees and volume, plus sensitivity to source revisions; optionally associate observed purchases with activity. Publish it as a limited proxy analysis, state the mechanical fee-volume relationship, and leave H1/H4 unresolved. This fulfills the statistical-analysis requirement only if the hackathon's evaluation accepts this limited empirical question; OQ-02 is an external judging risk. A no-data status alone does not fulfill P0 econometrics. If no defensible series/model is available, report the release incomplete.

There are no coefficients or fitted model outputs in this documentation. NI-052–NI-054 must run and validate real models after implementation is approved.

## P1

Explicit snapshot management, default investment template and public-thesis duplication, model-result blocks in private documents, PDF export, advanced supported filters, convenient document organization. Basic save-time pins and baseline range controls remain P0. Chart library, sources and public model view remain P0.

## P2 and excluded scope

Read-only public sharing, collaboration/CRDT, LLM assistant, interpretive integrity checks, automatic hypothesis monitoring, scenario simulators, multiple chains, Strategy/Portfolio screens from the legacy plan, trading/execution, billing and teams. No AI API key is required. Stub navigation must not suggest unavailable features work.

## Release checklist

1. Original public thesis includes H1–H4, supporting and contrary evidence, assumptions and limitations.
2. Every public number can be traced to real permitted inputs and a versioned calculation; missing values have explicit states.
3. One approved real refresh demonstrably publishes atomically; outages retain last good data.
4. One published deterministic empirical model reproduces offline, with inference limits and source definitions.
5. Two users can independently save/reopen research; cross-user CRUD, references and export fail safely.
6. Complete keyboard/touch research workflow works on phone/tablet/desktop.
7. Markdown bundle includes rendered chart assets, data, notes and a manifest, pinned to one document revision.
8. Production health, TLS, restore rehearsal and judge walkthrough pass. P0 tasks complete; remaining P1/P2 is labeled.
