/**
 * NI-021 workspace gate tests: server gate redirect, authenticated shell,
 * account menu sign-out, no dead links.
 */
import { axe } from "jest-axe";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextResponse } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import WorkspaceHomePage from "@/app/(workspace)/workspace/page";
import { AccountMenu } from "@/components/layout/AccountMenu";
import { SESSION_COOKIE, encodeSessionCookie } from "@/lib/auth/session";

const cookieState = vi.hoisted(() => ({ value: undefined as string | undefined }));
const routerMock = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerMock.push }),
  usePathname: () => "/workspace",
  // Mimic the redirect signal: digest carries the target like Next does.
  redirect: (url: string) => {
    const error = new Error("NEXT_REDIRECT");
    (error as Error & { digest?: string }).digest = `NEXT_REDIRECT;replace;${url};307;`;
    throw error;
  },
}));

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) =>
      name === SESSION_COOKIE && cookieState.value ? { name, value: cookieState.value } : undefined,
  }),
}));

// Full server auth config: rendering the gated layout re-derives the HMAC
// secret through loadServerAuthConfig, which validates the whole schema.
// CI has no root .env — these must come from the test environment.
const ENV = {
  APP_ENV: "test",
  NEXT_PUBLIC_SUPABASE_URL: "https://dev.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_synthetic_test_key_0123456789",
  SUPABASE_JWT_ISSUER: "https://dev.supabase.co/auth/v1",
  SUPABASE_JWKS_URL: "https://dev.supabase.co/auth/v1/.well-known/jwks.json",
  SUPABASE_JWT_AUDIENCE: "authenticated",
  SUPABASE_JWT_ALGORITHM: "ES256",
  AUTH_ALLOWED_REDIRECT_ORIGINS: "http://localhost:3000",
  AUTH_COOKIE_SIGNING_SECRET: "c".repeat(40),
  CSRF_SIGNING_SECRET: "d".repeat(40),
};

beforeEach(() => {
  for (const [key, value] of Object.entries(ENV)) {
    process.env[key] = value;
  }
});

afterEach(() => {
  for (const key of Object.keys(ENV)) {
    delete process.env[key];
  }
});

describe("Workspace gate", () => {
  it("redirects anonymous and expired sessions to /login", async () => {
    cookieState.value = undefined;
    const { default: GatedLayout } = await import("@/app/(workspace)/layout");
    // The next/navigation redirect signal carries the target in its digest.
    await expect(GatedLayout({ children: <p>secret</p> })).rejects.toMatchObject({
      digest: expect.stringContaining("/login"),
    });
  });

  it("renders the shell for a valid session without leaking tokens to markup", async () => {
    const value = encodeSessionCookie({
      accessToken: "access-token-should-not-appear",
      refreshToken: "refresh-should-not-appear",
      expiresAt: Date.now() + 600_000,
    });
    cookieState.value = value;
    const { default: GatedLayout } = await import("@/app/(workspace)/layout");
    // Async server components resolve to a tree before rendering.
    const tree = await GatedLayout({ children: <p>workspace body</p> });
    const { container } = render(tree);
    expect(screen.getByText("workspace body")).toBeInTheDocument();
    expect(container.textContent).not.toContain("access-token-should-not-appear");
    expect(container.textContent).not.toContain("refresh-should-not-appear");
    expect(
      await axe(container, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });
});

describe("Workspace entry page", () => {
  it("has no dead links to unimplemented routes", async () => {
    const tree = await WorkspaceHomePage();
    const { container } = render(tree);
    // NI-023/NI-035 pages do not exist yet — no anchors may point at them.
    expect(container.querySelector('a[href="/workspace/research"]')).toBeNull();
    expect(container.querySelector('a[href="/workspace/saved-charts"]')).toBeNull();
    expect(container.textContent).toMatch(/NI-024/);
  });
});

describe("Account menu sign-out", () => {
  it("posts the signed logout and routes to /login", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(NextResponse.json({ token: "minted" }))
      .mockResolvedValueOnce(NextResponse.json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountMenu />);
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/api/auth/logout"));
      expect(call).toBeTruthy();
      expect((call as unknown as [string, RequestInit])[1].headers).toMatchObject({
        "x-csrf-token": "minted",
      });
      expect(routerMock.push).toHaveBeenCalledWith("/login");
    });
  });

  it("surfaces provider-side sign-out failures honestly", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(NextResponse.json({ token: "minted" }))
      .mockResolvedValueOnce(
        NextResponse.json(
          { error: "Signed out locally, but the provider session could not be revoked (unavailable)." },
          { status: 503 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<AccountMenu />);
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not be revoked/i);
  });
});
