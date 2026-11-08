"""NI-041 chart-block insertion HTTP contracts.

Pinned to the API_SPECIFICATION "Research documents and versions" row
``POST /documents/{id}/chart-blocks``: the request carries the INSPECTED
chart context (definition version, selection, mode, pinned dataset version,
optional same-owner snapshot and insertion anchor) and the response is the
spec's ``MutationResult<{block_id}>`` — the moved document summary plus the
server-allocated block id. The client never supplies a ``block_id`` or any
owner field: the block identity and the pinned ``ResolvedContext`` are
resolved server-side (documents/chart_blocks.py), so one confirmation is one
valid block with one frozen evidence context.

The selection reuses the bounded ChartSelection contract. Source/recipient/
price-basis dimensions come from the registered charts; actual options are
validated against the referenced immutable definition before persistence.
The same shape is used in editor JSON and frozen inspection contexts.
"""

from typing import Literal
from uuid import UUID

from pydantic import model_validator

from near_api.schemas.common import ContractModel
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.home import DocumentSummary


class ChartBlockInsertRequest(ContractModel):
    """POST /documents/{id}/chart-blocks body (If-Match carries the CAS).

    ``dataset_version_id`` is the INSPECTED dataset version from the
    explorer/library/detail view: the server pins exactly that version and
    rejects the request when it is not an approved public dataset — it never
    substitutes latest (API_SPECIFICATION: "Server accepts the inspected
    dataset version to prevent data changing between preview and insertion").
    ``after_block_id`` positions the new block after an existing top-level
    block of the document; without it the block is appended last.
    """

    chart_definition_version_id: UUID
    selection: ChartSelection
    mode: Literal["live", "snapshot"]
    dataset_version_id: UUID
    snapshot_id: UUID | None = None
    after_block_id: UUID | None = None

    @model_validator(mode="after")
    def snapshot_mode_consistency(self):
        """Mirror the canonical liveChart rule (documents/schema): snapshot
        mode carries the inspected snapshot id, live mode never does."""
        if self.mode == "snapshot" and self.snapshot_id is None:
            raise ValueError("snapshot mode requires the inspected snapshot_id")
        if self.mode == "live" and self.snapshot_id is not None:
            raise ValueError("live mode cannot carry a snapshot_id")
        return self


class ChartBlockValue(ContractModel):
    """The inserted block identity (API_SPECIFICATION ``MutationResult`` value)."""

    block_id: UUID


class ChartBlockMutationResponse(ContractModel):
    """``MutationResult<{block_id}>``: the new revision summary plus the block.

    The new revision's content and resolved contexts (including the frozen
    context of the inserted block, keyed by ``block_id``) are fetchable
    through ``GET /documents/{id}`` — the response never makes the client
    guess the new revision (the ETag carries it).
    """

    document: DocumentSummary
    value: ChartBlockValue
