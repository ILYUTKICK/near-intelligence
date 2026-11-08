import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { forwardPrivate } from "@/lib/auth/private-gateway";

type Context = { params: Promise<{ segments?: string[] }> };
async function handle(request: NextRequest, context: Context) {
  const { segments = [] } = await context.params;
  if (segments.length > 1 || (segments.length === 1 && !z.uuid().safeParse(segments[0]).success)) {
    return NextResponse.json({ error: "Not found." }, { status: 404, headers: { "cache-control": "no-store" } });
  }
  const allowed = segments.length ? ["GET", "PATCH", "DELETE"] : ["GET", "POST"];
  if (!allowed.includes(request.method)) return new NextResponse(null, { status: 405,
    headers: { allow: allowed.join(", "), "cache-control": "no-store" } });
  return forwardPrivate(request, `/api/saved-charts${segments.length ? `/${segments[0]}` : ""}`);
}
export { handle as GET, handle as POST, handle as PATCH, handle as DELETE };
