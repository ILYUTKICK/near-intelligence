# Model dataset readiness gate (NI-051)

Research code that decides **which empirical question is admissible before any
fitting happens**. It implements the "Data readiness before any fit" section of
[docs/ECONOMETRIC_METHODOLOGY.md](../../docs/ECONOMETRIC_METHODOLOGY.md) and the
research feasibility gate of [docs/MVP_SCOPE.md](../../docs/MVP_SCOPE.md).

The gate fits nothing. It reads the saved research archive strictly through the
NI-029 loaders (`apps/api/src/near_api/metrics/loaders.py` — import only, no
duplication), builds one calendar-aligned prepared table, profiles every model
series and evaluates each preregistered specification config against the fixed
project rules. The estimator itself is NI-052; it must reuse the admitted
specification unchanged.

## Decision encoded by the gate

- The preferred dependent variable `protocol_revenue_usd` is a registry-gated
  metric with zero observations (OQ-01): the `true_revenue_daily_v1`
  specification is **NOT_READY** and nothing is fitted around it.
- No gross-fee/payout proxy passes as protocol revenue: a specification that is
  not the true-revenue one but declares protocol revenue as its target is
  always REJECTED (`PROXY_CANNOT_PASS_AS_PROTOCOL_REVENUE`).
- The explicitly named fallback `gross_fee_activity_v1` (provider gross fees
  versus provider volume, single source, log-difference baseline) is admitted
  only as **READY_WITH_LIMITS** with the mechanical fee-volume relationship,
  the OQ-02 judging risk, the single-provider-lineage and short-sample limits
  attached verbatim.
- `purchases_activity_v1` is the optional cohort fallback: cohort-limited,
  never whole-market demand, never protocol revenue.
- `supply_bounds_activity_v1` documents the standing rejection: issuance/burn
  are conservative lower bounds over 30-day windows with a partially audited
  mint-header set, so they are never exact daily regression outcomes.
- Windows shorter than 60 complete daily observations (for example the 3-day
  provenance attribution cohort or the 7-day reconciliation week) are rejected
  for daily long-run inference (`SHORT_ATTRIBUTION_WINDOW`).

## Layout

- `readiness.py` — the gate (prepared table, profiles, spec evaluation,
  invariants, deterministic report rendering, CLI).
- `configs/readiness_gate_policy_v1.json` — fixed project gate numbers
  (60 complete daily observations, 10 per parameter including intercept,
  3 substantive slopes max, long-run threshold), the evaluation order and the
  archive input bindings.
- `configs/*.json` — preregistered specification configs (typed and validated
  against the versioned metric registry at load time).
- `reports/` — generated output, **local only, never committed** (gitignored).

## Run

```bash
uv run --project apps/api python research/models/readiness.py \
    --archive-root /path/to/research \
    --configs-dir research/models/configs \
    --out-dir research/models/reports
```

Exit codes: 0 success, 4 contract/policy failure, 2 usage. Without `--out-dir`
the JSON report prints to stdout. The same inputs always produce a
byte-identical report: inputs are pinned by SHA-256, every number is an exact
Decimal string and there are no wall-clock timestamps.

Tests: `apps/api/tests/test_models_readiness.py` (synthetic fixtures in
disposable temp directories, always runs, part of the
`scripts/run-db-tests.py` discovery) and
`apps/api/tests/test_models_readiness_real_archive.py` (runs only with
`NI_REAL_ARCHIVE_ROOT` pointing at a read-only archive handoff, like the
NI-029 real-archive tests).

## Boundaries

- The archive is opened read-only; the gate writes only into the operator
  provided `--out-dir` (never inside `research/`).
- No network, no database access, no new collection, no paid providers.
- No migration is added by NI-051: the gate's artifact is the reproducible
  readiness report, and no fit run exists yet to persist. A `model_runs`
  table becomes meaningful with NI-052/NI-054 when fitted runs and published
  artifacts exist; that task owns the migration.
- Reports are evidence artifacts, not application code: they stay local. The
  gate code, configs and this README are shared because they are deterministic
  specifications, not research data.
