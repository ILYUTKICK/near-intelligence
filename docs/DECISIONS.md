# Architecture decision log

Accepted for the implementation specification on 5 November 2026; no application has yet been implemented. Revisit via a new dated ADR, preserving old decisions and migration consequences.

| ADR | Decision and reason | Alternatives / consequences |
| --- | --- | --- |
| ADR-001 | Preserve research archive and historical product-plan; new prompt defines canonical scope | Replacing prior work would lose provenance. Legacy Strategy/Portfolio and H1–H6 are outside new MVP |
| ADR-002 | Next.js + modular FastAPI backend + shared Python CLI | Next-only backend simplifies deploy but duplicates Python modeling; microservices add operational cost. CLI is same domain code, outside requests |
| ADR-003 | PostgreSQL with full immutable JSON revisions plus indexed per-revision projections | Normalizing editable prose into many mutable rows complicates autosave; JSON-only lacks FK/ownership query checks. JSON is canonical, projections regenerate in the same transaction |
| ADR-004 | Supabase Auth with server-managed cookies and API JWT validation | Clerk viable; DIY passwords excluded; Auth.js cross-language session handling adds work. Asymmetric keys, issuer/audience checks and two-user authorization tests required |
| ADR-005 | Tiptap core, custom nodes, no realtime collaboration | BlockNote reduces initial UI work; Tiptap chosen for exact evidence-node schema and persistence control. Adds bounded block-menu/outline implementation; prototype in NI-038 gates adoption |
| ADR-006 | ECharts through one chart adapter with accessible table fallback | Recharts simpler for basic React charts; ECharts covers scatter/model/renderer needs. Enable accessibility explicitly and do not rely on tooltips alone |
| ADR-007 | Immutable dataset versions and save-time document pins are P0 | User-friendly snapshot management stays P1. Live references alone cannot reproduce a prior claim |
| ADR-008 | Markdown ZIP with static charts/CSV/manifest is P0 export | Browser PDF/print alone loses exact interactive evidence; PDF is P1 using the same frozen render contract |
| ADR-009 | Approved immutable files on a persistent volume, metadata/series in PostgreSQL | MVP does not need object storage. VM disk requires offsite backup and capacity limits; S3-compatible adapter later if scale/durability needs change |
| ADR-010 | Production baseline: app containers on one VM, managed PostgreSQL/auth | Vercel is optional, not assumed required by stack. Workload includes scheduled scientific jobs and persistent artifacts; validate any later platform limits against current docs |
| ADR-011 | Measured purchases/payouts stay separate from fee-funded revenue | Provider “revenue” is a separate source-qualified metric. Avoids unsupported accounting/capture-rate claims |
| ADR-012 | H1–H4 use current canonical definitions; feasibility gates before fitting | Limited proxy association can be published with caveats; cannot answer protocol revenue question by renaming gross fees |
| ADR-013 | Original public thesis is reviewed content plus explicit evidence manifest | No automatic promotion of private document text. Public release includes only allowed assets and pinned published model outputs |
| ADR-014 | UTC half-open dates, integer/Decimal money and decimal-string transport | Floating arithmetic is allowed only for statistical fitting after explicit transformation; raw quantities remain exact |
| ADR-015 | Offline saved data first; ingestion opt-in with provider-specific bounds | No automatic restart of stopped RPC or paid BigQuery. “Live” release still needs at least one approved fresh series |
| ADR-016 | One-writer document revision CAS; conflict UI, no silent merge | CRDT/collaboration deferred. Whole-document autosave transaction is tractable within bounded document limits |
| ADR-017 | Provide a generated, hash-pinned root requirements.txt for CPython3.13 before API scaffolding | User requested convenient contributor/judge installation. requirements.in is the temporary direct source; NI-002 migrates to pyproject.toml/uv.lock and exports requirements.txt from it. No parallel independent locks; deployment still requires actual app/source/data/config. |

## ADR-018 — NI-038 prototype outcome: Tiptap adoption confirmed (2026-11-07)

**Context:** ADR-005 chose Tiptap with an explicit gate — the NI-038 prototype had to prove that typing, undo and JSON serialization survive custom React node views before the editor build depends on it.

**Outcome (confirmed):** the prototype (`apps/web/src/features/editor/prototype/`) implements two atomic custom nodes (chart block with node-view controls, insight card with a nested-editable title input) and asserts via tests: node-schema JSON round trip is identical after reload; typing/undo survive React node updates; editor commands (`undo`) escape from inside node views; an empty document parses validly. Node views use `contentEditable=false` islands with a nested editable input — the pattern for NI-039/NI-041 evidence nodes.

**Constraints verified:** Tiptap normalizes an empty document to one empty paragraph (doc schema requires block content — the canonical JSON must expect it); adjacent inserts may group into one history step (undo tests must not assume per-command granularity); `renderHTML` must return the tuple form and serialize attrs as data-attributes for HTML-level fidelity, while the canonical storage path is JSON (NI-036).

**Alternatives / consequences:** no custom rich-text engine was considered (ADR-005 stands); BlockNote not re-evaluated — the gate passed, so switching cost is unjustified. Next: production nodes bind to NI-031 chart registry entries (no synthetic fixtures) and NI-032 datasets.

## ADR-019 — NI-033 dependency: Apache ECharts 6.1.0, modular SVG renderer, no React wrapper (2026-11-08)

