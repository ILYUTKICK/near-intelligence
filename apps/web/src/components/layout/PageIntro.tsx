import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function PageIntro({
  eyebrow,
  title,
  description,
  action,
  compact,
  className,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-x-6 gap-y-4", className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="eyebrow mb-2">{eyebrow}</p> : null}
        <h1 className={cn(compact ? "text-title lg:text-[2.85rem] lg:leading-none" : "text-page", "text-pretty")}>
          {title}
        </h1>
        {description ? <p className="mt-3 max-w-(--width-prose) text-text-secondary">{description}</p> : null}
      </div>
      {action}
    </header>
  );
}
