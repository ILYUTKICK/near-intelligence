# PostgreSQL identity foundation (NI-003) and private ownership layer (NI-019)

NI-003 created the identity tables `app.users` and `app.user_profiles`;
NI-019 added the private document chain `app.documents`,
`app.document_versions` and `app.document_blocks` with forced row-level
security. The remaining domain tables (scientific/global data, saved charts,
snapshots, insight/hypothesis/evidence projections, jobs) are migrations of
their owning tasks. The API opens no database connection and runs no
migration/ingestion on import or startup.

## Credentials and bootstrap

Use three separate application credentials plus one optional public-query
context. `near_migrator` owns the app schema and migration history; `near_app`
is the runtime; `near_operator` can read identity rows and disable/remove
users; `near_public` (optional, NI-019) is the dedicated context for future
public queries and receives only CONNECT plus whatever read scopes public
data tables grant later. None is superuser, BYPASSRLS, CREATEROLE, CREATEDB
or REPLICATION; no memberships are granted. The bootstrap superuser is a
separate operator-only credential and must never appear in API/web
environments.

For a **new dedicated** database/cluster, `scripts/db/010-roles.sql` reads
DB_BOOTSTRAP_PASSWORD, DB_RUNTIME_PASSWORD, DB_MIGRATION_PASSWORD and
DB_OPERATOR_PASSWORD from the psql environment. It requires distinct
non-placeholder secrets of at least 24 characters, fails on existing role
names and creates the app schema atomically. Setting DB_PUBLIC_PASSWORD
additionally creates `near_public`; without that variable the bootstrap
skips the role and behaves exactly as before (the DB-only Compose service
does not set it yet). It does not alter existing deployment roles. Example
secret generation, to be run locally once per variable and stored only in
ignored .env/secret storage:

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

For native PostgreSQL, an operator creates the dedicated database, sets PGHOST,
PGPORT, PGUSER, PGDATABASE and PGPASSWORD for the bootstrap account, then runs:

```sh
psql --no-psqlrc --file scripts/db/010-roles.sql
```

