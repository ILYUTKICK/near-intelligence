import { NextResponse, type NextRequest } from "next/server";

import { AuthConfigError, loadServerAuthConfig } from "@/lib/auth/config";
import { ProviderAuthError, revokeSession } from "@/lib/auth/provider";
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
      await revokeSession(session);
    } catch (error) {
      // Honest logout: cookies are cleared, but a failed provider-side
      // revocation is reported instead of claiming success — the refresh
      // session could still be live on the provider.
      const message =
        error instanceof ProviderAuthError
          ? `Signed out locally, but the provider session could not be revoked (${error.kind}).`
          : "Signed out locally; the provider session could not be revoked.";
      const response = NextResponse.json({ error: message }, { status: 503 });
      clearAuthCookies(response);
      return response;
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
