import { loadPublicAuthConfig } from "./config";
import type { AuthSession } from "./session";

/**
 * Minimal Supabase Auth REST client (NI-017).
 *
 * The provider SDK is deliberately not used: the gateway needs exactly three
 * calls, full control over cookies, and generic error mapping. Endpoints and
 * payload shapes follow the documented Supabase Auth API. The publishable
 * key travels as the apikey header — it is public configuration, not
 * authorization. No credentials, tokens or password values are logged.
 */
export class ProviderAuthError extends Error {
  /** Generic, non-enumerating message for the client; details stay server-side. */
  constructor(
    public readonly kind: "invalid_credentials" | "rate_limited" | "expired_token" | "unavailable",
  ) {
    const messages = {
      invalid_credentials: "Invalid email or password.",
      rate_limited: "Too many attempts. Try again later.",
      expired_token: "This link has expired. Request a new one.",
      unavailable: "The authentication service is unavailable. Try again shortly.",
    } as const;
    super(messages[kind]);
    this.name = "ProviderAuthError";
  }
}

interface ProviderTokenResponse {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  msg?: string;
}

function providerFetch(path: string, init: RequestInit): Promise<Response> {
  const { NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY } = loadPublicAuthConfig();
  return fetch(new URL(path, `${NEXT_PUBLIC_SUPABASE_URL}/auth/v1/`), {
    ...init,
    headers: {
      apikey: NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
      "content-type": "application/json",
      ...init.headers,
    },
    // The gateway must not forward provider cookies anywhere.
    credentials: "omit",
  });
}

function toSession(body: ProviderTokenResponse): AuthSession {
  if (
    typeof body.access_token !== "string" ||
    typeof body.refresh_token !== "string" ||
    typeof body.expires_in !== "number"
  ) {
    throw new ProviderAuthError("unavailable");
  }
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
}

function mapProviderFailure(status: number): ProviderAuthError {
  if (status === 400 || status === 401 || status === 403) {
    return new ProviderAuthError("invalid_credentials");
  }
  if (status === 429) {
    return new ProviderAuthError("rate_limited");
  }
  return new ProviderAuthError("unavailable");
}

/** Email/password sign-in. 400-class provider responses map to one generic error. */
export async function signInWithPassword(email: string, password: string): Promise<AuthSession> {
  let response: Response;
  try {
    response = await providerFetch("token?grant_type=password", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new ProviderAuthError("unavailable");
  }
  if (!response.ok) {
    throw mapProviderFailure(response.status);
  }
  return toSession((await response.json()) as ProviderTokenResponse);
}

/**
 * Exchange an email-link token (signup confirmation or recovery) for a
 * session. Expired/used links map to the generic expired error.
 */
export async function exchangeOtp(
  tokenHash: string,
  type: "signup" | "recovery",
): Promise<AuthSession> {
  let response: Response;
  try {
    response = await providerFetch("verify", {
      method: "POST",
      body: JSON.stringify({ token_hash: tokenHash, type }),
    });
  } catch {
    throw new ProviderAuthError("unavailable");
  }
  if (!response.ok) {
    if (response.status >= 400 && response.status < 500) {
      throw new ProviderAuthError("expired_token");
    }
    throw mapProviderFailure(response.status);
  }
  return toSession((await response.json()) as ProviderTokenResponse);
}

/**
 * Revoke the provider session server-side. GoTrue's logout identifies the
 * session by the Bearer access token (scope=global revokes every session of
 * the user); failures are thrown so the gateway can report honest logout
 * state instead of silently keeping a live provider session.
 */
export async function revokeSession(session: AuthSession): Promise<void> {
  let response: Response;
  try {
    response = await providerFetch("logout?scope=global", {
      method: "POST",
      headers: { authorization: `Bearer ${session.accessToken}` },
      body: JSON.stringify({ refresh_token: session.refreshToken }),
    });
  } catch {
    throw new ProviderAuthError("unavailable");
  }
  if (!response.ok && response.status !== 404) {
    throw mapProviderFailure(response.status);
  }
}