The DB-only `docker-compose.yml` mounts the same bootstrap SQL for an empty
volume and binds TCP to loopback. It declares `postgres:18.6-bookworm`, a tag
listed by the [official image](https://github.com/docker-library/docs/blob/master/postgres/README.md).
PostgreSQL 18+ uses the versioned cluster layout under `/var/lib/postgresql`.
Set all four DB_*_PASSWORD variables in root .env, including the distinct
DB_BOOTSTRAP_PASSWORD, then the defined Compose command is:

```sh
docker compose up -d db
```

Docker is unavailable in the role-B Windows session: image execution, Compose
health/startup and Linux-container permissions remain unverified. The same SQL
bootstrap was executed by psql against native PostgreSQL 18.6. Do not describe
the Compose definition as a tested deployment. Existing nonempty volumes do not
rerun the init script or rotate credentials; never delete a volume to repair a
configuration mismatch. Full API/web packaging belongs to NI-066 and role A.

## Migrate explicitly

Set MIGRATION_DATABASE_URL to the `near_migrator` credential, DATABASE_URL to
`near_app`, with host/port for native access (or `db:5432` inside Compose).
Root .env is loaded explicitly; injected process variables win. No migration
uses DATABASE_URL as a fallback. From the repository root after frozen uv sync:

```sh
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api alembic -c apps/api/alembic.ini current
```

The migration environment checks the actual login and privileged role flags.
It supports online PostgreSQL migrations only. Downgrade to base is destructive
to identity rows and is for disposable tests or a separately reviewed rollback;
application startup never invokes it. Production uses TLS-protected credentials
and an explicit migration/backup step under deployment tasks.

## Runtime ownership boundary

`create_runtime_engine()` accepts only a near_app psycopg URL and creates a lazy
bounded pool. `user_transaction(engine, verified_subject)` requires an internal
UUID from verified JWT handling (NI-018) or None for an anonymous context, and
verifies after `set_config` that `app.current_user_id()` really matches the
subject — a silently missing identity fails the transaction closed. There is no
HTTP principal/header authorization implementation in NI-003. Callers must not
pass a client-supplied owner ID. NI-018's `bootstrap_principal`
(apps/api/src/near_api/auth/principal.py) is the first consumer: it upserts
identity rows for the JWT-verified subject and rejects disabled users inside
this boundary. NI-019 wires request ownership for domain tables:
`db/security.py` and `repositories/` (see below) are the standard entry points
for private queries.

Before user SQL, the transaction rejects privileged roles, schema/table owners,
memberships and autocommit. It sets `app.user_id` using parameterized
transaction-local set_config, explicitly clearing identity for anonymous work.
The pool reset clears session identity too. Only this boundary may be used for
private queries; repositories also add explicit owner predicates.

The identity tables and the private document chain have enabled and forced RLS.
Runtime can bootstrap only its own subject and cannot change
subject/provider/timestamps/disabled_at. Profiles are visible/mutable only for
the active owner. Documents, versions and blocks are visible/mutable only
through the policies below; versions and blocks are immutable for the runtime
role (no UPDATE grant — removal happens only through the parent-document
cascade). Operator permissions are explicit policies on these tables, not a
global bypass: no read or write access to private content, only the narrow
purge DELETE (USING(true) references no columns, so no SELECT is implied; the
purge flows through the users-table cascade). Disabled users can read their own
identity status so NI-018 can reject them, and `identity_is_active()` in every
private policy independently hides their content rows. `near_public` has no
grants on schema app at all. RLS is defense in depth against query mistakes,
not protection from arbitrary SQL execution with a stolen runtime credential
that can set another identity.

## Ownership helpers and the document repository (NI-019)

`apps/api/src/near_api/db/security.py` centralizes the request-scoped rules:
`verified_owner_id` rejects payload owner fields instead of trusting them,
`owner_scope` is the single allowed owner predicate, `one_or_not_found` raises
`ResourceNotFound` so absent and not-owned resources are the same generic 404,
and `scoped_page` takes the owner predicate as a required argument, applying it
to the same statement as LIMIT/OFFSET with an owner-scoped count — private
list/search cannot be paginated unscoped, and page bounds (default 20, maximum
100) are validated before any query. `principal_transaction` opens the standard
identity context for a verified `Principal`.

`apps/api/src/near_api/repositories/documents.py` is the reference
implementation for the private document chain: create/get/list/search/rename/
delete plus nested version and block access resolved compositionally (a version
is reachable only through an owned document, a block only through an owned
version). Every function takes a connection from `principal_transaction`;
ownership never comes from a request. Document content/schema validation, CAS
revision conflicts and projection regeneration remain with the document
revision service (NI-036); saved charts, snapshots and the
insight/hypothesis/evidence projections plug into the same helpers in their
owning tasks.

The profile PK covers its FK index; user UUIDs are primary keys. No redundant
indexes or unrelated domain tables are created. Timezone names are checked
against PostgreSQL's timezone catalog (excluding posix/right pseudo-paths),
strings have bounded lengths and updated_at changes in a server trigger.

`exact_numeric` rejects floats, nonfinite values, excess integer digits and scale
loss before PostgreSQL can round NUMERIC. The baseline has no financial tables:
tests exercise PostgreSQL NUMERIC(78,0) casts; actual metric column constraints
and raw-event semantics remain for their owning tasks.

## Reproduce real integration tests

With PostgreSQL 18 binaries installed, from repository root:

```sh
# Windows (PowerShell)
apps/api/.venv/Scripts/python.exe scripts/run-db-tests.py --pg-bin 'C:/Program Files/PostgreSQL/18/bin'

# POSIX equivalent (not executed in this session)
apps/api/.venv/bin/python scripts/run-db-tests.py --pg-bin /path/to/postgresql/18/bin
```

The runner uses a random loopback port, random in-memory test passwords, a fresh
cluster below ignored .local, the actual bootstrap SQL and SCRAM host auth. It
executes `test_database.py` (NI-003 identity/RLS), `test_auth_bootstrap.py`
(NI-018 principal bootstrap) and `test_ownership_rls.py` (NI-019 ownership
matrix and RLS probes). It stops only its own cluster before removing its
verified temporary directory; failed shutdown retains files for diagnosis. It
never uses an existing DB or provider. A direct unittest discovery without the
runner skips DB cases, and those skips do not count as an integration pass.

Verified on 6 November 2026: Windows 11, PostgreSQL 18.6, CPython 3.13.15,
frozen apps/api/uv.lock. Eight tests passed, including empty upgrade/down/up,
Alembic metadata drift check, Alice/Bob read/write isolation, anonymous denial,
RLS-off/role/DDL escalation denial, pooled identity reset after commit/rollback
and a session leak, operator-disabled users, invalid FK/timezone/length,
78-digit exact values/79-digit database overflow and atomic rollback. All
identities/amounts are synthetic test fixtures, never research output.

Verified on 6 November 2026 (NI-019, macOS, PostgreSQL 18.6 Homebrew, same
frozen lock): 21 integration tests across the three suites on a disposable
loopback cluster, no skips — including the new NI-019 matrix: two-user
CRUD/search/delete isolation, owner scoping before pagination (25-row scoped
pages, literal wildcard search, page-bound rejections), nested
version/block access rejected across owners, cross-owner FK probes returning
42501 (RLS WITH CHECK) and 23503 (composite FK), the runtime role denied
`UPDATE owner_id` by column grants and denied SET ROLE/DDL/row_security=off,
operator read/write denial with purge-by-delete only, `near_public` denied
everything on schema app, pooled identity reset verified on the private
tables, and the disabled-owner fail closed path (restorable). Empty
upgrade→downgrade→upgrade plus the Alembic metadata drift check cover the new
migration reversibly.
