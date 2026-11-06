import createClient from "openapi-fetch";
import type { paths } from "./generated/api.ts";

export type { components, operations, paths } from "./generated/api.ts";

// The caller selects its gateway/internal origin and supplies fetch when needed.
// No cookie, JWT, environment loading, retries or DTOs are maintained here.
export function createApiClient(baseUrl: string, fetcher: typeof globalThis.fetch = globalThis.fetch) {
  return createClient<paths>({ baseUrl, fetch: fetcher });
}
