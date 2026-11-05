import { NextResponse, type NextRequest } from "next/server";

import { AuthConfigError, loadPublicAuthConfig, loadServerAuthConfig } from "@/lib/auth/config";
import {
  CSRF_COOKIE,
  CSRF_HEADER,
  SESSION_COOKIE,
  encodeSessionCookie,
  mintCsrfToken,
  secureCookies,
  verifyCsrfPair,
} from "@/lib/auth/session";

/**
 * Demo sign-in (NI-017): a real provider session without a password, for
 * friction-free evaluation. Supabase anonymous sign-ins create a genuine
 * identity (own sub, own rows, full RLS ownership) — but it is an ephemeral
 * demo account, and the optional email is stored as a display label in
 * user_metadata only. It never authenticates anything and is never treated
 * as a verified address. The primary path remains password signup.
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
  if (!verifyCsrfPair(request.cookies.get(CSRF_COOKIE)?.value, request.headers.get(CSRF_HEADER))) {
    return NextResponse.json({ error: "Missing or invalid CSRF token." }, { status: 403 });
  }

  let parsed: { displayEmail?: unknown } = {};
  try {
    parsed = (await request.json().catch(() => ({}))) as { displayEmail?: unknown };
  } catch {
    parsed = {};
  }
  const displayEmail = typeof parsed.displayEmail === "string" ? parsed.displayEmail : "";
  if (displayEmail.length > 254) {
    return NextResponse.json({ error: "The demo email label is too long." }, { status: 400 });
  }

  let response: Response;
  try {
    const { NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY } = loadPublicAuthConfig();
    response = await fetch(new URL("signup", `${NEXT_PUBLIC_SUPABASE_URL}/auth/v1/`), {
      method: "POST",
      headers: { apikey: NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, "content-type": "application/json" },
      body: JSON.stringify({
        is_anonymous: true,
        data: displayEmail ? { demo_email_label: displayEmail } : {},
      }),
      credentials: "omit",
    });
  } catch {
    return NextResponse.json(
      { error: "The authentication service is unavailable. Try again shortly." },
      { status: 503 },
    );
  }

  if (!response.ok) {
    // Provider rejects anonymous sign-ins when the toggle is disabled.
    const status = response.status === 422 || response.status === 403 ? 403 : 503;
    return NextResponse.json(
      {
        error:
          status === 403
            ? "Demo sign-in is not enabled on the authentication provider."
            : "Demo sign-in failed. Try again shortly.",
      },
      { status },
    );
  }

  const body = (await response.json().catch(() => ({}))) as {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
  };
  if (typeof body.access_token !== "string" || typeof body.refresh_token !== "string" || typeof body.expires_in !== "number") {
    return NextResponse.json({ error: "Demo sign-in failed. Try again shortly." }, { status: 503 });
  }

  const secure = secureCookies();
  const sessionResponse = NextResponse.json({ status: "session", demo: true });
  sessionResponse.cookies.set(SESSION_COOKIE, encodeSessionCookie({
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    expiresAt: Date.now() + body.expires_in * 1000,
  }), { httpOnly: true, sameSite: "lax", secure, path: "/", expires: new Date(Date.now() + body.expires_in * 1000) });
  sessionResponse.cookies.set(CSRF_COOKIE, mintCsrfToken(), { httpOnly: false, sameSite: "lax", secure, path: "/" });
  return sessionResponse;
}
