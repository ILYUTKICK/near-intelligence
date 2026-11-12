/**
 * Canonical editor document schema — client render boundary (NI-039).
 *
 * This module mirrors the authoritative canonical validator
 * (apps/api/src/near_api/documents/schema.py, NI-036) so the editor can
 * reject malformed content before it is ever rendered and prove that every
 * structural operation serializes a valid document. It is a mirror, never a
 * second authority: the server re-validates and canonicalizes every save,
 * and the client never "fixes" content that fails here — it refuses it with
 * an honest issue list.
 *
 * Grammar (docs/EDITOR_SPECIFICATION.md block table, P0):
 * `{schema_version:1, type:"doc", content:BlockNode[]}` where every
 * top-level node carries `attrs.block_id:UUID`, headings carry level 1-3,
 * rich text allows paragraph/text with bold/italic/link marks and bullet/
 * ordered lists with depth <= 3, and same-document links (evidence ->
 * hypothesis/insight/chart block, insight/risk -> hypothesis) must resolve
 * inside the same document.
 */

import type { JSONContent } from "@tiptap/core";
import type { components } from "@near-intelligence/shared-types";

export const CANONICAL_SCHEMA_VERSION = 1;
export const MAX_TOP_LEVEL_BLOCKS = 200;
export const MAX_RICH_DEPTH = 3;
export const MAX_DATATABLE_CELLS = 1000;
export const MAX_DATATABLE_COLUMNS = 100;
export const MAX_TEXT_CHARS = 20_000;
export const MAX_BODY_PLAIN_CHARS = 10_000;
export const MAX_STATEMENT_CHARS = 2_000;
export const MAX_EXPLANATION_CHARS = 2_000;
export const MAX_TITLE_CHARS = 200;
export const MAX_LINK_CHARS = 2_000;
export const MAX_CELL_CHARS = 500;
export const MAX_METRIC_VERSIONS = 100;

export const BLOCK_TYPES = [
  "paragraph", "heading", "bullet_list", "ordered_list", "liveChart",
  "dataTable", "insight", "hypothesis", "evidence", "risk", "modelResult", "divider",
] as const;
export type BlockType = (typeof BLOCK_TYPES)[number];

export type InsightType = "observation" | "hypothesis" | "risk" | "conclusion";
export type Classification = "supporting" | "contradicting" | "uncertain";
export type Assessment = "untested" | "supported" | "mixed" | "weakened" | "insufficient_data";
export type EvidenceTargetKind = "insight" | "chart_block" | "model_run" | "citation";
export type ChartMode = "live" | "snapshot";

export const INSIGHT_TYPES: readonly InsightType[] = ["observation", "hypothesis", "risk", "conclusion"];
export const CLASSIFICATIONS: readonly Classification[] = ["supporting", "contradicting", "uncertain"];
export const ASSESSMENTS: readonly Assessment[] = ["untested", "supported", "mixed", "weakened", "insufficient_data"];
export const TARGET_KINDS: readonly EvidenceTargetKind[] = ["insight", "chart_block", "model_run", "citation"];
const CHART_MODES: readonly ChartMode[] = ["live", "snapshot"];
const DATA_TABLE_COLUMN_TYPES = ["string", "number", "date"] as const;
const RICH_LIST_TYPES = ["bullet_list", "ordered_list"] as const;
const INLINE_MARKS = ["bold", "italic", "link"] as const;

// --------------------------------------------------------------------------- //
// Canonical types
// --------------------------------------------------------------------------- //

export interface CanonicalIssue {
  path: string;
  reason: string;
}

export class CanonicalDocumentError extends Error {
  constructor(
    message: string,
    public readonly issues: readonly CanonicalIssue[],
  ) {
    super(message);
    this.name = "CanonicalDocumentError";
  }
}

export interface CanonicalMark {
  type: "bold" | "italic";
}
export interface CanonicalLinkMark {
  type: "link";
  attrs: { href: string };
}
export type CanonicalAnyMark = CanonicalMark | CanonicalLinkMark;

export interface CanonicalText {
  type: "text";
  text: string;
  marks?: CanonicalAnyMark[];
}

export interface CanonicalParagraph {
  type: "paragraph";
  content: CanonicalText[];
}
export interface CanonicalListItem {
  type: "list_item";
  content: RichFragment;
}
export interface CanonicalRichList {
  type: (typeof RICH_LIST_TYPES)[number];
  content: CanonicalListItem[];
}

export type RichFragment = Array<CanonicalParagraph | CanonicalRichList>;

export type CanonicalSelection = components["schemas"]["ChartSelection"];

/** Frozen chart inspection record (API_SPECIFICATION ResolvedContext). */
export interface CanonicalResolvedContext {
  chart_definition_version_id: string;
  dataset_version_id: string;
  selection: CanonicalSelection;
  context_hash: string;
  renderer_version: string;
  metric_definition_versions: string[];
  resolved_at: string;
}

/** Frozen model run record (API_SPECIFICATION ModelContext). */
export interface CanonicalModelContext {
  model_run_id: string;
  dataset_version_id: string;
  specification_version: string;
  context_hash: string;
}

export type CanonicalContext = CanonicalResolvedContext | CanonicalModelContext;

export interface CanonicalTableColumn {
  key: string;
  label: string;
  type: (typeof DATA_TABLE_COLUMN_TYPES)[number];
  unit?: string;
}

export type CanonicalCell = string | number | boolean | null;

