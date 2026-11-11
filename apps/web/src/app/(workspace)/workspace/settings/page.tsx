import type { Metadata } from "next";
import Link from "next/link";

import { AccountMenu } from "@/components/layout/AccountMenu";
import { PageIntro } from "@/components/layout/PageIntro";
import { ProductIcon } from "@/components/layout/ProductIcon";

export const metadata: Metadata = { title: "Settings — NEAR Intelligence" };

export default function SettingsPage() {
  return (
    <div>
      <PageIntro compact eyebrow="Account / Settings" title="A little less friction."
        description="Review your workspace preferences, draft recovery and account session." />
      <div className="mt-7 grid items-start gap-5 lg:grid-cols-[minmax(0,1.8fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <section className="paper-panel p-6" aria-labelledby="preferences-heading">
            <h2 id="preferences-heading" className="text-heading">Research preferences</h2>
            <dl className="mt-3 divide-y divide-border text-ui">
              <div className="flex flex-wrap items-baseline justify-between gap-3 py-3">
                <dt className="font-medium">Display name and timezone</dt>
                <dd><Link href="/workspace/profile" className="underline underline-offset-2">Edit profile</Link></dd>
              </div>
              <div className="flex flex-wrap items-baseline justify-between gap-3 py-3">
                <dt className="font-medium">Reduced motion</dt>
                <dd className="text-text-secondary">Follows system preference</dd>
              </div>
              <div className="flex flex-wrap items-baseline justify-between gap-3 pt-3">
                <dt className="font-medium">Analytical periods</dt>
                <dd className="rounded-full bg-surface-muted px-2.5 py-1 text-metadata text-text-secondary">UTC</dd>
              </div>
            </dl>
          </section>
          <section className="paper-panel p-6" aria-labelledby="drafts-heading">
            <h2 id="drafts-heading" className="text-heading">Local recovery</h2>
            <p className="mt-2 text-ui text-text-secondary">
              If a tab reloads with unsaved changes, reopen the document in that tab. The editor offers to restore or discard its recovery copy.
            </p>
            <Link href="/workspace/research" className="mt-3 inline-flex min-h-11 items-center gap-2 text-ui font-medium hover:underline">
              Open My Research <ProductIcon name="arrow" />
            </Link>
          </section>
          <section className="paper-panel p-6" aria-labelledby="account-heading">
            <h2 id="account-heading" className="text-heading">Account</h2>
            <p className="mt-2 text-ui text-text-secondary">Sign out to end this session. For account deletion, contact the project operator.</p>
            <div className="mt-3 flex"><AccountMenu /></div>
          </section>
        </div>
        <aside className="rounded-surface bg-sage p-6">
          <p className="eyebrow">Data policy</p>
          <h2 className="mt-2 text-heading">Freshness belongs to the source.</h2>
          <p className="mt-2 text-ui text-text-secondary">
            A chart records the period and dataset it uses. Saved revisions keep that evidence with the document.
          </p>
          <Link href="/methodology#sources" className="mt-3 inline-flex min-h-11 items-center gap-2 text-ui font-medium hover:underline">
            Read the source policy <ProductIcon name="arrow" />
          </Link>
        </aside>
      </div>
    </div>
  );
}
