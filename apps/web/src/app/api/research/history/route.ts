import { createApiClient } from "@near-intelligence/shared-types";
import { NextResponse, type NextRequest } from "next/server";
import { loadServerEnv } from "@/lib/env";

/** Public, read-only data gateway. No private cookies or authorization are forwarded. */
export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams;
  const allowed = new Set(["source", "start", "end", "dataset_version"]);
  if (request.nextUrl.search.length > 500 || [...query.keys()].some((key) => !allowed.has(key) || query.getAll(key).length !== 1)) {
    return NextResponse.json({ error: "Unsupported history selection." }, { status: 422 });
  }
  try {
    const client = createApiClient(loadServerEnv().API_INTERNAL_URL,
      (input, init) => fetch(input, { ...init, cache: "no-store", redirect: "error",
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(15_000)]) }));
    const result = await client.GET("/api/research/history", { params: { query: {
      ...(query.has("source") ? { source: query.get("source")! } : {}),
      ...(query.has("start") ? { start: query.get("start")! } : {}),
      ...(query.has("end") ? { end: query.get("end")! } : {}),
      ...(query.has("dataset_version") ? { dataset_version: query.get("dataset_version")! } : {}),
    } } });
    return NextResponse.json(result.response.ok ? result.data : { error: "Research history is unavailable for this selection." },
      { status: result.response.status, headers: { "cache-control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Research history could not be reached." }, { status: 503, headers: { "cache-control": "no-store" } });
  }
}