interface BlockBase {
  attrs: { block_id: string };
}

export interface CanonicalParagraphBlock extends BlockBase {
  type: "paragraph";
  content: CanonicalText[];
}
export interface CanonicalHeadingBlock extends BlockBase {
  type: "heading";
  attrs: { block_id: string; level: 1 | 2 | 3 };
  content: CanonicalText[];
}
export interface CanonicalListBlock extends BlockBase {
  type: (typeof RICH_LIST_TYPES)[number];
  content: CanonicalListItem[];
}
export interface CanonicalDividerBlock extends BlockBase {
  type: "divider";
}
export interface CanonicalLiveChartBlock extends BlockBase {
  type: "liveChart";
  attrs: {
    block_id: string;
    chart_definition_version_id: string;
    mode: ChartMode;
    selection: CanonicalSelection;
    observed_dataset_version_id: string;
    snapshot_id: string | null;
  };
}
export interface CanonicalDataTableBlock extends BlockBase {
  type: "dataTable";
  attrs: {
    block_id: string;
    columns: CanonicalTableColumn[];
    rows?: CanonicalCell[][];
    dataset_version_id?: string;
  };
}
export interface CanonicalInsightBlock extends BlockBase {
  type: "insight";
  attrs: {
    block_id: string;
    insight_id: string;
    type: InsightType;
    classification: Classification;
    body: RichFragment;
    context: CanonicalContext;
    authored_at: string;
    modified_at: string;
    hypothesis_id?: string;
  };
}
export interface CanonicalHypothesisBlock extends BlockBase {
  type: "hypothesis";
  attrs: {
    block_id: string;
    hypothesis_id: string;
    statement: string;
    assessment: Assessment;
    authored_at: string;
    modified_at: string;
  };
}
export interface CanonicalEvidenceBlock extends BlockBase {
  type: "evidence";
  attrs: {
    block_id: string;
    evidence_id: string;
    hypothesis_id: string;
    classification: Classification;
    target_kind: EvidenceTargetKind;
    target_id: string;
    explanation: string;
  };
}
export interface CanonicalRiskBlock extends BlockBase {
  type: "risk";
  attrs: {
    block_id: string;
    title: string;
    body: RichFragment;
    related_hypothesis_id?: string;
  };
}
/**
 * A pinned published model run with an editable interpretation (NI-055).
 * Only identities and the authored narrative are stored — coefficients and
 * diagnostics never live in the document JSON; the node view re-projects
 * them from the immutable published run row.
 */
export interface CanonicalModelResultBlock extends BlockBase {
  type: "modelResult";
  attrs: {
    block_id: string;
    model_run_id: string;
    dataset_version_id: string;
    interpretation: RichFragment;
  };
}

export type CanonicalBlock =
  | CanonicalParagraphBlock
  | CanonicalHeadingBlock
  | CanonicalListBlock
  | CanonicalDividerBlock
  | CanonicalLiveChartBlock
  | CanonicalDataTableBlock
  | CanonicalInsightBlock
  | CanonicalHypothesisBlock
  | CanonicalEvidenceBlock
  | CanonicalRiskBlock
  | CanonicalModelResultBlock;

export interface CanonicalDocument {
  schema_version: typeof CANONICAL_SCHEMA_VERSION;
  type: "doc";
  content: CanonicalBlock[];
}

// --------------------------------------------------------------------------- //
// Primitives
// --------------------------------------------------------------------------- //

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** ISO-8601 timestamp with an explicit UTC offset (server requires timezone). */
const TIMESTAMP_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|[+-]\d{2}:\d{2})$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

class IssueCollector {
  /**
   * Fail-fast, mirroring the server validator: the first violation raises
   * with its exact path and machine-readable reason, so an issue list always
   * pinpoints the first thing the document got wrong.
   */
  add(path: string, reason: string): never {
    throw new CanonicalDocumentError(`Invalid document at ${path}: ${reason}`, [
      { path, reason },
    ]);
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireObject(value: unknown, path: string, issues: IssueCollector): Record<string, unknown> {
  if (!isPlainObject(value)) {
    issues.add(path, "must_be_object");
  }
  return value;
}

function requireArray(value: unknown, path: string, issues: IssueCollector): unknown[] {
  if (!Array.isArray(value)) {
    issues.add(path, "must_be_array");
  }
  return value;
}

function requireString(
  value: unknown,
  path: string,
  max: number,
  issues: IssueCollector,
): string {
  if (typeof value !== "string") {
    issues.add(path, "must_be_string");
  }
  if (value.length > max) {
    issues.add(path, "too_long");
  }
  return value;
}

function requireNonEmptyString(
  value: unknown,
  path: string,
  max: number,
  issues: IssueCollector,
): string {
  const text = requireString(value, path, max, issues);
  if (!text.trim()) {
    issues.add(path, "must_not_be_empty");
  }
  return text;
}

function requireEnum<T extends string>(
  value: unknown,
  path: string,
  allowed: readonly T[],
  issues: IssueCollector,
): T {
  if (typeof value !== "string" || !(allowed as readonly string[]).includes(value)) {
    issues.add(path, "unsupported_value");
  }
  return value as T;
}

function requireUuid(value: unknown, path: string, issues: IssueCollector): string {
  if (typeof value !== "string") {
    issues.add(path, "must_be_uuid_string");
  }
  if (!UUID_PATTERN.test(value)) {
    issues.add(path, "must_be_uuid");
  }
  return value.toLowerCase();
}

function requireUuidOrNull(
  value: unknown,
  path: string,
  issues: IssueCollector,
): string | null {
  return value === null ? null : requireUuid(value, path, issues);
}

function requireTimestamp(value: unknown, path: string, issues: IssueCollector): string {
  if (typeof value !== "string") {
    issues.add(path, "must_be_timestamp_string");
  }
  if (TIMESTAMP_PATTERN.test(value)) {
    return value;
  }
  // A naive ISO datetime parses server-side but fails the timezone rule.
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?$/.test(value)) {
    issues.add(path, "timestamp_requires_timezone");
  }
  issues.add(path, "must_be_iso_timestamp");
}

function requireUnknownKeysOnly(
  object: Record<string, unknown>,
  allowed: readonly string[],
  path: string,
  issues: IssueCollector,
): void {
  for (const key of Object.keys(object)) {
    if (!allowed.includes(key)) {
      issues.add(`${path}.${key}`, "unknown_field");
    }
  }
}

function requireIsoDate(value: unknown, path: string, issues: IssueCollector): string {
  const text = requireString(value, path, 10, issues);
  if (!ISO_DATE_PATTERN.test(text)) {
    issues.add(path, "must_be_iso_date");
  }
  const [year, month, day] = text.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    Number.isNaN(date.getTime()) ||
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    issues.add(path, "must_be_iso_date");
  }
  return text;
}

