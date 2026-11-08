import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "jest-axe";
import { ChartAuthActions } from "@/features/charts/library/ChartAuthActions";
import { AddChartToResearch } from "@/features/charts/add-to-research/AddChartToResearch";
import { LoginForm } from "@/app/(auth)/login/LoginForm";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const id = "44444444-4444-4444-8444-444444444444";
const dataset = "55555555-5555-4555-8555-555555555555";
const summary = { id, title: "Synthetic research", revision: 3, schema_version: 1, current_version_id: id,
  created_at: "2026-11-08T10:00:00Z", updated_at: "2026-11-08T10:00:00Z", progress: { headings: 0, charts: 0, insights: 0 } };
const input = { chart_definition_version_id: id, dataset_version_id: dataset,
  selection: { start: "2026-01-01", end: "2026-01-08", frequency: "day" as const, filters: { source: "SRC-LLAMA" } }, mode: "live" as const };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

describe("NI-041 destination confirmation", () => {
  it("creates an owned destination and inserts the inspected context once with retry-safe keys", async () => {
    const mutations: Array<{ url: string; options: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return response({ subject: "synthetic-alice" });
      if (url === "/api/auth/csrf") return response({ token: "synthetic-csrf" });
      if (options.method === "POST") {
        mutations.push({ url, options });
        if (url === "/api/documents") return response({ ...summary, content: {}, resolved_contexts: {} }, 201);
        return response({ document: { ...summary, revision: 4 }, value: { block_id: id } }, 201);
      }
      if ((url === "/api/documents" || url.startsWith("/api/documents?"))) return response({ items: [], next_cursor: null });
      return response({ ...summary, content: {}, resolved_contexts: {} });
    }));
    const user = userEvent.setup(); render(<AddChartToResearch input={input} />);
    await user.click(screen.getByRole("button", { name: "Add to research" }));
    const dialog = await screen.findByRole("dialog");
    await screen.findByText(/No existing research matches/);
    expect(await axe(dialog)).toHaveNoViolations();
    expect(mutations).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Confirm Add Chart" }));
    expect(await screen.findByRole("link", { name: "Open research" })).toHaveAttribute("href", `/workspace/research/${id}`);
    expect(mutations).toHaveLength(2);
    const insert = mutations[1]; expect(JSON.parse(String(insert.options.body))).toEqual(input);
    expect(new Headers(insert.options.headers).get("if-match")).toBe('"3"');
    expect(new Headers(insert.options.headers).get("idempotency-key")).toMatch(/^[a-f0-9-]{36}$/);
  });

  it("retains the same insertion key after a lost response and reads the current revision", async () => {
    const keys: string[] = [];
    let revision = 3;
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return response({ subject: "synthetic-alice" });
      if (url === "/api/auth/csrf") return response({ token: "synthetic-csrf" });
      if (url.includes("chart-blocks")) {
        keys.push(new Headers(options.headers).get("idempotency-key")!);
        if (keys.length === 1) { revision = 4; throw new Error("Lost response after commit"); }
        return response({ document: { ...summary, revision: 4 }, value: { block_id: id } }, 201);
      }
      if ((url === "/api/documents" || url.startsWith("/api/documents?"))) return response({ items: [summary], next_cursor: null });
      return response({ ...summary, revision, content: {}, resolved_contexts: {} });
    }));
    const user = userEvent.setup(); render(<AddChartToResearch input={input} />);
    await user.click(screen.getByRole("button", { name: "Add to research" }));
    await screen.findByRole("option", { name: summary.title });
    await user.selectOptions(screen.getByLabelText("Destination"), id);
    await user.click(screen.getByRole("button", { name: "Confirm Add Chart" }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Retry confirmed insertion" }));
    await screen.findByRole("link", { name: "Open research" });
    expect(keys).toHaveLength(2); expect(keys[0]).toBe(keys[1]);
  });

  it("retains destination and retry keys through same-account focus and modal close", async () => {
    const keys: string[] = [];
    const creations: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return response({ subject: "synthetic-alice" });
      if (url === "/api/auth/csrf") return response({ token: "synthetic-csrf" });
      if (url === "/api/documents" && options.method === "POST") {
        creations.push(new Headers(options.headers).get("idempotency-key")!);
        return response({ ...summary, content: {}, resolved_contexts: {} }, 201);
      }
      if (url.includes("chart-blocks")) {
        keys.push(new Headers(options.headers).get("idempotency-key")!);
        if (keys.length === 1) throw new Error("Lost response after commit");
        return response({ document: { ...summary, revision: 4 }, value: { block_id: id } }, 201);
      }
      if (url === "/api/documents") return response({ items: [], next_cursor: null });
      return response({ ...summary, revision: 4, content: {}, resolved_contexts: {} });
    }));
    const user = userEvent.setup();
    render(<ChartAuthActions chartTitle="Synthetic" nextPath="/charts/intents-volume" saveInput={input} />);
    await user.click(await screen.findByRole("button", { name: "Add to research" }));
    await screen.findByText(/No existing research matches/);
    await user.clear(screen.getByLabelText("New research title"));
    await user.type(screen.getByLabelText("New research title"), "Synthetic retained draft");
    await user.click(screen.getByRole("button", { name: "Confirm Add Chart" }));
    await screen.findByRole("alert");
    fireEvent(window, new Event("focus"));
    expect(screen.queryByRole("dialog")).toBeNull();
    await screen.findByRole("dialog");
    expect(screen.getByLabelText("New research title")).toHaveValue("Synthetic retained draft");
    // Closing/reopening an uncertain attempt must also keep the same keys.
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Add to research" }));
    const retry = await screen.findByRole("button", { name: "Retry confirmed insertion" });
    await waitFor(() => expect(retry).toBeEnabled());
    await user.click(retry);
    await screen.findByRole("link", { name: "Open research" });
    expect(creations).toHaveLength(1);
    expect(keys).toHaveLength(2); expect(keys[1]).toBe(keys[0]);
    // A new confirmation after acknowledged success is a new intent.
    await user.click(screen.getByRole("button", { name: "Add to research" }));
    const confirm = await screen.findByRole("button", { name: "Confirm Add Chart" });
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);
    await screen.findByRole("link", { name: "Open research" });
    expect(creations).toHaveLength(2); expect(creations[1]).not.toBe(creations[0]);
    expect(keys[2]).not.toBe(keys[0]);
  });

  it("clears the old account's destination draft when focus verifies another subject", async () => {
    let subject = "synthetic-alice";
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/session"
      ? response({ subject }) : response({ items: [], next_cursor: null })));
    const user = userEvent.setup();
    render(<ChartAuthActions chartTitle="Synthetic" nextPath="/charts/intents-volume" saveInput={input} />);
    await user.click(await screen.findByRole("button", { name: "Add to research" }));
    await user.type(screen.getByLabelText("New research title"), " private Alice draft");
    subject = "synthetic-bob";
    fireEvent(window, new Event("focus"));
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(await screen.findByRole("button", { name: "Add to research" }));
    expect(screen.getByLabelText("New research title")).toHaveValue("Research with chart");
  });

  it("returns focus to the trigger on keyboard cancel without inserting", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/session" ? response({ subject: "synthetic-alice" }) : response({ items: [], next_cursor: null })));
    const user = userEvent.setup(); render(<AddChartToResearch input={input} />);
    const trigger = screen.getByRole("button", { name: "Add to research" });
    await user.click(trigger); await screen.findByRole("dialog"); await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull(); expect(trigger).toHaveFocus();
  });

  it("passes the pinned chart continuation through the login form", async () => {
    const next = `/charts/intents-volume?version=1&dataset_version=${dataset}&start=2026-01-01&end=2026-01-08`;
    let submitted: unknown;
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/csrf") return response({ token: "synthetic-csrf" });
      submitted = JSON.parse(String(options.body)); return response({ error: "Synthetic rejected login" }, 401);
    }));
    const user = userEvent.setup(); render(<LoginForm returnTo={next} />);
    await user.type(screen.getByLabelText("Email"), "synthetic@example.test");
    await user.type(screen.getByLabelText("Password", { exact: true }), "synthetic-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByRole("alert");
    expect(submitted).toMatchObject({ returnTo: next });
  });
});
