/**
 * Tiptap JSON <-> canonical document transform (NI-039).
 *
 * The storage path is canonical JSON (NI-036; ADR-018: "the canonical storage
 * path is JSON"). The Tiptap editor state differs from the canonical grammar
 * in exactly two bounded ways, which this module owns:
 *
 * 1. Node names for lists: Tiptap uses `bulletList`/`orderedList`/`listItem`
 *    (camelCase), the canonical schema uses `bullet_list`/`ordered_list`/
 *    `list_item`. Every other P0 type is named identically in both grammars
 *    (paragraph, heading, liveChart, dataTable, insight, hypothesis,
 *    evidence, risk, modelResult, divider).
 * 2. Tiptap omits empty inline `content` arrays; the canonical schema
 *    requires the `content` key (it may be an empty array). The transform
 *    normalizes this one way (Tiptap -> canonical) without inventing text.
 *
 * Everything else — attrs, marks, order, nesting — passes through and is
 * validated by the canonical validator before the result is returned, so a
 * failed structural operation can never reach the persistence boundary.
 */

import type { JSONContent } from "@tiptap/core";

import {
  validateCanonicalDocument,
  type CanonicalAnyMark,
  type CanonicalBlock,
  type CanonicalDocument,
  type CanonicalListItem,
  type CanonicalRichList,
  type CanonicalText,
  type RichFragment,
} from "./canonical";

/** Canonical -> Tiptap node names for the list family only. */
const CANONICAL_TO_TIPTAP: Record<string, string> = {
  bullet_list: "bulletList",
  ordered_list: "orderedList",
  list_item: "listItem",
};

function mapMarks(marks: CanonicalAnyMark[] | undefined): JSONContent["marks"] {
  if (!marks || marks.length === 0) {
    return undefined;
  }
  return marks.map((mark) =>
    mark.type === "link"
      ? { type: "link", attrs: { href: mark.attrs.href } }
      : { type: mark.type },
  );
}

function richFragmentToTiptap(fragment: RichFragment): JSONContent[] {
  return fragment.map((node) => {
    if (node.type === "paragraph") {
      return {
        type: "paragraph",
        content: node.content.map((run) => ({
          type: "text",
          text: run.text,
          ...(mapMarks(run.marks) ? { marks: mapMarks(run.marks) } : {}),
        })),
      };
    }
    return {
      type: CANONICAL_TO_TIPTAP[node.type],
      content: node.content.map(listItemToTiptap),
    };
  });
}

function listItemToTiptap(item: CanonicalListItem): JSONContent {
  return { type: "listItem", content: richFragmentToTiptap(item.content) };
}

/**
 * Convert a validated canonical document into a Tiptap document JSON
 * (for the editor `content` option / `setContent`). The input must already
 * be validated — pass persisted `content` only after
 * `validateCanonicalDocument` accepted it.
 */
export function canonicalToTiptapDoc(document: CanonicalDocument): JSONContent {
  return { type: "doc", content: canonicalToTiptapContent(document) };
}

/**
 * Convert a validated canonical document into Tiptap top-level node content
 * (an array — accepted by `insertContentAt`, NOT by the editor `content`
 * option, which needs {@link canonicalToTiptapDoc}).
 */
export function canonicalToTiptapContent(document: CanonicalDocument): JSONContent[] {
  return document.content.map((block) => canonicalBlockToTiptap(block));
}

/** Convert one validated canonical block into Tiptap JSON content. */
export function canonicalBlockToTiptap(block: CanonicalBlock): JSONContent {
  const attrs: Record<string, unknown> = { ...block.attrs };
  switch (block.type) {
    case "paragraph":
    case "heading":
      return {
        type: block.type,
        attrs,
        content: block.content.map((run) => ({
          type: "text",
          text: run.text,
          ...(mapMarks(run.marks) ? { marks: mapMarks(run.marks) } : {}),
        })),
      };
    case "bullet_list":
    case "ordered_list":
      return {
        type: CANONICAL_TO_TIPTAP[block.type],
        attrs,
        content: block.content.map(listItemToTiptap),
      };
    case "divider":
      return { type: "divider", attrs };
    case "liveChart":
    case "dataTable":
    case "insight":
    case "hypothesis":
    case "evidence":
    case "risk":
    case "modelResult":
      return { type: block.type, attrs };
  }
}

// --------------------------------------------------------------------------- //
// Tiptap -> canonical
// --------------------------------------------------------------------------- //

function textRunsToCanonical(runs: JSONContent[] | undefined): CanonicalText[] {
  return (runs ?? []).map((run) => {
    if (run.type !== "text" || typeof run.text !== "string") {
      // Non-text inline nodes (hardBreak etc.) are not in the canonical
      // grammar; the validator rejects them with an exact path below.
      return run as unknown as CanonicalText;
    }
    const marks = run.marks?.map((mark) => {
      if (mark.type === "link") {
        const href = (mark.attrs?.href as string | undefined) ?? "";
        return { type: "link", attrs: { href } } satisfies CanonicalAnyMark;
      }
      return { type: mark.type } as CanonicalAnyMark;
    });
    return marks && marks.length > 0
      ? { type: "text", text: run.text, marks }
      : { type: "text", text: run.text };
  });
}

function richFragmentToCanonical(nodes: JSONContent[] | undefined): RichFragment {
  return (nodes ?? []).map((node) => {
    if (node.type === "paragraph") {
      return { type: "paragraph", content: textRunsToCanonical(node.content) };
    }
    if (node.type === "bulletList" || node.type === "orderedList") {
      const list: CanonicalRichList = {
        type: node.type === "orderedList" ? "ordered_list" : "bullet_list",
        content: (node.content ?? []).map((item) => listItemToCanonical(item)),
      };
      return list;
    }
    // Unknown rich node: handed to the validator verbatim so it fails with
    // an exact path instead of being silently dropped.
    return node as unknown as RichFragment[number];
  });
}

