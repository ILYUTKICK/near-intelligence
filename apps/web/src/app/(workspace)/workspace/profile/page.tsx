import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";

import { ProfileForm } from "@/app/(workspace)/workspace/profile/ProfileForm";
import { PageIntro } from "@/components/layout/PageIntro";
import { ProductIcon } from "@/components/layout/ProductIcon";
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
    <div>
      <PageIntro compact eyebrow="Account / Profile" title="Make yourself at home."
        description="Manage how your profile appears in your private workspace." />
      <div className="mt-7 grid items-start gap-5 lg:grid-cols-[minmax(0,1.8fr)_minmax(0,1fr)]">
        <section aria-label="Edit profile" className="paper-panel min-w-0 p-6 sm:p-8">
          {session ? (
            <ProfileForm />
          ) : (
            <p role="alert" className="text-ui text-danger">
              Session could not be verified. Refresh the page to re-check, or sign in again.
            </p>
          )}
        </section>
        <aside className="space-y-5">
          <div className="rounded-surface bg-sage p-6">
            <ProductIcon name="shield" className="mb-4 size-6 text-accent" />
            <h2 className="text-heading">Private by default.</h2>
            <p className="mt-2 text-ui text-text-secondary">Your documents, saved selections and profile belong to your account.</p>
          </div>
          <div className="paper-panel p-6">
            <p className="eyebrow">Preferences</p>
            <h2 className="mt-2 text-heading">A workspace that stays focused.</h2>
            <Link href="/workspace/settings" className="mt-3 inline-flex min-h-11 items-center gap-2 text-ui font-medium hover:underline">
              Open Settings
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
