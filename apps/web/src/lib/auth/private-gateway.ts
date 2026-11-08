import { NextResponse, type NextRequest } from "next/server";
import { loadServerAuthConfig } from "./config";
import { CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE, decodeSessionCookie, verifyCsrfPair } from "./session";
import { loadServerEnv } from "@/lib/env";

/** Fixed internal API paths only; never forward browser cookies/Authorization. */
export async function forwardPrivate(request: NextRequest, apiPath: string) {
  const fail = (status: number, message: string) => NextResponse.json({ error: message },
    { status, headers: { "cache-control": "no-store" } });
  try {
    const config = loadServerAuthConfig();
    const session = decodeSessionCookie(request.cookies.get(SESSION_COOKIE)?.value);
    if (!session) return fail(401, "Sign in to continue.");
    const mutation = request.method !== "GET";
    if (mutation && (!config.AUTH_ALLOWED_REDIRECT_ORIGINS.includes(request.headers.get("origin") ?? "") ||
      !verifyCsrfPair(request.cookies.get(CSRF_COOKIE)?.value, request.headers.get(CSRF_HEADER)))) {
      return fail(403, "Request origin or CSRF token is invalid.");
    }
    const headers = new Headers({ accept: "application/json", authorization: `Bearer ${session.accessToken}` });
    for (const key of ["content-type", "idempotency-key", "if-match"]) {
      const value = request.headers.get(key);
      if (value) headers.set(key, value);
    }
    let body: string | undefined;
    if (mutation && request.body) {
      const reader = request.body.getReader();
      const decoder = new TextDecoder();
      let bytes = 0;
      body = "";
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        bytes += chunk.value.byteLength;
        if (bytes > 2_000_000) { await reader.cancel(); return fail(413, "Request is too large."); }
        body += decoder.decode(chunk.value, { stream: true });
      }
      body += decoder.decode();
    }
    const url = new URL(apiPath, loadServerEnv().API_INTERNAL_URL);
    url.search = request.nextUrl.search;
    const response = await fetch(url, { method: request.method, headers, body: body || undefined,
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(15_000) });
    const resultHeaders = new Headers({ "cache-control": "no-store" });
    for (const key of ["content-type", "content-disposition", "etag", "x-request-id"]) {
      const value = response.headers.get(key);
      if (value) resultHeaders.set(key, value);
    }
    return new NextResponse(response.status === 204 ? null : await response.arrayBuffer(),
      { status: response.status, headers: resultHeaders });
  } catch {
    return fail(503, "The private API could not be reached. Try again.");
  }
}
