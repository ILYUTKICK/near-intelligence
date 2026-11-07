# Model dataset readiness gate (NI-051), fixed estimator (NI-052) and diagnostics battery (NI-053)

Research code that decides **which empirical question is admissible before any
fitting happens**, fits exactly that question with a fixed deterministic
estimator, and then makes the fit assessable with a preregistered
diagnostics/robustness/interpretation battery. It implements the "Data
readiness before any fit", "Estimation and diagnostics" and "Model output
contract" sections of
[docs/ECONOMETRIC_METHODOLOGY.md](../../docs/ECONOMETRIC_METHODOLOGY.md)
and the research feasibility gate of
[docs/MVP_SCOPE.md](../../docs/MVP_SCOPE.md).

The gate fits nothing. It reads the saved research archive strictly through the
NI-029 loaders (`apps/api/src/near_api/metrics/loaders.py` — import only, no
duplication), builds one calendar-aligned prepared table, profiles every model
series and evaluates each preregistered specification config against the fixed
project rules. The estimator itself is NI-052; it must reuse the admitted
specification unchanged — and it does, by importing the gate's own loaders and
re-evaluating the same specification on the same archive before anything is
fitted. The diagnostics battery is NI-053; it reuses both import-only (the
gate's loaders and evaluation, the estimator's manifest/design/estimation) and
adds no estimation logic of its own.

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
- `diagnostics.py` — the NI-053 diagnostics/robustness/interpretation battery
  (stationarity tests with preregistered settings, residual ACF/Ljung–Box/
  Breusch–Pagan/Cook's distance, prespecified sensitivity presets only,
  template-rendered bounded interpretation, deterministic report, CLI).
- `configs/readiness_gate_policy_v1.json` — fixed project gate numbers
  (60 complete daily observations, 10 per parameter including intercept,
  3 substantive slopes max, long-run threshold), the evaluation order and the
  archive input bindings.
- `configs/*.json` — preregistered specification configs (typed and validated
  against the versioned metric registry at load time).
- `fit_configs/*.json` — preregistered estimator settings for one
  specification (covariance type/kernel/maxlags under a fixed
  `maxlags_rule`, `use_correction`, `use_t`, reproduction tolerances).
- `diagnostics_configs/*.json` — preregistered battery settings for one
  specification (declared stationarity series and fixed ADF/KPSS lag
  settings, decision alpha, residual ACF/Ljung–Box/Breusch–Pagan/Cook's
  settings, and the only sensitivity presets that may run). They live outside
  `configs/` on purpose: the gate scans `configs/*.json` as specifications,
  so estimator and diagnostics settings must not share that namespace.
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

### Diagnostics battery (NI-053)

```bash
uv run --project apps/api python -m near_api.research diagnostics \
    --archive-root /path/to/research \
    --out-dir research/reports/<run> \
    --code-commit <git sha>
```

The standalone `uv run --project apps/api python research/models/diagnostics.py ...`
entry point is equivalent; both exit 0/4/2 and both write
`diagnostics_report.json`/`diagnostics_report.md` into the operator-provided
output directory (or print the JSON to stdout without `--out-dir`). The
battery binds the same specification through the fit config and re-runs it,
then records: the gate sample/exclusion table verbatim; the coefficient/SE/
95% CI table cross-checked under the declared tolerances; ADF (fixed maxlag,
autolag disabled) and KPSS (fixed nlags) on the declared level series with
settings recorded next to every result and honest `undefined` statuses (null
with a reason) for short, constant or degenerate series; residual ACF,
Ljung–Box at the declared lags with `model_df` consuming the estimated
parameter count, Breusch–Pagan heteroskedasticity and Cook's distance
influence flags (reported with dates, never removed); the sensitivity
presets — and only those — declared in
`research/models/diagnostics_configs/gross_fee_activity_v1_diagnostics.json`
(HAC maxlags 3 and 14 when the sample supports them, the alternate provider
source, the alternate price basis), each reported as `estimated`,
`not_applicable` or `failed` with a reason from a fixed vocabulary; and a
bounded interpretation rendered only from fixed template sentences and
recorded numbers (association, not causality; no sustainability or
valuation wording; the mechanical fee–volume note repeated verbatim). The
report carries no wall-clock field and re-renders byte-identically on the
same platform. The real-archive diagnostics run is operator-side evidence,
not repository content.

Tests: `apps/api/tests/test_models_readiness.py` (gate, synthetic fixtures in
disposable temp directories, always runs),
`apps/api/tests/test_models_fit.py` (estimator, synthetic known-behavior
fixtures strictly separate from the real archive: exact-relationship
recovery, direct statsmodels HAC equivalence, rank failure, zero policy,
byte-identical double runs, CLI exit codes) and
`apps/api/tests/test_models_diagnostics.py` (battery outputs compared to
direct statsmodels calls on the same arrays; deliberately nonstationary
log-random-walk and mechanical fee=rate×volume synthetics honestly marked;
undefined reason codes; byte-identical double runs; CLI exit codes); all are
part of the `scripts/run-db-tests.py` discovery and run without a database.
`apps/api/tests/test_models_readiness_real_archive.py` runs only with
`NI_REAL_ARCHIVE_ROOT` pointing at a read-only archive handoff, like the
NI-029 real-archive tests.

## Boundaries

- The archive is opened read-only; the gate and the estimator write only into
  the operator-provided `--out-dir` (never inside `research/`).
- No network, no database access, no new collection, no paid providers, no
  arbitrary user code execution: the only code that ever runs is this
  repository's own research modules behind the fixed CLI.
- No migration is added by NI-051/NI-052/NI-053: the artifacts are the
  reproducible readiness report, the reproducible fit manifest and the
  reproducible diagnostics report, all rendered locally. A `model_runs` table
  becomes meaningful with NI-054 when fitted runs are published; that task
  owns the migration.
- Reports, fit manifests and diagnostics reports are evidence artifacts, not
  application code: they stay local. The gate code, the estimator code, the
  diagnostics code, the configs and this README are shared because they are
  deterministic specifications, not research data.
