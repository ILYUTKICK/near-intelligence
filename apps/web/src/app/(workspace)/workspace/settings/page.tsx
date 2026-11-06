import type { Metadata } from "next";

import { AccountMenu } from "@/components/layout/AccountMenu";

export const metadata: Metadata = { title: "Settings — NEAR Intelligence" };

/**
 * Minimal settings (NI-025): session/logout control lives here; local draft
 * clearing arrives with the editor (NI-038/040) and is stated honestly rather
 * than rendered as a dead control. Billing/team/account-deletion controls are
 * intentionally absent — operator-assisted deletion is documented in the
 * security specification, and this page must not fake success for it.
 */
export default function SettingsPage() {
  return (
    <div className="max-w-(--width-prose)">
      <h1>Settings</h1>
      <section aria-labelledby="session-heading" className="mt-8">
        <h2 id="session-heading" className="font-serif text-title leading-title">
          Session
        </h2>
        <p className="text-body leading-body text-text-secondary mt-2">
          Sign out ends your session server-side: the provider refresh token is revoked and
          both cookies are cleared from this browser.
        </p>
        <div className="mt-4">
          <AccountMenu />
        </div>
      </section>
      <section aria-labelledby="drafts-heading" className="mt-10">
        <h2 id="drafts-heading" className="font-serif text-title leading-title">
          Local drafts
        </h2>
        <p className="text-body leading-body text-text-secondary mt-2">
          Document drafts are kept in browser memory only while the editor is open. The explicit
          clear-drafts control is added together with the editor itself (NI-038/NI-040); nothing
          is stored on our servers before you save.
        </p>
      </section>
      <section aria-labelledby="account-heading" className="mt-10">
        <h2 id="account-heading" className="font-serif text-title leading-title">
          Account
        </h2>
        <p className="text-body leading-body text-text-secondary mt-2">
          Account deletion is operator-assisted: request it through the project contact and the
          operator removes your data and confirms back to you. There is no self-service deletion
          button, and this page will never pretend one succeeded.
        </p>
      </section>
    </div>
  );
}
