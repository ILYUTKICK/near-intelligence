"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { MobileNavDrawer } from "./MobileNavDrawer";
import { authNav, publicNav } from "@/lib/navigation";

import { cn } from "@/lib/utils";

function NavLink({ item, active }: { item: (typeof publicNav)[number]; active: boolean }) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "inline-flex h-11 items-center rounded-control px-3",
        "font-ui text-ui leading-ui",
        active ? "bg-surface-muted text-text font-medium" : "text-text-secondary hover:bg-surface-muted hover:text-text",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
      )}
    >
      {item.label}
    </Link>
  );
}

/**
 * Public header shell: brand, registry-driven navigation, sign-in action.
 * Below 768px the registry renders inside the mobile drawer instead; the
 * menu trigger is a 44px target. Active route is exposed via aria-current.
 */
export function PublicHeader() {
  const pathname = usePathname();
  const signIn = authNav[0];
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex w-full max-w-(--width-content-max) items-center gap-2 px-4 py-2">
        <Link
          href="/"
          className="font-serif text-heading leading-heading text-text mr-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          NEAR Intelligence
        </Link>
        <nav aria-label="Primary" className="hidden flex-1 items-center gap-1 md:flex">
          {publicNav.map((item) => (
            <NavLink key={item.href} item={item} active={pathname === item.href} />
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1">
          {signIn ? (
            <Link
              href={signIn.href}
              className="inline-flex h-11 items-center rounded-control px-3 font-ui text-ui leading-ui text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              {signIn.label}
            </Link>
          ) : null}
          <div className="md:hidden">
            <MobileNavDrawer items={publicNav} triggerLabel="Open site menu" />
          </div>
        </div>
      </div>
    </header>
  );
}
