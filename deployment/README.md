# Deployment artifacts (NI-066)

This directory records the packaging decisions and the live registry checks
behind the portable runtimes. The runnable artifacts are the root
[Dockerfile.web](../Dockerfile.web), [Dockerfile.api](../Dockerfile.api) and
[docker-compose.yml](../docker-compose.yml); the tested judge sequence is
[docs/JUDGE_SETUP.md](../docs/JUDGE_SETUP.md). Cloud provisioning is NOT part
of this task (NI-067 owns deployment; no hosting account or budget is touched
here).

## Images

| Image | Built from | Runs |
| --- | --- | --- |
| `near-intelligence-web:local` | `Dockerfile.web` | Next.js production server (`next start`, port 3000) |
| `near-intelligence-api:local` | `Dockerfile.api` | FastAPI (`uvicorn near_api.main:app`, port 8000), the Alembic migration step, the export worker CLI (NI-058) and the bounded refresh CLI (NI-030) |

Packaging decisions:

- **One Python image, four entry commands.** `api`, `migrate`, `worker` and
  `refresh` share the same immutable image and differ only by the command
  Compose passes. A second image would duplicate the locked scientific stack
  (pandas/NumPy/SciPy/statsmodels) for no isolation gain.
- **The Node renderer ships inside the API image.** The NI-057 renderer
  (`apps/web/scripts/render-charts.mjs` plus the three option-builder modules
  it imports) and its runtime dependency closure (`echarts`, `zrender`,
  `tslib`, `zod`) are extracted from a frozen pnpm install into the image at
  the preserved repo layout (`/app/apps/web/scripts/...`, `/app/node_modules`).
  The `NEAR_CHART_RENDERER_NODE=/usr/local/bin/node` and
  `NEAR_CHART_RENDERER_SCRIPT=/app/apps/web/scripts/render-charts.mjs` seams
  are pinned in the image ENV. Type-only imports (the generated shared-types
  client, echarts option types) are erased by Node type stripping and are
  deliberately not packaged. The renderer is spawned only by the export worker
  as a subprocess — never by the HTTP services.
- **No dev dependencies in runtimes.** Both images copy a prod-only dependency
  tree (`pnpm install --frozen-lockfile --prod` stage; `uv sync --frozen`
  resolves the locked runtime set). No package caches, no pnpm/uv download
  caches, no build tooling beyond the builder stages.
- **Repo layout preserved inside the API image** (`/app/apps/api`,
  `/app/apps/web/scripts`) so the renderer script default path — resolved from
  the `near_api.exports.charts` module location — and Node's upward
  `node_modules` resolution both hit packaged paths with no host mounts.
- **No secrets, no research data.** The `.dockerignore` excludes `.env*`,
  `research/`, `product-plan/`, local state and docs from the build context
  entirely (verified by exporting the exact context — see "Context boundary
  test" below). Images contain no credentials and no `.env`; Compose injects
  configuration at runtime and builds the container-host database URLs from
  the four role passwords in the ignored root `.env`.
- **No collection starts anywhere.** No image entrypoint or Compose service
  runs ingestion: the API factory starts only the HTTP service (NI-002
  contract, re-verified by NI-030's grep-audit), migrations run only via the
  explicit `migrate` one-shot, the export worker processes only queued export
  jobs, and the refresh CLI is a one-shot attempt behind the `refresh` profile
  that refuses (exit 3, zero requests) while the source allowlist is empty —
  which it is in every fresh environment.
- **Ports stay loopback.** db (5432), api (8000) and web (3000) publish to
  `127.0.0.1` only; containers talk over the internal bridge network. Exposing
  them publicly is a NI-067 production decision, not a default.
- **`restart: "no"` everywhere.** A local judge run stays deterministic; a
  production restart policy belongs to NI-067.

## Base image pins (live registry checks, 2026-11-10)

Digests are the multi-arch manifest-list digests of the tags below (recorded
from `docker buildx imagetools inspect`; the same digests are pinned in the
Dockerfiles and Compose file). Actual versions inside the pulled images were
executed and recorded, not assumed.

| Reference | Manifest-list digest | Executed version |
| --- | --- | --- |
| `node:24-slim` | `sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9` | Node v24.22.2 (matches `.node-version` family 24; corepack 0.36.0 activates the pinned pnpm 12.16.1) |
| `python:3.13-slim-bookworm` | `sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72` | Python 3.13.18 (`.python-version` family 3.13) |
| `postgres:18.6-bookworm` | `sha256:f1ea2a1a4fb7b68d4836be1fdcb8a6466a89b072158bf9d97663600538c294c5` | PostgreSQL 18.6 (the version NI-003 tested natively) |
| `ghcr.io/astral-sh/uv:0.12.13` | `sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6` | uv 0.12.13 (the version that froze `apps/api/uv.lock`; `uv sync --frozen` never re-resolves) |

Bumping any pin = new manifest check, new version record here, and the
DEPENDENCIES.md update rule applies (no invented versions; no silent bumps).

## Build and run

```sh
docker compose build                 # both images
docker compose up -d                 # db + api + web (nothing else)
docker compose run --rm migrate      # explicit Alembic upgrade head
docker compose ps                    # all three healthy
docker compose down                  # stop; add -v to also drop volumes
```

## Context boundary test

To prove what the daemon actually receives from the build context, export the
context through a scratch stage and inspect the listing:

```sh
printf 'FROM scratch\nCOPY . /ctx\n' > /tmp/Dockerfile.ctx
docker buildx build -f /tmp/Dockerfile.ctx --output type=local,dest=/tmp/ctx-out .
# then check /tmp/ctx-out/ctx contains no .env, no research/, no product-plan/
```

NI-066 ran exactly this: the exported context contained only `apps/`,
`packages/`, the root manifests, the two Dockerfiles, `docker-compose.yml`,
`requirements.txt` and `apps/api/README.md` (kept — hatchling needs it); no
`.env`, no `research/`, no `product-plan/`, no `node_modules`, no `.git`, no
`docs/`. Re-run the export check whenever `.dockerignore` changes.

## Credential/role matrix (local Compose)

| Service | DB identity | Source |
| --- | --- | --- |
| `db` bootstrap | `near_bootstrap` (superuser, init only) | `DB_BOOTSTRAP_PASSWORD` in `.env` |
| `migrate` | `near_migrator` (owns schema/history) | URL built from `DB_MIGRATION_PASSWORD` |
| `api` | `near_app` (runtime, RLS-scoped) | URL built from `DB_RUNTIME_PASSWORD` |
| `worker` | `near_app` for job-owner transactions + `near_operator` for lease claim/sweep | URLs built from `DB_RUNTIME_PASSWORD` / `DB_OPERATOR_PASSWORD` |
| `refresh` | `near_app` | URL built from `DB_RUNTIME_PASSWORD` |

The bootstrap superuser exists only inside the `db` container. None of the
application credentials is superuser/BYPASSRLS (enforced by
`scripts/db/010-roles.sql`); the migration environment re-verifies the role
flags at connect time. Provider credentials from `.env` are injected only into
the `api`/`web` containers via `env_file` and are read by no startup path;
`worker`/`migrate`/`refresh` receive only their database URLs and renderer
seams.
