# near-api

FastAPI backend runtime skeleton for NEAR Intelligence (NI-002).

- Source: `src/near_api/` (src layout, installed editable by `uv sync --project apps/api --frozen`).
- Configuration: root `.env` created from [.env.example](../../.env.example); loading is explicit and injected environment variables win. `/health` returns 503 with a readable message when required configuration is missing.
- Nothing else starts on boot: no collectors, no models, no ingestion, no scheduler.
- Runbook: [root README](../../README.md), [dependencies](../../docs/DEPENDENCIES.md), [deployment](../../docs/DEPLOYMENT.md).
- Identity-only PostgreSQL/Alembic foundation and real disposable-cluster checks: [database setup](../../docs/DATABASE_SETUP.md). Migrations are explicit; startup opens no database connection.
- Bearer-JWT verification, principal bootstrap and the `get_principal` dependency for private routes: `src/near_api/auth/` (NI-018; [authentication security](../../docs/AUTHENTICATION_SECURITY.md)). The runtime engine for authenticated routes is built lazily from `DATABASE_URL`.
- Common schemas, sanitized errors and generated TypeScript: [API contract](../../docs/API_CONTRACT.md). `/openapi.json` is read-only and generation runs offline.
