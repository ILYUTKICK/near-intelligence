import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { createApiClient } from "../src/index.ts";

test("typed client preserves health success and structured failure", async () => {
  const success = { status: "ok", service: "api", appEnv: "test", checkedAt: "2026-01-01T00:00:00Z" };
  const fixture = JSON.parse(await readFile(new URL("../../../apps/api/tests/fixtures/contracts.json", import.meta.url), "utf8"));
  for (const status of [200, 503]) {
    const responseBody = status === 200 ? success : fixture.error;
    const fetcher: typeof fetch = async (input) => {
      assert.equal((input as Request).url, "https://synthetic.invalid/health");
      return new Response(JSON.stringify(responseBody), { status, headers: { "Content-Type": "application/json" } });
    };
    const client = createApiClient("https://synthetic.invalid", fetcher);
    const result = await client.GET("/health");
    if (status === 200) assert.equal(result.data?.service, "api");
    else assert.equal(result.error?.error.code, "DATA_NOT_READY");
  }
  const exact = fixture.observations[0].value;
  assert.equal(typeof exact, "string");
  assert.equal(exact, "123456789012345678901234567890.000000000000000000000001");
  assert.equal(fixture.observations[1].value, null);
  assert.equal(fixture.observations[2].quality.bound_kind, "lower");
});
