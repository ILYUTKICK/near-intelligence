import { NextRequest } from "next/server";
import { afterEach, expect, it, vi } from "vitest";
import { GET } from "@/app/api/model-runs/[[...segments]]/route";

vi.mock("@/lib/env", () => ({ loadServerEnv: () => ({ API_INTERNAL_URL: "http://api.test:8000" }) }));

const runId = "77777777-7777-4777-8777-777777777777";
const path = `/api/model-runs/${runId}/manifest`;
const context = { params: Promise.resolve({ segments: [runId, "manifest"] }) };
afterEach(() => vi.unstubAllGlobals());

it("streams the recorded manifest attachment through the public route without credentials", async () => {
  const bytes = '{"synthetic":true}\n';
  const headers = { "content-type": "application/json", "content-disposition": 'attachment; filename="manifest.json"',
    "cache-control": "public, immutable", etag: `"${runId}"` };
  const upstream = vi.fn<(url: URL, init: RequestInit) => Promise<Response>>(async () => new Response(bytes, { headers }));
  vi.stubGlobal("fetch", upstream);
  const request = new NextRequest(`http://app.test${path}`, {
    headers: { cookie: "synthetic=private", authorization: "Bearer synthetic" },
  });
  const response = await GET(request, context);
  expect(response.status).toBe(200);
  expect(await response.text()).toBe(bytes);
  for (const [name, value] of Object.entries(headers)) expect(response.headers.get(name)).toBe(value);
  expect(upstream).toHaveBeenCalledOnce();
  const [[url, init]] = upstream.mock.calls;
  expect(url.href).toBe(`http://api.test:8000${path}`);
  expect(init.headers).toBeUndefined();
});

it("rejects manifest queries and unexpected subpaths before forwarding", async () => {
  const upstream = vi.fn();
  vi.stubGlobal("fetch", upstream);
  const request = new NextRequest(`http://app.test${path}?latest=true`);
  expect((await GET(request, context)).status).toBe(422);
  expect((await GET(new NextRequest(`http://app.test${path}/other`), {
    params: Promise.resolve({ segments: [runId, "manifest", "other"] }),
  })).status).toBe(404);
  expect(upstream).not.toHaveBeenCalled();
});
