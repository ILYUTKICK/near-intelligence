import type { Metadata } from "next";

import { ProfileForm } from "@/app/(workspace)/workspace/profile/ProfileForm";
import { SESSION_COOKIE, decodeSessionCookie } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Profile — NEAR Intelligence" };

/**
 * Profile (NI-025): display name and timezone are the only editable fields.
 * The verified subject is never editable and is not rendered here — identity
 * is shown on the settings page from the session check instead.
 */
export default async function ProfilePage() {
  const cookieStore = await cookies();
  const session = decodeSessionCookie(cookieStore.get(SESSION_COOKIE)?.value);

  return (
    <div className="max-w-(--width-prose)">
      <h1>Profile</h1>
      <p className="text-body leading-body text-text-secondary mt-4">
        Your display name appears only in your own workspace. The timezone preference changes
        how dates are displayed to you — it never alters stored data (all timestamps remain UTC).
      </p>
      {session ? (
        <ProfileForm />
      ) : (
        <p role="alert" className="text-ui leading-ui text-danger mt-6">
          Session could not be verified. Refresh the page to re-check, or sign in again.
        </p>
      )}
    </div>
  );
}
