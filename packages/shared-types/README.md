# Shared API types/client

Generated from FastAPI OpenAPI. Import `components`, `paths`, `operations` and
`createApiClient` from `@near-intelligence/shared-types`; there are no manually
maintained DTOs. [Generation, validation and evolution](../../docs/API_CONTRACT.md).

Run `pnpm api:generate` / `pnpm api:check` at root, then
`pnpm --filter @near-intelligence/shared-types typecheck` and `test`.
There is no auth/token storage or provider configuration in this package.
