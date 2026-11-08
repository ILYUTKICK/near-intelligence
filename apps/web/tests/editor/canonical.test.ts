/**
 * NI-039 canonical validator matrix: every P0 block type serializes a valid
 * canonical document and every canonical violation (unknown types/fields,
 * missing/duplicate ids, dangling links, bounds, marks, href rules) is
 * rejected with an exact path — the client mirror of the NI-036 validator.
 * All content below is synthetic and visibly labeled (fixture).
 */
import { describe, expect, it } from "vitest";

import {
  CanonicalDocumentError,
  buildLinkGraph,
  validateCanonicalDocument,
  type CanonicalAnyMark,
  type CanonicalBlock,
  type CanonicalSelection,
  type CanonicalText,
} from "@/features/editor/canonical";

const UUID_A = "11111111-1111-4111-8111-111111111111";
const UUID_B = "22222222-2222-4222-8222-222222222222";
const UUID_C = "33333333-3333-4333-8333-333333333333";
const UUID_D = "44444444-4444-4444-8444-444444444444";
const UUID_E = "55555555-5555-4555-8555-555555555555";

const TEXT = (text: string, marks?: CanonicalAnyMark[]): CanonicalText =>
  marks ? { type: "text", text, marks } : { type: "text", text };

const SELECTION: CanonicalSelection = { start: "2026-01-01", end: "2026-02-01", frequency: "day", filters: {} };
const RESOLVED_CONTEXT = {
  chart_definition_version_id: UUID_C,
  dataset_version_id: UUID_D,
  selection: SELECTION,
  context_hash: "a".repeat(64),
  renderer_version: "echarts-modular-svg@1",
  metric_definition_versions: [UUID_E],
  resolved_at: "2026-11-08T00:00:00Z",
};

const FIXTURE_BLOCKS: CanonicalBlock[] = [
  {
    type: "paragraph",
    attrs: { block_id: UUID_A },
    content: [TEXT("Fixture paragraph", [{ type: "bold" }])],
  },
  {
    type: "heading",
    attrs: { block_id: UUID_B, level: 2 },
    content: [TEXT("Fixture heading")],
  },
  {
    type: "bullet_list",
    attrs: { block_id: UUID_C },
    content: [
      { type: "list_item", content: [{ type: "paragraph", content: [TEXT("Item")] }] },
    ],
  },
  { type: "divider", attrs: { block_id: UUID_D } },
];

function doc(blocks: unknown) {
  return { schema_version: 1, type: "doc", content: blocks };
}

function expectInvalid(value: unknown, path: string, reason: string): void {
  try {
    validateCanonicalDocument(value);
  } catch (error) {
    expect(error).toBeInstanceOf(CanonicalDocumentError);
    const issueError = error as CanonicalDocumentError;
    expect(issueError.issues).toEqual([{ path, reason }]);
    return;
  }
  throw new Error(`Expected ${JSON.stringify(value).slice(0, 120)} to be rejected with ${path}: ${reason}`);
}

