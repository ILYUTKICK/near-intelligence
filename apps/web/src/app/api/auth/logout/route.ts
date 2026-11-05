import { NextResponse, type NextRequest } from "next/server";

import { AuthConfigError, loadServerAuthConfig } from "@/lib/auth/config";
import { ProviderAuthError, revokeRefreshSession } from "@/lib/auth/provider";
import {
  CSRF_COOKIE,
  CSRF_HEADER,
  SESSION_COOKIE,
  decodeSessionCookie,
  secureCookies,
  verifyCsrfPair,
} from "@/lib/auth/session";

/**
 * Logout (NI-017): revokes the provider refresh session server-side and
 * clears both cookies regardless, so the browser never keeps a session the
 * server considers gone. Cache clearing on the client is the caller's job
 * (NI-020 tests the cross-tab/cache-bleed behavior).
 */
export async function POST(request: NextRequest) {
  let allowedOrigins: string[];
  try {
    allowedOrigins = loadServerAuthConfig().AUTH_ALLOWED_REDIRECT_ORIGINS;
  } catch (error) {
    // Fail closed: without valid configuration no mutation is accepted.
    return NextResponse.json(
      { error: error instanceof AuthConfigError ? error.message : "Server configuration error." },
      { status: 503 },
    );
  }
  const origin = request.headers.get("origin");
  if (!origin || !allowedOrigins.includes(origin)) {
    return NextResponse.json({ error: "Request origin is not allowed." }, { status: 403 });
  }
  if (!verifyCsrfPair(request.cookies.get(CSRF_COOKIE)?.value, request.headers.get(CSRF_HEADER))) {
    return NextResponse.json({ error: "Missing or invalid CSRF token." }, { status: 403 });
  }

  const session = decodeSessionCookie(request.cookies.get(SESSION_COOKIE)?.value);
  if (session) {
    try {
      await revokeRefreshSession(session.refreshToken);
    } catch (error) {
      if (error instanceof ProviderAuthError && error.kind === "unavailable") {
        // Provider unreachable: cookies are still cleared below; the response
        // reports the honest state so the UI can inform the user.
        const response = NextResponse.json(
          { error: "Signed out locally; the provider could not be reached to revoke the session." },
          { status: 503 },
        );
        clearAuthCookies(response);
        return response;
      }
    }
  }
  const response = NextResponse.json({ ok: true });
  clearAuthCookies(response);
  return response;
}

function clearAuthCookies(response: NextResponse) {
  const secure = secureCookies();
  for (const name of [SESSION_COOKIE, CSRF_COOKIE]) {
    response.cookies.set(name, "", {
      httpOnly: name === SESSION_COOKIE,
      sameSite: "lax",
      secure,
      path: "/",
      maxAge: 0,
    });
  }
}
