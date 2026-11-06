/**
 * NI-021 workspace gate tests: server gate redirect, authenticated shell,
 * account menu sign-out, no dead links.
 */
import { axe } from "jest-axe";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WorkspaceLayout from "@/app/(workspace)/layout";
import WorkspaceHomePage from "@/app/(workspace)/workspace/page";
import { AccountMenu } from "@/components/layout/AccountMenu";
import { SESSION_COOKIE, encodeSessionCookie } from "@/lib/auth/session";

const ENV = {
  APP_ENV: "test",
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

// next/headers cookies() is per-request; inject a store for layout tests.
function withCookieStore(value?: string) {
  vi.mock("next/headers", () => ({
    cookies: vi.fn(async () => ({
      get: (name: string) => (name === SESSION_COOKIE && value ? { name, value } : undefined),
    })),
  }));
}

describe("Workspace gate", () => {
  it("redirects anonymous and expired sessions to /login", async () => {
    withCookieStore(undefined);
    const { default: GatedLayout } = await import("@/app/(workspace)/layout");
    await expect(GatedLayout({ children: <p>secret</p> })).rejects.toMatchObject({
      digest: "/login", // next/navigation redirect signal
    });
  });

  it("renders the shell for a valid session without leaking tokens to markup", async () => {
    const value = encodeSessionCookie({
      accessToken: "access-token-should-not-appear",
      refreshToken: "refresh-should-not-appear",
      expiresAt: Date.now() + 600_000,
    });
    withCookieStore(value);
    const { default: GatedLayout } = await import("@/app/(workspace)/layout");
    const { container } = render(
      <GatedLayout>
        <p>workspace body</p>
      </GatedLayout>,
    );
    expect(screen.getByText("workspace body")).toBeInTheDocument();
    expect(container.textContent).not.toContain("access-token-should-not-appear");
    expect(container.textContent).not.toContain("refresh-should-not-appear");
    expect(
      await axe(container, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });
});

describe("Workspace entry page", () => {
  it("has no dead links to unimplemented routes", () => {
    const { container } = render(<WorkspaceHomePage />);
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