describe("canonical validator — valid P0 documents", () => {
  it("accepts the empty document", () => {
    expect(validateCanonicalDocument(doc([]))).toEqual(doc([]));
  });

  it("accepts every P0 block type in one document", () => {
    const blocks: CanonicalBlock[] = [
      ...FIXTURE_BLOCKS,
      {
        type: "ordered_list",
        attrs: { block_id: UUID_E },
        content: [
          { type: "list_item", content: [{ type: "paragraph", content: [TEXT("First")] }] },
        ],
      },
      {
        type: "liveChart",
        attrs: {
          block_id: "66666666-6666-4666-8666-666666666666",
          chart_definition_version_id: UUID_C,
          mode: "live",
          selection: SELECTION,
          observed_dataset_version_id: UUID_D,
          snapshot_id: null,
        },
      },
      {
        type: "dataTable",
        attrs: {
          block_id: "77777777-7777-4777-8777-777777777777",
          columns: [
            { key: "column_1", label: "Column 1", type: "string" },
            { key: "column_2", label: "Net flow", type: "number", unit: "NEAR" },
          ],
          rows: [["a", 1], ["b", null]],
        },
      },
      {
        type: "insight",
        attrs: {
          block_id: "88888888-8888-4888-8888-888888888888",
          insight_id: "99999999-9999-4999-8999-999999999999",
          type: "observation",
          classification: "supporting",
          body: [{ type: "paragraph", content: [TEXT("Observed pattern (fixture)")] }],
          context: RESOLVED_CONTEXT,
          authored_at: "2026-11-08T00:00:00Z",
          modified_at: "2026-11-08T00:00:00Z",
        },
      },
      {
        type: "hypothesis",
        attrs: {
          block_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
          hypothesis_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          statement: "Fee growth follows app adoption (fixture)",
          assessment: "untested",
          authored_at: "2026-11-08T00:00:00Z",
          modified_at: "2026-11-08T00:00:00Z",
        },
      },
      {
        type: "evidence",
        attrs: {
          block_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
          evidence_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          hypothesis_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          classification: "supporting",
          target_kind: "chart_block",
          target_id: "66666666-6666-4666-8666-666666666666",
          explanation: "Chart shows the expected pattern (fixture)",
        },
      },
      {
        type: "risk",
        attrs: {
          block_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          title: "Sampling bias (fixture)",
          body: [{ type: "paragraph", content: [TEXT("The sample may be biased.")] }],
          related_hypothesis_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        },
      },
    ];
    const validated = validateCanonicalDocument(doc(blocks));
    expect(validated.content).toHaveLength(blocks.length);
    // The link graph inventory matches the fixture.
    const graph = buildLinkGraph(validated.content);
    expect(graph.hypothesisIds).toContain("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb");
    expect(graph.insightIds).toContain("99999999-9999-4999-8999-999999999999");
    expect(graph.chartBlockIds).toContain("66666666-6666-4666-8666-666666666666");
  });

  it("accepts an empty paragraph with an empty inline content array", () => {
    expect(validateCanonicalDocument(doc([
      { type: "paragraph", attrs: { block_id: UUID_A }, content: [] },
    ]))).toBeDefined();
  });

  it("accepts nested lists up to depth 3", () => {
    const level3 = {
      type: "bullet_list",
      content: [
        {
          type: "list_item",
          content: [
            { type: "paragraph", content: [TEXT("Level 3")] },
          ],
        },
      ],
    };
    const level2 = {
      type: "bullet_list",
      content: [
        {
          type: "list_item",
          content: [
            { type: "paragraph", content: [TEXT("Level 2")] },
            level3,
          ],
        },
      ],
    };
    expect(validateCanonicalDocument(doc([
      {
        type: "bullet_list",
        attrs: { block_id: UUID_A },
        content: [
          {
            type: "list_item",
            content: [{ type: "paragraph", content: [TEXT("Level 1")] }, level2],
          },
        ],
      },
    ]))).toBeDefined();
  });

  it("accepts a model-run context on an insight", () => {
    expect(validateCanonicalDocument(doc([
      {
        type: "insight",
        attrs: {
          block_id: UUID_A,
          insight_id: UUID_B,
          type: "conclusion",
          classification: "uncertain",
          body: [{ type: "paragraph", content: [TEXT("Conclusion body")] }],
          context: {
            model_run_id: UUID_C,
            dataset_version_id: UUID_D,
            specification_version: "ols-robust@1",
            context_hash: "b".repeat(64),
          },
          authored_at: "2026-11-08T00:00:00Z",
          modified_at: "2026-11-08T00:00:00Z",
        },
      },
    ]))).toBeDefined();
  });
});

