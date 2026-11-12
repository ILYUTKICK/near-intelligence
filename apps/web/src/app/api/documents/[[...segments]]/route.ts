import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { forwardPrivate } from "@/lib/auth/private-gateway";
type Context = { params: Promise<{ segments?: string[] }> };
async function handle(request: NextRequest, context: Context) {
  const { segments = [] } = await context.params;
  let allowed: string[] = [];
  const uuid = (value: string | undefined) => z.uuid().safeParse(value).success;
  const annotation = segments[1] === "insights" || segments[1] === "hypotheses" || segments[1] === "evidence";
  // NI-072 document organization: the metadata-only PATCH (tags/favorite).
  // The bare list GET's tag/favorite query filters flow through untouched.
  const organization = segments[1] === "organization";
  // NI-058 export jobs: create (POST), owner poll (GET) and the ZIP download
  // (GET .../download) — the same document-nested implemented paths the API
  // serves; the download itself carries no query string.
  const exportJob = segments[1] === "exports" && segments.length >= 3 && uuid(segments[2]);
  if (!segments.length) allowed = ["GET", "POST"];
  else if (uuid(segments[0])) {
    if (segments.length === 1) allowed = ["GET", "PATCH", "DELETE"];
    if (segments.length === 2 && organization) allowed = ["PATCH"];
    if (segments.length === 2 && segments[1] === "versions") allowed = ["GET", "POST"];
    if (segments.length === 2 && segments[1] === "chart-blocks") allowed = ["POST"];
    if (segments.length === 2 && segments[1] === "chart-view") allowed = ["GET"];
    if (segments.length === 2 && annotation) allowed = ["GET", "POST"];
    if (segments.length === 3 && annotation && uuid(segments[2])) allowed = ["PATCH", "DELETE"];
    if (segments.length === 2 && segments[1] === "evidence-targets") allowed = ["GET"];
    if (segments.length === 3 && segments[1] === "versions" && uuid(segments[2])) allowed = ["GET"];
    if (segments.length === 2 && segments[1] === "exports") allowed = ["POST"];
    if (exportJob && segments.length === 3) allowed = ["GET"];
    if (exportJob && segments.length === 4 && segments[3] === "download") allowed = ["GET"];
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
  if (annotation && request.nextUrl.search) {
    const entries = [...request.nextUrl.searchParams];
    const keys = segments[1] === "evidence" ? ["version_id", "hypothesis_id"] : ["version_id"];
    if (request.method !== "GET" || entries.some(([key, value]) =>
      !keys.includes(key) || !uuid(value) || request.nextUrl.searchParams.getAll(key).length !== 1)) {
      const label = segments[1] === "insights" ? "insight" : segments[1] === "hypotheses" ? "hypothesis" : "evidence";
      return NextResponse.json({ error: `Unsupported ${label} query.` }, { status: 422, headers: { "cache-control": "no-store" } });
    }
  }
  if (segments[1] === "evidence-targets") {
    const query = request.nextUrl.searchParams;
    const kind = query.get("target_kind");
    const keys = ["target_kind", "cursor", "limit"];
    if ((kind !== "model_run" && kind !== "citation") || request.nextUrl.search.length > 1000
      || [...query.keys()].some(key => !keys.includes(key) || query.getAll(key).length !== 1)) {
      return NextResponse.json({ error: "Unsupported evidence target query." }, { status: 422, headers: { "cache-control": "no-store" } });
    }
  }
  return forwardPrivate(request, `/api/documents${segments.length ? `/${segments.join("/")}` : ""}`);
}
export { handle as GET, handle as POST, handle as PATCH, handle as DELETE };
