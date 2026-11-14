# Judge and contributor setup — tested clean-clone sequence (NI-066)

For the current product overview and first local run, start with the [README](../README.md). For your own production domain use the [self-hosting guide](SELF_HOSTING.md); this page retains the detailed contributor/judge sequence and its dated verification evidence.

Status 10 November 2026: **the P0 application runtime is implemented and this
sequence was executed end to end** (fresh frozen installs, migrations, both
services, and one real export processed by the worker — see "Verification
record" at the bottom for what exactly ran and where). The repository does NOT
contain the raw research archive, so data pages boot into their honest
explicit "unavailable" states; nothing is ever faked to fill the gap. No
command below starts a collector or a provider request.

Two alternative run modes are documented; do not start both on the same ports.

- **Compose mode** (recommended): `docker compose up -d` starts db + api + web.
- **Native mode**: processes on the host against a Compose-or-native
  PostgreSQL 18 database.

## 1. Prerequisites

| Tool | Version | Check |
| --- | --- | --- |
| Git | any recent | `git --version` |
| Node.js | 24 LTS family (`.node-version`) | `node --version` — verified with v24.22.2 |
| pnpm | 12.16.1 (pinned via `packageManager`) | `corepack enable && pnpm --version` — verified 12.16.1 |
| CPython | 3.13 family (`.python-version`) | `python3.13 --version` — containers use 3.13.18 |
| uv | 0.12.13 or compatible | `uv --version` |
| Docker + Compose | for Compose mode and images | `docker version` — verified with Docker 29.9.2 (macOS ARM64) |

On macOS with Homebrew's keg-only `node@24`, prefix the PATH first:

```sh
export PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:$HOME/.local/bin:$PATH"
corepack enable --install-directory /tmp/ni066-bin && export PATH="/tmp/ni066-bin:$PATH"
```

(Any user-writable directory works; `corepack pnpm --version` must print
`12.16.1`, matching the `packageManager` pin in [package.json](../package.json).)

## 2. Clone

```sh
git clone https://github.com/ILYUTKICK/near-intelligence.git
cd near-intelligence
```

The repository is private; judges need explicitly granted read access. Pin the
exact release commit/tag once one is published (NI-069).

## 3. Frozen installs

```sh
pnpm install --frozen-lockfile            # exit 0 — verified fresh on 2026-11-10
uv sync --project apps/api --frozen       # exit 0 — verified fresh on 2026-11-10
uv lock --check --project apps/api        # OK — the lock is the exact source
```

These install packages only; nothing starts. Windows remains untested here
(see [DEPENDENCIES.md](DEPENDENCIES.md) for platform caveats).

## 4. Configuration

```sh
cp .env.example .env
```

Then edit `.env` (it is git-ignored; never commit it):

1. **Database secrets** — generate four DISTINCT values (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`; at least 24 characters, no
   `REPLACE` substring, URL-encode if they contain `@`/`:`):
   `DB_BOOTSTRAP_PASSWORD`, `DB_RUNTIME_PASSWORD`, `DB_MIGRATION_PASSWORD`,
   `DB_OPERATOR_PASSWORD`. They map to the four DB roles described in
   [DATABASE_SETUP.md](DATABASE_SETUP.md).
2. **Auth (real Supabase dev project)** — set `NEXT_PUBLIC_SUPABASE_URL`,
   `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_JWT_ISSUER`,
   `SUPABASE_JWKS_URL`, `SUPABASE_JWT_AUDIENCE` (default `authenticated`),
   `SUPABASE_JWT_ALGORITHM=ES256`, plus
   `AUTH_COOKIE_SIGNING_SECRET` and `CSRF_SIGNING_SECRET`
   (`openssl rand -base64 32`). To sign in, the dev project needs **Anonymous
   sign-ins enabled** (that is how the clearly labeled Demo sign-in creates a
   real isolated session — operator decision recorded in
   [AUTHENTICATION_SECURITY.md](AUTHENTICATION_SECURITY.md)).

   Honest limitation: the product supports Supabase Auth only. There is NO
   supported "local synthetic auth mode" — the synthetic session keys seen in
   the repository exist only inside the isolated test harness
   (`scripts/run-db-tests.py` and the e2e harness), never in the product.
   Without reachable provider configuration, login fails honestly while
   public pages and both `/health` endpoints still work.
3. **Runtime URLs** — keep `APP_ENV=development`,
   `APP_ORIGIN=http://localhost:3000`,
   `AUTH_ALLOWED_REDIRECT_ORIGINS=http://localhost:3000`. The `DATABASE_URL`,
   `MIGRATION_DATABASE_URL` and `OPERATOR_DATABASE_URL` localhost values in
   `.env.example` are for native mode; Compose builds its own container-side
   URLs from the four DB secrets, so the `localhost` values never enter a
   container. If host ports 3000/8000/5432 are occupied, set
   `WEB_HOST_PORT` / `API_HOST_PORT` / `DB_PORT` and align `APP_ORIGIN`
   accordingly.

## 5. Data availability (input bundle)

What a fresh clone CAN ship: documentation, model code and preregistered
configs, and Markdown research reports. What it CANNOT ship: the raw saved
research datasets, SQL and collection scripts (excluded from GitHub by the
user's sharing instruction; the local archive is machine-only). Therefore:

- With no input bundle, public data/chart pages render their explicit typed
  "unavailable" states (NI-032). Missing is not zero; nothing is fabricated.
- Real data arrives only via (a) a separately authorized, versioned,
  sanitized bundle handoff to the judge (not downloadable from the repository
  today), or (b) the operator-approved bounded refresh CLI (NI-030) — one
  guarded attempt per invocation, budgets persisted, effective allowlist
  empty in every fresh environment until an operator approves a source row.
- The legacy collectors are stopped (`STOP_PUBLIC_COLLECTION`); no command in
  this runbook resumes them.

## 6. Run — Compose mode

```sh
docker compose -f docker-compose.yml build api web
docker compose -f docker-compose.yml up -d --wait db
docker compose -f docker-compose.yml run --rm -T migrate
docker compose -f docker-compose.yml up -d --wait api web
docker compose -f docker-compose.yml ps
```

`up` never runs migrations, ingestion or the worker. The one-shot operator
actions are explicit:

- `docker compose run --rm migrate` — migrations (re-runnable; exits 0 when
  already current, and refuses non-`near_migrator` credentials with a
  readable error — both verified).
- `docker compose run --rm worker` — processes currently queued export jobs
  once and exits (near_app for job-owner transactions, near_operator for the
  lease; verified: empty queue → `processed 0 export job(s)`, exit 0).
- `docker compose --profile refresh run --rm refresh` — ONE guarded refresh
  attempt (near_operator). In a fresh environment this refuses with exit 3
  (`source_not_approved`) before any network request — verified.

## 7. Run — native mode (alternative)

Start only the database (Compose below, or your own PostgreSQL 18 with
`scripts/db/010-roles.sql` — see [DATABASE_SETUP.md](DATABASE_SETUP.md)):

```sh
docker compose up -d db
```

Migrate and run the services as host processes (env vars override the
localhost `.env` values when you changed ports):

```sh
export MIGRATION_DATABASE_URL="postgresql+psycopg://near_migrator:<DB_MIGRATION_PASSWORD>@localhost:5432/near_intelligence"
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head   # exit 0 — verified

export DATABASE_URL="postgresql+psycopg://near_app:<DB_RUNTIME_PASSWORD>@localhost:5432/near_intelligence"
export API_INTERNAL_URL=http://localhost:8000
pnpm --filter web build                                             # required before production start
uv run --project apps/api uvicorn near_api.main:app --port 8000          # verified /health 200

API_INTERNAL_URL=http://localhost:8000 pnpm --filter web start           # verified /health 200
```

The export worker runs the same way (the Node renderer resolves from the repo
layout; the seams `NEAR_CHART_RENDERER_NODE`/`NEAR_CHART_RENDERER_SCRIPT`
exist for operator pinning and tests):

```sh
export OPERATOR_DATABASE_URL="postgresql+psycopg://near_operator:<DB_OPERATOR_PASSWORD>@localhost:5432/near_intelligence"
uv run --project apps/api python -m near_api.exports.worker \
  --database-url "$DATABASE_URL" --operator-database-url "$OPERATOR_DATABASE_URL"
```

## 8. Verify

1. **Health/readiness** — `curl http://localhost:3000/health` and
   `curl http://localhost:8000/health` both return 200 JSON
   (`{"status":"ok",...}`; verified). A container/process missing required
   configuration returns a readable 503 naming the missing variables —
   verified for both images (`CONFIGURATION_ERROR: ... APP_ENV: Field
   required; ...`).
2. **Migration state** — `docker compose run --rm migrate` exits 0 on an
   already-migrated database; the applied head is `0012_export_jobs`.
3. **One export through the worker** (the full product path; verified
   end to end on 2026-11-10 — see the record at the bottom):
   1. Sign in via the clearly labeled **Demo** block on `/login` (creates a
      real anonymous provider session with full RLS ownership), or use
      email sign-in if you enabled it.
   2. Create a research document, type a paragraph, save a revision.
   3. Export → the dialog queues a job; run the worker (Compose or native
      command above) to process it; the dialog then downloads the ZIP.
   4. Unzip: `manifest.json` pins the exact revision, version id,
      `content_sha256` and per-file SHA-256 hashes — all re-verifiable.

   A prose-only export needs no dataset; chart blocks additionally need an
   approved dataset version in the scientific zone (see section 5). Without a
   session the export routes are owner-checked and generic-404 (verified by
   the NI-058/NI-063 suites: Bob cannot create, poll or download).
4. **Images contain no secrets/data** — see
   [deployment/README.md](../deployment/README.md) for the recorded digest
   pins and the context-boundary test (`.env`, `research/`, `product-plan/`
   never enter the build context; verified by exporting the exact context).

## 9. Shutdown and reset

```sh
docker compose down          # stop everything; volumes persist for the next session
docker compose down -v       # also drop the DB and artifact volumes (full reset)
```

`down -v` destroys all local data — it is a reset, not a repair. Never delete
a volume to "fix" a credential mismatch on a database you care about.

## 10. Verification record (2026-11-10, NI-066 dispatch, macOS ARM64, Docker 29.9.2)

Executed in this dispatch, from a clean worktree of origin/main af69f9a:
`pnpm install --frozen-lockfile` exit 0 (566 packages); `uv sync --project
apps/api --frozen` exit 0 (49 packages); `uv lock --check` OK; fresh Compose
volume `docker compose up -d` (db+api+web all healthy); api `/health` 200,
web `/health` 200, landing 200; `docker compose run --rm migrate` exit 0
(applied head `0012_export_jobs`, roles `near_app`/`near_migrator`/
`near_operator`/`near_bootstrap` verified); re-run exit 0 (idempotent);
wrong-role migration refused with the readable
`Migrations require the separate near_migrator psycopg credential` (exit 1);
worker one-shot on an empty queue exit 0; refresh one-shot with a `near_app`
URL refused (exit 5, typed credential error) and with the `near_operator`
URL refused with exit 3 `source_not_approved` before any request; both images
probed without configuration → readable 503s; build context exported and
contained no `.env`/`research/`/`product-plan/`/`node_modules`. The full
authenticated journey (demo session → document → revision 2 → export job →
worker `succeeded` → download → ZIP manifest hashes verified) ran on the
native runtime against a fresh disposable database on non-default ports
(3000/8000/5432 were occupied by unrelated local projects on this machine;
the ports themselves are a configuration matter, not a code path). The
in-image renderer check (Python boundary → packaged Node renderer → verified
SVG/CSV/hashes, echarts 6.1.0, node 24.22.2) ran inside the API image.

Not yet verified by the packaging evidence above (recorded, not claimed):
the final integrated Linux-container runtime rehearsal, production TLS
origin, and restore drills. Under the owner's 11 November finish→local→deploy
order, **NI-079 must verify the local Linux-container flow and local restore
before any remote rollout**. NI-067 verifies the final TLS origin; NI-068
verifies actual remote backups/restore; NI-069 verifies deployed judge
reproduction. These are separate gates, not claims of completed checks.
See [the current handoff](FINISH_BEFORE_DEPLOY_PROMPT.md). Windows native
remains untested (see [DEPENDENCIES.md](DEPENDENCIES.md)).
