# Judge and contributor setup

Status 5 November 2026: **the Python dependency environment is ready; the full application is not yet implemented/deployable.** This file is the release runbook entry point. NI-066 and NI-069 must turn the future release steps below into commands tested from a clean clone. Do not present a successful dependency installation as a working product deployment.

## 1. Repository access

Repository:[ILYUTKICK/near-intelligence](https://github.com/ILYUTKICK/near-intelligence), private. Judges need explicitly granted read access or a separately authorized release artifact. Collaborator access for BkycnocTbI does not automatically give judges access. No visibility change or judge invitation is part of the dependency setup.

```sh
git clone https://github.com/ILYUTKICK/near-intelligence.git
cd near-intelligence
```

Use the release's exact commit/tag once available. A branch name alone is mutable. Read README and this file before running any command.

## 2. What works now

Install CPython 3.13, create an isolated environment and install the pinned dependency set:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements.txt
.venv/bin/python -m pip check
```

The declared frontend tool versions are pinned and tool-checked, although no frontend dependency lockfile exists yet (NI-002 installs/pins those): with Node 24 and its bundled corepack on PATH, `corepack pnpm --version` must report `12.16.1` from the `packageManager` pin in [package.json](../package.json); `.node-version` declares the Node 24 LTS family. See [DEPENDENCIES.md](DEPENDENCIES.md) for verified versions, the hex-digest note and platform caveats.

These commands install packages only. They require package-index access or an independently prepared matching wheelhouse. They do not start the application, create users, run migrations or access a blockchain provider. Windows uses the corresponding .venv\Scripts\python.exe path and remains untested here. [Dependency policy and actual checks](DEPENDENCIES.md) specifies supported/tested platforms and version-update rules.

The current repository contains documentation, dependency manifests and visual mockups. Research Markdown reports are included; raw research data, SQL and analysis/collection scripts remain excluded under the user's sharing instruction. Some linked artifact paths intentionally refer to the unshared local archive.

## 3. Required before a judge can deploy the completed product

| Requirement | Deliverable / responsible tasks | Verification required |
| --- | --- | --- |
| Frontend runtime | package.json, pinned Node/pnpm and pnpm-lock.yaml; NI-001/NI-002 | Frozen install and production build from a clean clone |
| Python application | Actual near_api source, pyproject.toml/uv.lock and synchronized root requirements.txt; NI-002 | Dependency hashes match the lock; package imports and health endpoint work |
| Database | PostgreSQL service/roles and committed Alembic migrations; NI-003 | Empty database migrates with documented commands and correct runtime permissions |
| Authentication | Documented local or development Supabase Auth setup and callback/cookie config; NI-016–NI-020 | A new judge can create/use isolated credentials; no production service-role secret or disabled authorization shortcut |
| Configuration | Complete .env.example with required vs optional fields and service hostnames; NI-002/NI-066 | Missing settings fail clearly; copy-and-configure steps actually tested |
| Containers/startup | Dockerfiles, Compose services/volumes and exact one-path startup; NI-066 | docker compose up --build (target command, not available today) plus documented migration/setup produces healthy services |
| Real evidence | Permitted, versioned dataset/model-code artifacts, hashes and reviewed source definitions; NI-026–NI-030/NI-054 | Judge has real input access without hidden developer directories, paid queries or invented seed metrics |
| Model reproduction | Fixed recipe/config/code/locks/manifest; NI-054 | Clean offline rerun matches dataset/design hashes and statistics under stated tolerances |
| Full workflow | Public research→login→chart→document→insight→export; NI-063/NI-069 | Browser/API/DB persistence, two-user isolation and downloaded evidence actually verified |
| Operations | TLS/deployment settings, backups/restore, release tag; NI-067/NI-068 | Final-origin auth and a rehearsed recovery path |

No app command in the target column is claimed to work at this stage. Do not start stopped collectors or issue cloud/paid queries to fill a missing data bundle. The existing sharing restriction is a real release gate: obtain explicit permission for a permitted sanitized/versioned bundle or provide an authorized reproducible retrieval path and disclose any access barrier.

## 4. Required final-release command sequence

NI-066 must document one fully tested path covering prerequisites, clone/tag, environment settings, services, migrations, input import, health URLs, model rerun and shutdown/reset. A judge should not need to inspect application code to discover a missing startup step. Separate Docker and native alternatives; do not start both on the same ports.

Do not use a fabricated database seed, public mocked dashboard, automatic paid source backfill or disabled authentication as a deployment shortcut. Development fixtures belong only in clearly isolated test environments.

## 5. Release verification record

Before the demo, NI-069 records the exact commit/tag, machine/OS/CPU, Python/Node/Docker versions, commands and outputs, required credentials/access, setup time, tested URLs, dataset/model manifest hashes and remaining limitations. Record actual checks, not a copied acceptance checklist. Linux/container runtime verification is still required; Linux wheel availability alone does not satisfy this gate.
