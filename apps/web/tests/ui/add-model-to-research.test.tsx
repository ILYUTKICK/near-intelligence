/** NI-055 destination confirmation for the Add Model picker; synthetic only. */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "jest-axe";

import { AddModelToResearch } from "@/features/models/add-to-research/AddModelToResearch";
import { AUTH_CHANGE } from "@/lib/auth/change";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const id = "44444444-4444-4444-8444-444444444444";
const runId = "77777777-7777-4777-8777-777777777777";
const datasetId = "55555555-5555-4555-8555-555555555555";
const time = "2026-11-12T12:00:00Z";
const run = {
  run_id: runId, model_id: "gross_fee_activity_v1", model_version: 1,
  gate_verdict: "READY_WITH_LIMITS" as const,
  sample: { start: "2026-01-01", end_exclusive: "2026-02-01", nobs: 60 },
  tolerances: { coefficient_rtol: "0.00000001", coefficient_atol: "0.00000001" },
  code_commit: "a".repeat(40), manifest_url: `/api/model-runs/${runId}/manifest`,
  published_at: time, published_by: "Synthetic operator",
};
const summary = { id, title: "Synthetic research", revision: 3, schema_version: 1, current_version_id: id,
  created_at: time, updated_at: time, progress: { headings: 0, charts: 0, insights: 0 } };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

