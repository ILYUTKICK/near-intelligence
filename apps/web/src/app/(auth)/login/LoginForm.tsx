"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { announceAuthChange } from "@/lib/auth/change";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Same-origin login form (NI-017). The CSRF token is fetched fresh (double
 * submit), the request goes to our own gateway route; provider errors are
 * shown generically — the UI can never distinguish an unknown email from a
 * wrong password (anti-enumeration). Pending state blocks duplicate submits.
 */
export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const csrfResponse = await fetch("/api/auth/csrf", { credentials: "same-origin" });
      if (!csrfResponse.ok) {
        throw new Error("The authentication service is unavailable. Try again shortly.");
      }
      const { token } = (await csrfResponse.json()) as { token: string };
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "x-csrf-token": token },
        body: JSON.stringify({ email, password }),
      });
      const body = (await response.json()) as { error?: string; returnTo?: string };
      if (!response.ok) {
        setError(body.error ?? "Sign-in failed. Try again.");
        return;
      }
      announceAuthChange();
      // Client caches are cleared on account changes in NI-020; the redirect
      // target is the server-validated internal path.
      window.location.assign(body.returnTo ?? "/");
    } catch {
      setError("The authentication service is unavailable. Try again shortly.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4 max-w-sm" noValidate>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="login-email">Email</Label>
        <Input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="login-password">Password</Label>
        <Input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      {error ? (
        <p role="alert" className="text-ui leading-ui text-danger font-medium">
          {error}
        </p>
      ) : null}
      <Button type="submit" pending={pending}>
        Sign in
      </Button>
    </form>
  );
}
