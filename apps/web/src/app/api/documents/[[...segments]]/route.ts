import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { forwardPrivate } from "@/lib/auth/private-gateway";
type Context = { params: Promise<{ segments?: string[] }> };
async function handle(request: NextRequest, context: Context) {
  const { segments = [] } = await context.params;
  let allowed: string[] = [];
  const uuid = (value: string | undefined) => z.uuid().safeParse(value).success;
  if (!segments.length) allowed = ["GET", "POST"];
  else if (uuid(segments[0])) {
    if (segments.length === 1) allowed = ["GET", "PATCH", "DELETE"];
    if (segments.length === 2 && segments[1] === "versions") allowed = ["GET", "POST"];
    if (segments.length === 2 && segments[1] === "chart-blocks") allowed = ["POST"];
    if (segments.length === 2 && segments[1] === "chart-view") allowed = ["GET"];
    if (segments.length === 3 && segments[1] === "versions" && uuid(segments[2])) allowed = ["GET"];
    if (segments.length === 6 && segments[1] === "versions" && uuid(segments[2])
      && segments[3] === "chart-blocks" && uuid(segments[4])
      && (segments[5] === "view" || segments[5] === "csv")) {
      if (request.nextUrl.search) return NextResponse.json({ error: "Historical chart requests use saved pins." },
        { status: 422, headers: { "cache-control": "no-store" } });
      allowed = ["GET"];
    }
  }
  if (segments.length === 2 && segments[1] === "chart-view") {
    const keys = new Set(["chart_definition_version_id", "start", "end", "dataset_version", "filters"]);
    const query = request.nextUrl.searchParams;
    if (request.nextUrl.search.length > 3000 || [...query.keys()].some(key => !keys.has(key) || query.getAll(key).length !== 1)) {
      return NextResponse.json({ error: "Unsupported chart query." }, { status: 422, headers: { "cache-control": "no-store" } });
    }
  }
  if (!allowed.length) return NextResponse.json({ error: "Not found." }, { status: 404, headers: { "cache-control": "no-store" } });
  if (!allowed.includes(request.method)) return new NextResponse(null, { status: 405,
    headers: { allow: allowed.join(", "), "cache-control": "no-store" } });
  return forwardPrivate(request, `/api/documents${segments.length ? `/${segments.join("/")}` : ""}`);
}
export { handle as GET, handle as POST, handle as PATCH, handle as DELETE };
