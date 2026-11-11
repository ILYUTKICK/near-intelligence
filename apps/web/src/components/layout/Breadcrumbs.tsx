import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * Breadcrumbs per INFORMATION_ARCHITECTURE.md ("Workspace → My Research →
 * document title; Data → category → chart"). Last crumb is the current page
 * (aria-current), ancestors are links.
 */
export function Breadcrumbs({
  items,
  className,
  label = "Breadcrumb",
}: {
  items: Array<{ label: string; href?: string }>;
  className?: string;
  label?: string;
}) {
  return (
    <nav aria-label={label} className={cn("text-ui leading-ui", className)}>
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-1">
              {index > 0 ? (
                <span aria-hidden="true" className="text-text-secondary">
                  /
                </span>
              ) : null}
              {isLast || !item.href ? (
                <span aria-current={isLast ? "page" : undefined} className="text-text font-medium">
                  {item.label}
                </span>
              ) : (
                <Link
                  href={item.href}
                  className="text-text-secondary hover:text-text underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
