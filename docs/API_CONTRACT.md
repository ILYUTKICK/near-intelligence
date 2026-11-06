# Executable API contract (NI-004)

FastAPI/Pydantic is the contract source. `packages/shared-types/openapi.json` and
`src/generated/api.ts` are generated artifacts, not separate DTO definitions.
The package's small openapi-fetch wrapper uses generated paths/operations.
Existing implemented HTTP paths are `/health` and read-only `/openapi.json`;
business endpoints arrive with their owning tasks. No fake data route is exposed.

## Boundary rules

Common Pydantic models forbid unknown fields at every model level. Decimal
values are JSON strings: no floats, exponent syntax, nonfinite values or leading
zero ambiguity. DecimalString permits up to 78 integer and 30 fractional digits;
each metric must apply its own storage/economic bounds before serialization.
RawAmountString permits nonnegative integers of up to 78 digits. Model statistics
have their separate finite-float policy in later research tasks.

Selection uses ISO dates and a UTC half-open interval of 1–366 days, frequency
day. The bootstrap filters model accepts only `{}`; no chart filter has yet been
approved. NI-031 must add versioned allowlists and regenerate consumers before
advertising filters. Unsupported input is rejected, never ignored.

Coverage counts are nonnegative integers, observed ≤ expected. Missing/unavailable
quality requires reasons. An observation has a null value exactly when missing
or unavailable, with no fabricated bound; other observations preserve explicit
exact/estimate/lower/upper metadata. Observation timestamps require a timezone
and normalize to UTC. A point's null is never converted to numeric zero.

Errors use `{error:{code,message,request_id,details?,retryable}}`. HTTP validation
does not serialize Pydantic input/context/messages or arbitrary unknown keys;
details use a coarse body/query/path/header location and fixed reason codes.
Malformed application/json is 400; typed validation is 422. Exceptions and
HTTPException details/secret headers do not reach the response. Numeric bounded
Retry-After, Bearer challenge and safe Allow values preserve protocol behavior.
Request IDs are server-generated UUIDs, returned in X-Request-ID; errors are
no-store. Resource services must still implement ownership, safe messages and
private caching under NI-018/NI-019 and later domain tasks.

Health success keeps the existing web-compatible field names. Missing server
configuration still returns readable 503 naming the missing variable, now in
the shared error envelope. OpenAPI generation needs no .env, credentials, DB,
running service or network; the schema contains no observation values.

## Generate and check

After frozen Python and pnpm installs, from repository root:

```sh
pnpm api:generate
pnpm api:check
pnpm --filter @near-intelligence/shared-types typecheck
pnpm --filter @near-intelligence/shared-types test
```

The scripts use `apps/api/.venv` by default. For a different isolated Python:

```sh
node scripts/generate-api.mjs --python /absolute/path/to/python
node scripts/generate-api.mjs --check --python /absolute/path/to/python
```

Generation emits sorted UTF-8/LF OpenAPI and TypeScript with no timestamps or
machine paths. Check mode regenerates only into a verified temporary directory
below ignored .local, compares both artifacts and fails on missing/stale bytes.
It does not edit tracked output. Do not edit generated TypeScript manually.

Python fixtures are explicitly synthetic in `apps/api/tests/fixtures/contracts.json`:

```sh
# PowerShell
$env:PYTHONPATH = 'apps/api/src'
apps/api/.venv/Scripts/python.exe -m unittest discover -s apps/api/tests -p test_contracts.py -v

# POSIX equivalent
PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m unittest discover -s apps/api/tests -p test_contracts.py -v
```

## Verification and consumer handoff

Verified 6 November 2026 on Windows 11, CPython 3.13.15, Node 24.22.1 and pinned
pnpm 12.16.1. Six Python contract/ASGI tests pass; generated package strict
TypeScript check and its local typed-client transport test pass. Negative
compile cases reject numeric money, unknown selection/filter fields and
unimplemented endpoints. Two complete generations produced identical JSON/TS
SHA-256 values and `--check` passes. No provider requests ran.

TypeScript types are compile-time checks; they do not perform runtime response
validation. Dates/ranges and cross-field quality invariants are enforced by
Python. Consumers should import components/paths or createApiClient from
`@near-intelligence/shared-types`, not copy interfaces. No web data consumer is
wired in this task; A reviews the generated boundary/root lock before adoption.

To evolve an endpoint, change the executable Pydantic/route contract, give its
operation a stable unique ID, regenerate both artifacts, typecheck actual
consumers and update API_SPECIFICATION.md in the same PR. A breaking required
field or economic definition needs the consumer handoff from TEAM_PLAN.md.
Domain tasks register schemas when they implement their actual routes.
