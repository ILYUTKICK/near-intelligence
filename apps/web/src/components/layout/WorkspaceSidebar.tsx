"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { MobileNavDrawer } from "./MobileNavDrawer";
import { workspaceNavByGroup } from "@/lib/navigation";

import { cn } from "@/lib/utils";

function WorkspaceNavList({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="Workspace" className="flex flex-col gap-5">
      {workspaceNavByGroup().map(({ group, items }) => (
        <div key={group}>
          <p className="text-metadata leading-metadata text-text-secondary font-medium uppercase tracking-wide px-2">
            {group}
          </p>
          <ul>
            {items.map((item) => {
              const active = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex min-h-11 items-center rounded-control px-2",
                      "text-ui leading-ui",
                      active
                        ? "bg-surface-muted text-text font-medium"
                        : "text-text-secondary hover:bg-surface-muted hover:text-text",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                    )}
                  >
                    <span>
                      {item.label}
                      {item.availabilityNote ? (
                        <span className="text-metadata leading-metadata text-text-secondary block">
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
      <aside className="hidden w-(--width-sidebar) shrink-0 border-r border-border bg-surface p-4 md:block">
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
