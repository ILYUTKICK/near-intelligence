# Repository audit

Inspected 5 November 2026. Root: `/Users/ilyutkinn/Desktop/Near`. No root or applicable ancestor AGENTS.md was found before this delivery. No `.git`, app manifests, package lockfiles, migrations, API service or web app exist. `git status` reports “not a git repository”; branch and remote are therefore unknown. Do not infer a deployable repository.

| Existing path | Material | Reuse and boundary |
| --- | --- | --- |
| `product-plan/PRODUCT_PLAN.md` | Russian product plan, version 1, 4 November | Prior thesis/data/model/strategy/portfolio concept; preserve as historical input |
| `product-plan/*.svg`, `product-plan/mockups/*.svg` | Design references, composed screens | Visual inspiration; warm editorial direction, not canonical routes or functional implementation |
| `product-plan/build_*.py`, mockup interaction check scripts | Artifact-generation tooling | Not application infrastructure; do not convert accidentally into production code |
| `research/near-pilot` | SQL, receipt traces and four fee examples | Narrow source/attribution diagnostics |
| `research/near-weekly` | Reconciled weekly ledgers, source queries, manifests | Quality tests, collector mappings, known stopped collection |
| `research/near-longitudinal` | 90-day SQL exports and offline exact calculations | Canonical initial purchases/payout observations within a bounded cohort |
| `research/near-dollar` | Saved prices, dashboard/DefiLlama responses, daily USD estimates | Currency valuation and disagreement fixtures; estimated execution value |
| `research/near-supply` | Supply boundaries, partial issuance audit | Exact net change plus incomplete gross lower bounds |
| `research/near-treasury` | Indexed activity, RPC/governance snapshots | Retention scope and governance limitations |
| `research/near-provenance` | API cohort, onchain matches, inventory bounds | Source-to-fee attribution on limited dates, not full 90-day fee funding |
| `research/revenue-dashboard` | Captured HTML/JS/RSC/JSON | Third-party evidence snapshots, not source for our app or a stable ingestion API |

Research archive is roughly 150 MB, with provenance the largest portion (~124 MB); sizes are approximate. Some `__pycache__` artifacts exist. Do not mass-delete or commit archives before classifying license, secrets and storage. There is no pinned dependency environment for all legacy scripts; four main analysis scripts use stdlib, optional plotting uses matplotlib. They may write derived files in place.

## Conflicts resolved for this specification

The new prompt controls scope: public `/research`, `/data`, `/methodology` plus private `/workspace`. Earlier Strategy and Portfolio work is deferred, with no trading or portfolio engine in MVP. Canonical hypotheses are H1–H4 here; legacy H1–H6 are separate IDs and must not be remapped by number. The old optimistic thesis becomes a conditional question; declining token quantities and attribution gaps remain visible.

No original research or product-plan file was changed. New root instructions and docs define the target application. Future agents must wrap and test legacy calculation functions rather than treating scraped dashboard JS as owned app code.

## Feasibility assessment

A useful explorer and editor are feasible from saved 90-day observations. A daily series of protocol-attributable revenue is not yet established. Existing outputs are descriptive accounting analyses, not executed econometric model runs. Publishing a model requires a new locked reproducible run after approval. Daily provider fees/volume permit exploratory association, subject to source revisions and common mechanical construction. Full H1/H4 requires additional definitions and data; this is a release gate for claiming those questions answered, not a reason to fabricate results.