function requireSha256(value: unknown, path: string, issues: IssueCollector): string {
  if (typeof value !== "string" || !SHA256_PATTERN.test(value)) {
    issues.add(path, "must_be_sha256_hex");
  }
  return value;
}

// --------------------------------------------------------------------------- //
// Selection and contexts
// --------------------------------------------------------------------------- //

function parseSelection(value: unknown, path: string, issues: IssueCollector): CanonicalSelection {
  const selection = requireObject(value, path, issues);
  requireUnknownKeysOnly(selection, ["start", "end", "frequency", "filters"], path, issues);
  const start = requireIsoDate(selection.start, `${path}.start`, issues);
  const end = requireIsoDate(selection.end, `${path}.end`, issues);
  if (start >= end) {
    issues.add(`${path}.end`, "window_must_be_half_open_nonempty");
  }
  requireEnum(selection.frequency, `${path}.frequency`, ["day"], issues);
  const filters = requireObject(selection.filters, `${path}.filters`, issues);
  if (Object.keys(filters).length > 32) issues.add(`${path}.filters`, "too_many_filters");
  const checked: Array<[string, string]> = [];
  for (const [key, value] of Object.entries(filters)) {
    if (!key || key.length > 80 || typeof value !== "string" || !value || value.length > 200) {
      issues.add(`${path}.filters`, "invalid_filter_shape");
    }
    checked.push([key, value as string]);
  }
  // Values are preserved exactly; the API checks the immutable definition's domain.
  return { start, end, frequency: "day", filters: Object.fromEntries(checked) };
}

function parseContext(value: unknown, path: string, issues: IssueCollector): CanonicalContext {
  const context = requireObject(value, path, issues);
  if ("chart_definition_version_id" in context) {
    requireUnknownKeysOnly(
      context,
      [
        "chart_definition_version_id", "dataset_version_id", "selection",
        "context_hash", "renderer_version", "metric_definition_versions", "resolved_at",
      ],
      path,
      issues,
    );
    const versions = requireArray(context.metric_definition_versions, `${path}.metric_definition_versions`, issues);
    if (versions.length > MAX_METRIC_VERSIONS) {
      issues.add(`${path}.metric_definition_versions`, "too_many_entries");
    }
    return {
      chart_definition_version_id: requireUuid(context.chart_definition_version_id, `${path}.chart_definition_version_id`, issues),
      dataset_version_id: requireUuid(context.dataset_version_id, `${path}.dataset_version_id`, issues),
      selection: parseSelection(context.selection, `${path}.selection`, issues),
      context_hash: requireSha256(context.context_hash, `${path}.context_hash`, issues),
      renderer_version: requireNonEmptyString(context.renderer_version, `${path}.renderer_version`, 80, issues),
      metric_definition_versions: versions.map((entry, index) =>
        requireUuid(entry, `${path}.metric_definition_versions[${index}]`, issues)),
      resolved_at: requireTimestamp(context.resolved_at, `${path}.resolved_at`, issues),
    };
  }
  if ("model_run_id" in context) {
    requireUnknownKeysOnly(
      context,
      ["model_run_id", "dataset_version_id", "specification_version", "context_hash"],
      path,
      issues,
    );
    return {
      model_run_id: requireUuid(context.model_run_id, `${path}.model_run_id`, issues),
      dataset_version_id: requireUuid(context.dataset_version_id, `${path}.dataset_version_id`, issues),
      specification_version: requireNonEmptyString(context.specification_version, `${path}.specification_version`, 80, issues),
      context_hash: requireSha256(context.context_hash, `${path}.context_hash`, issues),
    };
  }
  issues.add(path, "unsupported_context_shape");
}

// --------------------------------------------------------------------------- //
// Rich text
// --------------------------------------------------------------------------- //

function parseLinkTarget(href: string, path: string, issues: IssueCollector): URL {
  let parsed: URL | null = null;
  try {
    parsed = new URL(href);
  } catch {
    parsed = null;
  }
  if (!parsed) {
    issues.add(path, "unsupported_link_target");
  }
  return parsed;
}

