# near-api

FastAPI backend runtime skeleton for NEAR Intelligence (NI-002).

- Source: `src/near_api/` (src layout, installed editable by `uv sync --project apps/api --frozen`).
- Configuration: root `.env` created from [.env.example](../../.env.example); loading is explicit and injected environment variables win. `/health` returns 503 with a readable message when required configuration is missing.
- Nothing else starts on boot: no collectors, no models, no ingestion, no scheduler.
- Runbook: [root README](../../README.md), [dependencies](../../docs/DEPENDENCIES.md), [deployment](../../docs/DEPLOYMENT.md).
