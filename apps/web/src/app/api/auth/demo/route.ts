import { NextResponse, type NextRequest } from "next/server";
import { randomUUID } from "node:crypto";
import { z } from "zod";

import { loadServerEnv } from "@/lib/env";
import { checkRateLimit, clientKey } from "@/lib/auth/rate-limit";
import { AuthConfigError, loadPublicAuthConfig, loadServerAuthConfig } from "@/lib/auth/config";
import {
  CSRF_COOKIE,
  CSRF_HEADER,
  SESSION_COOKIE,
  encodeSessionCookie,
  mintCsrfToken,
  secureCookies,
  safeInternalReturnTo,
  verifyCsrfPair,
} from "@/lib/auth/session";

/**
 * Demo sign-in (NI-017): a real provider session without a password, for
 * friction-free evaluation. Supabase anonymous sign-ins create a genuine
 * identity (own sub, own rows, full RLS ownership) — but it is an ephemeral
 * demo account, and the supplied email is stored as a display label in
 * user_metadata only. It never authenticates anything and is never treated
 * as a verified address. A starter investment template belongs to the new
 * verified anonymous identity; permanent accounts retain their separate path.
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
  const limit = checkRateLimit(`demo:${clientKey(request)}`, 5, 60_000);
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

  let parsed: { displayEmail?: unknown; returnTo?: unknown } = {};
  try {
    const value: unknown = await request.json();
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      parsed = value;
    }
  } catch {
    parsed = {};
  }
  const email = z.string().trim().max(254).email().safeParse(parsed.displayEmail);
  if (!email.success) {
    return NextResponse.json({ error: "Enter a valid email address to label your demo." }, { status: 400 });
  }
  const displayEmail = email.data;

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
      signal: AbortSignal.timeout(10_000),
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

  // Seed through the normal authenticated document endpoint: the verified
  // anonymous subject owns the template, never the unverified email label.
  try {
    const { API_INTERNAL_URL } = loadServerEnv();
    const starter = await fetch(new URL("/api/documents", API_INTERNAL_URL), {
      method: "POST",
      headers: {
        authorization: `Bearer ${body.access_token}`,
        "content-type": "application/json",
        "idempotency-key": randomUUID(),
      },
      body: JSON.stringify({ title: "My demo research", template_id: "investment-v1" }),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    if (!starter.ok) {
      throw new Error("Starter research unavailable");
    }
  } catch {
    return NextResponse.json({ error: "Your demo workspace could not be prepared. Try again shortly." }, { status: 503 });
  }

  const secure = secureCookies();
  const requestedReturnTo = safeInternalReturnTo(
    typeof parsed.returnTo === "string" && parsed.returnTo.length <= 4096 ? parsed.returnTo : null);
  const sessionResponse = NextResponse.json({ status: "session", demo: true,
    returnTo: requestedReturnTo === "/" ? "/workspace" : requestedReturnTo });
  sessionResponse.cookies.set(SESSION_COOKIE, encodeSessionCookie({
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    expiresAt: Date.now() + body.expires_in * 1000,
  }), { httpOnly: true, sameSite: "lax", secure, path: "/", expires: new Date(Date.now() + body.expires_in * 1000) });
  sessionResponse.cookies.set(CSRF_COOKIE, mintCsrfToken(), { httpOnly: false, sameSite: "lax", secure, path: "/" });
  return sessionResponse;
}
