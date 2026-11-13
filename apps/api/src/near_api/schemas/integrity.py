"""NI-065 advisory integrity and grounded-commentary contracts.

The integrity report is a deterministic, read-only analysis of ONE immutable
revision row. Every finding carries an advisory vocabulary severity — never a
truth score — plus the exact references (block/entity ids, context hash,
dataset/definition ids) an author needs to act. Findings never carry numeric
results: a check supplies counts and identifiers only, and an interpretive
commentary is a separate, optional, explicitly configured adapter response
whose numbers may only echo the provided context.

Published in the OpenAPI ``components`` (``INTEGRITY_CONTRACT_MODELS``
registered by :mod:`near_api.contracts`) so the generated TypeScript client
carries the validation types.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from near_api.documents.schema import MAX_TOP_LEVEL_BLOCKS
from near_api.schemas.common import ContractModel

FindingCheckId = Literal[
    "invalid_revision_content",
    "missing_chart_context",
    "invalid_chart_context",
    "missing_model_context",
    "invalid_model_context",
    "model_run_unavailable",
    "stale_chart_context",
    "chart_definition_unavailable",
    "dataset_pin_unavailable",
    "evidence_target_unavailable",
    "insight_context_unavailable",
    "uncited_pinned_chart",
    "uncited_pinned_dataset_table",
]
"""The bounded vocabulary of deterministic checks (ADR-022).

``warning`` severities signal stored evidence that looks inconsistent
(corruption signal: inspect before editing); ``advisory`` severities describe
states with an available explicit action. Neither implies any truth score."""

FindingSeverity = Literal["advisory", "warning"]

JumpTarget = Literal["block", "none"]
"""Where an editor finding can navigate: a top-level block of the checked
revision, or nowhere (document-level corruption signal)."""

BoundedMessage = Annotated[str, StringConstraints(min_length=1, max_length=500)]

MAX_FINDINGS = MAX_TOP_LEVEL_BLOCKS * 4 + 1
"""A chart can report context corruption, unavailable dataset, unavailable
chart definition and missing citation (four findings). Models have at most
three; tables at most two; other blocks at most one. Add one document-level
warning for a malformed context map. Never truncate corruption findings."""

Sha256Hex = Annotated[str, StringConstraints(min_length=64, max_length=64,
                                              pattern=r"^[0-9a-f]{64}$")]


class IntegrityFinding(ContractModel):
    """One deterministic advisory finding with exact references."""

    check_id: FindingCheckId
    severity: FindingSeverity
    message: BoundedMessage
    block_id: UUID | None = None
    entity_id: UUID | None = None
    context_hash: Sha256Hex | None = None
    dataset_version_id: UUID | None = None
    chart_definition_version_id: UUID | None = None
    latest_dataset_version_id: UUID | None = None
    target_kind: Literal["insight", "chart_block", "model_run", "citation"] | None = None
    jump: JumpTarget


class IntegrityCheckCount(ContractModel):
    """Summary count of one check id present in the report."""

    check_id: FindingCheckId
    count: int = Field(strict=True, ge=1)


class IntegrityReport(ContractModel):
    """The deterministic integrity report of one revision.

    Deterministic content only: no wall-clock field, because a rerun is a new
    GET over the same immutable row and must produce the same report. A
    historical (non-acknowledged) check carries ``is_acknowledged:false`` and
    stays read-only advisory — it is never refused.
    """

    document_id: UUID
    version_id: UUID | None
    revision: int = Field(strict=True, ge=1)
    is_acknowledged: bool
    findings: tuple[IntegrityFinding, ...] = Field(max_length=MAX_FINDINGS)
    counts: tuple[IntegrityCheckCount, ...]


# --------------------------------------------------------------------------- #
# Optional grounded commentary (opt-in adapter, server configuration only)
# --------------------------------------------------------------------------- #

MAX_COMMENTARY_BLOCKS = 10
"""Maximum explicitly selected blocks per commentary request."""

MAX_COMMENTARY_QUESTION_CHARS = 2_000
MAX_COMMENTARY_TEXT_CHARS = 4_000
"""Bound of one advisory commentary item returned by the adapter."""

COMMENTARY_NOTICE = (
    "Advisory commentary generated over the explicitly selected context only. "
    "It is interpretation, never a data source: verify every statement against "
    "the referenced blocks, and treat quoted numbers as read-backs of the "
    "pinned context, not as new results."
)
"""Server-authored notice carried verbatim on every commentary response; the
provider cannot influence or remove it."""

CommentaryState = Literal["ok", "unavailable", "failed"]

CommentaryReason = Literal[
    "adapter_disabled",
    "adapter_misconfigured",
    "no_acknowledged_revision",
    "unknown_block_reference",
    "unresolved_block_context",
    "context_too_large",
    "provider_http_status",
    "provider_unreachable",
    "response_too_large",
    "unsupported_provider_response",
    "ungrounded_commentary",
]
"""Typed availability/failure reasons. ``adapter_disabled`` is the honest
unavailable state — never a fabricated successful commentary."""


class GroundedCommentaryRequest(ContractModel):
    """The explicitly selected context for one grounded commentary request.

    Only block ids of the acknowledged revision may be selected; everything
    else the prompt contains is authored by the server. No provider, model or
    endpoint field exists on the request — external transmission happens only
    through server configuration.
    """

    block_ids: tuple[UUID, ...] = Field(min_length=1, max_length=MAX_COMMENTARY_BLOCKS)
    question: Annotated[str, StringConstraints(
        min_length=1, max_length=MAX_COMMENTARY_QUESTION_CHARS)]


class GroundedCommentaryItem(ContractModel):
    """One advisory commentary item bound to its selected source block."""

    block_id: UUID
    context_hash: Sha256Hex | None
    text: Annotated[str, StringConstraints(
        min_length=1, max_length=MAX_COMMENTARY_TEXT_CHARS)]


class GroundedCommentaryResponse(ContractModel):
    """Advisory commentary over the selected context — or the typed absence.

    ``advisory`` is contractually ``true``: this endpoint never returns a
    result the client could mistake for a data source. When the adapter is
    disabled or fails, ``state`` names it and ``items`` is empty; a fake
    successful commentary is impossible by construction.
    """

    document_id: UUID
    version_id: UUID | None
    revision: int | None
    state: CommentaryState
    reason: CommentaryReason | None = None
    message: Annotated[str, StringConstraints(max_length=500)] | None = None
    advisory: Literal[True]
    notice: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    items: tuple[GroundedCommentaryItem, ...] = Field(
        max_length=MAX_COMMENTARY_BLOCKS)

    @model_validator(mode="after")
    def states_are_honest(self):
        """A fake successful commentary is impossible by construction."""
        if self.state == "ok":
            if not self.items or self.reason is not None:
                raise ValueError("A successful commentary carries items and no failure reason")
        elif self.items:
            raise ValueError("Only a successful commentary carries items")
        if self.state == "unavailable" and self.reason != "adapter_disabled":
            raise ValueError("The unavailable state names the disabled adapter")
        if self.state == "failed" and (self.reason is None or self.reason == "adapter_disabled"):
            raise ValueError("A failed commentary names its typed failure reason")
        return self


INTEGRITY_CONTRACT_MODELS = (
    IntegrityFinding,
    IntegrityCheckCount,
    IntegrityReport,
    GroundedCommentaryRequest,
    GroundedCommentaryItem,
    GroundedCommentaryResponse,
)
