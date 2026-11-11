"use client";

import type { components } from "@near-intelligence/shared-types";
import { useState } from "react";
import { z } from "zod";

import { ErrorPanel, LoadingPanel } from "@/components/data-state/DataState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOwnedData } from "@/features/charts/saved/use-owned-data";

type ProfileUpdate = components["schemas"]["ProfileUpdateRequest"];
type Profile = Pick<components["schemas"]["ProfileResponse"], keyof ProfileUpdate>;

const profileSchema: z.ZodType<Profile> = z.object({
  display_name: z.string(),
  display_timezone: z.string(),
});

async function loadProfile(signal: AbortSignal): Promise<Profile> {
  const response = await fetch("/api/me", { credentials: "same-origin", cache: "no-store", signal });
  if (!response.ok) throw new Error("Your profile could not be loaded.");
  return profileSchema.parse(await response.json());
}

export function ProfileForm() {
  const { data, signal, loading, error, reload } = useOwnedData(loadProfile, "profile");
  if (loading) return <LoadingPanel label="Loading your profile" />;
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  return data && signal ? <ProfileFields profile={data} signal={signal} /> : null;
}

function ProfileFields({ profile, signal }: { profile: Profile; signal: AbortSignal }) {
  const [displayName, setDisplayName] = useState(profile.display_name);
  const [displayTimezone, setDisplayTimezone] = useState(profile.display_timezone);
  const [savedName, setSavedName] = useState(profile.display_name);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || signal.aborted) return;
    setPending(true);
    setSaveError(null);
    setSaved(false);
    try {
      const csrf = await fetch("/api/auth/csrf", { credentials: "same-origin", cache: "no-store", signal });
      if (!csrf.ok) throw new Error("Your session could not be checked. Try again.");
      const { token } = z.object({ token: z.string() }).parse(await csrf.json());
      const update: ProfileUpdate = { display_name: displayName, display_timezone: displayTimezone };
      const response = await fetch("/api/me", {
        method: "PATCH",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "content-type": "application/json", "x-csrf-token": token },
        body: JSON.stringify(update),
        signal,
      });
      if (response.status === 422) {
        throw new Error("Enter a display name and a valid IANA timezone.");
      }
      if (!response.ok) throw new Error("Your profile could not be saved. Try again.");
      const acknowledged = profileSchema.parse(await response.json());
      if (!signal.aborted) {
        setDisplayName(acknowledged.display_name);
        setDisplayTimezone(acknowledged.display_timezone);
        setSavedName(acknowledged.display_name);
        setSaved(true);
      }
    } catch (error) {
      if (!signal.aborted) {
        setSaveError(error instanceof Error ? error.message : "Your profile could not be saved. Try again.");
      }
    } finally {
      if (!signal.aborted) setPending(false);
    }
  }

  return (
    <form onSubmit={handleSave} className="flex flex-col gap-4">
      <div className="flex items-center gap-3 border-b border-border pb-4">
        <span aria-hidden="true" className="grid size-12 shrink-0 place-items-center rounded-full bg-sage font-serif text-heading text-accent">
          {Array.from(savedName)[0]?.toUpperCase() ?? "?"}
        </span>
        <div className="min-w-0">
          <p className="font-serif text-heading [overflow-wrap:anywhere]">{savedName}</p>
          <p className="text-metadata text-text-secondary">Private profile</p>
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="profile-name">Display name</Label>
        <Input id="profile-name" value={displayName} maxLength={80} required
          onChange={(event) => { setDisplayName(event.target.value); setSaved(false); }} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="profile-timezone">Timezone</Label>
        <Input id="profile-timezone" aria-describedby="timezone-hint" value={displayTimezone} maxLength={64} required
          onChange={(event) => { setDisplayTimezone(event.target.value); setSaved(false); }} />
        <p id="timezone-hint" className="text-metadata text-text-secondary">Use an IANA timezone such as Europe/Berlin or UTC. Analytical periods use UTC.</p>
      </div>
      {saveError ? <p role="alert" className="text-ui font-medium text-danger">{saveError}</p> : null}
      {saved ? <p role="status" className="text-ui font-medium text-accent">Profile saved.</p> : null}
      <Button type="submit" pending={pending} className="self-start">Save profile</Button>
    </form>
  );
}
