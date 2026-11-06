# Developer environment handoff (role B / second machine)

Prepared 6 November 2026 so role B can start **NI-018/NI-019** on a second machine. The identity provider is the operator's dev Supabase project (created from the [AUTHENTICATION_SECURITY.md](AUTHENTICATION_SECURITY.md) checklist). Read [AUTHENTICATION_SECURITY.md](AUTHENTICATION_SECURITY.md) and [CONTRIBUTING.md](../CONTRIBUTING.md) first; statuses live in [TASKS.md](TASKS.md).

## 0. Baseline (do first)

```sh
git pull origin main          # main moved past cfdd914: NI-006..NI-017 are merged
cp .env.example .env          # then fill per the table below
pnpm install --frozen-lockfile
pnpm lint && pnpm typecheck && pnpm test   # must be green before you start
```

Reviewer for your pull requests is **role A (ILYUTKICK agent session)**; open PRs against `main`, never merge them yourself unless the operator says so.

## 1. Identity provider (shared, non-secret)

| Variable | Value | Secret? |
| --- | --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://athvdjlaovigvffmksbi.supabase.co` | public |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | copy from dashboard → API Keys (**publishable** key, `sb_publishable_…`; never the `sb_secret_…` one) | public by design |
| `SUPABASE_JWT_ISSUER` | `https://athvdjlaovigvffmksbi.supabase.co/auth/v1` | public |
| `SUPABASE_JWKS_URL` | `https://athvdjlaovigvffmksbi.supabase.co/auth/v1/.well-known/jwks.json` | public |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | public |
| `SUPABASE_JWT_ALGORITHM` | `ES256` (verified: JWKS serves an EC key, GoTrue v2.197.0) | public |
| `AUTH_ALLOWED_REDIRECT_ORIGINS` | `http://localhost:3000` | public |

Verified 6 November 2026: JWKS serves ES256; a gateway round trip (login → HttpOnly cookie → ES256 verification against this JWKS → logout with `refresh_token_not_found` after revoke) passes.

## 2. Machine-local values (generate yourself, never share)

| Variable | How |
| --- | --- |
| `AUTH_COOKIE_SIGNING_SECRET` | `openssl rand -base64 32` (PowerShell: `-join ((1..48) \| % { [char](Get-Random -InputObject (48..57+65..90+97..122)) })` or any 32+ char random) |
| `CSRF_SIGNING_SECRET` | second independent random value |
| `DATABASE_URL` / `MIGRATION_DATABASE_URL` | only if you explicitly need the shared Supabase Postgres: the operator holds the DB password from project creation and shares it privately; **NI-018/NI-019 tests do not need it** — `scripts/run-db-tests.py` spins its own disposable PostgreSQL 18 cluster |
| `APP_ENV` / `APP_ORIGIN` / `API_INTERNAL_URL` | `development` / `http://localhost:3000` / `http://localhost:8000` |

## 3. Test account

`alice@test.local` exists in the dev project (email confirmed). Treat the shared password as disposable; rotate it from the dashboard (Authentication → Users → … → Send password recovery / set password) if you prefer your own.

Mint a **real token** for manual verification (never commit this into tests):

```sh
curl -s -X POST "https://athvdjlaovigvffmksbi.supabase.co/auth/v1/token?grant_type=password" \
  -H "apikey: <NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY>" -H "content-type: application/json" \
  -d '{"email":"alice@test.local","password":"<current>"}'
```

The response carries `access_token` (ES256 JWT), `refresh_token`, `expires_in`. Verify it exactly like the gateway does: ES256 signature against the JWKS URL, `iss`/`aud` as in the table, `exp`/`nbf`, `sub` UUID.

## 4. NI-018/NI-019 test recipe (CI-safe)

- **Committed tests must stay offline**: CI has no provider secrets and the [checks workflow](../.github/workflows/checks.yml) enforces frozen installs only. Follow the existing patterns: `apps/web/tests/auth-gateway.test.ts` (stubbed provider fetch) and `apps/api/tests/test_contracts.py` (in-process TestClient).
- Generate your own ES256 keypair locally for the mock JWKS, sign synthetic tokens with it, and verify your verifier accepts correct iss/aud and rejects forged/expired/wrong-issuer/wrong-audience/HS256/`alg=none` and JWT-supplied `jku`. The real-JWKS path is your **local-only smoke** (step 3), not a CI step.
- Server-side config already exists: `apps/api/src/near_api/auth_settings.py` (`get_auth_settings()`) and `apps/api/src/near_api/settings.py` (`find_repo_root`, error style). Web contract: `apps/web/src/lib/auth/config.ts`; provider REST client: `apps/web/src/lib/auth/provider.ts`.

## 5. PostgreSQL 18 on your machine

Your NI-003 verification already used `scripts/run-db-tests.py --pg-bin 'C:/Program Files/PostgreSQL/18/bin'` — same contract in CI (ubuntu + PGDG 18). Keep the disposable-cluster pattern; never point tests at the shared Supabase database.

## 6. Archive handoff (only when NI-026 unblocks)

NI-026 is BLOCKED on OQ-03 (operator must approve one refresh source + quota; see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)). When the operator approves and hands over the historical archive outside GitHub: verify byte hashes against the archive-owner manifest before importing anything (NI-027 rejects on mismatch). Do not request archive files through the repository.
