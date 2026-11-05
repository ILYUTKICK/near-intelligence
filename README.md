# NEAR Intelligence

Evidence-first blockchain investment research: **Read Research → Explore Data → Save Charts → Add Insights → Build Thesis → Validate Evidence → Export Research**.

The investment question is whether cross-chain adoption translates into sustainable revenue and measurable NEAR token value capture. The product must show contrary evidence and distinguish activity, fees, attributable revenue, observed purchases, treasury transfers and supply changes.

## Current state — 5 November 2026

The Git repository is initialized on branch `main` and published privately at [ILYUTKICK/near-intelligence](https://github.com/ILYUTKICK/near-intelligence). **GitHub sharing covers documentation and visual mockups, the Python dependency manifests, and — under the 5 November 2026 implementation authorization — new application code, tests, configuration and tooling manifests created by authorized NI-tasks.** Raw research inputs, SQL and calculation/collection scripts remain local and ignored. Some evidence links and offline commands below refer to that unshared local archive and are unavailable in a fresh clone; arrange a separately authorized data handoff before research implementation. The web runtime skeleton exists under [apps/web](apps/web) (NI-002 web part: Next.js App Router, strict TypeScript, pnpm-lock.yaml, `/health`); the API source, database migrations, uv.lock and Docker Compose file do not exist yet — NI-002's API part is handed off to role B. A tested Python dependency baseline is available in requirements.txt, and Node 24 LTS / pnpm 12.16.1 are pinned in [.node-version](.node-version) and [package.json](package.json) with the root [pnpm workspace](pnpm-workspace.yaml). On 5 November 2026 the user (participant A, ILYUTKICK) authorized starting implementation of role-A tasks through [PLAN.md](PLAN.md). Local evidence is historical, principally 6 August–3 November 2026 UTC; it must never be labeled live merely because a page loads.

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

Planned database/compose commands remain target contracts until NI-003 and later foundation tasks implement them:

```sh
# Planned Compose services: db, api, web; no collector starts automatically.
docker compose up --build
uv run --project apps/api alembic upgrade head
```

Compose mode and native development mode are alternatives; do not start both on the same ports. Native mode starts only `docker compose up -d db` before migrations and app processes. Web `.env` loading is implemented explicitly in [apps/web/src/lib/env.ts](apps/web/src/lib/env.ts) and API loading in [apps/api/src/near_api/settings.py](apps/api/src/near_api/settings.py); missing required configuration makes `/health` return a readable 503 on both services. Production settings and health gates: [deployment](docs/DEPLOYMENT.md). Credentials are placeholders in [.env.example](.env.example).

## Delivery gates

P0 requires real attributable data, public thesis/methodology, a reproducible statistical analysis, authentication, private persisted research, interactive charts, Add Chart/Add Insight, Markdown export and a deployed end-to-end workflow. Full H1 revenue econometrics remains gated on an adequate revenue series. An exploratory model on a clearly named observable proxy does not establish protocol revenue; see the fallback rules in [MVP_SCOPE.md](docs/MVP_SCOPE.md).
