"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/data-state/Skeleton";

/**
 * Profile form (NI-025): GET /api/me fills the fields, PATCH saves. Only the
 * verified subject is editable server-side; the subject is never part of the
 * payload. Errors stay on the form with the typed values retained.
 */
interface MeProfile {
  subject: string;
  display_name: string;
  display_timezone: string;
}

export function ProfileForm() {
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [displayTimezone, setDisplayTimezone] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch("/api/me", { credentials: "same-origin" });
        if (!response.ok) {
          throw new Error("Profile could not be loaded.");
        }
        const body = (await response.json()) as MeProfile;
        if (!cancelled) {
          setProfile(body);
          setDisplayName(body.display_name);
          setDisplayTimezone(body.display_timezone);
        }
      } catch {
        if (!cancelled) {
          setLoadError("Profile could not be loaded.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) {
      return;
    }
    setPending(true);
    setSaveError(null);
    setSaved(false);
    try {
      const response = await fetch("/api/me", {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ display_name: displayName, display_timezone: displayTimezone }),
      });
      const body = (await response.json()) as MeProfile & { detail?: string };
      if (!response.ok) {
        setSaveError(body.detail ?? "Profile update failed. Values are kept.");
        return;
      }
      setProfile(body);
      setSaved(true);
    } catch {
      setSaveError("Profile update failed. Values are kept.");
    } finally {
      setPending(false);
    }
  }

  if (loadError) {
    return (
      <p role="alert" className="text-ui leading-ui text-danger font-medium mt-6">
        {loadError}
      </p>
    );
  }
  if (!profile) {
    return (
      <div className="mt-6 flex flex-col gap-2 max-w-sm">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-11 w-full" />
      </div>
    );
  }

  return (
    <form onSubmit={handleSave} className="mt-6 flex flex-col gap-4 max-w-sm" noValidate>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="profile-name">Display name</Label>
        <Input
          id="profile-name"
          value={displayName}
          maxLength={80}
          required
          onChange={(event) => setDisplayName(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="profile-timezone">Timezone (IANA, display only)</Label>
        <Input
          id="profile-timezone"
          value={displayTimezone}
          required
          onChange={(event) => setDisplayTimezone(event.target.value)}
        />
        <p className="text-metadata leading-metadata text-text-secondary">
          e.g. Europe/Berlin or UTC. Stored dates stay UTC; this preference changes your
          display only.
        </p>
      </div>
      {saveError ? (
        <p role="alert" className="text-ui leading-ui text-danger font-medium">
          {saveError}
        </p>
      ) : null}
      {saved ? (
        <p role="status" className="text-ui leading-ui text-accent font-medium">
          Profile saved.
        </p>
      ) : null}
      <Button type="submit" pending={pending} className="self-start">
        Save profile
      </Button>
    </form>
  );
}