function parseMarks(value: unknown, path: string, issues: IssueCollector): CanonicalAnyMark[] {
  if (value === undefined || value === null) {
    return [];
  }
  const marks = requireArray(value, path, issues);
  if (marks.length > INLINE_MARKS.length) {
    issues.add(path, "too_many_marks");
  }
  const seen = new Set<string>();
  return marks.map((mark, index) => {
    const markPath = `${path}[${index}]`;
    const object = requireObject(mark, markPath, issues);
    requireUnknownKeysOnly(object, ["type", "attrs"], markPath, issues);
    const kind = requireEnum(object.type, `${markPath}.type`, INLINE_MARKS, issues);
    if (seen.has(kind)) {
      issues.add(`${markPath}.type`, "duplicate_mark");
    }
    seen.add(kind);
    if (kind === "link") {
      const attrs = requireObject(object.attrs, `${markPath}.attrs`, issues);
      requireUnknownKeysOnly(attrs, ["href"], `${markPath}.attrs`, issues);
      const href = requireString(attrs.href, `${markPath}.attrs.href`, MAX_LINK_CHARS, issues);
      const parsed = parseLinkTarget(href, `${markPath}.attrs.href`, issues);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        issues.add(`${markPath}.attrs.href`, "unsupported_link_target");
      }
      if (parsed.username || parsed.password) {
        issues.add(`${markPath}.attrs.href`, "credentials_in_link");
      }
      return { type: "link", attrs: { href } } satisfies CanonicalLinkMark;
    }
    if ("attrs" in object) {
      issues.add(`${markPath}.attrs`, "mark_has_no_attributes");
    }
    return { type: kind } satisfies CanonicalMark;
  });
}

function parseTextRuns(value: unknown, path: string, issues: IssueCollector): CanonicalText[] {
  const nodes = requireArray(value, path, issues);
  if (nodes.length > 1000) {
    issues.add(path, "too_many_inline_nodes");
  }
  return nodes.map((node, index) => {
    const nodePath = `${path}[${index}]`;
    const object = requireObject(node, nodePath, issues);
    requireUnknownKeysOnly(object, ["type", "text", "marks"], nodePath, issues);
    requireEnum(object.type, `${nodePath}.type`, ["text"], issues);
    const text = requireString(object.text, `${nodePath}.text`, MAX_TEXT_CHARS, issues);
    if (!text) {
      issues.add(`${nodePath}.text`, "must_not_be_empty");
    }
    const marks = parseMarks(object.marks, `${nodePath}.marks`, issues);
    return marks.length > 0 ? { type: "text", text, marks } : { type: "text", text };
  });
}

function parseRichFragment(
  value: unknown,
  path: string,
  depth: number,
  issues: IssueCollector,
): RichFragment {
  const nodes = requireArray(value, path, issues);
  if (nodes.length > MAX_TOP_LEVEL_BLOCKS) {
    issues.add(path, "too_many_rich_nodes");
  }
  const fragment: RichFragment = [];
  for (const [index, node] of nodes.entries()) {
    const nodePath = `${path}[${index}]`;
    const object = requireObject(node, nodePath, issues);
    const kind = object.type;
    if (kind === "paragraph") {
      requireUnknownKeysOnly(object, ["type", "content"], nodePath, issues);
      fragment.push({ type: "paragraph", content: parseTextRuns(object.content, `${nodePath}.content`, issues) });
    } else if (kind === "bullet_list" || kind === "ordered_list") {
      fragment.push(parseRichList(object, nodePath, depth, issues));
    } else {
      issues.add(`${nodePath}.type`, "unsupported_rich_node");
    }
  }
  return fragment;
}

function parseRichList(
  node: Record<string, unknown>,
  path: string,
  depth: number,
  issues: IssueCollector,
): CanonicalRichList {
  if (depth > MAX_RICH_DEPTH) {
    issues.add(path, "nesting_too_deep");
  }
  requireUnknownKeysOnly(node, ["type", "content"], path, issues);
  const kind = requireEnum(node.type, `${path}.type`, RICH_LIST_TYPES, issues);
  const items = requireArray(node.content, `${path}.content`, issues);
  if (items.length === 0) {
    issues.add(`${path}.content`, "list_requires_items");
  }
  const content: CanonicalListItem[] = items.map((item, index) => {
    const itemPath = `${path}.content[${index}]`;
    const object = requireObject(item, itemPath, issues);
    requireUnknownKeysOnly(object, ["type", "content"], itemPath, issues);
    requireEnum(object.type, `${itemPath}.type`, ["list_item"], issues);
    const children = requireArray(object.content, `${itemPath}.content`, issues);
    if (children.length === 0) {
      issues.add(`${itemPath}.content`, "list_item_requires_content");
    }
    let sawParagraph = false;
    const itemContent: RichFragment = children.map((child, childIndex) => {
      const childPath = `${itemPath}.content[${childIndex}]`;
      const childObject = requireObject(child, childPath, issues);
      const childKind = childObject.type;
      if (childKind === "paragraph") {
        sawParagraph = true;
        requireUnknownKeysOnly(childObject, ["type", "content"], childPath, issues);
        return {
          type: "paragraph",
          content: parseTextRuns(childObject.content, `${childPath}.content`, issues),
        };
      }
      if (childKind === "bullet_list" || childKind === "ordered_list") {
        if (!sawParagraph) {
          issues.add(`${childPath}.type`, "nested_list_requires_preceding_paragraph");
        }
        return parseRichList(childObject, childPath, depth + 1, issues);
      }
      issues.add(`${childPath}.type`, "unsupported_rich_node");
    });
    return { type: "list_item", content: itemContent };
  });
  return { type: kind, content };
}

