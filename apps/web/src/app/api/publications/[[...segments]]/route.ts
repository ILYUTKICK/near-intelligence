import { NextResponse, type NextRequest } from "next/server";
import { loadServerEnv } from "@/lib/env";
import { forwardPrivate } from "@/lib/auth/private-gateway";

type Context = { params: Promise<{ segments?: string[] }> };

/**
 * NI-045 publications gateway. Two implemented API paths, each with the
 * exact method/segment shape the API serves:
 *
 * - GET /api/publications/{slug}[?version=n] — a PUBLIC read of the
 *   operator-seeded release (no session, no identity forwarded). Only a
 *   bounded, allow-listed query string (version) is forwarded; the response
 *   carries the API's public cache headers and the projection of published
 *   content only.
 * - POST /api/publications/{slug}/duplicate — an authenticated mutation that
 *   rides the signed-cookie private gateway (session, origin and CSRF pair
 *   verified, Idempotency-Key forwarded) and creates the requester's private
 *   copy server-side. The caller never sends ownership or content.
 *
 * Any other segment shape or method is a typed 404/405 — no open forwarding.
 */
const SLUG = /^[a-z0-9][a-z0-9-]{0,79}$/;

async function handle(request: NextRequest, context: Context) {
  const { segments = [] } = await context.params;
  if (segments.length === 1 && SLUG.test(segments[0])) {
    if (request.method !== "GET") {
      return new NextResponse(null, {
        status: 405,
        headers: { allow: "GET", "cache-control": "no-store" },
      });
    }
    // Public read: no session requirement; only the pinned version query is
    // forwarded (a single positive integer), everything else is refused.
    const query = request.nextUrl.searchParams;
    const version = query.get("version");
    if (request.nextUrl.search.length > 100
      || [...query.keys()].some((key) => key !== "version")
      || query.getAll("version").length > 1
      || (version !== null && !/^[1-9][0-9]{0,8}$/.test(version))) {
      return NextResponse.json(
        { error: "Unsupported publication query." },
        { status: 422, headers: { "cache-control": "no-store" } },
      );
    }
    try {
      const url = new URL(`/api/publications/${segments[0]}`, loadServerEnv().API_INTERNAL_URL);
      url.search = request.nextUrl.search;
      const response = await fetch(url, {
        headers: { accept: "application/json" },
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(15_000)]),
      });
      const headers = new Headers({ "cache-control": response.headers.get("cache-control") ?? "no-store" });
      for (const key of ["content-type", "etag", "x-request-id"]) {
        const value = response.headers.get(key);
        if (value) headers.set(key, value);
      }
      return new NextResponse(response.body, {
        status: response.status, headers,
      });
    } catch {
      return NextResponse.json(
        { error: "The public API could not be reached. Try again." },
        { status: 503, headers: { "cache-control": "no-store" } },
      );
    }
  }
  if (segments.length === 2 && segments[1] === "duplicate" && SLUG.test(segments[0])) {
    if (request.method !== "POST") {
      return new NextResponse(null, {
        status: 405,
        headers: { allow: "POST", "cache-control": "no-store" },
      });
    }
    if (request.nextUrl.search) return NextResponse.json({ error: "Unsupported publication query." }, {
      status: 422, headers: { "cache-control": "no-store" },
    });
    return forwardPrivate(request, `/api/publications/${segments[0]}/duplicate`, {
      expectedSubject: request.headers.get("x-session-subject"),
    });
  }
  return NextResponse.json({ error: "Not found." }, { status: 404, headers: { "cache-control": "no-store" } });
}

export { handle as GET, handle as POST };