describe("NI-055 destination confirmation", () => {
  it("creates an owned destination and inserts the pinned result once with retry-safe keys", async () => {
    const mutations: Array<{ url: string; options: RequestInit; body: unknown }> = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return response({ subject: "synthetic-alice" });
      if (url === "/api/auth/csrf") return response({ token: "synthetic-csrf" });
      if (options.method === "POST") {
        mutations.push({ url, options, body: JSON.parse(String(options.body)) });
        if (url === "/api/documents") return response({ ...summary, content: {}, resolved_contexts: {} }, 201);
        return response({ document: { ...summary, revision: 4 }, value: { block_id: id } }, 201);
      }
      if ((url === "/api/documents" || url.startsWith("/api/documents?"))) return response({ items: [], next_cursor: null });
      return response({ ...summary, content: {}, resolved_contexts: {} });
    }));
    const user = userEvent.setup(); render(<AddModelToResearch run={run} />);
    await user.click(await screen.findByRole("button", { name: "Add to research" }));
    const dialog = await screen.findByRole("dialog");
    await screen.findByText(/No existing research matches/);
    expect(await axe(dialog)).toHaveNoViolations();
    expect(mutations).toHaveLength(0);
    // The route supplies the exact published run. The author selects the dataset.
    expect(dialog).toHaveTextContent(runId);
    expect(screen.getByLabelText("Approved dataset version (UUID)")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Confirm Add Model" })).toBeDisabled();
    await user.type(screen.getByLabelText("Approved dataset version (UUID)"), datasetId);
    await user.type(screen.getByLabelText("Interpretation of the pinned model result"), "Recorded result reads as association only.");
    await user.click(screen.getByRole("button", { name: "Confirm Add Model" }));
    expect(await screen.findByRole("link", { name: "Open research" })).toHaveAttribute("href", `/workspace/research/${id}`);
    expect(mutations).toHaveLength(2);
    const insert = mutations[1];
    expect(insert.url).toBe(`/api/documents/${id}/model-blocks`);
    expect(insert.body).toEqual({ model_run_id: runId, dataset_version_id: datasetId,
      interpretation: [{ type: "paragraph", content: [
        { type: "text", text: "Recorded result reads as association only.", marks: [] }] }] });
    expect(new Headers(insert.options.headers).get("if-match")).toBe('"3"');
    expect(new Headers(insert.options.headers).get("idempotency-key")).toMatch(/^[a-f0-9-]{36}$/);
  });

  it("retains the same insertion key after a lost response and reads the current revision", async () => {
    const inserts: Array<{ key: string | null; ifMatch: string | null }> = [];
    let revision = 3;
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return response({ subject: "synthetic-alice" });
      if (url === "/api/auth/csrf") return response({ token: "synthetic-csrf" });
      if (url.includes("model-blocks")) {
        const headers = new Headers(options.headers);
        inserts.push({ key: headers.get("idempotency-key"), ifMatch: headers.get("if-match") });
        if (inserts.length === 1) { revision = 4; throw new Error("Lost response after commit"); }
        return response({ document: { ...summary, revision: 4 }, value: { block_id: id } }, 201);
      }
      if ((url === "/api/documents" || url.startsWith("/api/documents?"))) return response({ items: [summary], next_cursor: null });
      return response({ ...summary, revision, content: {}, resolved_contexts: {} });
    }));
    const user = userEvent.setup(); render(<AddModelToResearch run={run} />);
    await user.click(await screen.findByRole("button", { name: "Add to research" }));
    await screen.findByRole("option", { name: summary.title });
    await user.selectOptions(screen.getByLabelText("Destination"), id);
    await user.type(screen.getByLabelText("Approved dataset version (UUID)"), datasetId);
    await user.type(screen.getByLabelText("Interpretation of the pinned model result"), "Synthetic interpretation");
    await user.click(screen.getByRole("button", { name: "Confirm Add Model" }));
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Approved dataset version (UUID)")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Confirm Add Model" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry confirmed insertion" }));
    await screen.findByRole("link", { name: "Open research" });
    expect(inserts).toHaveLength(2);
    expect(inserts[0].key).toBeTruthy();
    expect(inserts[1].key).toBe(inserts[0].key);
    // The first attempt CASed the revision it read (3); the retry re-reads
    // the CURRENT revision (4) and carries the SAME key with the same body —
    // the write-once store replays the original result for that fingerprint.
    expect(inserts[0].ifMatch).toBe('"3"');
    expect(inserts[1].ifMatch).toBe('"4"');
  });

  it("keeps the draft and the created destination when the dataset pin needs correction", async () => {
    let creates = 0;
    let inserts = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string, options: RequestInit = {}) => {
      if (url === "/api/auth/session") return response({ subject: "synthetic-alice" });
      if (url === "/api/auth/csrf") return response({ token: "synthetic-csrf" });
      if (options.method === "POST") {
        if (url === "/api/documents") {
          creates++;
          return response({ ...summary, content: {}, resolved_contexts: {} }, 201);
        }
        inserts++;
        if (inserts === 2) return response({ document: { ...summary, revision: 4 }, value: { block_id: id } }, 201);
        return response({ error: { code: "REFERENCE_INVALID", message: "Referenced dataset version does not exist or is not an approved public dataset",
          request_id: "synthetic", retryable: false, details: [{ path: "dataset_version_id", reason: "dangling_dataset_reference" }] } }, 422);
      }
      if ((url === "/api/documents" || url.startsWith("/api/documents?"))) return response({ items: [], next_cursor: null });
      return response({ ...summary, content: {}, resolved_contexts: {} });
    }));
    const user = userEvent.setup(); render(<AddModelToResearch run={run} />);
    await user.click(await screen.findByRole("button", { name: "Add to research" }));
    await screen.findByText(/No existing research matches/);
    const dataset = screen.getByLabelText("Approved dataset version (UUID)");
    await user.type(dataset, datasetId);
    await user.type(screen.getByLabelText("Interpretation of the pinned model result"), "Retained synthetic prose");
    await user.click(screen.getByRole("button", { name: "Confirm Add Model" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not an approved public dataset");
    expect(screen.getByLabelText("Interpretation of the pinned model result")).toHaveValue("Retained synthetic prose");
    expect(screen.getByLabelText("Destination")).toHaveValue(id);
    await user.clear(dataset);
    await user.type(dataset, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
    await user.click(screen.getByRole("button", { name: "Confirm Add Model" }));
    expect(await screen.findByRole("link", { name: "Open research" })).toHaveAttribute("href", `/workspace/research/${id}`);
    expect(creates).toBe(1);
  });

  it("suspends an open draft until the account is verified and clears it after a switch", async () => {
    let subject = "synthetic-alice";
    let available = true;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url === "/api/auth/session") return available ? response({ subject }) : response({}, 503);
      if (url === "/api/documents") return response({ items: [{ ...summary, title: subject }], next_cursor: null });
      throw new Error(`Unexpected synthetic request ${url}`);
    }));
    const user = userEvent.setup();
    render(<AddModelToResearch run={run} />);
    await user.click(await screen.findByRole("button", { name: "Add to research" }));
    const prose = "Only Alice's draft";
    await user.type(screen.getByLabelText("Interpretation of the pinned model result"), prose);
    available = false;
    fireEvent.focus(window);
    const retry = await screen.findByRole("button", { name: "Retry sign-in check" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    available = true;
    await user.click(retry);
    expect(await screen.findByLabelText("Interpretation of the pinned model result")).toHaveValue(prose);
    subject = "synthetic-bob";
    fireEvent(window, new Event(AUTH_CHANGE));
    await user.click(await screen.findByRole("button", { name: "Add to research" }));
    expect(await screen.findByRole("option", { name: "synthetic-bob" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "synthetic-alice" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Interpretation of the pinned model result")).toHaveValue("");
  });
});
