"use client";

import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { NavItem } from "@/lib/navigation";

import { cn } from "@/lib/utils";

/**
 * Mobile navigation drawer (below 768px): focus-trapped by vaul, closes on
 * Escape, restores focus to the trigger. One registry drives desktop and
 * mobile; this renders the same items grouped as the desktop sidebar.
 */
export function MobileNavDrawer({
  items,
  groups,
  onNavigate,
  triggerLabel = "Open navigation menu",
  className,
}: {
  items: NavItem[];
  /** Group headers rendered inside the drawer (workspace grouping). */
  groups?: string[];
  /** Called when a link is chosen so the caller can close the drawer. */
  onNavigate?: () => void;
  triggerLabel?: string;
  className?: string;
}) {
  const grouped =
    groups && groups.length > 0
      ? groups.map((group) => ({ group, items: items.filter((item) => item.group === group && item.enabled) }))
      : [{ group: "", items: items.filter((item) => item.enabled) }];

  return (
    <Drawer>
      <DrawerTrigger
        aria-label={triggerLabel}
        className={cn(
          "inline-flex size-11 items-center justify-center rounded-control",
          "text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
          className,
        )}
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" className="size-5">
          <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      </DrawerTrigger>
      <DrawerContent>
        <nav aria-label="Mobile navigation" className="flex flex-col gap-4">
          {grouped.map(({ group, items: groupItems }) =>
            groupItems.length === 0 ? null : (
              <div key={group || "public"}>
                {group ? (
                  <p className="text-metadata leading-metadata text-text-secondary font-medium uppercase tracking-wide px-2">
                    {group}
                  </p>
                ) : null}
                <ul>
                  {groupItems.map((item) => (
                    <li key={item.href}>
                      <a
                        href={item.href}
                        onClick={onNavigate}
                        className="flex min-h-11 items-center rounded-control px-2 text-body leading-body text-text hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                      >
                        <span>
                          {item.label}
                          {item.availabilityNote ? (
                            <span className="text-metadata leading-metadata text-text-secondary block">
                              {item.availabilityNote}
                            </span>
                          ) : null}
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ),
          )}
        </nav>
      </DrawerContent>
    </Drawer>
  );
}
