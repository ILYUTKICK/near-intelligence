# Contributing

Read [AGENTS.md](AGENTS.md), the mandatory [PLAN.md](PLAN.md), and the task's linked specification. Select only an eligible NI-task, record its claim in TASKS.md before implementation, and follow the plan's handoff/completion protocol. Application implementation is not authorized by this documentation delivery. Git is initialized on `main`; repository setup covers the Git portion of NI-001, while its runtime/toolchain requirements remain pending. See [collaboration setup](docs/COLLABORATION.md). Never reset or rewrite the research archive to obtain a clean tree.

## Workflow

Choose a ready task from [TASKS.md](docs/TASKS.md), confirm its dependencies, set IN_PROGRESS, and use `feat/ni-XXX-description`, `fix/ni-XXX-description` or `docs/ni-XXX-description`. Keep PRs independently reviewable. Declare any contract changes before dependent UI/API work. Generated OpenAPI client updates belong in the same PR as their source schema.

Follow strict TypeScript, typed Pydantic boundaries, Decimal monetary math, UTC periods and central registries. Format with the pinned frontend formatter and Ruff; keep scientific notebooks thin wrappers over versioned Python modules. Do not commit credentials, local cookies, provider responses with authorization headers, or private research exports. Raw research redistribution requires the source/license gate; preserve local evidence until a deliberate archive decision is made.

## Verification contract

Foundation tasks must implement these root scripts/commands and CI equivalents:

```sh
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
uv run --project apps/api ruff check .
uv run --project apps/api pytest
uv run --project apps/api python -m near_api.cli research verify --manifest <path>
```

These commands are planned, not currently installed. Run checks proportional to the change plus affected integration contracts. Private-resource changes require Alice/Bob ownership tests; monetary changes require exact-precision and duplicate-event tests; editor changes require save/reopen/conflict tests. Data changes require immutable old versions and new provenance hashes. [Testing strategy](docs/TESTING_STRATEGY.md) defines mandatory release checks.

## Pull requests

State the user-visible behavior, task ID, rationale, actual checks and results, changed data/definitions, migrations and rollback implications. Include visual evidence for UI work and a source-to-claim trace for research changes. Label synthetic fixtures and do not report fixture models as findings. Review against acceptance criteria before marking DONE; blocked provider access remains BLOCKED with the blocking question ID.

Any new dependency needs a reason, current official documentation, license check, pinned lock entry and compatibility validation. ADRs are required for changing authentication, editor schema, canonical storage, deployment topology or model methodology. Update documentation whenever routes, fields, states, commands, metric definitions or priorities change.

## Dependency changes

Read [DEPENDENCIES.md](docs/DEPENDENCIES.md). The current requirements.txt is generated from requirements.in with exact versions and hashes; use a clean CPython3.13 environment and hash-checked installation. NI-002 migrates declarations to pyproject.toml/uv.lock and exports the compatibility requirements file from that lock. Do not hand-edit the generated file or freeze an unrelated personal environment. Frontend dependencies use package.json/pnpm-lock.yaml once implemented.

Judge setup is a release acceptance criterion: keep [JUDGE_SETUP.md](docs/JUDGE_SETUP.md) synchronized with real working commands. A Python install is not evidence that Docker/auth/database/data/model reproduction works.
