# Development and deployment

Planned topology; no resources are provisioned and no deployment has occurred. Baseline is deliberately portable: reverse proxy + Next.js + FastAPI on one VM, managed PostgreSQL and Supabase Auth, persistent artifact volume, scheduled Python CLI/worker. No hosting purchase or account creation is part of this documentation work.

## Dependency baseline and judge handoff

[DEPENDENCIES.md](DEPENDENCIES.md) defines the tested CPython3.13 hash-pinned requirements baseline and migration to the future uv.lock. Python dependencies are installable now; application services are not implemented. [JUDGE_SETUP.md](JUDGE_SETUP.md) is the mandatory clean-clone deployment/reproduction runbook for NI-066/NI-069, including frontend locks, database/auth configuration and explicitly authorized evidence input access. A dependency-only smoke test does not satisfy deployment acceptance.

## Local development contract

NI-001–NI-003 creates exact runtime pins, pnpm/uv locks, `.gitignore`, Dockerfiles, Compose and root scripts. Compose services: `db` (PostgreSQL major chosen/tested at bootstrap), `api` (FastAPI), `web` (Next.js); optional explicit `worker` profile for exports. Startup must not run ingestion, models, fetch scripts or cloud SQL automatically. Supabase Auth is an explicitly configured dev project or optional local stack; do not silently use production auth.

Copy [.env.example](../.env.example) and replace only local/dev placeholders. Host commands use localhost DB/API; container configuration uses service hostnames db/api. Compose reads env and injects values per service; root .env is not implicitly visible to every process. UI sees only public Supabase URL/key; backend sees JWT metadata/DB/storage/provider secrets.

Create volumes, start db, migrate with the dedicated migration role, start API/web, run health checks and import an approved saved manifest. For native mode use the README commands after scripts exist. A working onboarding run from a clean machine is acceptance, not just Compose syntax validation.

## Production layout and release

One public HTTPS origin, Caddy or equivalent reverse proxy to web; API/DB not internet-exposed. Web gateway forwards to API over the private network. Managed PostgreSQL in the same region, TLS required, pooled connection budget fits all web/API/worker processes. Persistent ARTIFACT_ROOT mounted read/write for importer/worker and controlled read for API; chart export runtime includes pinned Node/ECharts code plus Python worker.

Build immutable images tagged with Git commit and include lockfiles, migrations, generated OpenAPI client and model code/configs. Release process: checks → build → staging migration/health/E2E → DB+artifact backup → reviewed migration → app rollout → smoke test → enable approved scheduler. Never apply destructive automatic migrations on HTTP startup. Default collector allowlist is empty in every new environment.

Database expansion-first migrations must keep one previous app version compatible; irreversible/data-loss migrations require a documented backup/restore plan. Failed app rollout returns to previous image while preserving dataset/document revisions. Never overwrite a published dataset/model as a rollback mechanism; revert active pointer to a prior approved version and audit the action.

## Scheduler and jobs

Use a host scheduler/systemd timer or platform scheduler invoking the same CLI container. Per-source advisory locks prevent overlap; restricted provider credentials injected only into ingestion invocation. Export worker polls/leases queued jobs, max2 retries, 60s rendering timeout initially, one active export/user. Model jobs run operator-triggered fixed configurations with resource/time limits; neither starts in HTTP handlers.

Enable one low-cost reliable finalized-header refresh after source verification; retain explicit historical series for the rest. Source errors cannot bring down document editing. New deployment does not resume legacy stopped collectors.

The finalized-header refresh adapter (NI-030) is implemented as `python -m near_api.ingestion.refresh --once --database-url URL --storage-root DIR [--repo-root DIR]`: every timer tick performs at most one guarded attempt (exit 0 published/unchanged, 3 refused before any request, 4 failed after the attempt with last good retained, 5 database error), so the host timer only decides frequency — the recorded OQ-03 approval allows 1 request/minute and the cadence target is every 15 minutes. Nothing starts it automatically: no application startup path imports the adapter, it never runs in HTTP handlers, the per-source advisory lock plus the persisted checkpoint/daily-counter budgets (migration 0008) make overlapping or repeated ticks harmless, and the effective allowlist (`app.sources.access_status = 'approved'`) starts empty in every new environment until an operator approves the row. A stopped timer resumes cleanly from the persisted height checkpoint; legacy `STOP_PUBLIC_COLLECTION` markers keep the adapter refused wherever they are present.

## Health, monitoring and backup

Liveness is process-only; readiness verifies DB connectivity, expected migration revision and artifact read/write access without costly provider calls. Alert on failed exports, missing artifacts/hash mismatch, stalled job lease, source freshness breach, repeated 401/429, storage >80% and unauthorized attempts. Logs are structured with request/run IDs and no secrets/content. Source health dashboard reports last successful data date as well as retrieval time.

Target backups: nightly DB and daily incremental artifact copy to offsite encrypted storage; initial RPO 24h, RTO 4h, both targets until rehearsed. Snapshot DB and referenced artifact manifest coherently; retain artifact bytes needed by DB backups. Restore into isolated environment, verify hashes and private ownership, then cut over. Perform a restore drill before release and after backup strategy changes.

## Hosting alternatives and unresolved inputs

Vercel may host web or combined services later; current platform capabilities and limits must be rechecked before choosing it. Do not infer that scientific jobs/persistent files will work on any request runtime. Moving storage to object storage requires an adapter, scoped downloads and the same content hashes. OQ-04 records budget/provider/region; OQ-07 records residency/retention. No deadline, cloud budget or production domain was provided.

## Deployment acceptance

TLS, callback allowlist and cookies work at the final origin; migration from empty DB passes; fresh user can complete public→private→export workflow; public raw artifacts obey license restrictions; last-good metrics survive a provider failure; clean offline model reproduction and restored artifact hashes match; health and logs redact secrets; production fixtures are disabled. Record exact URLs/commit/versions and real test results in a release report.