function listItemToCanonical(item: JSONContent): CanonicalListItem {
  return { type: "list_item", content: richFragmentToCanonical(item.content) };
}

/**
 * Canonical attrs are constructed per block family, mirroring the server's
 * canonicalization exactly: Tiptap resolves missing attrs to defaults and
 * `getJSON` emits the FULL resolved set whenever any attr differs from the
 * defaults (so an ordered list leaks `start`/`type`, and a nested paragraph
 * can leak `block_id: null`). The canonical grammar only knows the keys
 * below; optional null keys (hypothesis_id, related_hypothesis_id, rows,
 * dataset_version_id) are omitted like the server omits them, while
 * `liveChart.snapshot_id` is kept explicitly null for live charts.
 */
function canonicalAttrs(nodeType: string, source: Record<string, unknown>): Record<string, unknown> {
  const pick = (key: string): unknown => source[key];
  switch (nodeType) {
    case "paragraph":
    case "divider":
      return { block_id: pick("block_id") };
    case "heading":
      return { block_id: pick("block_id"), level: pick("level") };
    case "bulletList":
    case "orderedList":
      return { block_id: pick("block_id") };
    case "liveChart":
      return {
        block_id: pick("block_id"),
        chart_definition_version_id: pick("chart_definition_version_id"),
        mode: pick("mode"),
        selection: pick("selection"),
        observed_dataset_version_id: pick("observed_dataset_version_id"),
        snapshot_id: pick("snapshot_id") ?? null,
      };
    case "dataTable": {
      const attrs: Record<string, unknown> = {
        block_id: pick("block_id"),
        columns: pick("columns"),
      };
      if (pick("rows") != null) {
        attrs.rows = pick("rows");
      }
      if (pick("dataset_version_id") != null) {
        attrs.dataset_version_id = pick("dataset_version_id");
      }
      return attrs;
    }
    case "insight": {
      const attrs: Record<string, unknown> = {
        block_id: pick("block_id"),
        insight_id: pick("insight_id"),
        type: pick("type"),
        classification: pick("classification"),
        body: pick("body"),
        context: pick("context"),
        authored_at: pick("authored_at"),
        modified_at: pick("modified_at"),
      };
      if (pick("hypothesis_id") != null) {
        attrs.hypothesis_id = pick("hypothesis_id");
      }
      return attrs;
    }
    case "hypothesis":
      return {
        block_id: pick("block_id"),
        hypothesis_id: pick("hypothesis_id"),
        statement: pick("statement"),
        assessment: pick("assessment"),
        authored_at: pick("authored_at"),
        modified_at: pick("modified_at"),
      };
    case "evidence":
      return {
        block_id: pick("block_id"),
        evidence_id: pick("evidence_id"),
        hypothesis_id: pick("hypothesis_id"),
        classification: pick("classification"),
        target_kind: pick("target_kind"),
        target_id: pick("target_id"),
        explanation: pick("explanation"),
      };
    case "risk": {
      const attrs: Record<string, unknown> = {
        block_id: pick("block_id"),
        title: pick("title"),
        body: pick("body"),
      };
      if (pick("related_hypothesis_id") != null) {
        attrs.related_hypothesis_id = pick("related_hypothesis_id");
      }
      return attrs;
    }
    case "modelResult":
      // Ids + interpretation only: any coefficient a client injected into the
      // node attrs is dropped here and then rejected by the validator.
      return {
        block_id: pick("block_id"),
        model_run_id: pick("model_run_id"),
        dataset_version_id: pick("dataset_version_id"),
        interpretation: pick("interpretation"),
      };
    default:
      return { ...source };
  }
}

function nodeToCanonicalBlock(node: JSONContent): unknown {
  switch (node.type) {
    case "paragraph":
    case "heading":
      // Tiptap omits empty inline content; the canonical grammar wants the
      // key present (possibly an empty array).
      return {
        type: node.type,
        attrs: canonicalAttrs(node.type, (node.attrs ?? {}) as Record<string, unknown>),
        content: textRunsToCanonical(node.content),
      };
    case "bulletList":
    case "orderedList":
      return {
        type: node.type === "orderedList" ? "ordered_list" : "bullet_list",
        attrs: canonicalAttrs(node.type, (node.attrs ?? {}) as Record<string, unknown>),
        content: (node.content ?? []).map(listItemToCanonical),
      };
    case "divider":
    case "liveChart":
    case "dataTable":
    case "insight":
    case "hypothesis":
    case "evidence":
    case "risk":
    case "modelResult":
      return { type: node.type, attrs: canonicalAttrs(node.type, (node.attrs ?? {}) as Record<string, unknown>) };
    default:
      // Unknown top-level node: validated verbatim so it is rejected with an
      // exact path, never silently dropped.
      return node;
  }
}

/**
 * Convert the Tiptap editor JSON into the canonical document shape and
 * validate it. Throws {@link CanonicalDocumentError} when the editor state is
 * not representable canonically (which can only happen through content the
 * schema never accepted — the validator names the exact path).
 */
export function tiptapToCanonicalDocument(doc: JSONContent): CanonicalDocument {
  const topLevel = doc.type === "doc" ? (doc.content ?? []) : [doc];
  const content: unknown[] = topLevel.map((node) => nodeToCanonicalBlock(node));
  return validateCanonicalDocument({ schema_version: 1, type: "doc", content });
}
