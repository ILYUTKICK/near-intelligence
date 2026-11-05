# Python dependencies and installation contract

Baseline verified 5 November 2026 under NI-001. The user requested an explicit requirements.txt for the second contributor and judges. This change defines and tests the dependency environment; it does not implement the API, database, frontend or actual econometric analysis.

## Files and ownership

- [requirements.in](../requirements.in): direct Python dependencies for the selected backend/research stack. This is the single declaration source until NI-002 creates the Python project.
- [requirements.txt](../requirements.txt): generated exact versions for direct/transitive packages and SHA-256 distribution hashes, with environment markers. Do not edit it by hand or install the unconstrained .in file for a release.
- [.python-version](../.python-version): supported interpreter family CPython 3.13. The family is pinned; final patch/container digest and uv tool pin are still part of foundation/deployment work. Actual smoke-test interpreter was 3.13.3.
- Frontend dependencies belong in future package.json and pnpm-lock.yaml. Python requirements cannot install Next.js/ECharts/Tiptap or replace PostgreSQL, Docker, Node or an auth service.

RoleA owns this NI-001 handoff; roleB reviews API/scientific compatibility and later maintains Python project dependencies. Do not independently upgrade packages in separate environments and call the results one reproducible baseline.

## Verified direct packages

Versions came from the official PyPI index, not remembered version numbers. License strings below are extracted from installed distribution metadata and linked to the matching primary package release; binary distributions may include additional third-party notices. This records a dependency review, not a legal opinion or a guarantee that every bundled license has the same identifier.

| Package | Pinned version | Purpose | Declared license metadata |
| --- | --- | --- | --- |
| [fastapi](https://pypi.org/project/fastapi/0.162.0/) | 0.162.0 | Typed REST API | MIT |
| [uvicorn](https://pypi.org/project/uvicorn/0.54.0/) | 0.54.0 | ASGI server | BSD-3-Clause |
| [pydantic](https://pypi.org/project/pydantic/2.14.3/) | 2.14.3 | Boundary schemas | MIT |
| [pydantic-settings](https://pypi.org/project/pydantic-settings/2.16.2/) | 2.16.2 | Environment configuration | MIT |
| [SQLAlchemy](https://pypi.org/project/SQLAlchemy/2.1.8/) | 2.1.8 | Database access/transactions | MIT |
| [alembic](https://pypi.org/project/alembic/1.20.1/) | 1.20.1 | Schema migrations | MIT |
| [psycopg](https://pypi.org/project/psycopg/3.3.8/) | 3.3.8 | PostgreSQL driver; binary extra | LGPL-3.0-only |
| [httpx](https://pypi.org/project/httpx/0.28.1/) | 0.28.1 | Provider HTTP and API test client | License :: OSI Approved :: BSD License |
| [PyJWT](https://pypi.org/project/PyJWT/2.15.1/) | 2.15.1 | JWT verification; cryptography extra | MIT |
| [pandas](https://pypi.org/project/pandas/3.1.1/) | 3.1.1 | Tabular research data | BSD-3-Clause |
| [numpy](https://pypi.org/project/numpy/2.5.4/) | 2.5.4 | Numeric arrays | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| [scipy](https://pypi.org/project/scipy/1.18.1/) | 1.18.1 | Scientific/statistical routines | License :: OSI Approved :: BSD License |
| [statsmodels](https://pypi.org/project/statsmodels/0.15.0/) | 0.15.0 | Econometric estimation/diagnostics | BSD-3-Clause |
| [matplotlib](https://pypi.org/project/matplotlib/3.11.2/) | 3.11.2 | Offline diagnostic figures | License :: OSI Approved :: Python Software Foundation License |

There are 48 resolved requirement entries including transitive dependencies. Database authentication/ownership is not delegated to these libraries automatically; application code and tests must implement the security specification. No LLM, wallet-signing, cloud-query SDK or notebook server is added.

## Install now: Python environment only

From the repository root, using an installed CPython 3.13:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements.txt
.venv/bin/python -m pip check
```

On Windows use the installed Python3.13 launcher to create the environment and .venv\Scripts\python.exe for pip; Windows execution is not verified by this baseline. On macOS/Linux python3 may be used if its actual version is 3.13. Do not use sudo or modify system packages. No provider credentials or data collection are needed to install dependencies.

Hash-checking installs fail if an unpinned/unhashed dependency is introduced. Binary-only installation fails clearly on an unsupported platform instead of silently compiling a scientific stack. See [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/).

## Update and regenerate

Resolver used for this baseline: uv 0.12.13. Maintain the direct list, then resolve all dependencies together and review the diff. The fixed cutoff reproduces this baseline; a deliberate upgrade changes the cutoff and requires fresh compatibility checks.

```sh
uv pip compile requirements.in --python-version 3.13 --universal --generate-hashes --only-binary :all: --default-index https://pypi.org/simple --exclude-newer 2026-11-05T15:55:39Z --output-file requirements.txt
```

The universal resolution emits platform markers; it does not prove every operating system/architecture works. Do not manually use pip freeze from a personal environment, append new top-level names to the generated file, remove hashes to make installation pass, or publish package caches/virtual environments. [uv locking documentation](https://docs.astral.sh/uv/pip/compile/) describes the generation mechanism.

### Transition in NI-002

When apps/api/pyproject.toml and apps/api/uv.lock are implemented, move the direct declarations into that project, preserve the reviewed baseline unless a justified update is required, and make uv.lock the exact environment source. Export root requirements.txt from the frozen lock with hashes; update these instructions and remove/deprecate requirements.in in the same change. There must not be independent uv and pip version selections. Include all Python dependencies used by the registered research runner in the export; development-only test/lint packages belong in explicit dev groups.

The intended export contract, to verify against the actual future project, is:

```sh
uv export --project apps/api --frozen --no-dev --no-emit-project --output-file requirements.txt
```

Do not claim this command works now: the project and uv.lock do not yet exist. Requirements install only third-party dependencies; the future Docker/app startup must also include/install the actual near_api source package.

## Actual verification and limits

- Fresh isolated venv on macOS ARM64, CPython 3.13.3: hash-checked binary-only installation passed; pip check reported no broken requirements.
- All 14 direct module imports passed, including PostgreSQL driver and cryptography-backed JWT package.
- Synthetic NumPy/SciPy/statsmodels linear-algebra/OLS smoke passed; Matplotlib rendered a temporary PNG. This is package compatibility verification, not a published research result or fitted NEAR model.
- Hash-checked binary wheel installation into a temporary cross-platform target for CPython 3.13 Linux x86_64/manylinux 2.28 passed. Linux binaries were not executed on macOS.
- No database connection, JWT-provider configuration, API service, browser flow or Docker application deployment was tested. Docker daemon is unavailable in the current session. Windows and Linux runtime execution remain release checks.
- Legacy research scripts/inputs remain excluded from GitHub. Installing dependencies does not make missing research inputs available. Judge reproduction needs a separately authorized versioned input/code bundle.

See [judge setup](JUDGE_SETUP.md) for the distinction between a ready dependency environment and a deployable release.
