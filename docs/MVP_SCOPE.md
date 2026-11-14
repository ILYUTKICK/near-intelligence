# Strict MVP scope

P0 defines the minimum hackathon product. **Owner scope update — 12 November 2026:** all six registered P1 and both P2 tasks are now required before deployment; the current release extends the original MVP. Preserve the largely completed desktop design and prioritize working local charts. [Task priorities](TASKS.md) are normative. No fixed hackathon deadline or team capacity was supplied; do not promise calendar completion.

## P0 commitments

**Publication direction and implementation — 14 November 2026:** NI-084 records
and NI-085 locally implements a public Blog/research-article library. The complete
`/research` is its first article, with stable existing anchors and evidence.
See [the publication brief](BLOG_PUBLICATIONS.md). Shared curated metadata and an
article template support subsequent real publications. No CMS, automatic public
promotion of private drafts or daily collection is introduced. This owner-requested
batch is included in NI-079; other data/model/workspace/release gates remain.

**Approved Overview — 14 November 2026:** NI-086 implements the owner's approved
editorial design, presenting the product and its research rather than repeating
the full thesis tables on the homepage. The original NI-012 evidence-first
requirement remains satisfied through the real featured article and working
data/source/methodology links; the earlier on-home metric-strip acceptance is
superseded by explicit owner instruction. No quantitative/model release gate
is removed. NI-086 is included in NI-079 local acceptance before deployment.

**User scope update — 8 November 2026:** remaining implementation and release verification target desktop. Mobile development/adaptation and mobile, touch, phone and tablet QA are excluded from the current authorized scope to limit execution cost. Existing responsive code and historical verification evidence are preserved; no new mobile viewport/device passes or screenshots are required. Desktop keyboard/accessibility, ownership, persistence and reproducibility requirements remain in force.

Public landing, full original thesis, methodology and public data explorer; shared source/metric/chart registries; daily historical analytics from saved real data; scheduled refresh for at least one approved reliable source; visibly historical fallback for any failed source. Working Supabase login, private workspace/home, saved charts, document CRUD, Tiptap editor, text/heading/chart/table/insight/hypothesis/evidence/risk/divider blocks, Add Chart, Add Insight, typed context, server ownership, autosave/reopen and reproducible published quantitative analysis. Markdown bundle export is the single reliable MVP export.

P0 live charts use canonical versioned definitions and mutable “latest approved dataset” resolution, with explicit observation/retrieval timestamps. Every document revision freezes the exact dataset resolved at save; reopening the working document in live mode may show newer data with a change badge, but historical revision/export uses the pin. This minimum pin is P0 integrity infrastructure, despite the original priority list placing advanced chart snapshots at P1. An explicit snapshot creation/browsing UX is P1.

At least one regularly refreshed real series is needed for the challenge. The saved archive alone is insufficient for a “live dashboard” release. Refresh starts only after provider entitlement, scope, quotas and data quality pass. No stopped mass collectors are restarted by the product.

## Research feasibility gate

Preferred P0 model: activity versus a comparable daily protocol-attributable revenue series. This series is not currently established. NI-051 evaluates readiness before fitting; never relabel gross fees or treasury payouts as protocol revenue.

Fallback: execute a reproducible exploratory time-series association using explicitly provider-reported daily gross fees and volume, plus sensitivity to source revisions; optionally associate observed purchases with activity. Publish it as a limited proxy analysis, state the mechanical fee-volume relationship, and leave H1/H4 unresolved. This fulfills the statistical-analysis requirement only if the hackathon's evaluation accepts this limited empirical question; OQ-02 is an external judging risk. A no-data status alone does not fulfill P0 econometrics. If no defensible series/model is available, report the release incomplete.

NI-051 implements this gate as offline research code (`research/models/readiness.py` with preregistered `research/models/configs/`): the true-revenue specification stays NOT_READY while OQ-01 is open, only the explicitly named `gross_fee_activity_v1` proxy is admitted — always with limits, never as protocol revenue — and windows below the project sample minimum are rejected. Generated readiness reports stay local and are not committed.

There are no coefficients or fitted model outputs in this documentation. NI-052–NI-054 must run and validate real models after implementation is approved.

## P1

Explicit snapshot management, default investment template and public-thesis duplication, model-result blocks in private documents, PDF export, advanced supported filters, convenient document organization. Basic save-time pins and baseline range controls remain P0. Chart library, sources and public model view remain P0.

## P2 included before deployment

NI-060 implements consent-based revocable read-only sharing of one frozen revision with scoped assets, expiry and owner management. NI-065 implements deterministic metadata integrity checks and an optional grounded AI adapter with evidence references; no-key local operation remains mandatory and external calls are opt-in under actual permissions. Their earlier design-only/plan-only acceptance is replaced by implemented and tested local journeys in TASKS.

## Still excluded

Collaboration/CRDT, automatic hypothesis monitoring, scenario simulators, multiple chains, Strategy/Portfolio screens from the legacy plan, trading/execution, billing and teams are not registered P1/P2 implementation tasks and remain outside this release. No mandatory AI API key or paid provider is introduced. Stub navigation must not suggest unavailable features work.

## Release checklist

**Owner sequencing update — 12 November 2026:** finish all registered P0/P1/P2 and targeted NI-078 fixes while preserving the design; verify the integrated release candidate locally under NI-079 before any NI-067 remote rollout. Local acceptance includes actual permitted research/model gates, not only synthetic engineering tests. Missing data/results/permission remain blockers. P1/P2 are now included; mobile scope remains excluded. Final-origin TLS/callbacks, remote operations/restore and deployed walkthrough remain NI-067/068/069 checks after placement; these tasks themselves are not prerequisites of the local gate. See [current agent handoff](FINISH_BEFORE_DEPLOY_PROMPT.md) and [PLAN section 10](../PLAN.md#10-завершение-до-размещения--обязательный-порядок).

1. Original public thesis includes H1–H4, supporting and contrary evidence, assumptions and limitations.
2. Every public number can be traced to real permitted inputs and a versioned calculation; missing values have explicit states.
3. One approved real refresh demonstrably publishes atomically; outages retain last good data.
4. One published deterministic empirical model reproduces offline, with inference limits and source definitions.
5. Two users can independently save/reopen research; cross-user CRUD, references and export fail safely.
6. Complete research workflow works on desktop with keyboard access and accessible chart data. Mobile/tablet/touch development and verification are excluded by the 8 November 2026 user scope update.
7. Markdown bundle includes rendered chart assets, data, notes and a manifest, pinned to one document revision.
8. Production health, TLS, restore rehearsal and judge walkthrough pass. All registered P0/P1/P2 tasks complete; no required feature deferred merely because of its priority label.

9. Snapshots, templates/duplication, model blocks, PDF, advanced supported filters, tags/favorites, revocable sharing and integrity tools pass actual local persistence/security/chart journeys before NI-079 DONE. Historical/live data semantics, exact values and source references survive every path. Existing visual direction is retained.
