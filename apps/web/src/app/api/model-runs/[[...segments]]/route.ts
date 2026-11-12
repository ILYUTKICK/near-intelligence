import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { forwardPrivate } from "@/lib/auth/private-gateway";
import { loadServerEnv } from "@/lib/env";
type Context = { params: Promise<{ segments?: string[] }> };

/** The public run detail links here even for anonymous readers. */
async function forwardManifest(request: NextRequest, path: string) {
  try {
    const upstream = await fetch(new URL(path, loadServerEnv().API_INTERNAL_URL), {
      cache: "no-store", redirect: "error", signal: AbortSignal.any([request.signal, AbortSignal.timeout(15_000)]),
    });
    const headers = new Headers({ "cache-control": upstream.ok ? upstream.headers.get("cache-control") ?? "no-store" : "no-store" });
    for (const key of ["content-type", "content-disposition", "etag", "x-request-id"]) {
      const value = upstream.headers.get(key);
      if (value) headers.set(key, value);
    }
    return new NextResponse(upstream.body, { status: upstream.status, headers });
  } catch {
    return NextResponse.json({ error: "The model manifest could not be reached. Try again." },
      { status: 503, headers: { "cache-control": "no-store" } });
  }
}

async function handle(request: NextRequest, context: Context) {
  const { segments = [] } = await context.params;
  const run = z.uuid().safeParse(segments[0]);
  const manifest = segments.length === 2 && segments[1] === "manifest";
  if (segments.length && (!run.success || (segments.length !== 1 && !manifest))) {
    return NextResponse.json({ error: "Not found." }, { status: 404, headers: { "cache-control": "no-store" } });
  }
  if (request.method !== "GET") return new NextResponse(null, { status: 405,
    headers: { allow: "GET", "cache-control": "no-store" } });
  const query = request.nextUrl.searchParams;
  if (segments.length) {
    if (request.nextUrl.search) return NextResponse.json({ error: "Unsupported model query." },
      { status: 422, headers: { "cache-control": "no-store" } });
  } else {
    const keys = new Set(["cursor", "limit", "model_id"]);
    if (request.nextUrl.search.length > 1000
      || [...query.keys()].some(key => !keys.has(key) || query.getAll(key).length !== 1)) {
      return NextResponse.json({ error: "Unsupported model catalog query." },
        { status: 422, headers: { "cache-control": "no-store" } });
    }
  }
  const path = `/api/model-runs${segments.length ? `/${segments.join("/")}` : ""}`;
  return manifest ? forwardManifest(request, path) : forwardPrivate(request, path);
}
export { handle as GET };
