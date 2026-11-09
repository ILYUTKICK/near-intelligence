"""Typed insight, evidence, hypothesis and risk contracts (NI-046).

The structured research annotations of EDITOR_SPECIFICATION (insight,
hypothesis, evidence, risk blocks) are shared by three consumers: the editor
document JSON, the REST layer and the per-revision relational projections.
This module is the single Pydantic contract surface for all of them; the
values, shapes and limits it declares are pinned to two authoritative sources
instead of re-implemented:

- the node taxonomy and rich-text grammar live in
  :mod:`near_api.documents.schema` (NI-036 canonical EditorDocument
  validator — one authoritative schema). The Literal unions below are built
  from that module's tuples and every rich text body is validated by calling
  :func:`near_api.documents.schema.canonical_rich_body_json`, so the
  sanitization whitelist and bounds are never duplicated;
- the field sets live in API_SPECIFICATION.md (``InsightInput``/``Insight``,
  ``HypothesisInput``/``Hypothesis``, ``EvidenceInput``/``Evidence``,
  ``ResolvedContext``/``ModelContext``). Convenience REST routes arrive with
  NI-047/NI-048/NI-049 and must reuse these models; in the meantime the models
  are published in the OpenAPI ``components`` (``INSIGHT_CONTRACT_MODELS``
  registered by :mod:`near_api.contracts`) so the generated TypeScript client
  already carries the validation types.

Fixed rules enforced here (TASKS.md NI-046 acceptance):

- **Author timestamps are server-side.** Input contracts carry no timestamp
  fields; ``extra="forbid"`` turns a client-supplied ``authored_at``/
  ``modified_at`` (or any unknown field) into a typed 422. The response
  contracts carry ``authored_at``/``modified_at`` as server-authored
  ``ServerTimestamp`` fields normalized to UTC. (The canonical editor node
  persists these values verbatim across revisions — the server authored them
  when the annotation was created through the convenience API, and the whole-
  document save path preserves immutable history byte-for-byte.)
- **No trusted client owner field.** No model declares ``owner_id``/
  ``user_id``; ownership is derived from the verified principal exactly like
  :func:`near_api.db.security.verified_owner_id` (NI-019), and a payload that
  tries to declare one is rejected as an unknown field.
- **Rich text is bounded and sanitized.** Annotation bodies reuse the
  canonical editor rich-text grammar: paragraph/bullet/ordered list nodes with
  bold/italic/link marks only, list nesting depth <= 3, per-node text bounds,
  http(s) link targets without embedded credentials, and at most
  ``MAX_BODY_PLAIN_CHARS`` plain-text-equivalent characters (the API_SPECIFICATION
  InsightInput 10k limit). Everything else raises a typed validation error.
- **Contexts are frozen inspection records.** ``ResolvedContext`` (chart) and
  ``ModelContext`` (model run) carry the selected range (``selection.start``/
  ``selection.end``), the filters as passed, the immutable pinned dataset
  version (``dataset_version_id`` UUID) and the stable identifier set
  (chart definition version, metric definition versions, ``context_hash``)
  exactly as API_SPECIFICATION defines them.
- **Stable IDs are opaque allocated UUIDs.** ``block_id`` (and the optional
  ``hypothesis_id`` link) may be supplied by the client for a new node per
  API_SPECIFICATION; entity ids (``Insight.id``/``Hypothesis.id``/``Evidence.id``)
  are server responses only. Ids are allocated once (uuid4 semantics) and then
  persist unchanged across revisions — they are intentionally NOT derived from
  content (uuid5), because edited statement/body text must keep the same id so
  evidence links and outline anchors stay valid (NI-048). Uniqueness inside a
  document is enforced by the canonical validator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BeforeValidator,
    Field,
    StringConstraints,
    field_validator,
)

from near_api.documents.schema import (
    ASSESSMENTS,
    CLASSIFICATIONS,
    INSIGHT_TYPES,
    MAX_EXPLANATION_CHARS,
    MAX_LINK_CHARS,
    MAX_STATEMENT_CHARS,
    MAX_TEXT_CHARS,
    MAX_TITLE_CHARS,
    TARGET_KINDS,
    canonical_rich_body_json,
)
from near_api.schemas.common import ContractModel
from near_api.schemas.chart_selection import ChartSelection

# --------------------------------------------------------------------------- #
# Taxonomy (single source: the canonical node taxonomy of documents.schema)
# --------------------------------------------------------------------------- #

InsightType = Literal[INSIGHT_TYPES]
"""observation | hypothesis | risk | conclusion (EDITOR_SPECIFICATION insight node)."""

EvidenceClassification = Literal[CLASSIFICATIONS]
"""supporting | contradicting | uncertain (EDITOR_SPECIFICATION; never a causal claim)."""

HypothesisAssessment = Literal[ASSESSMENTS]
"""Authored assessment states (API_SPECIFICATION HypothesisInput) — manual, never
an automated support score derived from missing metrics."""

EvidenceTargetKind = Literal[TARGET_KINDS]
"""insight | chart_block | model_run | citation (DATABASE_SCHEMA evidence_links)."""

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
"""Lowercase SHA-256 context hash (DATABASE_SCHEMA global conventions)."""


def _no_epoch_number(value: object) -> object:
    """Timestamps arrive as ISO 8601 strings with an explicit timezone — the
    canonical editor schema's own rule — never as epoch numbers (the same
    fail-closed rule as :class:`near_api.schemas.common.Observation`)."""
    if not isinstance(value, (str, datetime)):
        raise ValueError("use an ISO 8601 timestamp with an explicit timezone")
    return value


def _to_utc(value: datetime) -> datetime:
    """Server timestamps are stored/serialized in UTC (API protocol: ISO 8601 UTC)."""
    return value.astimezone(UTC)


ServerTimestamp = Annotated[AwareDatetime, BeforeValidator(_no_epoch_number),
                            AfterValidator(_to_utc)]
"""Server-authored annotation timestamp (response side only; never client input)."""


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must_not_be_blank")
    return value


BoundedStatement = Annotated[str, StringConstraints(
    min_length=1, max_length=MAX_STATEMENT_CHARS), AfterValidator(_not_blank)]
BoundedExplanation = Annotated[str, StringConstraints(
    min_length=1, max_length=MAX_EXPLANATION_CHARS), AfterValidator(_not_blank)]
BoundedTitle = Annotated[str, StringConstraints(
    min_length=1, max_length=MAX_TITLE_CHARS), AfterValidator(_not_blank)]


# --------------------------------------------------------------------------- #
# Frozen inspection contexts (ResolvedContext | ModelContext)
# --------------------------------------------------------------------------- #


class ResolvedContext(ContractModel):
    """Frozen chart inspection record (API_SPECIFICATION ``ResolvedContext``).

    Contains the selected range (``selection.start``/``selection.end`` with the
    half-open UTC window rules of :class:`near_api.schemas.common.Selection`),
    the bounded registered filter dimensions as passed (the referenced chart
    definition controls the exact allowed values), the immutable pinned dataset version and the stable
    version identifiers whose ``context_hash`` binds them together. Server
    resolution/verification of every id happens where the context is created;
    this contract keeps a stored context from drifting afterwards.
    """

    chart_definition_version_id: UUID
    dataset_version_id: UUID
    selection: ChartSelection
    context_hash: Sha256Hex
    renderer_version: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    metric_definition_versions: tuple[UUID, ...] = Field(max_length=100)
    resolved_at: ServerTimestamp


class ModelContext(ContractModel):
    """Frozen model-run inspection record (API_SPECIFICATION ``ModelContext``)."""

    model_run_id: UUID
    dataset_version_id: UUID
    specification_version: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    context_hash: Sha256Hex


InsightContext = ResolvedContext | ModelContext
"""One frozen inspection record. The shapes are disjoint (``ResolvedContext``
requires ``chart_definition_version_id``, ``ModelContext`` requires
``model_run_id``; both forbid unknown fields), so the union is unambiguous and
any other shape — including one carrying both keys — is a typed validation
error."""


# --------------------------------------------------------------------------- #
# Rich text: typed projection of the canonical editor grammar
# --------------------------------------------------------------------------- #


class RichTextLinkAttrs(ContractModel):
    """Canonical link mark attributes. Scheme/credential rules for the target
    are enforced by the canonical rich text parser, which validates every body
    before these shapes are constructed."""

    href: Annotated[str, StringConstraints(min_length=1, max_length=MAX_LINK_CHARS)]


class RichTextBoldMark(ContractModel):
    type: Literal["bold"]


class RichTextItalicMark(ContractModel):
    type: Literal["italic"]


class RichTextLinkMark(ContractModel):
    type: Literal["link"]
    attrs: RichTextLinkAttrs


RichTextMark = Annotated[
    RichTextBoldMark | RichTextItalicMark | RichTextLinkMark,
    Field(discriminator="type"),
]


class RichTextRun(ContractModel):
    """One text node with its (bounded, deduplicated) inline marks."""

    type: Literal["text"]
    text: Annotated[str, StringConstraints(min_length=1, max_length=MAX_TEXT_CHARS)]
    marks: tuple[RichTextMark, ...] = Field(default=(), max_length=3)


class RichTextParagraph(ContractModel):
    type: Literal["paragraph"]
    content: tuple[RichTextRun, ...]


RichTextChild = Annotated["RichTextParagraph | RichTextList", Field(discriminator="type")]


class RichTextListItem(ContractModel):
    """One list item. The canonical parser enforces the ordering rule (a nested
    list must follow a paragraph) and the depth <= 3 bound before these shapes
    are constructed."""

    type: Literal["list_item"]
    content: Annotated[tuple[RichTextChild, ...], Field(min_length=1)]


class RichTextList(ContractModel):
    type: Literal["bullet_list", "ordered_list"]
    content: Annotated[tuple[RichTextListItem, ...], Field(min_length=1)]


RichTextBody = Annotated[
    tuple[Annotated[RichTextParagraph | RichTextList, Field(discriminator="type")], ...],
    Field(min_length=1),
]
"""Bounded, sanitized annotation body (API_SPECIFICATION ``body:RichText``).

