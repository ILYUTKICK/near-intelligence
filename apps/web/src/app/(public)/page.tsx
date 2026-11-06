import Link from "next/link";

import { MechanismFlow } from "@/features/public-research/MechanismFlow";
import { landing } from "@/features/public-research/content";

export default function HomePage() {
  return (
    <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
      <h1>{landing.title}</h1>
      <p className="text-body leading-body text-text-secondary max-w-(--width-prose) mt-4">
        {landing.standfirst}
      </p>
      <p className="text-body leading-body max-w-(--width-prose) mt-4">{landing.whatYouCanDo}</p>
      <ul className="mt-6 flex flex-wrap gap-2">
        {landing.links.map((link) => (
          <li key={link.href}>
            <Link
              href={link.href}
              className="inline-flex h-11 items-center rounded-control border border-control-border bg-surface px-4 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
      <MechanismFlow />
    </div>
  );
}
