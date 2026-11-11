import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { forwardPrivate } from "@/lib/auth/private-gateway";

type Context = { params: Promise<{ segments?: string[] }> };
async function handle(request: NextRequest, context: Context) {
  const { segments = [] } = await context.params;
  // Allowed shapes: "" (collection), "/{uuid}", "/{uuid}/compare-live".
  const compareLive = segments.length === 2 && segments[1] === "compare-live"
    && z.uuid().safeParse(segments[0]).success;
  const item = segments.length === 1 && z.uuid().safeParse(segments[0]).success;
  if (segments.length > 2 || (segments.length === 2 && !compareLive) || (segments.length === 1 && !item)) {
    return NextResponse.json({ error: "Not found." }, { status: 404, headers: { "cache-control": "no-store" } });
  }
  const allowed = segments.length ? ["GET", "DELETE"] : ["GET", "POST"];
  if (!allowed.includes(request.method)) return new NextResponse(null, { status: 405,
    headers: { allow: allowed.join(", "), "cache-control": "no-store" } });
  return forwardPrivate(request, `/api/snapshots${segments.length ? `/${segments.join("/")}` : ""}`);
}
export { handle as GET, handle as POST, handle as DELETE };
