import { NextResponse, type NextRequest } from "next/server";

import { checkRateLimit, clientKey } from "@/lib/auth/rate-limit";
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
 * Email/password signup (NI-017). Same origin + CSRF as login; the provider
 * decides whether a confirmation email is required: when the response
 * carries a session (auto-confirm projects) cookies are set exactly like
 * login, otherwise the response reports "confirmation sent" and no session
 * exists until the email link is exchanged at /auth/callback.
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
  const limit = checkRateLimit(`signup:${clientKey(request)}`, 5, 60_000);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: "Too many attempts. Try again later." },
      { status: 429, headers: { "retry-after": String(limit.retryAfterSeconds) } },
    );
  }
  const origin = request.headers.get("origin");
  if (!origin || !allowedOrigins.includes(origin)) {
    return NextResponse.json({ error: "Request origin is not allowed." }, { status: 403 });
  }
  if (!verifyCsrfPair(request.cookies.get(CSRF_COOKIE)?.value, request.headers.get(CSRF_HEADER))) {
    return NextResponse.json({ error: "Missing or invalid CSRF token." }, { status: 403 });
  }

  let email: unknown;
  let password: unknown;
  try {
    ({ email, password } = (await request.json()) as Record<string, unknown>);
  } catch {
    return NextResponse.json({ error: "Malformed request body." }, { status: 400 });
  }
  if (typeof email !== "string" || typeof password !== "string" || !email.includes("@") || password.length < 8) {
    return NextResponse.json(
      { error: "A valid email and a password of at least 8 characters are required." },
      { status: 400 },
    );
  }

  let response: Response;
  try {
    const { NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY } = loadPublicAuthConfig();
    response = await fetch(new URL("signup", `${NEXT_PUBLIC_SUPABASE_URL}/auth/v1/`), {
      method: "POST",
      headers: { apikey: NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
      credentials: "omit",
    });
  } catch {
    return NextResponse.json(
      { error: "The authentication service is unavailable. Try again shortly." },
      { status: 503 },
    );
  }

  if (response.status === 422) {
    const detail = (await response.json().catch(() => ({}))) as { msg?: string; error_description?: string };
    const alreadyRegistered = /already/i.test(detail.msg ?? detail.error_description ?? "");
    return NextResponse.json(
      {
        error: alreadyRegistered
          ? "This email is already registered. Sign in instead, or recover your password."
          : "The provider rejected this signup. Check the email format and password length.",
      },
      { status: 422 },
    );
  }
  if (response.status === 429) {
    return NextResponse.json(
      { error: "Too many attempts. Try again later." },
      { status: 429 },
    );
  }
  if (!response.ok) {
    return NextResponse.json(
      { error: "Signup failed. Try again shortly." },
      { status: 503 },
    );
  }

  const body = (await response.json().catch(() => ({}))) as {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
  };
  const secure = secureCookies();

  if (typeof body.access_token === "string" && typeof body.refresh_token === "string" && typeof body.expires_in === "number") {
    // Auto-confirmed project: a session exists immediately.
    const sessionResponse = NextResponse.json({ status: "session" });
    sessionResponse.cookies.set(SESSION_COOKIE, encodeSessionCookie({
      accessToken: body.access_token,
      refreshToken: body.refresh_token,
      expiresAt: Date.now() + body.expires_in * 1000,
    }), { httpOnly: true, sameSite: "lax", secure, path: "/", expires: new Date(Date.now() + body.expires_in * 1000) });
    sessionResponse.cookies.set(CSRF_COOKIE, mintCsrfToken(), { httpOnly: false, sameSite: "lax", secure, path: "/" });
    return sessionResponse;
  }

  const confirmationResponse = NextResponse.json({ status: "confirmation_sent" });
  confirmationResponse.cookies.set(CSRF_COOKIE, mintCsrfToken(), { httpOnly: false, sameSite: "lax", secure, path: "/" });
  return confirmationResponse;
}
