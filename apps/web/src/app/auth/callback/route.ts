import { NextResponse, type NextRequest } from "next/server";

import { AuthConfigError, loadServerAuthConfig } from "@/lib/auth/config";
import { ProviderAuthError, exchangeOtp } from "@/lib/auth/provider";
import {
  CSRF_COOKIE,
  SESSION_COOKIE,
  encodeSessionCookie,
  mintCsrfToken,
  safeInternalReturnTo,
  secureCookies,
} from "@/lib/auth/session";

/**
 * Email-link callback (NI-017): signup confirmation and recovery links land
 * here with token_hash + type. The link is exchanged for a session
 * server-side; the browser receives HttpOnly cookies and a redirect to the
 * internal returnTo (allowlisted) — external redirect URLs are impossible
 * by construction. Invalid or expired links return to the login page with a
 * generic error flag, never with provider details.
 */
export async function GET(request: NextRequest) {
  try {
    loadServerAuthConfig();
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof AuthConfigError ? error.message : "Server configuration error." },
      { status: 503 },
    );
  }
  const tokenHash = request.nextUrl.searchParams.get("token_hash");
  const type = request.nextUrl.searchParams.get("type");
  const returnTo = safeInternalReturnTo(request.nextUrl.searchParams.get("return_to"));

  if (!tokenHash || (type !== "signup" && type !== "recovery")) {
    return NextResponse.redirect(new URL("/login?error=invalid_link", request.nextUrl.origin));
  }

  try {
    const session = await exchangeOtp(tokenHash, type);
    const secure = secureCookies();
    const response = NextResponse.redirect(new URL(returnTo, request.nextUrl.origin));
    response.cookies.set(SESSION_COOKIE, encodeSessionCookie(session), {
      httpOnly: true,
      sameSite: "lax",
      secure,
      path: "/",
      expires: new Date(session.expiresAt),
    });
    response.cookies.set(CSRF_COOKIE, mintCsrfToken(), {
      httpOnly: false,
      sameSite: "lax",
      secure,
      path: "/",
    });
    return response;
  } catch (error) {
    if (error instanceof ProviderAuthError && error.kind === "expired_token") {
      return NextResponse.redirect(new URL("/login?error=expired_link", request.nextUrl.origin));
    }
    return NextResponse.redirect(new URL("/login?error=unavailable", request.nextUrl.origin));
  }
}