Validated by the canonical editor grammar through
:func:`near_api.documents.schema.canonical_rich_body_json` — the Pydantic
shapes above are the typed projection of what that validator emits, so the TS
client gets precise node unions while the whitelist stays defined once.
"""


def _validate_canonical_body(value: object) -> list[dict]:
    return canonical_rich_body_json(value, path="body")


# --------------------------------------------------------------------------- #
# Input contracts (client -> server; extra="forbid" everywhere)
# --------------------------------------------------------------------------- #


class InsightInput(ContractModel):
    """POST /documents/{id}/insights body (API_SPECIFICATION ``InsightInput``).

    The insight TYPE carries the research role (observation/hypothesis/risk/
    conclusion); ``classification`` records how the observation relates to the
    linked hypothesis (supporting/contradicting/uncertain — a classification,
    never an inferred causal claim). ``body`` is bounded/sanitized rich text
    (max 10k plain-text-equivalent characters); ``context`` is the frozen
    inspection record the insight must stay tied to after live refresh.
    ``authored_at``/``modified_at`` do not exist here by construction: the
    server authors them.
    """

    block_id: UUID
    type: InsightType
    classification: EvidenceClassification
    body: RichTextBody
    context: InsightContext
    hypothesis_id: UUID | None = None

    @field_validator("body", mode="before")
    @classmethod
    def _canonical_body(cls, value: object) -> list[dict]:
        return _validate_canonical_body(value)


class HypothesisInput(ContractModel):
    """POST /documents/{id}/hypotheses body (API_SPECIFICATION ``HypothesisInput``).

    ``assessment`` is an authored state with rationale in the document, never
    an automatic truth badge; unsupported values are rejected.
    """

    block_id: UUID
    statement: BoundedStatement
    assessment: HypothesisAssessment


class EvidenceInput(ContractModel):
    """POST /documents/{id}/evidence body (API_SPECIFICATION ``EvidenceInput``).

    ``target_kind``/``target_id`` must resolve to an allowed typed target in
    the same revision or to a public immutable artifact; that visibility/
    reference validation is service scope (NI-049) — this contract rejects the
    shapes it can reject (unknown kinds, non-UUID ids, unbounded explanation).
    """

    block_id: UUID
    hypothesis_id: UUID
    classification: EvidenceClassification
    target_kind: EvidenceTargetKind
    target_id: UUID
    explanation: BoundedExplanation


class RiskInput(ContractModel):
    """Canonical risk node contract (EDITOR_SPECIFICATION ``risk`` row).

    An explicit counterargument card: ``title`` + bounded rich text ``body``
    with an optional same-document hypothesis link. There is deliberately no
    algorithmic probability score field. No convenience REST route is
    specified for risk blocks; risk nodes are edited through the document
    revision flow (NI-039/NI-040), so this contract serves the editor, the
    projections and the export path.
    """

    block_id: UUID
    title: BoundedTitle
    body: RichTextBody
    related_hypothesis_id: UUID | None = None

    @field_validator("body", mode="before")
    @classmethod
    def _canonical_body(cls, value: object) -> list[dict]:
        return _validate_canonical_body(value)


# --------------------------------------------------------------------------- #
# Response contracts (server -> client; ids and timestamps server-authored)
# --------------------------------------------------------------------------- #


class Insight(InsightInput):
    """API_SPECIFICATION ``Insight``: InsightInput plus server-authored fields.

    ``id`` is the stable entity id allocated once at creation (uuid4) and kept
    unchanged across revisions so outline anchors and evidence references stay
    valid; ``document_id`` comes from the verified parent; the timestamps are
    authored by the server (``PATCH`` preserves the original ``authored_at``).
    """

    id: UUID
    document_id: UUID
    authored_at: ServerTimestamp
    modified_at: ServerTimestamp


class Hypothesis(HypothesisInput):
    """API_SPECIFICATION ``Hypothesis``: HypothesisInput plus server fields."""

    id: UUID
    document_id: UUID
    authored_at: ServerTimestamp
    modified_at: ServerTimestamp


class Evidence(EvidenceInput):
    """API_SPECIFICATION ``Evidence``: EvidenceInput plus server fields.

    ``authored_at``/``modified_at`` are response metadata authored by the
    server; the canonical evidence node itself stays timestamp-free per
    EDITOR_SPECIFICATION (timestamps live on the revision that carries it).
    """

    id: UUID
    document_id: UUID
    authored_at: ServerTimestamp
    modified_at: ServerTimestamp


RichTextListItem.model_rebuild()


INSIGHT_CONTRACT_MODELS = (
    ResolvedContext, ModelContext,
    RichTextLinkAttrs, RichTextBoldMark, RichTextItalicMark, RichTextLinkMark,
    RichTextRun, RichTextParagraph, RichTextListItem, RichTextList,
    InsightInput, HypothesisInput,
    EvidenceInput, Evidence, RiskInput,
)
"""Contracts published in the OpenAPI ``components`` (NI-004 mechanism) so the
generated TypeScript client carries the validation types before the convenience
routes of NI-047/NI-048/NI-049 exist. Nested models are listed explicitly so
the published surface is deliberate, not incidental."""
