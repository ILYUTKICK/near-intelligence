"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * Account menu (NI-021): sign-out through the same-origin gateway route,
 * which revokes the provider session server-side and clears cookies. After
 * logout the router moves to /login; any private-state clearing that becomes
 * necessary as workspace state lands is wired there (NI-020 card notes).
 */
export function AccountMenu() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSignOut() {
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const csrfResponse = await fetch("/api/auth/csrf", { credentials: "same-origin" });
      if (!csrfResponse.ok) {
        throw new Error((await csrfResponse.json().catch(() => ({}))).error ?? "Sign out failed.");
      }
      const { token } = (await csrfResponse.json()) as { token: string };
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json", "x-csrf-token": token },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        setError((await response.json().catch(() => ({}))).error ?? "Sign out failed.");
        return;
      }
      router.push("/login");
    } catch {
      setError("Sign out failed. Try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="quiet" onClick={handleSignOut} pending={pending} className="px-3">
        Sign out
      </Button>
      {error ? (
        <p role="alert" className="text-metadata leading-metadata text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
