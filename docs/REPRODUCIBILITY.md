# Research reproducibility

Two layers: existing offline descriptive analyses already in the directory, and the future versioned application/model pipeline. Never describe planned commands as currently installed. Source rights may limit public raw download; retain sanitized manifests and permitted reproduction paths.

## Existing offline analyses

Run from repository root in a disposable copy because scripts rewrite derived outputs in place. Inspection found the four primary analyze.py scripts use stdlib; optional plotting needs matplotlib and is not required for recomputing amounts. Record `python3 --version` and hash inputs first. No new API key/cloud job is needed for the saved-input path.

| Purpose | Existing command | Inputs / derived output |
| --- | --- | --- |
| 90-day conversions/payouts | `python3 research/near-longitudinal/scripts/analyze.py` | data/flows_90d_raw.json and weekly collector scope; analysis/summary.json, payout matches and issues |
| Daily USD sensitivity | `python3 research/near-dollar/scripts/analyze.py` | longitudinal saved outputs plus data/coingecko.json, llama_* and dashboard records; analysis/daily.json and summary.json |
| Net supply and lower bounds | `python3 research/near-supply/scripts/analyze.py` | saved headers/indexed boundaries and prior observations; analysis/summary.json; incomplete gross audit remains incomplete |
| Treasury retention scope | `python3 research/near-treasury/scripts/analyze.py` | saved FastNear history/RPC/governance; data/summary.json and reconciliations |
| Small provenance sample | `python3 research/near-provenance/scripts/audit_sample.py` | saved API sample and receipt traces; analysis/sample_summary.json |
| Full saved creation cohort | `python3 research/near-provenance/scripts/audit_cohort.py` | 23 saved API pages/cohort and incoming events; analysis/cohort_summary.json |
| Inventory bounds | `python3 research/near-provenance/scripts/inventory_bounds.py` then same command with `--exact-integer-only` | saved matched fees and reconciled ledgers; expanded/strict inventory summaries |
| Collector route bounds | `python3 research/near-provenance/scripts/collector_routes.py` | saved matched ledgers/treasury paths; route artifacts |
| Final provenance summary | `python3 research/near-provenance/scripts/summarize.py` | preceding generated summaries; analysis/final_summary.json |

Inspect each script's read paths before execution: not every legacy script is a reusable pure function, and some depend on earlier generated outputs. Saved manifests live in the respective research directories and record raw hashes/job/source metadata. Existing final findings are linked from [thesis](INVESTMENT_THESIS.md). These commands reproduce saved-input accounting, not new complete-market data or statistical regressions.

**Do not run** fetch scripts, archival header collection, cloud SQL or stopped account-balance collectors as part of offline reproduction. Do not remove STOP_PUBLIC_COLLECTION. In particular the supply audit must continue to report 6/297 verified headers; no offline calculation can invent missing gross issuance/burn. Do not rerun Explorer collection requiring the former token.

## Dependency baseline

The root [requirements.txt](../requirements.txt) now contains a tested hash-pinned Python dependency set; [DEPENDENCIES.md](DEPENDENCIES.md) records platforms and checks. This does not include the unshared research code/data. NI-002 will make pyproject.toml/uv.lock the declaration/lock source and export the pip-compatible file, keeping one exact version source. A published model must record its actual Python patch, dependency lock/hash and input manifests; installing packages alone does not reproduce a model.

## Future reproducibility bundle

Each approved dataset bundle includes manifest schema version, dataset UUID/key/version, UTC scope and cohort, raw artifact names/byte hashes, source URLs/query IDs/SQL hashes, source cutoff/retrieved times, original units/decimals, cleaning/matching rules, metric definition versions, code commit, dependency lock hash, config and canonical transformed-data hash. Include quality/coverage/revisions/known exclusions/license restrictions.

Canonical JSON uses UTF-8, normalized key ordering and deterministic separators, decimal strings unchanged, UTC timestamps with explicit Z, sorted records by defined primary key; no volatile wall-clock field participates in the content-addressed semantic hash. Raw-byte SHA hashes still cover exact original responses. Manifest metadata and semantic data hash are separate. Identical content may be deduplicated within a dataset key; retrieval records remain separate lineage.

Dataset immutability: only staged artifacts mutate; approved dataset bytes/rows never do. Re-fetch revisions create a new version/supersedes relationship. Content hash is integrity evidence, not an authenticity guarantee or a substitute for source trust. Signed/provider-authenticated receipts are not assumed available.

For document revision, include editor schema/content hash, publication source if copied, every chart definition/renderer/metric version, selection/filter/mode, exact dataset pin and context hash, insight/evidence metadata and model run references. Snapshots reconstruct the same evidence; live mode is merely a working-view resolution policy.

## Planned deterministic commands — implement in NI-028/NI-051–NI-054

```sh
uv sync --project apps/api --frozen
uv run --project apps/api python -m near_api.cli datasets build --config research/models/configs/intents_daily_v1.json --offline
uv run --project apps/api python -m near_api.cli research readiness --model gross-fee-activity-v1 --dataset <UUID>
uv run --project apps/api python -m near_api.cli research run --model gross-fee-activity-v1 --dataset <UUID> --config research/models/configs/gross_fee_activity_v1.json --offline
uv run --project apps/api python -m near_api.cli research verify --manifest research/reports/<run-id>/manifest.json
```

Config paths and CLI do not exist yet; tasks must create them. Models for true protocol revenue are enabled only after their readiness gates pass. `--offline` rejects provider HTTP and cloud access, not merely omits an API key. Publication command must validate that artifact/code/lock/config inputs are all resolvable and licensed for their intended distribution.

Model bundle adds model version, sample/exclusions, transformed design, coefficient/SE/CI/test outputs, covariance/lag settings, diagnostics, interpretation/limitations, Python/OS/BLAS versions and seeds. Exact data hashes must match; fitted floats use documented tolerance (initial rtol1e-8/atol1e-10); rendering pixels/ZIP timestamps may differ while canonical values/pins match.

## Reviewer recipe and acceptance

1. Obtain an explicit published research release and permitted immutable input bundle; verify each hash and license/source note.
2. Check out exact code commit and install frozen lockfiles in an isolated environment; print environment metadata.
3. Run offline dataset builder and compare canonical data/design hashes, date coverage and exclusions.
4. Run the registered model/config, compare coefficient/SE/CI/diagnostics under stated tolerance; include unsuccessful readiness reports when applicable.
5. Reconstruct a document/export using its pinned contexts; verify chart CSV and source/model references.

If a provider forbids redistribution, supply the original query/API retrieval recipe and approved summary artifacts, clearly disclosing any entitlement/cost barrier. A supposedly independent reproduction that cannot access required inputs must be reported as limited, not passed. P0 should prefer publishable saved inputs so hackathon judges can actually rerun without paid credentials. NI-054 and NI-069 perform the clean-machine/offline and demo verification after implementation.