**Context:** ADR-006 chose "ECharts through one chart adapter" over Recharts, with a table fallback, but no concrete package/version existed. NI-033 must add the real dependency, align the renderer with the NI-031 registry `renderer_version` (`echarts-modular-svg@1`) and keep the frozen-export path (NI-057) able to reuse the same option builder in Node.

**Decision:** adopt `echarts` **6.1.0** in `apps/web` — the npm registry `dist-tags.latest` at the time of selection (published 2026-05-19, so pnpm's `minimumReleaseAge` supply-chain window has long cleared), Apache-2.0, runtime dependencies limited to `zrender` 6.1.0 and `tslib` 2.3.0. Only modular entry points are imported (`echarts/core` plus `LineChart`/`BarChart`/`ScatterChart` from `echarts/charts`, `Grid`/`Tooltip`/`Aria` from `echarts/components`, `SVGRenderer` from `echarts/renderers`) to keep the bundle bounded; the full `echarts` bundle import is not used. The SVG renderer (not canvas) is the documented default: SVG keeps plotted text as DOM (screen-reader/export friendly) and matches the registry's renderer capability string.

**Structure consequence:** there is no React chart wrapper. A pure typed option builder (`features/charts/renderer/option-builder.ts`) converts the generated `ChartViewResponse` into a JSON-safe `EChartsOption`; the React `ChartView.tsx` only mounts ECharts lazily, feeds it the built option, cancels stale requests and disposes on unmount. The same builder is callable from Node without DOM/browser globals, which is what the NI-057 static export (`apps/web/scripts/render-charts.mjs`) must reuse instead of growing a second renderer.

**Numeric decision (recorded, tested):** decimal strings from the API are the only source of exact values — the accessible table and tooltip formatters render the original strings (with grouping separators, bound labels and gap reasons). Parsing to `Number` happens only for plot coordinates (axis positioning), where a 29+ significant-digit yocto-scale value intentionally loses digits that only affect sub-pixel position. This is the documented float boundary of ADR-014 for rendering; no financial aggregation ever happens in the renderer.

**Alternatives / consequences:** Recharts — rejected in ADR-006 (React-coupled, no panel/scatter depth, no Node SSR story); Chart.js — canvas-first, weaker labeling/accessibility and panel layout for this purpose; uPlot/lightweight-charts — too narrow (time-series/finance) for panels/bounds labeling. Version alternatives: echarts 5.6.0 (2024-12) is the previous major; 6.0.0 (2025-07) → 6.1.0 is its stable successor and the maintained `latest`, so pinning 5.x would immediately lag the maintained line. Consequence: the registry definition carries `renderer_version: "echarts-modular-svg@1"`; the renderer module exports the same constant and refuses to render a definition pinned to a different renderer capability set (honest unsupported-renderer state, never a best-effort redraw). Upgrades of echarts require a registry decision only if the capability set changes, because definitions pin the capability, not the npm version.

**Verification:** version/license/integrity taken from the npm registry (`npm view echarts version dist-tags license` — `6.1.0`, `latest`, Apache-2.0; package entry `exports` inspected for `./core`, `./charts`, `./components`, `./renderers`, `./ssr/client`); frozen-lockfile install diff contained to echarts/zrender/tslib; renderer tests cover gaps, bounds, large decimals, range-change metadata survival and dispose/cleanup.

## Evidence behind tool choices

Official references reviewed: [Tiptap nodes](https://tiptap.dev/docs/editor/extensions/custom-extensions/create-new/node), [BlockNote custom blocks](https://www.blocknotejs.org/docs/features/custom-schemas/custom-blocks), [ECharts accessibility](https://echarts.apache.org/handbook/en/best-practices/aria/), [Supabase JWT verification](https://supabase.com/docs/guides/auth/jwts), and [statsmodels robust covariance](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLSResults.get_robustcov_results.html). These support capabilities, not a compatibility guarantee for an unpinned installation. NI-001/NI-002 resolve supported versions and record locks.

Minimum amendment record: context, decision, alternatives, scientific/security effect, affected contracts, migration/rollback, verification and date. An unknown provider limit stays unknown until verified; an ADR must not manufacture a quota or redistribution right.

## ADR-020 — Complete registered P1/P2 before deployment (2026-11-12)

**Context:** the owner corrected the 11 November MVP-only handoff: the desktop design is largely complete; finish all P1/P2 and make the whole product work locally with charts before deployment.

**Decision:** retain priority labels and direct technical dependencies, move NI-044/045/055/059/071/072/060/065 before NI-079, and make all eight direct dependencies of this local acceptance gate. The former global P0-completion barrier is superseded for these features; remote NI-067/068/069 follow NI-079. NI-060/065 acceptance changes from design/plan-only to working implementation with bounded security/data/tool contracts. No new framework, microservice, realtime collaboration or mandatory LLM dependency is selected.

**Consequences:** preserve NI-075 design and target NI-078 defects; sharing projects only an explicitly consented frozen revision, never exposes private UUID routes. Integrity checks are deterministic; optional grounded commentary is separately configured and permitted. Existing no-collection/no-paid-request/private-context boundaries remain. Implementers document schema/API migrations and rollback before code; NI-079 verifies new migrations, owner isolation, graph/pin/asset invariants and all chart/export paths. No implementation or runtime readiness is claimed by this ADR.
