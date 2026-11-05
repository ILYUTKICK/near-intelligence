import type { components } from "../src/index.ts";
import { createApiClient } from "../src/index.ts";

type Observation = components["schemas"]["Observation"];
type Selection = components["schemas"]["Selection"];
const selection: Selection = { start: "2026-01-01", end: "2026-01-02", frequency: "day", filters: {} };
const exact: Observation["value"] = "123456789012345678901234567890.000000000000000000000001";
const absent: Observation["value"] = null;
// @ts-expect-error Money must not become a JavaScript number.
const numeric: Observation["value"] = 1.25;
// @ts-expect-error Unknown selection fields are forbidden.
const unknown: Selection = { ...selection, owner_id: "synthetic-forbidden" };
// @ts-expect-error No filter is approved in the bootstrap contract.
const filters: Selection["filters"] = { unsupported: true };
const client = createApiClient("https://synthetic.invalid");
// This function is compiled, never called; it performs no network I/O.
async function compileOnly() {
  const result = await client.GET("/health");
  const service: "api" | undefined = result.data?.service;
  // @ts-expect-error Domain endpoints are not implemented/advertised by NI-004.
  await client.GET("/api/v1/unimplemented");
  return service;
}
void [exact, absent, numeric, unknown, filters, compileOnly];
