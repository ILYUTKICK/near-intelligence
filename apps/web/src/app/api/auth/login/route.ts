import { NextResponse, type NextRequest } from "next/server";

import { ProviderAuthError, signInWithPassword } from "@/lib/auth/provider";
import {
  CSRF_COOKIE,
  CSRF_HEADER,
  SESSION_COOKIE,
  encodeSessionCookie,
  mintCsrfToken,
  safeInternalReturnTo,
  secureCookies,
  verifyCsrfPair,
} from "@/lib/auth/session";

import { loadServerAuthConfig } from "@/lib/auth/config";

/**
 * Same-origin login (NI-017). Mutations require the Origin to be allowlisted
 * AND a valid signed double-submit CSRF pair (cookie + header). Provider
 * failures map to generic, non-enumerating errors. On success the session is
 * stored in a signed HttpOnly cookie; the CSRF cookie rotates.
 */
export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  const allowedOrigins = loadServerAuthConfig().AUTH_ALLOWED_REDIRECT_ORIGINS;
  if (!origin || !allowedOrigins.includes(origin)) {
    return NextResponse.json({ error: "Request origin is not allowed." }, { status: 403 });
  }
  if (!verifyCsrfPair(request.cookies.get(CSRF_COOKIE)?.value, request.headers.get(CSRF_HEADER))) {
    return NextResponse.json({ error: "Missing or invalid CSRF token." }, { status: 403 });
  }

  let email: unknown;
  let password: unknown;
  let returnTo: unknown;
  try {
    ({ email, password, returnTo } = (await request.json()) as Record<string, unknown>);
  } catch {
    return NextResponse.json({ error: "Malformed request body." }, { status: 400 });
  }
  if (typeof email !== "string" || typeof password !== "string" || email.length === 0 || password.length === 0) {
    return NextResponse.json({ error: "Email and password are required." }, { status: 400 });
  }

  try {
    const session = await signInWithPassword(email, password);
    const secure = secureCookies();
    const response = NextResponse.json({ returnTo: safeInternalReturnTo(typeof returnTo === "string" ? returnTo : null) });
    response.cookies.set(SESSION_COOKIE, encodeSessionCookie(session), {
      httpOnly: true,
      sameSite: "lax",
      secure,
      path: "/",
      expires: new Date(session.expiresAt),
    });
    // Rotate the CSRF token with every session change.
    response.cookies.set(CSRF_COOKIE, mintCsrfToken(), {
      httpOnly: false, // double-submit: the client echoes it in a header
      sameSite: "lax",
      secure,
      path: "/",
    });
    return response;
  } catch (error) {
    if (error instanceof ProviderAuthError) {
      const status = error.kind === "rate_limited" ? 429 : error.kind === "unavailable" ? 503 : 401;
      return NextResponse.json({ error: error.message }, { status });
    }
    return NextResponse.json({ error: "Unexpected sign-in failure." }, { status: 500 });
  }
}
