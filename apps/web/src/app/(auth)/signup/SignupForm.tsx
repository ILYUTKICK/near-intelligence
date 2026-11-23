"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Signup form (NI-017): same-origin, fresh CSRF per attempt, pending state.
 * Two honest outcomes: a confirmation email is sent, or a session exists
 * immediately (auto-confirm projects). Provider rejections surface verbatim
 * classes (already registered / validation), never token details.
 */
export function SignupForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
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
      const response = await fetch("/api/auth/signup", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "x-csrf-token": token },
        body: JSON.stringify({ email, password }),
      });
      const body = (await response.json()) as { error?: string; status?: string };
      if (!response.ok) {
        setError(body.error ?? "Signup failed. Try again.");
        return;
      }
      if (body.status === "session") {
        router.push("/");
        return;
      }
      setSentTo(email);
    } catch {
      setError("The authentication service is unavailable. Try again shortly.");
    } finally {
      setPending(false);
    }
  }

  if (sentTo) {
    return (
      <div role="status" className="mt-6 max-w-sm rounded-surface border-2 border-panel-border bg-surface-muted p-4">
        <p className="text-body leading-body text-text font-medium">
          Confirmation email sent to {sentTo}
        </p>
        <p className="text-body leading-body text-text-secondary mt-2">
          Follow the link in that email from this browser to activate your session. The link
          works only for this origin and expires with the provider&apos;s policy.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="signup-email">Email</Label>
        <Input
          id="signup-email"
          name="email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="signup-password">Password</Label>
        <Input
          id="signup-password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="text-metadata leading-metadata text-text-secondary">At least 8 characters.</p>
      </div>
      {error ? (
        <p role="alert" className="text-ui leading-ui text-danger font-medium">
          {error}
        </p>
      ) : null}
      <Button type="submit" pending={pending}>
        Create account
      </Button>
    </form>
  );
}