function plainTextLength(fragment: RichFragment): number {
  let total = 0;
  const stack: Array<CanonicalParagraph | CanonicalRichList | CanonicalListItem> = [...fragment];
  while (stack.length > 0) {
    const node = stack.pop();
    if (!node) {
      continue;
    }
    if (node.type === "paragraph") {
      total += node.content.reduce((sum, run) => sum + run.text.length, 0);
    } else if (node.type === "list_item") {
      stack.push(...node.content);
    } else {
      stack.push(...node.content);
    }
  }
  return total;
}

function requireRichBody(value: unknown, path: string, issues: IssueCollector): RichFragment {
  const fragment = parseRichFragment(value, path, 1, issues);
  if (fragment.length === 0) {
    issues.add(path, "must_not_be_empty");
  }
  if (plainTextLength(fragment) > MAX_BODY_PLAIN_CHARS) {
    issues.add(path, "body_too_long");
  }
  return fragment;
}

// --------------------------------------------------------------------------- //
// Top-level blocks
// --------------------------------------------------------------------------- //

type BlockAttrs = Record<string, unknown>;

function parseBlockKeys(
  node: Record<string, unknown>,
  path: string,
  { withContent }: { withContent: boolean },
  issues: IssueCollector,
): void {
  const allowed = withContent ? ["type", "attrs", "content"] : ["type", "attrs"];
  requireUnknownKeysOnly(node, allowed, path, issues);
  if (!withContent && "content" in node) {
    issues.add(`${path}.content`, "block_type_takes_no_content");
  }
}

function parseBlockAttrs(
  node: Record<string, unknown>,
  path: string,
  allowed: readonly string[],
  issues: IssueCollector,
): BlockAttrs {
  const attrs = requireObject(node.attrs, `${path}.attrs`, issues);
  requireUnknownKeysOnly(attrs, allowed, `${path}.attrs`, issues);
  return attrs;
}

function parseParagraphBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalParagraphBlock {
  parseBlockKeys(node, path, { withContent: true }, issues);
  const attrs = parseBlockAttrs(node, path, ["block_id"], issues);
  const blockId = requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues);
  if (node.content === undefined || node.content === null) {
    issues.add(`${path}.content`, "paragraph_requires_content");
  }
  return {
    type: "paragraph",
    attrs: { block_id: blockId },
    content: parseTextRuns(node.content, `${path}.content`, issues),
  };
}

function parseHeadingBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalHeadingBlock {
  parseBlockKeys(node, path, { withContent: true }, issues);
  const attrs = parseBlockAttrs(node, path, ["block_id", "level"], issues);
  const blockId = requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues);
  const level = attrs.level;
  if (typeof level !== "number" || !Number.isInteger(level)) {
    issues.add(`${path}.attrs.level`, "must_be_integer");
  }
  if (level < 1 || level > 3) {
    issues.add(`${path}.attrs.level`, "out_of_range");
  }
  if (node.content === undefined || node.content === null) {
    issues.add(`${path}.content`, "heading_requires_content");
  }
  return {
    type: "heading",
    attrs: { block_id: blockId, level: level as 1 | 2 | 3 },
    content: parseTextRuns(node.content, `${path}.content`, issues),
  };
}

function parseListBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalListBlock {
  parseBlockKeys(node, path, { withContent: true }, issues);
  const attrs = parseBlockAttrs(node, path, ["block_id"], issues);
  const blockId = requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues);
  const kind = requireEnum(node.type, `${path}.type`, RICH_LIST_TYPES, issues);
  const richList = parseRichList(
    { type: kind, content: node.content },
    path,
    1,
    issues,
  );
  return { type: kind, attrs: { block_id: blockId }, content: richList.content };
}

function parseDividerBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalDividerBlock {
  parseBlockKeys(node, path, { withContent: false }, issues);
  const attrs = parseBlockAttrs(node, path, ["block_id"], issues);
  const blockId = requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues);
  return { type: "divider", attrs: { block_id: blockId } };
}

function parseLiveChartBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalLiveChartBlock {
  parseBlockKeys(node, path, { withContent: false }, issues);
  const attrs = parseBlockAttrs(node, path, [
    "block_id", "chart_definition_version_id", "mode", "selection",
    "observed_dataset_version_id", "snapshot_id",
  ], issues);
  const blockId = requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues);
  const mode = requireEnum(attrs.mode, `${path}.attrs.mode`, CHART_MODES, issues);
  const selection = parseSelection(attrs.selection, `${path}.attrs.selection`, issues);
  const snapshotId = requireUuidOrNull(attrs.snapshot_id, `${path}.attrs.snapshot_id`, issues);
  if (mode === "snapshot" && snapshotId === null) {
    issues.add(`${path}.attrs.snapshot_id`, "snapshot_mode_requires_snapshot_id");
  }
  if (mode === "live" && snapshotId !== null) {
    issues.add(`${path}.attrs.snapshot_id`, "live_mode_cannot_carry_snapshot_id");
  }
  return {
    type: "liveChart",
    attrs: {
      block_id: blockId,
      chart_definition_version_id: requireUuid(attrs.chart_definition_version_id, `${path}.attrs.chart_definition_version_id`, issues),
      mode,
      selection,
      observed_dataset_version_id: requireUuid(attrs.observed_dataset_version_id, `${path}.attrs.observed_dataset_version_id`, issues),
      snapshot_id: snapshotId,
    },
  };
}

function parseDataTableBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalDataTableBlock {
  parseBlockKeys(node, path, { withContent: false }, issues);
  const attrs = parseBlockAttrs(node, path, ["block_id", "columns", "rows", "dataset_version_id"], issues);
  const blockId = requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues);
  const columnsValue = requireArray(attrs.columns, `${path}.attrs.columns`, issues);
  if (columnsValue.length === 0) {
    issues.add(`${path}.attrs.columns`, "table_requires_columns");
  }
  if (columnsValue.length > MAX_DATATABLE_COLUMNS) {
    issues.add(`${path}.attrs.columns`, "too_many_columns");
  }
  const columnKeys = new Set<string>();
  const columns: CanonicalTableColumn[] = columnsValue.map((column, index) => {
    const columnPath = `${path}.attrs.columns[${index}]`;
    const object = requireObject(column, columnPath, issues);
    requireUnknownKeysOnly(object, ["key", "label", "type", "unit"], columnPath, issues);
    const key = requireString(object.key, `${columnPath}.key`, 100, issues);
    if (!key.trim() || columnKeys.has(key)) {
      issues.add(`${columnPath}.key`, "duplicate_or_empty_column_key");
    }
    columnKeys.add(key);
    const entry: CanonicalTableColumn = {
      key,
      label: requireNonEmptyString(object.label, `${columnPath}.label`, 200, issues),
      type: requireEnum(object.type, `${columnPath}.type`, DATA_TABLE_COLUMN_TYPES, issues),
    };
    if (object.unit !== undefined && object.unit !== null) {
      entry.unit = requireNonEmptyString(object.unit, `${columnPath}.unit`, 40, issues);
    }
    return entry;
  });
  const hasRows = "rows" in attrs;
  const hasDataset = "dataset_version_id" in attrs;
  if (hasRows === hasDataset) {
    issues.add(`${path}.attrs`, "table_requires_rows_or_dataset_reference_not_both");
  }
  let rows: CanonicalCell[][] | undefined;
  let datasetVersionId: string | undefined;
  if (hasRows) {
    const rowsValue = requireArray(attrs.rows, `${path}.attrs.rows`, issues);
    if (rowsValue.length * columns.length > MAX_DATATABLE_CELLS) {
      issues.add(`${path}.attrs.rows`, "too_many_cells");
    }
    rows = rowsValue.map((row, rowIndex) => {
      const rowPath = `${path}.attrs.rows[${rowIndex}]`;
      const cells = requireArray(row, rowPath, issues);
      if (cells.length !== columns.length) {
        issues.add(rowPath, "row_width_must_match_columns");
      }
      return cells.map((cell, cellIndex) => {
        const cellPath = `${rowPath}[${cellIndex}]`;
        if (cell === null || typeof cell === "boolean") {
          return cell;
        }
        if (typeof cell === "string") {
          if (cell.length > MAX_CELL_CHARS) {
            issues.add(cellPath, "cell_too_long");
          }
          return cell;
        }
        if (typeof cell === "number") {
          if (!Number.isFinite(cell)) {
            issues.add(cellPath, "cell_must_be_finite");
          }
          return cell;
        }
        issues.add(cellPath, "unsupported_cell_type");
      });
    });
  } else {
    datasetVersionId = requireUuid(attrs.dataset_version_id, `${path}.attrs.dataset_version_id`, issues);
  }
  const canonicalAttrs: CanonicalDataTableBlock["attrs"] = { block_id: blockId, columns };
  if (rows !== undefined) {
    canonicalAttrs.rows = rows;
  } else {
    canonicalAttrs.dataset_version_id = datasetVersionId;
  }
  return { type: "dataTable", attrs: canonicalAttrs };
}

function parseInsightBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalInsightBlock {
  parseBlockKeys(node, path, { withContent: false }, issues);
  const attrs = parseBlockAttrs(node, path, [
    "block_id", "insight_id", "type", "classification", "body", "context",
    "authored_at", "modified_at", "hypothesis_id",
  ], issues);
  const blockId = requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues);
  const canonicalAttrs: CanonicalInsightBlock["attrs"] = {
    block_id: blockId,
    insight_id: requireUuid(attrs.insight_id, `${path}.attrs.insight_id`, issues),
    type: requireEnum(attrs.type, `${path}.attrs.type`, INSIGHT_TYPES, issues),
    classification: requireEnum(attrs.classification, `${path}.attrs.classification`, CLASSIFICATIONS, issues),
    body: requireRichBody(attrs.body, `${path}.attrs.body`, issues),
    context: parseContext(attrs.context, `${path}.attrs.context`, issues),
    authored_at: requireTimestamp(attrs.authored_at, `${path}.attrs.authored_at`, issues),
    modified_at: requireTimestamp(attrs.modified_at, `${path}.attrs.modified_at`, issues),
  };
  if (attrs.hypothesis_id !== undefined && attrs.hypothesis_id !== null) {
    canonicalAttrs.hypothesis_id = requireUuid(attrs.hypothesis_id, `${path}.attrs.hypothesis_id`, issues);
  }
  return { type: "insight", attrs: canonicalAttrs };
}

function parseHypothesisBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalHypothesisBlock {
  parseBlockKeys(node, path, { withContent: false }, issues);
  const attrs = parseBlockAttrs(node, path, [
    "block_id", "hypothesis_id", "statement", "assessment", "authored_at", "modified_at",
  ], issues);
  return {
    type: "hypothesis",
    attrs: {
      block_id: requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues),
      hypothesis_id: requireUuid(attrs.hypothesis_id, `${path}.attrs.hypothesis_id`, issues),
      statement: requireNonEmptyString(attrs.statement, `${path}.attrs.statement`, MAX_STATEMENT_CHARS, issues),
      assessment: requireEnum(attrs.assessment, `${path}.attrs.assessment`, ASSESSMENTS, issues),
      authored_at: requireTimestamp(attrs.authored_at, `${path}.attrs.authored_at`, issues),
      modified_at: requireTimestamp(attrs.modified_at, `${path}.attrs.modified_at`, issues),
    },
  };
}

function parseEvidenceBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalEvidenceBlock {
  parseBlockKeys(node, path, { withContent: false }, issues);
  const attrs = parseBlockAttrs(node, path, [
    "block_id", "evidence_id", "hypothesis_id", "classification", "target_kind", "target_id", "explanation",
  ], issues);
  return {
    type: "evidence",
    attrs: {
      block_id: requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues),
      evidence_id: requireUuid(attrs.evidence_id, `${path}.attrs.evidence_id`, issues),
      hypothesis_id: requireUuid(attrs.hypothesis_id, `${path}.attrs.hypothesis_id`, issues),
      classification: requireEnum(attrs.classification, `${path}.attrs.classification`, CLASSIFICATIONS, issues),
      target_kind: requireEnum(attrs.target_kind, `${path}.attrs.target_kind`, TARGET_KINDS, issues),
      target_id: requireUuid(attrs.target_id, `${path}.attrs.target_id`, issues),
      explanation: requireNonEmptyString(attrs.explanation, `${path}.attrs.explanation`, MAX_EXPLANATION_CHARS, issues),
    },
  };
}

function parseRiskBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalRiskBlock {
  parseBlockKeys(node, path, { withContent: false }, issues);
  const attrs = parseBlockAttrs(node, path, ["block_id", "title", "body", "related_hypothesis_id"], issues);
  const canonicalAttrs: CanonicalRiskBlock["attrs"] = {
    block_id: requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues),
    title: requireNonEmptyString(attrs.title, `${path}.attrs.title`, MAX_TITLE_CHARS, issues),
    body: requireRichBody(attrs.body, `${path}.attrs.body`, issues),
  };
  if (attrs.related_hypothesis_id !== undefined && attrs.related_hypothesis_id !== null) {
    canonicalAttrs.related_hypothesis_id = requireUuid(attrs.related_hypothesis_id, `${path}.attrs.related_hypothesis_id`, issues);
  }
  return { type: "risk", attrs: canonicalAttrs };
}

function parseModelResultBlock(node: Record<string, unknown>, path: string, issues: IssueCollector): CanonicalModelResultBlock {
  // NI-055: ids + rich-text interpretation only — every other attr (any
  // statistical value) is an unknown field and rejected, mirroring the
  // server parser so summaries are always re-projected from the run row.
  parseBlockKeys(node, path, { withContent: false }, issues);
  const attrs = parseBlockAttrs(node, path, [
    "block_id", "model_run_id", "dataset_version_id", "interpretation",
  ], issues);
  return {
    type: "modelResult",
    attrs: {
      block_id: requireUuid(attrs.block_id, `${path}.attrs.block_id`, issues),
      model_run_id: requireUuid(attrs.model_run_id, `${path}.attrs.model_run_id`, issues),
      dataset_version_id: requireUuid(attrs.dataset_version_id, `${path}.attrs.dataset_version_id`, issues),
      interpretation: requireRichBody(attrs.interpretation, `${path}.attrs.interpretation`, issues),
    },
  };
}

const BLOCK_PARSERS: Record<string, (node: Record<string, unknown>, path: string, issues: IssueCollector) => CanonicalBlock> = {
  paragraph: parseParagraphBlock,
  heading: parseHeadingBlock,
  bullet_list: parseListBlock,
  ordered_list: parseListBlock,
  liveChart: parseLiveChartBlock,
  dataTable: parseDataTableBlock,
  insight: parseInsightBlock,
  hypothesis: parseHypothesisBlock,
  evidence: parseEvidenceBlock,
  risk: parseRiskBlock,
  modelResult: parseModelResultBlock,
  divider: parseDividerBlock,
};

// --------------------------------------------------------------------------- //
// Document root and same-document links
// --------------------------------------------------------------------------- //

export interface LinkGraph {
  hypothesisIds: Set<string>;
  insightIds: Set<string>;
  chartBlockIds: Set<string>;
  evidenceIds: Set<string>;
  blockIds: Set<string>;
}

/**
 * Entity/link inventory of one validated document. Evidence targets of kind
 * `chart_block` reference the chart's block_id; `insight` targets reference
 * the insight's entity id (EDITOR_SPECIFICATION canonical schema).
 */
