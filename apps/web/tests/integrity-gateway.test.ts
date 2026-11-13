/** NI-065 gateway routing; synthetic UUIDs, no network or provider access. */
import { NextRequest } from "next/server";
import { afterEach, expect, it, vi } from "vitest";
import { GET, POST, DELETE } from "@/app/api/documents/[[...segments]]/route";
import { forwardPrivate } from "@/lib/auth/private-gateway";

vi.mock("@/lib/auth/private-gateway", () => ({
  forwardPrivate: vi.fn(async () => new Response("{}", { headers: { "cache-control": "no-store" } })),
}));
afterEach(() => vi.clearAllMocks());
const documentId = "22222222-2222-4222-8222-222222222222";
const versionId = "33333333-3333-4333-8333-333333333333";
function request(method: string, segment: string, search = "") {
  const segments = [documentId, segment];
  return [new NextRequest(`http://localhost:3000/api/documents/${segments.join("/")}${search}`, { method }),
    { params: Promise.resolve({ segments }) }] as const;
}

it("forwards current and exact historical integrity reads", async () => {
  for (const query of ["", `?version_id=${versionId}`]) {
    const [input, context] = request("GET", "integrity", query);
    expect((await GET(input, context)).status).toBe(200);
    expect(forwardPrivate).toHaveBeenLastCalledWith(input, `/api/documents/${documentId}/integrity`);
    expect(input.nextUrl.search).toBe(query);
  }
});

it.each([
  "?version_id=invalid", "?version_id=", `?version_id=${versionId}&version_id=${versionId}`,
  `?value=${versionId}`, `?version_id=${versionId}&owner_id=${documentId}`,
  `?version_id=${versionId}&extra=${"x".repeat(100)}`,
])("rejects unsupported integrity query %s without forwarding", async query => {
  const response = await GET(...request("GET", "integrity", query));
  expect(response.status).toBe(422);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(forwardPrivate).not.toHaveBeenCalled();
});

it("permits only GET integrity and POST commentary", async () => {
  expect((await POST(...request("POST", "integrity"))).status).toBe(405);
  expect((await DELETE(...request("DELETE", "integrity"))).status).toBe(405);
  expect((await GET(...request("GET", "grounded-commentary"))).status).toBe(405);
  expect(forwardPrivate).not.toHaveBeenCalled();
  const [input, context] = request("POST", "grounded-commentary");
  expect((await POST(input, context)).status).toBe(200);
  expect(forwardPrivate).toHaveBeenCalledWith(input, `/api/documents/${documentId}/grounded-commentary`);
});

it("rejects commentary query strings before any private forward", async () => {
  expect((await POST(...request("POST", "grounded-commentary", "?endpoint=https://synthetic.example"))).status).toBe(422);
  expect(forwardPrivate).not.toHaveBeenCalled();
});
