# near-api

FastAPI backend runtime skeleton for NEAR Intelligence (NI-002).

- Source: `src/near_api/` (src layout, installed editable by `uv sync --project apps/api --frozen`).
- Configuration: root `.env` created from [.env.example](../../.env.example); loading is explicit and injected environment variables win. `/health` returns 503 with a readable message when required configuration is missing.
- Nothing else starts on boot: no collectors, no models, no ingestion, no scheduler.
- Runbook: [root README](../../README.md), [dependencies](../../docs/DEPENDENCIES.md), [deployment](../../docs/DEPLOYMENT.md).
- Identity-only PostgreSQL/Alembic foundation and real disposable-cluster checks: [database setup](../../docs/DATABASE_SETUP.md). Migrations are explicit; startup opens no database connection.
- Bearer-JWT verification, principal bootstrap and the `get_principal` dependency for private routes: `src/near_api/auth/` (NI-018; [authentication security](../../docs/AUTHENTICATION_SECURITY.md)). The runtime engine for authenticated routes is built lazily from `DATABASE_URL`.
- Request-scoped ownership: `src/near_api/db/security.py` (verified-owner helpers, standardized `ResourceNotFound` 404, owner-scoped pagination) and `src/near_api/repositories/` (owner-scoped document chain access; NI-019; [database setup](../../docs/DATABASE_SETUP.md)). Private tables carry forced RLS with transaction-local identity; private queries always go through `db/security.principal_transaction`.
- Owner-scoped workspace home: `GET /api/home` in `src/near_api/workspace/` (NI-022; [API specification](../../docs/API_SPECIFICATION.md)). Recent documents are capped at 5 with owner-scoped totals from one `scoped_page` call; pending sections (recent_charts/recent_insights/indicators) serialize as documented empty arrays until NI-035/NI-046-047/NI-031-032 land. Private responses are `no-store`; errors are 401/403 through `get_principal` and the one generic `ResourceNotFound` 404.
- Common schemas, sanitized errors and generated TypeScript: [API contract](../../docs/API_CONTRACT.md). `/openapi.json` is read-only and generation runs offline.