export function buildLinkGraph(content: readonly CanonicalBlock[]): LinkGraph {
  const graph: LinkGraph = {
    hypothesisIds: new Set(),
    insightIds: new Set(),
    chartBlockIds: new Set(),
    evidenceIds: new Set(),
    blockIds: new Set(),
  };
  for (const block of content) {
    graph.blockIds.add(block.attrs.block_id);
    if (block.type === "insight") {
      graph.insightIds.add(block.attrs.insight_id);
    } else if (block.type === "hypothesis") {
      graph.hypothesisIds.add(block.attrs.hypothesis_id);
    } else if (block.type === "evidence") {
      graph.evidenceIds.add(block.attrs.evidence_id);
    } else if (block.type === "liveChart") {
      graph.chartBlockIds.add(block.attrs.block_id);
    }
  }
  return graph;
}

function checkSameDocumentLinks(
  content: readonly CanonicalBlock[],
  graph: LinkGraph,
  issues: IssueCollector,
): void {
  // The server reports dangling same-document links with the bare "content"
  // path (the whole link set is checked after parsing), not per attribute.
  for (const block of content) {
    if (block.type === "insight") {
      if (block.attrs.hypothesis_id && !graph.hypothesisIds.has(block.attrs.hypothesis_id)) {
        issues.add("content", "dangling_hypothesis_reference");
      }
    } else if (block.type === "risk") {
      if (block.attrs.related_hypothesis_id && !graph.hypothesisIds.has(block.attrs.related_hypothesis_id)) {
        issues.add("content", "dangling_hypothesis_reference");
      }
    } else if (block.type === "evidence") {
      if (!graph.hypothesisIds.has(block.attrs.hypothesis_id)) {
        issues.add("content", "dangling_hypothesis_reference");
      }
      if (block.attrs.target_kind === "insight" && !graph.insightIds.has(block.attrs.target_id)) {
        issues.add("content", "dangling_insight_reference");
      }
      if (block.attrs.target_kind === "chart_block" && !graph.chartBlockIds.has(block.attrs.target_id)) {
        issues.add("content", "dangling_chart_block_reference");
      }
    }
  }
}

/**
 * Validate one parsed canonical EditorDocument. Throws
 * {@link CanonicalDocumentError} with a bounded issue list on any violation —
 * the editor never renders or mutates content that failed this check.
 */
export function validateCanonicalDocument(value: unknown): CanonicalDocument {
  const issues = new IssueCollector();
  const root = requireObject(value, "document", issues);
  requireUnknownKeysOnly(root, ["schema_version", "type", "content"], "document", issues);
  if (typeof root.schema_version !== "number" || !Number.isInteger(root.schema_version)) {
    issues.add("document.schema_version", "must_be_integer");
  }
  if (root.schema_version !== CANONICAL_SCHEMA_VERSION) {
    issues.add("document.schema_version", "unsupported_schema_version");
  }
  if (root.type !== "doc") {
    issues.add("document.type", "must_be_doc");
  }
  const contentValue = requireArray(root.content, "document.content", issues);
  if (contentValue.length > MAX_TOP_LEVEL_BLOCKS) {
    issues.add("document.content", "too_many_blocks");
  }
  const seenBlockIds = new Set<string>();
  const content: CanonicalBlock[] = contentValue.map((node, index) => {
    const path = `document.content[${index}]`;
    const object = requireObject(node, path, issues);
    const kind = object.type;
    if (typeof kind !== "string" || !(kind in BLOCK_PARSERS)) {
      issues.add(`${path}.type`, "unsupported_block_type");
    }
    const block = BLOCK_PARSERS[kind as string](object, path, issues);
    if (seenBlockIds.has(block.attrs.block_id)) {
      // The server reports the position of the duplicate occurrence.
      issues.add(path, "duplicate_block_id");
    }
    seenBlockIds.add(block.attrs.block_id);
    return block;
  });

  const graph = buildLinkGraph(content);
  if (graph.insightIds.size !== content.filter((b) => b.type === "insight").length) {
    issues.add("content", "duplicate_insight_id");
  }
  if (graph.hypothesisIds.size !== content.filter((b) => b.type === "hypothesis").length) {
    issues.add("content", "duplicate_hypothesis_id");
  }
  if (graph.evidenceIds.size !== content.filter((b) => b.type === "evidence").length) {
    issues.add("content", "duplicate_evidence_id");
  }
  checkSameDocumentLinks(content, graph, issues);

  // Byte ceiling, mirroring the server's canonical serialization size check.
  // The input comes from parsed JSON, so stringify cannot fail here.
  const serialized = JSON.stringify({ schema_version: CANONICAL_SCHEMA_VERSION, type: "doc", content });
  if (new TextEncoder().encode(serialized).length > 2 * 1024 * 1024) {
    issues.add("document", "too_large");
  }

  return { schema_version: CANONICAL_SCHEMA_VERSION, type: "doc", content };
}

// --------------------------------------------------------------------------- //
// Tiptap JSON helpers (shared by the serializer and the operations layer)
// --------------------------------------------------------------------------- //

/** Tiptap node names that map to a different canonical type string. */
const TIPTAP_TO_CANONICAL: Record<string, BlockType> = {
  bulletList: "bullet_list",
  orderedList: "ordered_list",
};

export function canonicalBlockTypeOf(node: JSONContent): BlockType | null {
  const kind = node.type;
  if (!kind) {
    return null;
  }
  if (kind in TIPTAP_TO_CANONICAL) {
    return TIPTAP_TO_CANONICAL[kind];
  }
  return (BLOCK_TYPES as readonly string[]).includes(kind) ? (kind as BlockType) : null;
}
