import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { forwardPrivate } from "@/lib/auth/private-gateway";
type Context = { params: Promise<{ segments?: string[] }> };

/**
 * Same-origin read gateway for the NI-054 public model-run catalog
 * (NI-055): the editor's model-result block and its published-run chooser
 * fetch published runs through the session-checked private gateway like
 * every other API read — never a browser-direct cross-origin call and never
 * an arbitrary forwarded URL. GET only: the catalog and one run detail.
 */
async function handle(request: NextRequest, context: Context) {
  const { segments = [] } = await context.params;
  const uuid = (value: string | undefined) => z.uuid().safeParse(value).success;
  let allowed: string[] = [];
  if (!segments.length) allowed = ["GET"];
  else if (segments.length === 1 && uuid(segments[0])) allowed = ["GET"];
  if (!allowed.length) return NextResponse.json({ error: "Not found." }, { status: 404, headers: { "cache-control": "no-store" } });
  if (!allowed.includes(request.method)) return new NextResponse(null, { status: 405,
    headers: { allow: allowed.join(", "), "cache-control": "no-store" } });
  const query = request.nextUrl.searchParams;
  if (segments.length === 1) {
    // One run detail is identified by its path only.
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
  return forwardPrivate(request, `/api/model-runs${segments.length ? `/${segments.join("/")}` : ""}`);
}
export { handle as GET };
