# NEAR Intelligence

Evidence-first blockchain investment research: **Read Research → Explore Data → Save Charts → Add Insights → Build Thesis → Validate Evidence → Export Research**.

The investment question is whether cross-chain adoption translates into sustainable revenue and measurable NEAR token value capture. The product must show contrary evidence and distinguish activity, fees, attributable revenue, observed purchases, treasury transfers and supply changes.

## Product direction — 14 November 2026

The public product is organized around a collection of original research articles,
with a **Blog** catalog implemented locally in NI-085. The current complete
research at `/research` is the first article; later publications can add new
investigations and dated updates through the shared publication registry/template.
Interactive charts, sources and reproducible calculations support each article,
and the private workspace remains available for readers' own research.
The [Blog/publication brief](docs/BLOG_PUBLICATIONS.md) records the direction
(NI-084) and local implementation. `/blog/near-thesis-2026-11` redirects to the
original `/research`; existing anchors and evidence remain intact. The
Overview homepage follows the owner-approved editorial design (NI-086), with
featured research, data directions, methodology and workspace entry. Detailed
financial evidence remains in the article/data views; the homepage works even
when the data API is unavailable.

## Current state — 10 November 2026

The repository is published privately at [ILYUTKICK/near-intelligence](https://github.com/ILYUTKICK/near-intelligence). **GitHub sharing covers documentation, visual mockups, dependency manifests and new application source/tests/configuration created by authorized NI-tasks.** Participant A authorized role A on 5 November and participant B authorized role B on 6 November; claims and actual acceptance are recorded in [TASKS.md](docs/TASKS.md) through [PLAN.md](PLAN.md). The P0 application is implemented through the research workflow (public data → auth → saved charts → documents → export); the P0 runtime is packaged: NI-066 adds production web/API images (digest-pinned bases, Node renderer included), the Compose deployment with explicit one-shot migrate/worker/refresh actions, and the tested clean-clone sequence in [JUDGE_SETUP.md](docs/JUDGE_SETUP.md). Docker execution was verified locally on macOS ARM64; the final integrated local Linux-container rehearsal is required by NI-079 before rollout, and deployed judge reproduction remains NI-069. Raw historical research inputs, SQL and legacy scripts stay outside GitHub and are absent from a fresh clone; linked offline evidence needs a separately authorized file/hash handoff. Historical findings principally cover 6 August–3 November 2026 UTC and must retain their actual dates.

- **[Mandatory agent execution plan](PLAN.md)** — read before selecting or implementing any task.
- [Latest correction-batch handoff (NI-080–086)](docs/LOCAL_CORRECTIONS_HANDOFF.md) — branch, checks, local archive and continuation boundaries.
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

## Run the application

Full prerequisites, configuration (four DB role secrets, a Supabase dev
project for auth) and the tested clean-clone sequence — including images,
migrations, and one real export through the worker — live in
[JUDGE_SETUP.md](docs/JUDGE_SETUP.md). The short forms:

**Compose mode** (images built from [Dockerfile.web](Dockerfile.web) and
[Dockerfile.api](Dockerfile.api); base images are digest-pinned — see
[deployment/README.md](deployment/README.md)):

```sh
cp .env.example .env             # then set the secrets per JUDGE_SETUP section 4
docker compose build             # web + api images
docker compose up -d             # db + api + web; nothing else starts, ever
docker compose run --rm migrate  # explicit Alembic upgrade head (near_migrator)
docker compose ps                # all three services healthy
```

One-shot operator actions, all explicit and never auto-started:
`docker compose run --rm worker` (process queued exports once) and
`docker compose --profile refresh run --rm refresh` (ONE guarded refresh
attempt; refuses before any request while the source allowlist is empty, as
it is in every fresh environment).

**Native mode** (alternative; same database, host processes):

```sh
cp .env.example .env
docker compose up -d db          # or your own PostgreSQL 18 via scripts/db/010-roles.sql
pnpm install --frozen-lockfile
uv sync --project apps/api --frozen
export MIGRATION_DATABASE_URL="postgresql+psycopg://near_migrator:<DB_MIGRATION_PASSWORD>@localhost:5432/near_intelligence"
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
export DATABASE_URL="postgresql+psycopg://near_app:<DB_RUNTIME_PASSWORD>@localhost:5432/near_intelligence"
uv run --project apps/api uvicorn near_api.main:app --port 8000
API_INTERNAL_URL=http://localhost:8000 pnpm --filter web start   # or: pnpm --filter web dev
```

Configure distinct credentials using the [database setup
runbook](docs/DATABASE_SETUP.md). Both services expose `/health`, which
returns 200 when configured and a readable 503 naming the missing required
variables otherwise. Missing research data renders as explicit unavailable
states — nothing is fabricated; see [JUDGE_SETUP.md](docs/JUDGE_SETUP.md)
section 5 for the input-bundle boundary. Development hot-reload:
`pnpm --filter web dev` and `uv run --project apps/api uvicorn
near_api.main:app --reload --port 8000`.

Developer checks (NI-005; CI runs them on every pull request — web, API and a disposable PostgreSQL 18 database job):

```sh
pnpm lint && pnpm typecheck && pnpm test
pnpm check:contracts && pnpm check:doc-links
pnpm test:api:unit          # offline API suites
pnpm test:api:db            # needs local PostgreSQL 18 binaries
```

The landing integration (updated in NI-086) uses production Next.js and FastAPI
over loopback HTTP with a fresh disposable PostgreSQL 18 cluster. It checks the
editorial Overview before/after dataset publication and during an API outage,
while independently preserving exact metric-delivery and approval checks:

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
or supplies production seed data. The test checks exact metric API values and
explicit unavailable data independently; the editorial homepage and its research
entry links stay unchanged during publication and API outage.

Compose mode and native mode are alternatives; do not start both on the same ports. Native mode starts only `docker compose up -d db` before migrations and app processes. Web `.env` loading is implemented explicitly in [apps/web/src/lib/env.ts](apps/web/src/lib/env.ts) and API loading in [apps/api/src/near_api/settings.py](apps/api/src/near_api/settings.py); missing required configuration makes `/health` return a readable 503 on both services. Production settings, health gates and the scheduler opt-in contract: [deployment](docs/DEPLOYMENT.md). Credentials are placeholders in [.env.example](.env.example); the image digest pins and packaging decisions are recorded in [deployment/README.md](deployment/README.md).

## Delivery gates

**Owner sequence — 12 November 2026:** preserve the largely completed desktop design, implement all registered P0/P1/P2 (NI-044/045/055/059/071/072 and working NI-060/065), complete targeted NI-078 fixes, then pass final integrated **local** chart/workflow acceptance in NI-079, then deploy through NI-067 → NI-068 → NI-069. NI-067 has an explicit dependency on NI-079; earlier task results and a synthetic review preview do not establish release readiness. [Current agent handoff](docs/FINISH_BEFORE_DEPLOY_PROMPT.md), [mandatory order](PLAN.md#10-завершение-до-размещения--обязательный-порядок). TASKS remains the only status registry. Remote TLS/auth/restore/demo checks still happen after deployment.

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

## Existing VPS handoff (NI-090)

For the current Overview/Blog release and `near-intelligence.me`, use the
[dedicated VPS runbook](docs/VPS_DEPLOYMENT.md). Its isolated production Compose,
secret initializer, source bundle, operator commands and backup/restore checks
are separate from the local/judge Compose. Remote rollout still requires NI-079.
