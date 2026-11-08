"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { announceAuthChange } from "@/lib/auth/change";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Demo sign-in (NI-017): one real provider session without a password. The
 * email field is an optional display label stored as user metadata — it is
 * never verified and never used for authentication. Clearly labeled as demo
 * so it cannot be mistaken for a production account path.
 */
export function DemoSignIn({ returnTo = "/" }: { returnTo?: string }) {
  const router = useRouter();
  const [displayEmail, setDisplayEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleDemo() {
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
      const response = await fetch("/api/auth/demo", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "x-csrf-token": token },
        body: JSON.stringify({ displayEmail, returnTo }),
      });
      const body = (await response.json()) as { error?: string; returnTo?: string };
      if (!response.ok) {
        setError(body.error ?? "Demo sign-in failed.");
        return;
      }
      announceAuthChange();
      router.push(body.returnTo ?? "/");
    } catch {
      setError("The authentication service is unavailable. Try again shortly.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mt-8 max-w-sm rounded-surface border border-border bg-surface-muted p-4">
      <p className="font-ui text-ui leading-ui font-medium text-text">Demo sign-in</p>
      <p className="text-metadata leading-metadata text-text-secondary mt-1">
        No password and no verification email: a temporary demo account is created for this
        browser. The address below is only a label.
      </p>
      <div className="mt-3 flex flex-col gap-1.5">
        <Label htmlFor="demo-email">Email (label only)</Label>
        <Input
          id="demo-email"
          name="displayEmail"
          type="email"
          placeholder="you@example.com"
          value={displayEmail}
          onChange={(event) => setDisplayEmail(event.target.value)}
        />
      </div>
      {error ? (
        <p role="alert" className="text-ui leading-ui text-danger font-medium mt-2">
          {error}
        </p>
      ) : null}
      <Button variant="secondary" className="mt-3" onClick={handleDemo} pending={pending}>
        Enter demo
      </Button>
    </div>
  );
}
