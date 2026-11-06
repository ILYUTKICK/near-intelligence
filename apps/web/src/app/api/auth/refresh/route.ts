import { NextResponse, type NextRequest } from "next/server";

import { AuthConfigError, loadPublicAuthConfig, loadServerAuthConfig } from "@/lib/auth/config";
import {
  SESSION_COOKIE,
  decodeSessionCookie,
  encodeSessionCookie,
  mintCsrfToken,
  secureCookies,
} from "@/lib/auth/session";
import { checkRateLimit, clientKey } from "@/lib/auth/rate-limit";

/**
 * Server-side refresh-token rotation (NI-020): the gateway exchanges the
 * session's refresh token for a fresh access token and rotates both cookies.
 * A revoked or expired refresh token clears the session honestly (401) —
 * the browser must never keep a session the provider no longer honors.
 */
export async function POST(request: NextRequest) {
  let allowedOrigins: string[];
  try {
    allowedOrigins = loadServerAuthConfig().AUTH_ALLOWED_REDIRECT_ORIGINS;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof AuthConfigError ? error.message : "Server configuration error." },
      { status: 503 },
    );
  }
  const origin = request.headers.get("origin");
  if (!origin || !allowedOrigins.includes(origin)) {
    return NextResponse.json({ error: "Request origin is not allowed." }, { status: 403 });
  }
  // Refresh is a credential-bearing mutation: the same conservative bucket.
  const limit = checkRateLimit(`refresh:${clientKey(request)}`, 10, 60_000);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: "Too many attempts. Try again later." },
      { status: 429, headers: { "retry-after": String(limit.retryAfterSeconds) } },
    );
  }

  const session = decodeSessionCookie(request.cookies.get(SESSION_COOKIE)?.value);
  if (!session) {
    return NextResponse.json({ error: "No valid session." }, { status: 401 });
  }

  let response: Response;
  try {
    const { NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY } = loadPublicAuthConfig();
    response = await fetch(new URL("token?grant_type=refresh_token", `${NEXT_PUBLIC_SUPABASE_URL}/auth/v1/`), {
      method: "POST",
      headers: { apikey: NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refreshToken }),
      credentials: "omit",
    });
  } catch {
    // Provider outage: keep the (still signed) session cookie so the client
    // can retry; do not pretend the rotation happened.
    return NextResponse.json(
      { error: "The authentication service is unavailable. Try again shortly." },
      { status: 503 },
    );
  }

  if (!response.ok) {
    // 400-class from the provider means the refresh token is revoked/expired.
    const cleared = NextResponse.json({ error: "Session expired. Sign in again." }, { status: 401 });
    cleared.cookies.set(SESSION_COOKIE, "", { httpOnly: true, sameSite: "lax", secure: secureCookies(), path: "/", maxAge: 0 });
    return cleared;
  }

  const body = (await response.json().catch(() => ({}))) as {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
  };
  if (typeof body.access_token !== "string" || typeof body.refresh_token !== "string" || typeof body.expires_in !== "number") {
    return NextResponse.json({ error: "Session refresh failed." }, { status: 503 });
  }

  const secure = secureCookies();
  const sessionResponse = NextResponse.json({ status: "refreshed" });
  sessionResponse.cookies.set(SESSION_COOKIE, encodeSessionCookie({
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    expiresAt: Date.now() + body.expires_in * 1000,
  }), { httpOnly: true, sameSite: "lax", secure, path: "/", expires: new Date(Date.now() + body.expires_in * 1000) });
  sessionResponse.cookies.set("ni_csrf", mintCsrfToken(), { httpOnly: false, sameSite: "lax", secure, path: "/" });
  return sessionResponse;
}

