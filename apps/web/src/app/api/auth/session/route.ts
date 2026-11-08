import { NextResponse, type NextRequest } from "next/server";

import { AuthConfigError, loadServerAuthConfig } from "@/lib/auth/config";
import { SESSION_COOKIE, decodeSessionCookie, secureCookies } from "@/lib/auth/session";

/**
 * Session check (NI-020): the client asks "who am I" and receives one of
 * exactly three honest answers — a session with its subject (200), 401 with
 * the cookie cleared (expired/tampered/revoked bearer), or 503
 * (configuration error, cookie kept).
 *
 * Integrity boundary: the cookie is HMAC-signed by this gateway, so its
 * payload is trusted for identity display. Cryptographic JWT verification
 * against the provider JWKS is the API's job (NI-018, apps/api) and runs on
 * every private request; a disabled account fails closed there.
 */
function jwtPayloadSubject(accessToken: string): string | null {
  const [, payload] = accessToken.split(".");
  if (!payload) {
    return null;
  }
  try {
    const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as {
      sub?: unknown;
    };
    return typeof claims.sub === "string" ? claims.sub : null;
  } catch {
    return null;
  }
}

export async function GET(request: NextRequest) {
  try {
    loadServerAuthConfig();
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof AuthConfigError ? error.message : "Server configuration error." },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }

  const session = decodeSessionCookie(request.cookies.get(SESSION_COOKIE)?.value);
  if (!session) {
    const response = NextResponse.json({ error: "No valid session." }, { status: 401, headers: { "cache-control": "no-store" } });
    if (request.cookies.get(SESSION_COOKIE)?.value) {
      // Cookie present but expired/tampered: clear it so the client stops retrying.
      response.cookies.set(SESSION_COOKIE, "", {
        httpOnly: true,
        sameSite: "lax",
        secure: secureCookies(),
        path: "/",
        maxAge: 0,
      });
    }
    return response;
  }

  return NextResponse.json({
    status: "ok",
    subject: jwtPayloadSubject(session.accessToken) ?? "unknown",
    expiresAt: new Date(session.expiresAt).toISOString(),
  }, { headers: { "cache-control": "no-store" } });
}
