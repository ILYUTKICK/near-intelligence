"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { announceAuthChange } from "@/lib/auth/change";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Demo sign-in (NI-017): one real provider session without a password. The
 * email field is a display label stored as user metadata — it is
 * never verified and never used for authentication. Clearly labeled as demo
 * so it cannot be mistaken for a production account path.
 */
export function DemoSignIn({ returnTo = "/workspace" }: { returnTo?: string }) {
  const router = useRouter();
  const [displayEmail, setDisplayEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleDemo(event: React.FormEvent<HTMLFormElement>) {
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
      router.push(body.returnTo ?? "/workspace");
    } catch {
      setError("The authentication service is unavailable. Try again shortly.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleDemo} className="mt-6 flex flex-col gap-4">
      <p className="text-metadata leading-metadata text-text-secondary mt-1">
        Use any email to explore your own demo workspace. No password or verification
        email is needed. The address is only a label, and each sign-in starts a separate demo.
      </p>
      <div className="mt-3 flex flex-col gap-1.5">
        <Label htmlFor="demo-email">Email</Label>
        <Input
          id="demo-email"
          name="displayEmail"
          type="email"
          autoComplete="email"
          required
          maxLength={254}
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
      <Button type="submit" pending={pending}>
        Enter demo workspace
      </Button>
    </form>
  );
}
