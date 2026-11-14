# Development and deployment

Portable deployment topology. NI-067 deployed and verified the owner instance; see the [actual release report](verification/ni-067.md). For a new local or own-domain installation follow the [self-hosting guide](SELF_HOSTING.md); for the existing instance use the [VPS runbook](VPS_DEPLOYMENT.md). Baseline is deliberately portable: reverse proxy + Next.js + FastAPI on one VM, managed PostgreSQL and Supabase Auth, persistent artifact volume, scheduled Python CLI/worker. No hosting purchase or account creation is part of this documentation work.

## Dependency baseline and judge handoff

[DEPENDENCIES.md](DEPENDENCIES.md) defines the tested CPython 3.13 baseline: apps/api/pyproject.toml declares direct dependencies, apps/api/uv.lock is the frozen resolution and requirements.txt is its generated export. The frozen application images and local/judge setup are implemented; remote release acceptance remains separate. [JUDGE_SETUP.md](JUDGE_SETUP.md) is the mandatory clean-clone deployment/reproduction runbook for NI-066/NI-069, including frontend locks, database/auth configuration and explicitly authorized evidence input access. A dependency-only smoke test does not satisfy deployment acceptance.

## Local development contract

NI-001–NI-003 creates exact runtime pins, pnpm/uv locks, `.gitignore`, Dockerfiles, Compose and root scripts. Compose services: `db` (PostgreSQL major chosen/tested at bootstrap), `api` (FastAPI), `web` (Next.js); optional explicit `worker` profile for exports. Startup must not run ingestion, models, fetch scripts or cloud SQL automatically. Supabase Auth is an explicitly configured dev project or optional local stack; do not silently use production auth.

Copy [.env.example](../.env.example) and replace only local/dev placeholders. Host commands use localhost DB/API; container configuration uses service hostnames db/api. Local root Compose uses env_file and passes the complete local .env to API/web; it is a development profile. The hardened deployment/vps/compose.yaml uses explicit per-service variable allowlists: web has no DB credentials, while API receives JWT-provider settings without gateway cookie/CSRF secrets. Browser code sees only browser-safe public configuration.

Create volumes, start db, migrate with the dedicated migration role, start API/web, run health checks and import an approved saved manifest. For native mode use the README commands after scripts exist. A working onboarding run from a clean machine is acceptance, not just Compose syntax validation.

## Production layout and release

**Owner release order — 12 November 2026:** no remote staging/production rollout until NI-079 final local acceptance is DONE for the actual release candidate. First finish all registered P0/P1/P2 and targeted NI-078 fixes, preserving the existing design, then local production build/full workflow/real-research gates/container/restore rehearsal. Deployment configuration and runbook preparation may proceed without remote mutation. After this local gate, NI-067 performs staging and final-origin checks, NI-068 actual remote backups/restore/monitoring and NI-069 the deployed demonstration. These remote checks are not claimed by local acceptance. See [the current agent assignment](FINISH_BEFORE_DEPLOY_PROMPT.md) and [PLAN](../PLAN.md). Existing resource/budget/access permissions and owner-only merge still apply.

One public HTTPS origin, Caddy or equivalent reverse proxy to web; API/DB not internet-exposed. Web gateway forwards to API over the private network. Managed PostgreSQL remains an option (TLS required). The owner’s existing-VPS handoff uses a dedicated private PostgreSQL18 container with durable storage and explicit backup/restore tooling (ADR-025); its connection budget must fit all API/worker processes. Persistent ARTIFACT_ROOT mounted read/write for importer/worker and controlled read for API; chart export runtime includes pinned Node/ECharts code plus Python worker.

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

Vercel may host web or combined services later; current platform capabilities and limits must be rechecked before choosing it. Do not infer that scientific jobs/persistent files will work on any request runtime. Moving storage to object storage requires an adapter, scoped downloads and the same content hashes. OQ-04 records budget/provider/region; OQ-07 records residency/retention. The owner instance at near-intelligence.me was deployed to Ubuntu 24.04 x86_64 on DigitalOcean in NI-067 with final-origin Supabase configuration. This does not provision another installation or its data; each operator supplies and validates their own host, domain, identity provider and inputs.

## Deployment acceptance

TLS, callback allowlist and cookies work at the final origin; migration from empty DB passes; fresh user can complete public→private→export workflow; public raw artifacts obey license restrictions; last-good metrics survive a provider failure; clean offline model reproduction and restored artifact hashes match; health and logs redact secrets; production fixtures are disabled. Record exact URLs/commit/versions and real test results in a release report.

## Existing VPS handoff — NI-090

The [VPS runbook](VPS_DEPLOYMENT.md) contains exact preparation/rollout steps,
scoped production configuration, source-bundle checks and isolated restore.
The [local preparation report](verification/ni-090.md) records only executed checks.
Root Compose remains the local/judge path; use the dedicated VPS file explicitly.
