# Model dataset readiness gate (NI-051) and fixed estimator (NI-052)

Research code that decides **which empirical question is admissible before any
fitting happens** — and then fits exactly that question with a fixed
deterministic estimator. It implements the "Data readiness before any fit"
section of [docs/ECONOMETRIC_METHODOLOGY.md](../../docs/ECONOMETRIC_METHODOLOGY.md)
and the research feasibility gate of
[docs/MVP_SCOPE.md](../../docs/MVP_SCOPE.md).

The gate fits nothing. It reads the saved research archive strictly through the
NI-029 loaders (`apps/api/src/near_api/metrics/loaders.py` — import only, no
duplication), builds one calendar-aligned prepared table, profiles every model
series and evaluates each preregistered specification config against the fixed
project rules. The estimator itself is NI-052; it must reuse the admitted
specification unchanged — and it does, by importing the gate's own loaders and
re-evaluating the same specification on the same archive before anything is
fitted.

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
- `fit.py` — the NI-052 fixed deterministic estimator (pure design builder,
  pre-estimation intercept/rank/condition checks, OLS + preregistered HAC,
  deterministic manifest, CLI).
- `configs/readiness_gate_policy_v1.json` — fixed project gate numbers
  (60 complete daily observations, 10 per parameter including intercept,
  3 substantive slopes max, long-run threshold), the evaluation order and the
  archive input bindings.
- `configs/*.json` — preregistered specification configs (typed and validated
  against the versioned metric registry at load time).
- `fit_configs/*.json` — preregistered estimator settings for one
  specification (covariance type/kernel/maxlags under a fixed
  `maxlags_rule`, `use_correction`, `use_t`, reproduction tolerances). They
  live outside `configs/` on purpose: the gate scans `configs/*.json` as
  specifications, so estimator settings must not share that namespace.
- `reports/` — generated output, **local only, never committed** (gitignored).

## Run

### Gate (NI-051)

```bash
uv run --project apps/api python research/models/readiness.py \
    --archive-root /path/to/research \
    --configs-dir research/models/configs \
    --out-dir research/models/reports
```

### Estimator (NI-052)

```bash
uv run --project apps/api python -m near_api.research fit \
    --archive-root /path/to/research \
    --out-dir research/models/reports \
    --code-commit <git sha>
```

The `near_api.research` wrapper owns only dispatch: it loads
`research/models/fit.py` import-only and forwards the arguments, so there is
exactly one estimator implementation. The standalone
`uv run --project apps/api python research/models/fit.py ...` entry point is
equivalent.

Both commands exit 0 on success, 4 on contract/policy failure and 2 on usage;
without `--out-dir` the JSON document prints to stdout. The same inputs always
produce a byte-identical document: inputs are pinned by SHA-256, every source
number is an exact Decimal string and there are no wall-clock timestamps.
Cross-platform reproduction compares fitted values under the declared
tolerance (rtol 1e-8 / atol 1e-10) recorded in the fit config; the manifest
additionally carries an IEEE-754 hex design digest that is a same-platform
byte-identity aid.

The estimator refuses to fit when the gate verdict for the bound
specification is not `READY`/`READY_WITH_LIMITS`, when zeros or negatives
enter a strict-log design (they are never epsiloned away), when the design is
rank deficient (no pseudo-inverse, no column dropping) and when the fit
config does not bind the declared specification exactly. It never selects
variables, lags or samples from p-values; the HAC lag count is a fixed
preregistered number. The real-archive fit run itself is operator-side
evidence (like the NI-051 gate run), not repository content.

Tests: `apps/api/tests/test_models_readiness.py` (gate, synthetic fixtures in
disposable temp directories, always runs) and
`apps/api/tests/test_models_fit.py` (estimator, synthetic known-behavior
fixtures strictly separate from the real archive: exact-relationship
recovery, direct statsmodels HAC equivalence, rank failure, zero policy,
byte-identical double runs, CLI exit codes); both are part of the
`scripts/run-db-tests.py` discovery and run without a database.
`apps/api/tests/test_models_readiness_real_archive.py` runs only with
`NI_REAL_ARCHIVE_ROOT` pointing at a read-only archive handoff, like the
NI-029 real-archive tests.

## Boundaries

- The archive is opened read-only; the gate and the estimator write only into
  the operator-provided `--out-dir` (never inside `research/`).
- No network, no database access, no new collection, no paid providers, no
  arbitrary user code execution: the only code that ever runs is this
  repository's own research modules behind the fixed CLI.
- No migration is added by NI-051/NI-052: the artifacts are the reproducible
  readiness report and the reproducible fit manifest, both rendered locally.
  A `model_runs` table becomes meaningful with NI-054 when fitted runs are
  published; that task owns the migration.
- Reports and fit manifests are evidence artifacts, not application code:
  they stay local. The gate code, the estimator code, the configs and this
  README are shared because they are deterministic specifications, not
  research data.
