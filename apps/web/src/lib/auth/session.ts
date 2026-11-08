import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

import { loadServerAuthConfig } from "./config";

/**
 * Signed session-cookie lifecycle (NI-017).
 *
 * The browser receives cookies only; application JS can never read tokens
 * (HttpOnly). The cookie value is HMAC-signed with the server secret so a
 * tampered payload is rejected before any provider call. Secure is enforced
 * in production; SameSite=Lax per AUTHENTICATION_SECURITY.md — the CSRF
 * token, not SameSite alone, guards mutations.
 */
export const SESSION_COOKIE = "ni_session";
export const CSRF_COOKIE = "ni_csrf";
export const CSRF_HEADER = "x-csrf-token";

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  /** Absolute expiry (epoch ms) of the access token. */
  expiresAt: number;
}

function signingSecret(): string {
  return loadServerAuthConfig().AUTH_COOKIE_SIGNING_SECRET;
}

export function secureCookies(): boolean {
  // APP_ENV comes from the web env contract (NI-002); production runs behind
  // TLS, so Secure is mandatory there.
  return process.env.APP_ENV === "production";
}

function sign(payload: string): string {
  return createHmac("sha256", signingSecret()).update(payload).digest("base64url");
}

function constantTimeEqual(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  if (left.length !== right.length) {
    return false;
  }
  return timingSafeEqual(left, right);
}

export function encodeSignedPayload(payload: object): string {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${body}.${sign(body)}`;
}

export function decodeSignedPayload<T>(value: string | undefined): T | null {
  if (!value) {
    return null;
  }
  const [body, signature] = value.split(".");
  if (!body || !signature) {
    return null;
  }
  if (!constantTimeEqual(signature, sign(body))) {
    return null;
  }
  try {
    return JSON.parse(Buffer.from(body, "base64url").toString("utf8")) as T;
  } catch {
    return null;
  }
}

export function encodeSessionCookie(session: AuthSession): string {
  return encodeSignedPayload(session);
}

export function decodeSessionCookie(value: string | undefined): AuthSession | null {
  const session = decodeSignedPayload<AuthSession>(value);
  if (
    !session ||
    typeof session.accessToken !== "string" ||
    typeof session.refreshToken !== "string" ||
    typeof session.expiresAt !== "number" ||
    session.expiresAt <= Date.now()
  ) {
    return null;
  }
  return session;
}

/** Signed double-submit CSRF token: random body + server signature. */
export function mintCsrfToken(): string {
  return encodeSignedPayload({ nonce: randomBytes(24).toString("base64url"), mintedAt: Date.now() });
}

/** Concurrent first requests for one signed session must mint the same token.
 * The session bearer is never exposed: only a domain-separated keyed digest
 * is included in the signed double-submit payload. Existing valid CSRF
 * cookies are reused even when an access token is refreshed.
 */
export function mintSessionCsrfToken(session: AuthSession): string {
  const nonce = createHmac("sha256", signingSecret())
    .update(`csrf-session:${session.accessToken}`).digest("base64url");
  return encodeSignedPayload({ nonce });
}

export function verifyCsrfPair(cookieValue: string | undefined, headerValue: string | null): boolean {
  if (!cookieValue || !headerValue) {
    return false;
  }
  if (!constantTimeEqual(cookieValue, headerValue)) {
    return false;
  }
  return decodeSignedPayload<{ nonce: string }>(cookieValue) !== null;
}

/** Internal-only redirect targets: same-origin paths, never protocol-relative. */
export function safeInternalReturnTo(value: string | null | undefined): string {
  if (value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\")) {
    return value;
  }
  return "/";
}
