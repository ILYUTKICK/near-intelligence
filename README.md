# NEAR Intelligence

Evidence-first blockchain investment research: **Read Research → Explore Data → Save Charts → Add Insights → Build Thesis → Validate Evidence → Export Research**.

The investment question is whether cross-chain adoption translates into sustainable revenue and measurable NEAR token value capture. The product must show contrary evidence and distinguish activity, fees, attributable revenue, observed purchases, treasury transfers and supply changes.

## Current state — 6 November 2026

The repository is published privately at [ILYUTKICK/near-intelligence](https://github.com/ILYUTKICK/near-intelligence). **GitHub sharing covers documentation, visual mockups, dependency manifests and new application source/tests/configuration created by authorized NI-tasks.** Participant A authorized role A on 5 November and participant B authorized role B on 6 November; claims and actual acceptance are recorded in [TASKS.md](docs/TASKS.md) through [PLAN.md](PLAN.md). Web/API runtime skeletons and frozen pnpm/uv locks exist. NI-003 adds the identity-only PostgreSQL/Alembic foundation with native migration/RLS checks and a DB-only Compose definition; Docker execution remains unverified. NI-004 adds strict API schemas and a generated TypeScript client. Node 24 LTS / pnpm 12.16.1 are pinned in [.node-version](.node-version) and [package.json](package.json). The full product/data workflow remains incomplete. Raw historical research inputs, SQL and legacy scripts stay outside GitHub and are absent from this fresh clone; linked offline evidence needs a separately authorized file/hash handoff. Historical findings principally cover 6 August–3 November 2026 UTC and must retain their actual dates.

- **[Mandatory agent execution plan](PLAN.md)** — read before selecting or implementing any task.
- [Collaboration and repository setup](docs/COLLABORATION.md)
- [Python dependency baseline](docs/DEPENDENCIES.md) and [judge setup checklist](docs/JUDGE_SETUP.md)
- [Documentation index](docs/INDEX.md)
- [Repository audit](docs/REPOSITORY_AUDIT.md) and [source verification](docs/SOURCE_VERIFICATION.md)
- [Product requirements](docs/PRODUCT_REQUIREMENTS.md), [strict MVP](docs/MVP_SCOPE.md)
- [Architecture](docs/ARCHITECTURE.md), [database](docs/DATABASE_SCHEMA.md), [API](docs/API_SPECIFICATION.md)
- [Thesis and existing findings](docs/INVESTMENT_THESIS.md), [methodology](docs/ECONOMETRIC_METHODOLOGY.md)
- [Roadmap](docs/IMPLEMENTATION_ROADMAP.md), [task backlog](docs/TASKS.md), [two-person team plan](docs/TEAM_PLAN.md), [open questions](docs/OPEN_QUESTIONS.md)
- [Agent instructions](AGENTS.md), [contributing](CONTRIBUTING.md), [documentation validation](docs/VALIDATION.md)

## Selected stack

Next.js App Router, React, TypeScript, Tailwind, shadcn/ui primitives, Apache ECharts, Tiptap, TanStack Query, Zod; FastAPI/Pydantic, SQLAlchemy/Alembic, PostgreSQL; pandas/NumPy/SciPy/statsmodels. Supabase Auth issues sessions; FastAPI enforces resource ownership. A single Python CLI runs ingestion and research outside HTTP requests. [Decision log](docs/DECISIONS.md) records alternatives.

## Existing offline research

Inspect each research README before running it. These commands read saved inputs and rewrite derived outputs, so use a disposable copy when auditing:

```sh
python3 research/near-longitudinal/scripts/analyze.py
python3 research/near-dollar/scripts/analyze.py
python3 research/near-supply/scripts/analyze.py
python3 research/near-treasury/scripts/analyze.py
```

These four analysis scripts use Python standard-library modules. Optional plotting and future econometrics need pinned scientific dependencies. Do not run `fetch_*`, cloud SQL, stopped balance collection or archival mint collection to reproduce existing findings. [Detailed reproduction](docs/REPRODUCIBILITY.md) covers provenance scripts and caveats.

## Available now — Python dependencies

Preferred path (uv, frozen lock):

```sh
uv sync --project apps/api --frozen
uv lock --check --project apps/api
```

pip/venv path from the generated export (judges without uv):

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements.txt
.venv/bin/python -m pip check
```

[apps/api/uv.lock](apps/api/uv.lock) is the exact frozen environment at the cutoff recorded in [apps/api/pyproject.toml](apps/api/pyproject.toml); [requirements.txt](requirements.txt) is its generated hash-pinned export. This installs dependencies only; it does not launch an application or supply the unshared research archive. See [DEPENDENCIES.md](docs/DEPENDENCIES.md) for tested platforms and [JUDGE_SETUP.md](docs/JUDGE_SETUP.md) for the remaining deployment gates.

NI-004 API contract checks (after frozen Python/pnpm install): `pnpm api:generate`,
`pnpm api:check`, `pnpm --filter @near-intelligence/shared-types typecheck` and
`pnpm --filter @near-intelligence/shared-types test`. These generate from local
Pydantic/FastAPI source without starting data collection. See the
[API contract workflow](docs/API_CONTRACT.md).

## Planned onboarding contract — unavailable until foundation tasks finish

Future prerequisites: Node 24 LTS (pinned in [.node-version](.node-version)), pnpm pinned through `packageManager` (12.16.1), CPython 3.13, uv, Docker Compose, Supabase development auth project. Python packages are resolved and hash-pinned now, Node/pnpm tool versions are pinned and pnpm-lock.yaml is committed; the API uv.lock is completed in NI-002's API part.

Tested runtime commands (NI-002; nothing else starts on boot):

```sh
cp .env.example .env
pnpm install --frozen-lockfile
pnpm --filter web dev            # boots apps/web on :3000; /health validates required config
pnpm --filter web build && pnpm --filter web start
uv sync --project apps/api --frozen
uv run --project apps/api uvicorn near_api.main:app --reload --port 8000   # boots apps/api on :8000
```

NI-003 defines a DB-only Compose service and explicit identity migrations. Native
PostgreSQL migration/RLS checks are tested; Docker execution is unverified in the
role-B Windows session. Configure distinct credentials using the
[database setup runbook](docs/DATABASE_SETUP.md) first:

```sh
# Defined DB-only Compose path; API/web packaging belongs to NI-066.
docker compose up -d db
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
```

Developer checks (NI-005; CI runs them on every pull request — web, API and a disposable PostgreSQL 18 database job):

```sh
pnpm lint && pnpm typecheck && pnpm test
pnpm check:contracts && pnpm check:doc-links
pnpm test:api:unit          # offline API suites
pnpm test:api:db            # needs local PostgreSQL 18 binaries
```

NI-012 landing integration uses production Next.js and FastAPI over loopback HTTP
with a fresh disposable PostgreSQL 18 cluster (no auth/provider service):

```sh
pnpm install --frozen-lockfile
pnpm build
uv run --project apps/api python scripts/run-db-tests.py --pg-bin /usr/lib/postgresql/18/bin --suite landing
# Optional offline reproduction with the separately supplied local research archive:
NI_LANDING_ARCHIVE_ROOT=/absolute/path/to/research uv run --project apps/api python scripts/run-db-tests.py --pg-bin /usr/lib/postgresql/18/bin --suite landing
```

Use your PostgreSQL 18 binary directory (Homebrew macOS:
`/opt/homebrew/opt/postgresql@18/bin`). The default run stages visibly synthetic
regression data; the opt-in archive run reads the existing longitudinal flows
and daily analysis, stages them only in the disposable test database, and
checks both source files remain byte-identical. Neither mode contacts providers
or supplies production seed data. The test checks visible metric cards against
the real API response, explicit unavailable data, and API outage recovery.

Compose mode and native development mode are alternatives; do not start both on the same ports. Native mode starts only `docker compose up -d db` before migrations and app processes. Web `.env` loading is implemented explicitly in [apps/web/src/lib/env.ts](apps/web/src/lib/env.ts) and API loading in [apps/api/src/near_api/settings.py](apps/api/src/near_api/settings.py); missing required configuration makes `/health` return a readable 503 on both services. Production settings and health gates: [deployment](docs/DEPLOYMENT.md). Credentials are placeholders in [.env.example](.env.example).

## Delivery gates

P0 requires real attributable data, public thesis/methodology, a reproducible statistical analysis, authentication, private persisted research, interactive charts, Add Chart/Add Insight, Markdown export and a deployed end-to-end workflow. Full H1 revenue econometrics remains gated on an adequate revenue series. An exploratory model on a clearly named observable proxy does not establish protocol revenue; see the fallback rules in [MVP_SCOPE.md](docs/MVP_SCOPE.md).

NI-035 saved charts HTTP integration (production web build, disposable PostgreSQL, synthetic data/auth transport only):

```sh
pnpm build
uv run --project apps/api python scripts/run-db-tests.py --pg-bin /usr/lib/postgresql/18/bin --saved-charts-http
```

Use your PostgreSQL 18 binary directory (macOS Homebrew: `/opt/homebrew/opt/postgresql@18/bin`). The saved suite exercises real cookie/CSRF forwarding, ES256 JWT verification, identity bootstrap, RLS, idempotent save/reopen and Bob's denied access. The six saved-chart API/DB regressions also run in the default database suite. The provider JWKS transport uses an ephemeral synthetic key and never contacts Supabase.

NI-041 insertion HTTP integration (after the same frozen production build):

```sh
uv run --project apps/api python scripts/run-db-tests.py --pg-bin /usr/lib/postgresql/18/bin --chart-insertion-http
```

The isolated suite exercises chart-block race/retry/ownership cases, then the actual web gateway and ES256 principal/RLS path. NI-042 adds the shared editor chart inspection route, explicit range/filter save/reopen, latest adoption, old-pin preservation and chart-outage/prose-save checks. A newer dataset is published between inspection and insertion; the original pin survives insertion, replay, prose save and reopen. Bob cannot read or append to Alice's document. No external provider/account or research archive is used.

NI-024 Home continuation integration (after the production web build):

```sh
uv run --project apps/api python scripts/run-db-tests.py --pg-bin /usr/lib/postgresql/18/bin --workspace-home-http
```

This runs the Home aggregation checks and production cookie/CSRF gateway against
isolated PostgreSQL with synthetic auth/data only. It verifies an empty first-use
workspace, persisted creation/current-revision continuation, owned saved charts
and notes, and an indicator SQL outage that leaves documents available. Home's
Create action saves an empty document immediately; Continue opens the newest
owned document. The checklist counts work in that document, without assessing
the truth of its claims. Indicators reuse one day from each latest approved
dataset and preserve dates, exact decimals, quality and provenance.