describe("canonical validator — rejections", () => {
  it("rejects unknown root fields and wrong schema version", () => {
    expectInvalid({ schema_version: 1, type: "doc", content: [], extra: 1 }, "document.extra", "unknown_field");
    expectInvalid({ schema_version: 2, type: "doc", content: [] }, "document.schema_version", "unsupported_schema_version");
    expectInvalid({ schema_version: 1, type: "not-doc", content: [] }, "document.type", "must_be_doc");
  });

  it("rejects unsupported and malformed block types", () => {
    expectInvalid(doc([{ type: "blockquote", attrs: { block_id: UUID_A } }]), "document.content[0].type", "unsupported_block_type");
    expectInvalid(doc([{ type: "horizontalRule", attrs: { block_id: UUID_A } }]), "document.content[0].type", "unsupported_block_type");
  });

  it("rejects a missing block_id and duplicates", () => {
    expectInvalid(doc([{ type: "divider", attrs: {} }]), "document.content[0].attrs.block_id", "must_be_uuid_string");
    expectInvalid(doc([{ type: "divider", attrs: { block_id: "not-a-uuid" } }]), "document.content[0].attrs.block_id", "must_be_uuid");
    expectInvalid(doc([
      { type: "divider", attrs: { block_id: UUID_A } },
      { type: "divider", attrs: { block_id: UUID_A } },
    ]), "document.content[1]", "duplicate_block_id");
    expectInvalid(doc([
      { type: "divider", attrs: { block_id: "not-a-uuid" } },
    ]), "document.content[0].attrs.block_id", "must_be_uuid");
  });

  it("rejects unknown attrs per block family", () => {
    expectInvalid(
      doc([{ type: "paragraph", attrs: { block_id: UUID_A, level: 1 }, content: [TEXT("x")] }]),
      "document.content[0].attrs.level",
      "unknown_field",
    );
    expectInvalid(
      doc([{ type: "heading", attrs: { block_id: UUID_B, level: 4 }, content: [TEXT("x")] }]),
      "document.content[0].attrs.level",
      "out_of_range",
    );
    expectInvalid(
      doc([{ type: "divider", attrs: { block_id: UUID_D }, content: [] }]),
      "document.content[0].content",
      "unknown_field",
    );
    expectInvalid(
      doc([{ type: "paragraph", attrs: { block_id: UUID_A } }]),
      "document.content[0].content",
      "paragraph_requires_content",
    );
  });

  it("rejects non-whitelisted marks and bad link targets", () => {
    expectInvalid(
      doc([{ type: "paragraph", attrs: { block_id: UUID_A }, content: [TEXT("x", [{ type: "code" } as unknown as CanonicalAnyMark])] }]),
      "document.content[0].content[0].marks[0].type",
      "unsupported_value",
    );
    expectInvalid(
      doc([{ type: "paragraph", attrs: { block_id: UUID_A }, content: [TEXT("x", [{ type: "link", attrs: { href: "javascript:alert(1)" } }])] }]),
      "document.content[0].content[0].marks[0].attrs.href",
      "unsupported_link_target",
    );
    expectInvalid(
      doc([{ type: "paragraph", attrs: { block_id: UUID_A }, content: [TEXT("x", [{ type: "link", attrs: { href: "https://user:pass@example.test/" } }])] }]),
      "document.content[0].content[0].marks[0].attrs.href",
      "credentials_in_link",
    );
    expectInvalid(
      doc([{ type: "paragraph", attrs: { block_id: UUID_A }, content: [TEXT("x", [{ type: "bold" }, { type: "bold" }])] }]),
      "document.content[0].content[0].marks[1].type",
      "duplicate_mark",
    );
  });

  it("rejects list grammar violations", () => {
    expectInvalid(
      doc([{ type: "bullet_list", attrs: { block_id: UUID_A }, content: [] }]),
      "document.content[0].content",
      "list_requires_items",
    );
    expectInvalid(
      doc([{
        type: "bullet_list",
        attrs: { block_id: UUID_A },
        content: [
          { type: "list_item", content: [{ type: "bullet_list", content: [{ type: "list_item", content: [{ type: "paragraph", content: [TEXT("x")] }] }] }] },
        ],
      }]),
      "document.content[0].content[0].content[0].type",
      "nested_list_requires_preceding_paragraph",
    );
  });

  it("rejects out-of-bounds content", () => {
    const tooDeep = buildDeepList(4);
    expect(tooDeep.path).toBe(
      "document.content[0].content[0].content[1].content[0].content[1].content[0].content[1]",
    );
    expect(tooDeep.reason).toBe("nesting_too_deep");
  });

  it("rejects dataTable violations", () => {
    expectInvalid(
      doc([{ type: "dataTable", attrs: { block_id: UUID_A, columns: [] } }]),
      "document.content[0].attrs.columns",
      "table_requires_columns",
    );
    expectInvalid(
      doc([{
        type: "dataTable",
        attrs: {
          block_id: UUID_A,
          columns: [{ key: "column_1", label: "A", type: "string" }],
          rows: [["1"]],
          dataset_version_id: UUID_B,
        },
      }]),
      "document.content[0].attrs",
      "table_requires_rows_or_dataset_reference_not_both",
    );
    expectInvalid(
      doc([{
        type: "dataTable",
        attrs: {
          block_id: UUID_A,
          columns: [{ key: "column_1", label: "A", type: "string" }],
          rows: [["1", "2"]],
        },
      }]),
      "document.content[0].attrs.rows[0]",
      "row_width_must_match_columns",
    );
    expectInvalid(
      doc([{
        type: "dataTable",
        attrs: {
          block_id: UUID_A,
          columns: [{ key: "column_1", label: "A", type: "string" }],
          rows: [[Infinity]],
        },
      }]),
      "document.content[0].attrs.rows[0][0]",
      "cell_must_be_finite",
    );
    const wideColumns = Array.from({ length: 101 }, (_, index) => ({
      key: `column_${index + 1}`,
      label: `Column ${index + 1}`,
      type: "string",
    }));
    expectInvalid(
      doc([{
        type: "dataTable",
        attrs: { block_id: UUID_A, columns: wideColumns, rows: [[]] },
      }]),
      "document.content[0].attrs.columns",
      "too_many_columns",
    );
  });

  it("rejects liveChart mode/snapshot inconsistencies", () => {
    expectInvalid(
      doc([{
        type: "liveChart",
        attrs: {
          block_id: UUID_A,
          chart_definition_version_id: UUID_B,
          mode: "snapshot",
          selection: SELECTION,
          observed_dataset_version_id: UUID_C,
          snapshot_id: null,
        },
      }]),
      "document.content[0].attrs.snapshot_id",
      "snapshot_mode_requires_snapshot_id",
    );
    expectInvalid(
      doc([{
        type: "liveChart",
        attrs: {
          block_id: UUID_A,
          chart_definition_version_id: UUID_B,
          mode: "live",
          selection: SELECTION,
          observed_dataset_version_id: UUID_C,
          snapshot_id: UUID_D,
        },
      }]),
      "document.content[0].attrs.snapshot_id",
      "live_mode_cannot_carry_snapshot_id",
    );
    expectInvalid(
      doc([{
        type: "liveChart",
        attrs: {
          block_id: UUID_A,
          chart_definition_version_id: UUID_B,
          mode: "live",
          selection: { start: "2026-02-01", end: "2026-01-01", frequency: "day", filters: {} },
          observed_dataset_version_id: UUID_C,
          snapshot_id: null,
        },
      }]),
      "document.content[0].attrs.selection.end",
      "window_must_be_half_open_nonempty",
    );
  });

  it("rejects dangling same-document links", () => {
    expectInvalid(
      doc([{
        type: "evidence",
        attrs: {
          block_id: UUID_A,
          evidence_id: UUID_B,
          hypothesis_id: UUID_C,
          classification: "supporting",
          target_kind: "citation",
          target_id: UUID_D,
          explanation: "No hypothesis exists in this document (fixture)",
        },
      }]),
      "content",
      "dangling_hypothesis_reference",
    );
    const hypothesisId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
    const evidenceId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
    expectInvalid(
      doc([
        {
          type: "hypothesis",
          attrs: {
            block_id: UUID_A,
            hypothesis_id: hypothesisId,
            statement: "Statement (fixture)",
            assessment: "untested",
            authored_at: "2026-11-08T00:00:00Z",
            modified_at: "2026-11-08T00:00:00Z",
          },
        },
        {
          type: "evidence",
          attrs: {
            block_id: UUID_B,
            evidence_id: evidenceId,
            hypothesis_id: hypothesisId,
            classification: "supporting",
            target_kind: "insight",
            target_id: "99999999-9999-4999-8999-999999999999",
            explanation: "Targets an insight that does not exist (fixture)",
          },
        },
      ]),
      "content",
      "dangling_insight_reference",
    );
  });

  it("rejects duplicate entity ids", () => {
    const hypothesis = (blockId: string) => ({
      type: "hypothesis",
      attrs: {
        block_id: blockId,
        hypothesis_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        statement: "Statement (fixture)",
        assessment: "untested",
        authored_at: "2026-11-08T00:00:00Z",
        modified_at: "2026-11-08T00:00:00Z",
      },
    });
    expectInvalid(
      doc([hypothesis(UUID_A), hypothesis(UUID_B)]),
      "content",
      "duplicate_hypothesis_id",
    );
  });

  it("rejects annotation timestamps without a timezone", () => {
    expectInvalid(
      doc([{
        type: "hypothesis",
        attrs: {
          block_id: UUID_A,
          hypothesis_id: UUID_B,
          statement: "Statement (fixture)",
          assessment: "untested",
          authored_at: "2026-11-08T00:00:00",
          modified_at: "2026-11-08T00:00:00Z",
        },
      }]),
      "document.content[0].attrs.authored_at",
      "timestamp_requires_timezone",
    );
  });

  it("rejects more than 200 top-level blocks", () => {
    const blocks = Array.from({ length: 201 }, (_, index) => ({
      type: "divider",
      attrs: { block_id: formatUuid(index) },
    }));
    expectInvalid(doc(blocks), "document.content", "too_many_blocks");
  });
});

function formatUuid(index: number): string {
  const hex = index.toString(16).padStart(8, "0");
  return `${hex}-0000-4000-8000-000000000000`;
}

function buildDeepList(depth: number): { path: string; reason: string } {
  // Build a bullet list nested `depth` levels; validate and capture the issue.
  let inner: unknown = {
    type: "list_item",
    content: [{ type: "paragraph", content: [TEXT("Deepest")] }],
  };
  for (let level = 0; level < depth - 1; level += 1) {
    inner = {
      type: "list_item",
      content: [
        { type: "paragraph", content: [TEXT(`Level ${depth - level - 1}`)] },
        { type: "bullet_list", content: [inner] },
      ],
    };
  }
  try {
    validateCanonicalDocument(doc([{ type: "bullet_list", attrs: { block_id: UUID_A }, content: [inner] }]));
  } catch (error) {
    const issueError = error as CanonicalDocumentError;
    return { path: issueError.issues[0].path, reason: issueError.issues[0].reason };
  }
  throw new Error("Expected the deep list to be rejected");
}
