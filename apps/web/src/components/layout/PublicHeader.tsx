"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Brand } from "./Brand";
import { MobileNavDrawer } from "./MobileNavDrawer";
import { ProductIcon } from "./ProductIcon";
import { Button } from "@/components/ui/button";
import { authNav, isPublicNavActive, publicNav } from "@/lib/navigation";

import { cn } from "@/lib/utils";

function NavLink({ item, active }: { item: (typeof publicNav)[number]; active: boolean }) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "inline-flex h-11 items-center border-b-2 border-transparent text-ui leading-ui",
        active ? "border-accent font-medium text-accent" : "text-text-secondary hover:text-accent",
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
    <header className="border-b border-border bg-canvas">
      <div className="mx-auto flex w-full max-w-(--width-content-max) items-center justify-between gap-4 px-(--page-gutter) py-4 md:py-6">
        <Brand />
        <nav aria-label="Primary" className="hidden items-center gap-4 md:flex lg:gap-7">
          {publicNav.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={isPublicNavActive(pathname, item.href)}
            />
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-1 lg:gap-2">
          {signIn ? (
            <Link
              href={signIn.href}
              className="inline-flex h-11 items-center rounded-control px-2 text-ui font-medium text-accent hover:underline"
            >
              {signIn.label}
            </Link>
          ) : null}
          <Button asChild className="hidden lg:inline-flex">
            <Link href="/workspace">Open workspace <ProductIcon name="arrow" /></Link>
          </Button>
          <div className="md:hidden">
            <MobileNavDrawer items={publicNav} triggerLabel="Open site menu" />
          </div>
        </div>
      </div>
    </header>
  );
}
