/**
 * NI-039 smoke: the canonical serialize/load layer against the assembled
 * extension set (synthetic fixture content, visibly labeled).
 */
import { Editor } from "@tiptap/core";
import { describe, expect, it } from "vitest";

import type { CanonicalDocument } from "@/features/editor/canonical";
import { EDITOR_EXTENSIONS } from "@/features/editor/extensions";
import { canonicalToTiptapDoc, tiptapToCanonicalDocument } from "@/features/editor/serialize";

const BLOCK = "11111111-1111-4111-8111-111111111111";

export const FIXTURE_DOC: CanonicalDocument = {
  schema_version: 1,
  type: "doc",
  content: [
    {
      type: "heading",
      attrs: { block_id: BLOCK, level: 1 },
      content: [{ type: "text", text: "Section (fixture)" }],
    },
    {
      type: "paragraph",
      attrs: { block_id: "22222222-2222-4222-8222-222222222222" },
      content: [
        { type: "text", text: "Bold ", marks: [{ type: "bold" }] },
        { type: "text", text: "and ", marks: [{ type: "italic" }] },
        {
          type: "text",
          text: "a link",
          marks: [{ type: "link", attrs: { href: "https://example.test/spec" } }],
        },
      ],
    },
    {
      type: "bullet_list",
      attrs: { block_id: "33333333-3333-4333-8333-333333333333" },
      content: [
        {
          type: "list_item",
          content: [{ type: "paragraph", content: [{ type: "text", text: "Item one" }] }],
        },
      ],
    },
    { type: "divider", attrs: { block_id: "44444444-4444-4444-8444-444444444444" } },
    {
      type: "risk",
      attrs: {
        block_id: "55555555-5555-4555-8555-555555555555",
        title: "Attribution risk (fixture)",
        body: [{ type: "paragraph", content: [{ type: "text", text: "Sample could be biased." }] }],
      },
    },
    {
      type: "dataTable",
      attrs: {
        block_id: "66666666-6666-4666-8666-666666666666",
        columns: [
          { key: "column_1", label: "Column 1", type: "string" },
          { key: "column_2", label: "Column 2", type: "string" },
        ],
        rows: [["a", "b"]],
      },
    },
    {
      type: "liveChart",
      attrs: {
        block_id: "77777777-7777-4777-8777-777777777777",
        chart_definition_version_id: "88888888-8888-4888-8888-888888888888",
        mode: "live",
        selection: { start: "2026-01-01", end: "2026-02-01", frequency: "day", filters: {} },
        observed_dataset_version_id: "99999999-9999-4999-8999-999999999999",
        snapshot_id: null,
      },
    },
  ],
};

describe("canonical serialize/load (smoke)", () => {
  it("loads a canonical fixture and re-serializes identically", () => {
    const editor = new Editor({ extensions: EDITOR_EXTENSIONS, content: canonicalToTiptapDoc(FIXTURE_DOC) });
    const canonical = tiptapToCanonicalDocument(editor.getJSON());
    editor.destroy();
    expect(canonical).toEqual(FIXTURE_DOC);
  });

  it("keeps the editor round trip stable (load -> getJSON -> serialize -> reload -> serialize)", () => {
    const editor = new Editor({ extensions: EDITOR_EXTENSIONS, content: canonicalToTiptapDoc(FIXTURE_DOC) });
    const first = tiptapToCanonicalDocument(editor.getJSON());
    const reloaded = new Editor({ extensions: EDITOR_EXTENSIONS, content: canonicalToTiptapDoc(first) });
    const second = tiptapToCanonicalDocument(reloaded.getJSON());
    editor.destroy();
    reloaded.destroy();
    expect(second).toEqual(first);
  });
});
