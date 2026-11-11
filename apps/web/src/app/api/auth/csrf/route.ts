import { NextResponse, type NextRequest } from "next/server";

import { loadServerAuthConfig, AuthConfigError } from "@/lib/auth/config";
import { CSRF_COOKIE, SESSION_COOKIE, decodeSessionCookie, mintCsrfToken,
  mintSessionCsrfToken, secureCookies, verifyCsrfPair } from "@/lib/auth/session";

/**
 * Mints the signed double-submit CSRF cookie for an anonymous visitor (the
 * login form reads it via document.cookie and echoes it in X-CSRF-Token).
 * GET is safe: minting a token grants no privileges by itself.
 */
export async function GET(request: NextRequest) {
  try {
    loadServerAuthConfig();
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof AuthConfigError ? error.message : "Server configuration error." },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
  const existing = request.cookies.get(CSRF_COOKIE)?.value;
  if (existing && verifyCsrfPair(existing, existing)) {
    return NextResponse.json({ token: existing }, { headers: { "cache-control": "no-store" } });
  }
  const session = decodeSessionCookie(request.cookies.get(SESSION_COOKIE)?.value);
  const token = session ? mintSessionCsrfToken(session) : mintCsrfToken();
  const response = NextResponse.json({ token }, { headers: { "cache-control": "no-store" } });
  response.cookies.set(CSRF_COOKIE, token, {
    httpOnly: false, // double-submit requires client-side read
    sameSite: "lax",
    secure: secureCookies(),
    path: "/",
  });
  return response;
}
