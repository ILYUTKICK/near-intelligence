"""Canonical editor document JSON validation (NI-036).

The source of the structure is docs/EDITOR_SPECIFICATION.md: an
``EditorDocument`` is ``{schema_version:1, type:"doc", content:BlockNode[]}``
where every top-level block node carries ``attrs.block_id:UUID``. This module
is the single authoritative validator of that JSON: it is pure (no database,
no request objects), strict (unknown node types, unknown attributes, unknown
marks, arbitrary HTML/iframe/executable nodes and remote-image nodes are
rejected because they are not in the P0 node set), bounded (every string,
collection and the whole document have explicit size limits) and
canonicalizing (UUIDs/timestamps/URLs are normalized to one spelling so the
stored revision and its ``content_sha256`` are deterministic).

P0 node taxonomy (EDITOR_SPECIFICATION block table):

- ``paragraph``/``heading``: rich text blocks (text/bold/italic/link marks).
- ``bullet_list``/``ordered_list``: top-level rich text list blocks (Tiptap
  document shape); every top-level node carries ``attrs.block_id`` and list
  nesting obeys depth <= 3. Rich text bodies (insight/risk) reuse the same
  list grammar; their internal paragraph/list children carry no block ids.
- ``liveChart``: chart reference + mode + selection + observed dataset pin.
- ``dataTable``: small authored table (max 1k cells) or a dataset reference.
- ``insight``/``hypothesis``/``evidence``/``risk``: typed research
  annotations (insight types observation|hypothesis|risk|conclusion;
  classifications supporting|contradicting|uncertain; hypothesis assessments
  untested|supported|mixed|weakened|insufficient_data).
- ``modelResult`` (NI-055): pinned published model run + interpretation
  rich text. The block stores ONLY ids and the authored narrative —
  coefficients/diagnostics never live in the document JSON; summaries are
  re-projected from the immutable published ``app.model_runs`` row, so
  editing the prose can never change the recorded result and a source
  revision never refits it.
- ``divider``: semantic separator.

Same-document private links are validated here without the database: every
``evidence.hypothesis_id``/``insight.hypothesis_id``/``risk.related_hypothesis_id``
must resolve to a hypothesis node of the SAME document, and an evidence
``insight``/``chart_block`` target must resolve inside the same document.
Database-backed reference checks (approved dataset pins, public citation
artifacts, registry availability gates) live in the revision service
(:mod:`near_api.documents.service`), which runs them inside the save
transaction so invalid content creates zero rows.

The empty document (``content: []``) is valid.

Validation failures raise :class:`DocumentSchemaError` (422),
:class:`DocumentTooLarge` (413) or :class:`ReferenceInvalid` (422
REFERENCE_INVALID); each carries a bounded list of ``path``/``reason`` details.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

MAX_CONTENT_BYTES = 2 * 1024 * 1024
"""Hard ceiling for the canonical JSON serialization (2 MiB)."""

MAX_TOP_LEVEL_BLOCKS = 200
"""Hard ceiling for top-level block nodes (EDITOR_SPECIFICATION)."""

MAX_RICH_DEPTH = 3
"""Maximum bullet/ordered list nesting depth (EDITOR_SPECIFICATION)."""

MAX_DATATABLE_CELLS = 1000
"""Maximum authored dataTable cells, rows x columns (EDITOR_SPECIFICATION)."""

MAX_DATATABLE_COLUMNS = 100
MAX_DATATABLE_ROW_CELLS = 500
MAX_TEXT_CHARS = 20_000
"""Maximum characters of one text node (the 2 MiB ceiling bounds the rest)."""

MAX_BODY_PLAIN_CHARS = 10_000
"""Maximum plain-text-equivalent characters of a rich text body
(API_SPECIFICATION InsightInput: max 10k plain-text-equivalent characters)."""

MAX_STATEMENT_CHARS = 2_000
MAX_EXPLANATION_CHARS = 2_000
MAX_TITLE_CHARS = 200
MAX_LINK_CHARS = 2_000
MAX_CELL_CHARS = 500
MAX_CONTEXTS = MAX_TOP_LEVEL_BLOCKS

SCHEMA_VERSION = 1
"""The only document schema version this service accepts for saving."""

BLOCK_TYPES = (
    "paragraph", "heading", "liveChart", "dataTable",
    "insight", "hypothesis", "evidence", "risk", "modelResult", "divider",
)
INSIGHT_TYPES = ("observation", "hypothesis", "risk", "conclusion")
CLASSIFICATIONS = ("supporting", "contradicting", "uncertain")
ASSESSMENTS = ("untested", "supported", "mixed", "weakened", "insufficient_data")
TARGET_KINDS = ("insight", "chart_block", "model_run", "citation")
CHART_MODES = ("live", "snapshot")
DATA_TABLE_COLUMN_TYPES = ("string", "number", "date")
RICH_LIST_TYPES = ("bullet_list", "ordered_list")
INLINE_MARKS = ("bold", "italic", "link")


class DocumentSchemaError(ValueError):
    """The document JSON violates the canonical editor schema (HTTP 422)."""

    def __init__(self, message: str, details: list[tuple[str, str]] | None = None):
        super().__init__(message)
        self.details = tuple(details or [( "document", "invalid_value")])
        if len(self.details) > 20:  # bounded, like every error detail list
            self.details = self.details[:20]


class DocumentTooLarge(DocumentSchemaError):
    """The document exceeds a hard size ceiling (HTTP 413)."""


class ReferenceInvalid(DocumentSchemaError):
    """A reference is dangling, cross-owner or targets an unavailable
    registry (HTTP 422 with the API error code REFERENCE_INVALID)."""


# --------------------------------------------------------------------------- #
# Primitive strict readers
# --------------------------------------------------------------------------- #


def _fail(path: str, reason: str):
    raise DocumentSchemaError(f"Invalid document at {path}: {reason}",
                              [(path, reason)])


def _require_object(value, path: str) -> dict:
    if not isinstance(value, dict):
        _fail(path, "must_be_object")
    return value


def _require_list(value, path: str) -> list:
    if not isinstance(value, list):
        _fail(path, "must_be_array")
    return value


def _require_string(value, path: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        _fail(path, "must_be_string")
    if len(value) > max_length:
        _fail(path, "too_long")
    return value


def _require_nonempty_string(value, path: str, *, max_length: int) -> str:
    text = _require_string(value, path, max_length=max_length)
    if not text.strip():
        _fail(path, "must_not_be_empty")
    return text


def _require_uuid(value, path: str) -> UUID:
    if not isinstance(value, str):
        _fail(path, "must_be_uuid_string")
    try:
        return UUID(value)
    except ValueError:
        _fail(path, "must_be_uuid")


def _require_uuid_or_none(value, path: str) -> UUID | None:
    return None if value is None else _require_uuid(value, path)


def _require_timestamp(value, path: str) -> datetime:
    """Parse an ISO-8601 timestamp that carries an explicit UTC offset."""
    if not isinstance(value, str):
        _fail(path, "must_be_timestamp_string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail(path, "must_be_iso_timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(path, "timestamp_requires_timezone")
    return parsed.astimezone(timezone.utc)


def _require_enum(value, path: str, allowed: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in allowed:
        _fail(path, "unsupported_value")
    return value


def _require_int(value, path: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "must_be_integer")
    if not minimum <= value <= maximum:
        _fail(path, "out_of_range")
    return value


def _canonical_timestamp(value: datetime) -> str:
    text = value.astimezone(timezone.utc).isoformat()
    return text.replace("+00:00", "Z")


def _canonical_uuid(value: UUID) -> str:
    return str(value)


def _sha256_of_canonical(canonical: dict) -> str:
    return hashlib.sha256(canonical_bytes(canonical)).hexdigest()


def canonical_bytes(canonical: dict) -> bytes:
    """Deterministic serialization used for hashing and the size ceiling.

    ``allow_nan=False`` additionally rejects NaN/Infinity, which Python's JSON
    decoder would otherwise admit inside authored table cells.
    """
    return json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def empty_document() -> dict:
    """The canonical empty document (a valid document per the specification)."""
    return {"schema_version": SCHEMA_VERSION, "type": "doc", "content": []}


# --------------------------------------------------------------------------- #
# Rich text (inline content of paragraph/heading and of rich text bodies)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TextRun:
    text: str
    marks: tuple[dict, ...]


@dataclass(frozen=True)
class Paragraph:
    runs: tuple[TextRun, ...]


@dataclass(frozen=True)
class RichList:
    ordered: bool
    items: tuple["ListItem", ...]


@dataclass(frozen=True)
class ListItem:
    content: tuple["RichNode", ...]


RichNode = Paragraph | RichList


def _parse_marks(value, path: str) -> tuple[dict, ...]:
    if value is None:
        return ()
    marks = _require_list(value, path)
    if len(marks) > len(INLINE_MARKS):
        _fail(path, "too_many_marks")
    seen: set[str] = set()
    canonical: list[dict] = []
    for index, mark in enumerate(marks):
        mark_path = f"{path}[{index}]"
        mark_object = _require_object(mark, mark_path)
        unknown = set(mark_object) - {"type", "attrs"}
        if unknown:
            _fail(f"{mark_path}.{'/'.join(sorted(unknown))}", "unknown_field")
        kind = _require_enum(mark_object.get("type"), f"{mark_path}.type", INLINE_MARKS)
        if kind in seen:
            _fail(f"{mark_path}.type", "duplicate_mark")
        seen.add(kind)
        if kind == "link":
            attrs = mark_object.get("attrs")
            if not isinstance(attrs, dict):
                _fail(f"{mark_path}.attrs", "must_be_object")
            unknown = set(attrs) - {"href"}
            if unknown:
                _fail(f"{mark_path}.attrs.{'/'.join(sorted(unknown))}", "unknown_field")
            href = _require_string(attrs.get("href"), f"{mark_path}.attrs.href",
                                   max_length=MAX_LINK_CHARS)
            parts = urlsplit(href)
            if parts.scheme not in ("http", "https") or not parts.netloc:
                _fail(f"{mark_path}.attrs.href", "unsupported_link_target")
            if parts.username or parts.password or "@" in parts.netloc:
                _fail(f"{mark_path}.attrs.href", "credentials_in_link")
            canonical.append({"type": "link", "attrs": {"href": href}})
        else:
            if "attrs" in mark_object:
                _fail(f"{mark_path}.attrs", "mark_has_no_attributes")
            canonical.append({"type": kind})
    return tuple(canonical)


def _parse_text_node(node: dict, path: str) -> TextRun:
    unknown = set(node) - {"type", "text", "marks"}
    if unknown:
        _fail(f"{path}.{'/'.join(sorted(unknown))}", "unknown_field")
    text = _require_string(node.get("text"), f"{path}.text", max_length=MAX_TEXT_CHARS)
    if not text:
        _fail(f"{path}.text", "must_not_be_empty")
    marks = _parse_marks(node.get("marks"), f"{path}.marks")
    return TextRun(text=text, marks=marks)


def _parse_inline_content(value, path: str) -> tuple[TextRun, ...]:
    nodes = _require_list(value, path)
    if len(nodes) > 1000:
        _fail(path, "too_many_inline_nodes")
    return tuple(_parse_text_node(_require_object(node, f"{path}[{index}]"),
                                  f"{path}[{index}]")
                 for index, node in enumerate(nodes))


def _parse_list_items(children: list, path: str, depth: int) -> tuple[ListItem, ...]:
    if not children:
        _fail(f"{path}.content", "list_requires_items")
    return tuple(_parse_list_item(_require_object(child, f"{path}.content[{index}]"),
                                  f"{path}.content[{index}]", depth)
                 for index, child in enumerate(children))


def _parse_list_node(node: dict, path: str, depth: int) -> RichList:
    """A rich text body list: no attrs, keyed by type and content only."""
    if depth > MAX_RICH_DEPTH:
        _fail(path, "nesting_too_deep")
    unknown = set(node) - {"type", "content", "attrs"}
    if unknown:
        _fail(f"{path}.{'/'.join(sorted(unknown))}", "unknown_field")
    if "attrs" in node:
        _fail(f"{path}.attrs", "list_has_no_attributes")
    kind = _require_enum(node.get("type"), f"{path}.type", RICH_LIST_TYPES)
    return RichList(ordered=kind == "ordered_list",
                    items=_parse_list_items(
                        _require_list(node.get("content"), f"{path}.content"),
                        path, depth))


def _parse_list_item(node: dict, path: str, depth: int) -> ListItem:
    unknown = set(node) - {"type", "content"}
    if unknown:
        _fail(f"{path}.{'/'.join(sorted(unknown))}", "unknown_field")
    kind = _require_enum(node.get("type"), f"{path}.type", ("list_item",))
    children = _require_list(node.get("content"), f"{path}.content")
    if not children:
        _fail(f"{path}.content", "list_item_requires_content")
    content: list[RichNode] = []
    saw_paragraph = False
    for index, child in enumerate(children):
        child_path = f"{path}.content[{index}]"
        child_object = _require_object(child, child_path)
        child_type = child_object.get("type")
        if child_type == "paragraph":
            saw_paragraph = True
            content.append(_parse_paragraph_node(child_object, child_path))
        elif child_type in RICH_LIST_TYPES:
            if not saw_paragraph:
                _fail(f"{child_path}.type", "nested_list_requires_preceding_paragraph")
            content.append(_parse_list_node(child_object, child_path, depth + 1))
        else:
            _fail(f"{child_path}.type", "unsupported_rich_node")
    return ListItem(content=tuple(content))


def _parse_paragraph_node(node: dict, path: str) -> Paragraph:
    unknown = set(node) - {"type", "content"}
    if unknown:
        _fail(f"{path}.{'/'.join(sorted(unknown))}", "unknown_field")
    kind = _require_enum(node.get("type"), f"{path}.type", ("paragraph",))
    del kind
    return Paragraph(runs=_parse_inline_content(node.get("content"), f"{path}.content"))


def _parse_rich_fragment(value, path: str) -> tuple[RichNode, ...]:
    """A rich text body: paragraphs and (nested) lists, no block IDs required."""
    nodes = _require_list(value, path)
    if len(nodes) > MAX_TOP_LEVEL_BLOCKS:
        _fail(path, "too_many_rich_nodes")
    content: list[RichNode] = []
    for index, node in enumerate(nodes):
        node_path = f"{path}[{index}]"
        node_object = _require_object(node, node_path)
        kind = node_object.get("type")
        if kind == "paragraph":
            content.append(_parse_paragraph_node(node_object, node_path))
        elif kind in RICH_LIST_TYPES:
            content.append(_parse_list_node(node_object, node_path, depth=1))
        else:
            _fail(f"{node_path}.type", "unsupported_rich_node")
    return tuple(content)


def _plain_text_length(fragment: tuple[RichNode, ...]) -> int:
    total = 0
    stack: list[RichNode | ListItem] = list(fragment)
    while stack:
        node = stack.pop()
        if isinstance(node, Paragraph):
            total += sum(len(run.text) for run in node.runs)
        elif isinstance(node, RichList):
            stack.extend(node.items)
        elif isinstance(node, ListItem):
            stack.extend(node.content)
    return total


def _rich_to_json(fragment: tuple[RichNode, ...]) -> list[dict]:
    output: list[dict] = []
    for node in fragment:
        if isinstance(node, Paragraph):
            output.append({"type": "paragraph", "content": [
                {"type": "text", "text": run.text, "marks": [dict(mark) for mark in run.marks]}
                for run in node.runs]})
        elif isinstance(node, RichList):
            output.append(_list_to_json(node))
    return output


def _list_to_json(node: RichList) -> dict:
    return {"type": "ordered_list" if node.ordered else "bullet_list", "content": [
        {"type": "list_item", "content": [
            _list_to_json(child) if isinstance(child, RichList)
            else {"type": "paragraph", "content": [
                {"type": "text", "text": run.text, "marks": [dict(mark) for mark in run.marks]}
                for run in child.runs]}
            for child in item.content]}
        for item in node.items]}


def _require_rich_body(value, path: str) -> tuple[RichNode, ...]:
    fragment = _parse_rich_fragment(value, path)
    if not fragment:
        _fail(path, "must_not_be_empty")
    if _plain_text_length(fragment) > MAX_BODY_PLAIN_CHARS:
        _fail(path, "body_too_long")
    return fragment


def canonical_rich_body_json(value: object, *, path: str = "body") -> list[dict]:
    """Validate one bounded, sanitized rich text body; return its canonical JSON.

    NI-046 reuse point for the structured annotation contracts
    (:mod:`near_api.insights.schemas`): the grammar (paragraph/list nodes with
    bold/italic/link marks), the sanitization whitelist (no arbitrary HTML,
    unsupported marks, non-http(s) or credential-bearing link targets) and the
    bounds (nesting depth, node counts, :data:`MAX_BODY_PLAIN_CHARS`) stay
    defined HERE once — this wrapper only exposes them so a contract module can
    validate annotation bodies without re-implementing any rule. Raises
    :class:`DocumentSchemaError` on every violation.
    """
    return _rich_to_json(_require_rich_body(value, path))


# --------------------------------------------------------------------------- #
# Contexts (frozen inspection records: ResolvedContext | ModelContext)
# --------------------------------------------------------------------------- #


def _parse_selection(value, path: str) -> dict:
    """Structural selection validation; filter rules are NI-031 registry scope."""
    selection = _require_object(value, path)
    unknown = set(selection) - {"start", "end", "frequency", "filters"}
    if unknown:
        _fail(f"{path}.{'/'.join(sorted(unknown))}", "unknown_field")
    start = _require_string(selection.get("start"), f"{path}.start", max_length=10)
    end = _require_string(selection.get("end"), f"{path}.end", max_length=10)
    for name, text in (("start", start), ("end", end)):
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            _fail(f"{path}.{name}", "must_be_iso_date")
    if start >= end:
        _fail(f"{path}.end", "window_must_be_half_open_nonempty")
    if _require_enum(selection.get("frequency"), f"{path}.frequency", ("day",)) != "day":
        _fail(f"{path}.frequency", "unsupported_value")
    filters = _require_object(selection.get("filters"), f"{path}.filters")
    from pydantic import ValidationError
    from near_api.schemas.chart_selection import ChartSelection
    try:
        return ChartSelection.model_validate(selection).model_dump(mode="json")
    except ValidationError:
        _fail(path, "invalid_selection")


def _require_sha256(value, path: str) -> str:
    digest = _require_string(value, path, max_length=64)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        _fail(path, "must_be_sha256_hex")
    return digest


def _parse_context(value, path: str) -> dict:
    """Validate one frozen context object (ResolvedContext or ModelContext)."""
    context = _require_object(value, path)
    if "chart_definition_version_id" in context:
        unknown = set(context) - {
            "chart_definition_version_id", "dataset_version_id", "selection",
            "context_hash", "renderer_version", "metric_definition_versions", "resolved_at",
        }
        if unknown:
            _fail(f"{path}.{'/'.join(sorted(unknown))}", "unknown_field")
        resolved_at = _require_timestamp(context.get("resolved_at"), f"{path}.resolved_at")
        versions = _require_list(context.get("metric_definition_versions"),
                                 f"{path}.metric_definition_versions")
        if len(versions) > 100:
            _fail(f"{path}.metric_definition_versions", "too_many_entries")
        return {
            "chart_definition_version_id": _canonical_uuid(
                _require_uuid(context.get("chart_definition_version_id"),
                              f"{path}.chart_definition_version_id")),
            "dataset_version_id": _canonical_uuid(
                _require_uuid(context.get("dataset_version_id"),
                              f"{path}.dataset_version_id")),
            "selection": _parse_selection(context.get("selection"), f"{path}.selection"),
            "context_hash": _require_sha256(context.get("context_hash"),
                                            f"{path}.context_hash"),
            "renderer_version": _require_nonempty_string(
                context.get("renderer_version"), f"{path}.renderer_version", max_length=80),
            "metric_definition_versions": [
                _canonical_uuid(_require_uuid(item, f"{path}.metric_definition_versions[{index}]"))
                for index, item in enumerate(versions)],
            "resolved_at": _canonical_timestamp(resolved_at),
        }
    if "model_run_id" in context:
        unknown = set(context) - {
            "model_run_id", "dataset_version_id", "specification_version", "context_hash",
        }
        if unknown:
            _fail(f"{path}.{'/'.join(sorted(unknown))}", "unknown_field")
        return {
            "model_run_id": _canonical_uuid(_require_uuid(
                context.get("model_run_id"), f"{path}.model_run_id")),
            "dataset_version_id": _canonical_uuid(_require_uuid(
                context.get("dataset_version_id"), f"{path}.dataset_version_id")),
            "specification_version": _require_nonempty_string(
                context.get("specification_version"),
                f"{path}.specification_version", max_length=80),
            "context_hash": _require_sha256(context.get("context_hash"),
                                            f"{path}.context_hash"),
        }
    _fail(path, "unsupported_context_shape")


def canonical_context_json(value: object, *, path: str = "context") -> dict:
    """Validate one frozen inspection record; return its canonical JSON.

    NI-041 reuse point for the chart-block insertion service
    (:mod:`near_api.documents.chart_blocks`): the ``ResolvedContext`` /
    ``ModelContext`` field sets, UUID/timestamp/hash spellings and the
    selection structure stay defined HERE once — a context-producing module
    validates through this wrapper instead of re-implementing any rule, so a
    stored context always matches the shape the canonical editor grammar and
    the per-revision map expect. Raises :class:`DocumentSchemaError` on every
    violation.
    """
    return _parse_context(value, path)


# --------------------------------------------------------------------------- #
# Top-level P0 blocks
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Block:
    """A validated top-level block node."""

    block_id: UUID
    block_type: str
    attrs: dict


@dataclass(frozen=True)
class InsightNode:
    block_id: UUID
    insight_id: UUID
    insight_type: str
    classification: str
    body: tuple[RichNode, ...]
    context: dict
    authored_at: datetime
    modified_at: datetime
    hypothesis_id: UUID | None
    body_json: list[dict]


@dataclass(frozen=True)
class HypothesisNode:
    block_id: UUID
    hypothesis_id: UUID
    statement: str
    assessment: str
    authored_at: datetime
    modified_at: datetime


@dataclass(frozen=True)
class EvidenceNode:
    block_id: UUID
    evidence_id: UUID
    hypothesis_id: UUID
    classification: str
    target_kind: str
    target_id: UUID
    explanation: str


@dataclass(frozen=True)
class RiskNode:
    block_id: UUID
    related_hypothesis_id: UUID | None


@dataclass(frozen=True)
class LiveChartNode:
    block_id: UUID
    chart_definition_version_id: UUID
    mode: str
    selection: dict
    observed_dataset_version_id: UUID
    snapshot_id: UUID | None


@dataclass(frozen=True)
class DataTableNode:
    block_id: UUID
    columns: tuple[dict, ...]
    rows: tuple[tuple[object, ...], ...] | None
    dataset_version_id: UUID | None
    columns_json: list[dict]
    rows_json: list[list[object]] | None


@dataclass(frozen=True)
class ModelResultNode:
    """A pinned published model run with an editable interpretation.

    Only identities and the authored narrative are stored: ``model_run_id``
    must reference a published immutable ``app.model_runs`` row (verified in
    the save transaction), ``dataset_version_id`` the approved public dataset
    the interpretation reads against, and ``interpretation`` is rich text in
    the canonical annotation grammar. No coefficient or diagnostic value is
    ever stored here.
    """

    block_id: UUID
    model_run_id: UUID
    dataset_version_id: UUID
    interpretation: tuple[RichNode, ...]
    interpretation_json: list[dict]


def _parse_block_node_keys(node: dict, path: str, *, with_content: bool) -> None:
    """Top-level node keys are exactly {type, attrs} (+ content for text blocks)."""
    allowed = {"type", "attrs"} | ({"content"} if with_content else set())
    unknown = set(node) - allowed
    if unknown:
        _fail(f"{path}.{'/'.join(sorted(unknown))}", "unknown_field")
    if not with_content and "content" in node:
        _fail(f"{path}.content", "block_type_takes_no_content")


def _parse_block_attrs(node: dict, path: str, allowed: tuple[str, ...]) -> dict:
    attrs = node.get("attrs")
    attrs = _require_object(attrs, f"{path}.attrs")
    unknown = set(attrs) - set(allowed)
    if unknown:
        _fail(f"{path}.attrs.{'/'.join(sorted(unknown))}", "unknown_field")
    return attrs


def _parse_paragraph_block(node: dict, path: str) -> tuple[Block, Paragraph]:
    _parse_block_node_keys(node, path, with_content=True)
    attrs = _parse_block_attrs(node, path, ("block_id",))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    content = node.get("content")
    if content is None:
        _fail(f"{path}.content", "paragraph_requires_content")
    paragraph = Paragraph(runs=_parse_inline_content(content, f"{path}.content"))
    canonical_attrs = {"block_id": _canonical_uuid(block_id)}
    return Block(block_id, "paragraph", canonical_attrs), paragraph


def _parse_heading_block(node: dict, path: str) -> tuple[Block, tuple[TextRun, ...]]:
    _parse_block_node_keys(node, path, with_content=True)
    attrs = _parse_block_attrs(node, path, ("block_id", "level"))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    level = _require_int(attrs.get("level"), f"{path}.attrs.level", minimum=1, maximum=3)
    content = node.get("content")
    if content is None:
        _fail(f"{path}.content", "heading_requires_content")
    runs = _parse_inline_content(content, f"{path}.content")
    canonical_attrs = {"block_id": _canonical_uuid(block_id), "level": level}
    return Block(block_id, "heading", canonical_attrs), runs


def _parse_list_block(node: dict, path: str) -> tuple[Block, RichList]:
    """A top-level list block: Tiptap-shape content with a required block_id."""
    _parse_block_node_keys(node, path, with_content=True)
    attrs = _parse_block_attrs(node, path, ("block_id",))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    kind = _require_enum(node.get("type"), f"{path}.type", RICH_LIST_TYPES)
    rich_list = RichList(
        ordered=kind == "ordered_list",
        items=_parse_list_items(
            _require_list(node.get("content"), f"{path}.content"), path, depth=1))
    return (Block(block_id, kind, {"block_id": _canonical_uuid(block_id)}), rich_list)


def _parse_divider_block(node: dict, path: str) -> tuple[Block]:
    _parse_block_node_keys(node, path, with_content=False)
    attrs = _parse_block_attrs(node, path, ("block_id",))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    return (Block(block_id, "divider", {"block_id": _canonical_uuid(block_id)}),)


def _parse_live_chart_block(node: dict, path: str) -> tuple[Block, LiveChartNode]:
    _parse_block_node_keys(node, path, with_content=False)
    attrs = _parse_block_attrs(node, path, (
        "block_id", "chart_definition_version_id", "mode", "selection",
        "observed_dataset_version_id", "snapshot_id",
    ))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    chart_definition_version_id = _require_uuid(
        attrs.get("chart_definition_version_id"),
        f"{path}.attrs.chart_definition_version_id")
    mode = _require_enum(attrs.get("mode"), f"{path}.attrs.mode", CHART_MODES)
    selection = _parse_selection(attrs.get("selection"), f"{path}.attrs.selection")
    observed = _require_uuid(attrs.get("observed_dataset_version_id"),
                             f"{path}.attrs.observed_dataset_version_id")
    snapshot_id = _require_uuid_or_none(attrs.get("snapshot_id"),
                                        f"{path}.attrs.snapshot_id")
    if mode == "snapshot" and snapshot_id is None:
        _fail(f"{path}.attrs.snapshot_id", "snapshot_mode_requires_snapshot_id")
    if mode == "live" and snapshot_id is not None:
        _fail(f"{path}.attrs.snapshot_id", "live_mode_cannot_carry_snapshot_id")
    canonical_attrs = {
        "block_id": _canonical_uuid(block_id),
        "chart_definition_version_id": _canonical_uuid(chart_definition_version_id),
        "mode": mode,
        "selection": selection,
        "observed_dataset_version_id": _canonical_uuid(observed),
        "snapshot_id": None if snapshot_id is None else _canonical_uuid(snapshot_id),
    }
    node_data = LiveChartNode(
        block_id=block_id, chart_definition_version_id=chart_definition_version_id,
        mode=mode, selection=selection, observed_dataset_version_id=observed,
        snapshot_id=snapshot_id)
    return Block(block_id, "liveChart", canonical_attrs), node_data


def _parse_data_table_block(node: dict, path: str) -> tuple[Block, DataTableNode]:
    _parse_block_node_keys(node, path, with_content=False)
    attrs = _parse_block_attrs(node, path, (
        "block_id", "columns", "rows", "dataset_version_id",
    ))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    columns_value = _require_list(attrs.get("columns"), f"{path}.attrs.columns")
    if not columns_value:
        _fail(f"{path}.attrs.columns", "table_requires_columns")
    if len(columns_value) > MAX_DATATABLE_COLUMNS:
        _fail(f"{path}.attrs.columns", "too_many_columns")
    columns: list[dict] = []
    column_keys: set[str] = set()
    for index, column in enumerate(columns_value):
        column_path = f"{path}.attrs.columns[{index}]"
        column_object = _require_object(column, column_path)
        unknown = set(column_object) - {"key", "label", "type", "unit"}
        if unknown:
            _fail(f"{column_path}.{'/'.join(sorted(unknown))}", "unknown_field")
        key = _require_string(column_object.get("key"), f"{column_path}.key", max_length=100)
        if not key.strip() or key in column_keys:
            _fail(f"{column_path}.key", "duplicate_or_empty_column_key")
        column_keys.add(key)
        label = _require_nonempty_string(column_object.get("label"),
                                         f"{column_path}.label", max_length=200)
        kind = _require_enum(column_object.get("type"), f"{column_path}.type",
                             DATA_TABLE_COLUMN_TYPES)
        unit = None
        if column_object.get("unit") is not None:
            unit = _require_nonempty_string(column_object.get("unit"),
                                            f"{column_path}.unit", max_length=40)
        entry = {"key": key, "label": label, "type": kind}
        if unit is not None:
            entry["unit"] = unit
        columns.append(entry)
    has_rows = "rows" in attrs
    has_dataset = "dataset_version_id" in attrs
    if has_rows == has_dataset:
        _fail(f"{path}.attrs", "table_requires_rows_or_dataset_reference_not_both")
    rows_json: list[list[object]] | None = None
    rows: tuple[tuple[object, ...], ...] | None = None
    dataset_version_id: UUID | None = None
    if has_rows:
        rows_value = _require_list(attrs.get("rows"), f"{path}.attrs.rows")
        if len(rows_value) * len(columns) > MAX_DATATABLE_CELLS:
            _fail(f"{path}.attrs.rows", "too_many_cells")
        canonical_rows: list[list[object]] = []
        parsed_rows: list[tuple[object, ...]] = []
        for row_index, row in enumerate(rows_value):
            row_path = f"{path}.attrs.rows[{row_index}]"
            row_cells = _require_list(row, row_path)
            if len(row_cells) != len(columns):
                _fail(row_path, "row_width_must_match_columns")
            canonical_cells: list[object] = []
            for cell_index, cell in enumerate(row_cells):
                cell_path = f"{row_path}[{cell_index}]"
                if cell is None or isinstance(cell, bool):
                    canonical_cells.append(cell)
                elif isinstance(cell, str):
                    if len(cell) > MAX_CELL_CHARS:
                        _fail(cell_path, "cell_too_long")
                    canonical_cells.append(cell)
                elif isinstance(cell, int):
                    canonical_cells.append(cell)
                elif isinstance(cell, float):
                    if cell != cell or cell in (float("inf"), float("-inf")):
                        _fail(cell_path, "cell_must_be_finite")
                    canonical_cells.append(cell)
                else:
                    _fail(cell_path, "unsupported_cell_type")
            canonical_rows.append(canonical_cells)
            parsed_rows.append(tuple(canonical_cells))
        rows = tuple(parsed_rows)
        rows_json = canonical_rows
    else:
        dataset_version_id = _require_uuid(attrs.get("dataset_version_id"),
                                           f"{path}.attrs.dataset_version_id")
    canonical_attrs: dict = {
        "block_id": _canonical_uuid(block_id), "columns": columns,
    }
    if rows_json is not None:
        canonical_attrs["rows"] = rows_json
    else:
        canonical_attrs["dataset_version_id"] = _canonical_uuid(dataset_version_id)
    node_data = DataTableNode(block_id=block_id, columns=tuple(columns), rows=rows,
                              dataset_version_id=dataset_version_id,
                              columns_json=columns, rows_json=rows_json)
    return Block(block_id, "dataTable", canonical_attrs), node_data


def _parse_insight_block(node: dict, path: str) -> tuple[Block, InsightNode]:
    _parse_block_node_keys(node, path, with_content=False)
    attrs = _parse_block_attrs(node, path, (
        "block_id", "insight_id", "type", "classification", "body", "context",
        "authored_at", "modified_at", "hypothesis_id",
    ))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    insight_id = _require_uuid(attrs.get("insight_id"), f"{path}.attrs.insight_id")
    insight_type = _require_enum(attrs.get("type"), f"{path}.attrs.type", INSIGHT_TYPES)
    classification = _require_enum(attrs.get("classification"),
                                   f"{path}.attrs.classification", CLASSIFICATIONS)
    body = _require_rich_body(attrs.get("body"), f"{path}.attrs.body")
    context = _parse_context(attrs.get("context"), f"{path}.attrs.context")
    authored_at = _require_timestamp(attrs.get("authored_at"), f"{path}.attrs.authored_at")
    modified_at = _require_timestamp(attrs.get("modified_at"), f"{path}.attrs.modified_at")
    hypothesis_id = _require_uuid_or_none(attrs.get("hypothesis_id"),
                                          f"{path}.attrs.hypothesis_id")
    canonical_attrs = {
        "block_id": _canonical_uuid(block_id),
        "insight_id": _canonical_uuid(insight_id),
        "type": insight_type,
        "classification": classification,
        "body": _rich_to_json(body),
        "context": context,
        "authored_at": _canonical_timestamp(authored_at),
        "modified_at": _canonical_timestamp(modified_at),
    }
    if hypothesis_id is not None:
        canonical_attrs["hypothesis_id"] = _canonical_uuid(hypothesis_id)
    node_data = InsightNode(block_id=block_id, insight_id=insight_id,
                            insight_type=insight_type, classification=classification,
                            body=body, context=context, authored_at=authored_at,
                            modified_at=modified_at, hypothesis_id=hypothesis_id,
                            body_json=canonical_attrs["body"])
    return Block(block_id, "insight", canonical_attrs), node_data


def _parse_model_result_block(node: dict, path: str) -> tuple[Block, ModelResultNode]:
    """NI-055: published-run pin + editable interpretation, never coefficients.

    The authoritative attr set (EDITOR_SPECIFICATION ``modelResult`` row) is
    exactly ``block_id``, ``model_run_id``, ``dataset_version_id`` and the
    rich-text ``interpretation``. Any statistical value inside the node JSON
    is an unknown field and rejected — summaries are re-projected from the
    immutable published run row, never stored in the document.
    """
    _parse_block_node_keys(node, path, with_content=False)
    attrs = _parse_block_attrs(node, path, (
        "block_id", "model_run_id", "dataset_version_id", "interpretation",
    ))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    model_run_id = _require_uuid(attrs.get("model_run_id"),
                                 f"{path}.attrs.model_run_id")
    dataset_version_id = _require_uuid(attrs.get("dataset_version_id"),
                                       f"{path}.attrs.dataset_version_id")
    interpretation = _require_rich_body(attrs.get("interpretation"),
                                        f"{path}.attrs.interpretation")
    canonical_attrs = {
        "block_id": _canonical_uuid(block_id),
        "model_run_id": _canonical_uuid(model_run_id),
        "dataset_version_id": _canonical_uuid(dataset_version_id),
        "interpretation": _rich_to_json(interpretation),
    }
    node_data = ModelResultNode(
        block_id=block_id, model_run_id=model_run_id,
        dataset_version_id=dataset_version_id, interpretation=interpretation,
        interpretation_json=canonical_attrs["interpretation"])
    return Block(block_id, "modelResult", canonical_attrs), node_data


def _parse_hypothesis_block(node: dict, path: str) -> tuple[Block, HypothesisNode]:
    _parse_block_node_keys(node, path, with_content=False)
    attrs = _parse_block_attrs(node, path, (
        "block_id", "hypothesis_id", "statement", "assessment",
        "authored_at", "modified_at",
    ))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    hypothesis_id = _require_uuid(attrs.get("hypothesis_id"),
                                  f"{path}.attrs.hypothesis_id")
    statement = _require_nonempty_string(attrs.get("statement"),
                                         f"{path}.attrs.statement",
                                         max_length=MAX_STATEMENT_CHARS)
    assessment = _require_enum(attrs.get("assessment"), f"{path}.attrs.assessment",
                               ASSESSMENTS)
    authored_at = _require_timestamp(attrs.get("authored_at"), f"{path}.attrs.authored_at")
    modified_at = _require_timestamp(attrs.get("modified_at"), f"{path}.attrs.modified_at")
    canonical_attrs = {
        "block_id": _canonical_uuid(block_id),
        "hypothesis_id": _canonical_uuid(hypothesis_id),
        "statement": statement,
        "assessment": assessment,
        "authored_at": _canonical_timestamp(authored_at),
        "modified_at": _canonical_timestamp(modified_at),
    }
    node_data = HypothesisNode(block_id=block_id, hypothesis_id=hypothesis_id,
                               statement=statement, assessment=assessment,
                               authored_at=authored_at, modified_at=modified_at)
    return Block(block_id, "hypothesis", canonical_attrs), node_data


def _parse_evidence_block(node: dict, path: str) -> tuple[Block, EvidenceNode]:
    _parse_block_node_keys(node, path, with_content=False)
    attrs = _parse_block_attrs(node, path, (
        "block_id", "evidence_id", "hypothesis_id", "classification",
        "target_kind", "target_id", "explanation",
    ))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    evidence_id = _require_uuid(attrs.get("evidence_id"), f"{path}.attrs.evidence_id")
    hypothesis_id = _require_uuid(attrs.get("hypothesis_id"),
                                  f"{path}.attrs.hypothesis_id")
    classification = _require_enum(attrs.get("classification"),
                                   f"{path}.attrs.classification", CLASSIFICATIONS)
    target_kind = _require_enum(attrs.get("target_kind"), f"{path}.attrs.target_kind",
                                TARGET_KINDS)
    target_id = _require_uuid(attrs.get("target_id"), f"{path}.attrs.target_id")
    explanation = _require_nonempty_string(attrs.get("explanation"),
                                           f"{path}.attrs.explanation",
                                           max_length=MAX_EXPLANATION_CHARS)
    canonical_attrs = {
        "block_id": _canonical_uuid(block_id),
        "evidence_id": _canonical_uuid(evidence_id),
        "hypothesis_id": _canonical_uuid(hypothesis_id),
        "classification": classification,
        "target_kind": target_kind,
        "target_id": _canonical_uuid(target_id),
        "explanation": explanation,
    }
    node_data = EvidenceNode(block_id=block_id, evidence_id=evidence_id,
                             hypothesis_id=hypothesis_id, classification=classification,
                             target_kind=target_kind, target_id=target_id,
                             explanation=explanation)
    return Block(block_id, "evidence", canonical_attrs), node_data


def _parse_risk_block(node: dict, path: str) -> tuple[Block, RiskNode]:
    _parse_block_node_keys(node, path, with_content=False)
    attrs = _parse_block_attrs(node, path, (
        "block_id", "title", "body", "related_hypothesis_id",
    ))
    block_id = _require_uuid(attrs.get("block_id"), f"{path}.attrs.block_id")
    title = _require_nonempty_string(attrs.get("title"), f"{path}.attrs.title",
                                     max_length=MAX_TITLE_CHARS)
    body = _require_rich_body(attrs.get("body"), f"{path}.attrs.body")
    related = _require_uuid_or_none(attrs.get("related_hypothesis_id"),
                                    f"{path}.attrs.related_hypothesis_id")
    canonical_attrs: dict = {
        "block_id": _canonical_uuid(block_id), "title": title,
        "body": _rich_to_json(body),
    }
    if related is not None:
        canonical_attrs["related_hypothesis_id"] = _canonical_uuid(related)
    return (Block(block_id, "risk", canonical_attrs),
            RiskNode(block_id=block_id, related_hypothesis_id=related))


_BLOCK_PARSERS = {
    "paragraph": _parse_paragraph_block,
    "heading": _parse_heading_block,
    "bullet_list": _parse_list_block,
    "ordered_list": _parse_list_block,
    "liveChart": _parse_live_chart_block,
    "dataTable": _parse_data_table_block,
    "insight": _parse_insight_block,
    "hypothesis": _parse_hypothesis_block,
    "evidence": _parse_evidence_block,
    "risk": _parse_risk_block,
    "modelResult": _parse_model_result_block,
    "divider": _parse_divider_block,
}


# --------------------------------------------------------------------------- #
# Document root
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CanonicalDocument:
    """A validated canonical document and its derived identification."""

    canonical: dict
    content_sha256: str
    blocks: tuple[Block, ...]
    insights: tuple[InsightNode, ...]
    hypotheses: tuple[HypothesisNode, ...]
    evidence: tuple[EvidenceNode, ...]
    risks: tuple[RiskNode, ...]
    live_charts: tuple[LiveChartNode, ...]
    data_tables: tuple[DataTableNode, ...]
    model_results: tuple[ModelResultNode, ...] = ()

    @property
    def block_ids(self) -> set[UUID]:
        return {block.block_id for block in self.blocks}


def _check_same_document_links(document: CanonicalDocument) -> None:
    hypothesis_ids = {item.hypothesis_id for item in document.hypotheses}
    insight_ids = {item.insight_id for item in document.insights}
    chart_block_ids = {chart.block_id for chart in document.live_charts}
    # Entity identifiers are unique per document: their projections are keyed
    # by (revision, entity id), so a duplicate would silently merge two nodes.
    if len(insight_ids) != len(document.insights):
        raise DocumentSchemaError("Duplicate insight_id in the document",
                                  [("content", "duplicate_insight_id")])
    if len(hypothesis_ids) != len(document.hypotheses):
        raise DocumentSchemaError("Duplicate hypothesis_id in the document",
                                  [("content", "duplicate_hypothesis_id")])
    evidence_ids = {item.evidence_id for item in document.evidence}
    if len(evidence_ids) != len(document.evidence):
        raise DocumentSchemaError("Duplicate evidence_id in the document",
                                  [("content", "duplicate_evidence_id")])
    for item in document.insights:
        if item.hypothesis_id is not None and item.hypothesis_id not in hypothesis_ids:
            raise ReferenceInvalid(
                "Insight links a hypothesis that does not exist in the same document",
                [("content", "dangling_hypothesis_reference")])
    for risk in document.risks:
        if risk.related_hypothesis_id is not None and risk.related_hypothesis_id not in hypothesis_ids:
            raise ReferenceInvalid(
                "Risk links a hypothesis that does not exist in the same document",
                [("content", "dangling_hypothesis_reference")])
    for item in document.evidence:
        if item.hypothesis_id not in hypothesis_ids:
            raise ReferenceInvalid(
                "Evidence links a hypothesis that does not exist in the same document",
                [("content", "dangling_hypothesis_reference")])
        if item.target_kind == "insight" and item.target_id not in insight_ids:
            raise ReferenceInvalid(
                "Evidence targets an insight that does not exist in the same document",
                [("content", "dangling_insight_reference")])
        if item.target_kind == "chart_block" and item.target_id not in chart_block_ids:
            raise ReferenceInvalid(
                "Evidence targets a chart block that does not exist in the same document",
                [("content", "dangling_chart_block_reference")])


def parse_document(document: dict, *, max_bytes: int = MAX_CONTENT_BYTES) -> CanonicalDocument:
    """Validate one canonical EditorDocument; return its canonical form.

    The input is the parsed JSON object of the editor document (including
    ``schema_version``). Any violation raises before any database write
    happens; the revision service calls this inside its transaction so an
    invalid save leaves zero rows.
    """
    root = _require_object(document, "document")
    unknown = set(root) - {"schema_version", "type", "content"}
    if unknown:
        _fail(f"document.{'/'.join(sorted(unknown))}", "unknown_field")
    version = _require_int(root.get("schema_version"), "document.schema_version",
                           minimum=0, maximum=2**31 - 1)
    if version != SCHEMA_VERSION:
        raise DocumentSchemaError(
            f"Unsupported document schema version {version}; this service saves "
            f"version {SCHEMA_VERSION} only",
            [("document.schema_version", "unsupported_schema_version")])
    if root.get("type") != "doc":
        _fail("document.type", "must_be_doc")
    content = _require_list(root.get("content"), "document.content")
    if len(content) > MAX_TOP_LEVEL_BLOCKS:
        raise DocumentTooLarge(
            f"Document exceeds the maximum of {MAX_TOP_LEVEL_BLOCKS} top-level blocks",
            [("document.content", "too_many_blocks")])

    blocks: list[Block] = []
    insights: list[InsightNode] = []
    hypotheses: list[HypothesisNode] = []
    evidence: list[EvidenceNode] = []
    risks: list[RiskNode] = []
    live_charts: list[LiveChartNode] = []
    data_tables: list[DataTableNode] = []
    model_results: list[ModelResultNode] = []
    seen_block_ids: set[UUID] = set()
    canonical_blocks: list[dict] = []
    for index, node in enumerate(content):
        path = f"document.content[{index}]"
        node_object = _require_object(node, path)
        node_type = node_object.get("type")
        if node_type not in _BLOCK_PARSERS:
            _fail(f"{path}.type", "unsupported_block_type")
        block, *payload = _BLOCK_PARSERS[node_type](node_object, path)
        if block.block_id in seen_block_ids:
            raise DocumentSchemaError(
                f"Duplicate block_id {block.block_id} at position {index}",
                [(path, "duplicate_block_id")])
        seen_block_ids.add(block.block_id)
        blocks.append(block)
        canonical_blocks.append({"type": block.block_type, "attrs": dict(block.attrs)})
        if node_type == "paragraph":
            paragraph = payload[0]
            canonical_blocks[-1]["content"] = _inline_to_json(paragraph.runs)
        elif node_type == "heading":
            runs = payload[0]
            canonical_blocks[-1]["content"] = _inline_to_json(runs)
        elif node_type in RICH_LIST_TYPES:
            canonical_blocks[-1]["content"] = _list_to_json(payload[0])["content"]
        elif node_type == "liveChart":
            live_charts.append(payload[0])
        elif node_type == "dataTable":
            data_tables.append(payload[0])
        elif node_type == "modelResult":
            model_results.append(payload[0])
        elif node_type == "insight":
            insights.append(payload[0])
        elif node_type == "hypothesis":
            hypotheses.append(payload[0])
        elif node_type == "evidence":
            evidence.append(payload[0])
        elif node_type == "risk":
            risks.append(payload[0])

    canonical = {"schema_version": SCHEMA_VERSION, "type": "doc",
                 "content": canonical_blocks}
    document_bytes = canonical_bytes(canonical)
    if len(document_bytes) > max_bytes:
        raise DocumentTooLarge(
            f"Document exceeds the {max_bytes} byte canonical size limit",
            [("document", "too_large")])
    result = CanonicalDocument(
        canonical=canonical, content_sha256=_sha256_of_canonical(canonical),
        blocks=tuple(blocks), insights=tuple(insights), hypotheses=tuple(hypotheses),
        evidence=tuple(evidence), risks=tuple(risks), live_charts=tuple(live_charts),
        data_tables=tuple(data_tables), model_results=tuple(model_results))
    _check_same_document_links(result)
    return result


def _inline_to_json(runs: tuple[TextRun, ...]) -> list[dict]:
    return [{"type": "text", "text": run.text,
             "marks": [dict(mark) for mark in run.marks]}
            for run in runs]
