"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Brand } from "./Brand";
import { MobileNavDrawer } from "./MobileNavDrawer";
import { ProductIcon } from "./ProductIcon";
import { isWithinRoute, workspaceNavByGroup } from "@/lib/navigation";

import { cn } from "@/lib/utils";

function WorkspaceNavList({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Workspace" className="flex flex-1 flex-col gap-5">
      {workspaceNavByGroup().map(({ group, items }) => (
        <div key={group} className={group === "Account" ? "mt-auto" : undefined}>
          {group === "Data Explorer" || group === "Analytics" ? (
            <p className="px-3 pb-1 text-metadata font-medium tracking-widest text-text-secondary uppercase">{group}</p>
          ) : null}
          <ul className="space-y-0.5">
            {items.map((item) => {
              const active = item.href === "/workspace" ? pathname === item.href : isWithinRoute(pathname, item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex min-h-11 items-center gap-3 rounded-[14px] px-3 py-1.5",
                      "text-ui leading-ui",
                      active
                        ? "bg-sage font-semibold text-accent"
                        : "text-text-secondary hover:bg-surface-muted hover:text-text",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                    )}
                  >
                    {item.icon ? <ProductIcon name={item.icon} className="size-[18px] shrink-0" /> : null}
                    <span>
                      {item.label}
                      {item.availabilityNote ? (
                        <span className="sr-only">
                          {item.availabilityNote}
                        </span>
                      ) : null}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/**
 * Workspace sidebar shell (240px per DESIGN_SYSTEM.md). Route protection and
 * the authenticated session come with NI-021 — this is the navigational
 * shell only. Below 768px the same registry renders in the modal drawer
 * with focus restoration.
 */
export function WorkspaceSidebar() {
  const pathname = usePathname();
  return (
    <>
      <aside aria-label="Workspace navigation panel" className="sticky top-0 hidden max-h-dvh w-(--width-sidebar) shrink-0 flex-col gap-8 self-start overflow-y-auto border-r border-border bg-surface/55 px-4 py-7 md:flex md:min-h-dvh">
        <div className="px-2"><Brand /></div>
        <WorkspaceNavList pathname={pathname} />
      </aside>
      <div className="md:hidden p-2">
        <MobileNavDrawer
          items={workspaceNavByGroup().flatMap(({ items }) => items)}
          groups={["Workspace", "Data Explorer", "Analytics", "Account"]}
          triggerLabel="Open workspace menu"
        />
      </div>
    </>
  );
}
