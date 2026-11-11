import type { ProductIconName } from "@/components/layout/ProductIcon";

/**
 * Canonical route registry (NI-008) — single data-driven source for desktop
 * and mobile navigation, mirroring docs/INFORMATION_ARCHITECTURE.md exactly.
 * Labels and routes there override the earlier product-plan proposal; no
 * Strategy/Portfolio routes exist in this product. When IA changes, update
 * that document and this registry in the same change.
 */
export interface NavItem {
  label: string;
  href: string;
  group: string;
  priority: "P0" | "P1";
  enabled: boolean;
  icon?: ProductIconName;
  /** Stable availability note shown next to data-explorer entries. */
  availabilityNote?: string;
}

/** Top-level public header navigation (public pages, NI-011/NI-013/NI-015). */
export const publicNav: NavItem[] = [
  { label: "Overview", href: "/", group: "public", priority: "P0", enabled: true },
  { label: "Research", href: "/research", group: "public", priority: "P0", enabled: true },
  { label: "Data", href: "/data", group: "public", priority: "P0", enabled: true },
  { label: "Methodology", href: "/methodology", group: "public", priority: "P0", enabled: true },
  { label: "Models", href: "/models", group: "public", priority: "P0", enabled: true },
];

/**
 * Workspace sidebar, grouped per INFORMATION_ARCHITECTURE.md. The Data
 * Explorer and Analytics entries target the IMPLEMENTED public routes
 * (`/data/*`, `/models` — NI-015/NI-054): the former `/workspace/data/*` and
 * `/workspace/models` aliases had no implemented pages, so the sidebar
 * prefetched 404s (NI-024 regression, reconciled in NI-064). There is exactly
 * one data explorer and one model catalog implementation; the workspace never
 * mounts a second one.
 */
export const workspaceNav: NavItem[] = [
  { label: "Home", href: "/workspace", group: "Workspace", priority: "P0", enabled: true, icon: "home" },
  { label: "My Research", href: "/workspace/research", group: "Workspace", priority: "P0", enabled: true, icon: "book" },
  { label: "Saved Charts", href: "/workspace/saved-charts", group: "Workspace", priority: "P0", enabled: true, icon: "chart" },
  {
    label: "Network Activity",
    href: "/data/network",
    group: "Data Explorer",
    priority: "P0",
    enabled: true,
    icon: "globe",
    availabilityNote: "availability varies by source",
  },
  { label: "Intents & Adoption", href: "/data/intents", group: "Data Explorer", priority: "P0", enabled: true, icon: "layers" },
  { label: "Revenue & Fees", href: "/data/revenue", group: "Data Explorer", priority: "P0", enabled: true, icon: "chart" },
  { label: "Token Economics", href: "/data/token-economics", group: "Data Explorer", priority: "P0", enabled: true, icon: "leaf" },
  {
    label: "Ecosystem",
    href: "/data/ecosystem",
    group: "Data Explorer",
    priority: "P0",
    enabled: true,
    icon: "grid",
    availabilityNote: "empty until source validation",
  },
  { label: "Econometric Models", href: "/models", group: "Analytics", priority: "P0", enabled: true, icon: "filter" },
  { label: "Profile", href: "/workspace/profile", group: "Account", priority: "P0", enabled: true, icon: "user" },
  { label: "Settings", href: "/workspace/settings", group: "Account", priority: "P0", enabled: true, icon: "settings" },
];

/** Auth entry points rendered as actions, not sidebar groups. */
export const authNav: NavItem[] = [
  { label: "Sign in", href: "/login", group: "auth", priority: "P0", enabled: true },
  { label: "Sign up", href: "/signup", group: "auth", priority: "P0", enabled: true },
];

export const workspaceGroups = ["Workspace", "Data Explorer", "Analytics", "Account"] as const;

export function isWithinRoute(pathname: string | null, href: string): boolean {
  return pathname === href || Boolean(pathname?.startsWith(`${href}/`));
}

/** Group-ordered workspace items (registry order is already canonical). */
export function workspaceNavByGroup(): Array<{ group: string; items: NavItem[] }> {
  return workspaceGroups.map((group) => ({
    group,
    items: workspaceNav.filter((item) => item.group === group && item.enabled),
  }));
}

/** Stable editorial anchors from INFORMATION_ARCHITECTURE.md. */
export const editorialAnchors = {
  h1: "/research#h1",
  h4: "/research#h4",
  sources: "/methodology#sources",
  reproduce: "/methodology#reproduce",
} as const;
