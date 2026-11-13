"""NI-055 model-block insertion HTTP contracts.

Pinned to the API_SPECIFICATION "Research documents and versions" row
``POST /documents/{id}/model-blocks``: the request carries the chosen
published run identity, the approved dataset version pin, the authored
interpretation rich text and an optional insertion anchor; the response is
the spec's ``MutationResult<{block_id}>`` — the moved document summary plus
the server-allocated block id. The client never supplies a ``block_id`` or
any owner field: the block identity and the frozen ``ModelContext`` are
resolved server-side (documents/model_blocks.py), so one confirmation is one
valid block with one frozen context.

The interpretation reuses the bounded canonical rich-text body grammar
through :func:`near_api.documents.schema.canonical_rich_body_json` (one
authoritative grammar, like the NI-046 annotation contracts). No
coefficient, diagnostic or any other statistical value is part of the
contract: the block stores ids + narrative only, and summaries are
re-projected from the immutable published run row.
"""

from uuid import UUID

from pydantic import field_validator

from near_api.documents.schema import canonical_rich_body_json
from near_api.insights.schemas import RichTextBody
from near_api.schemas.common import ContractModel
from near_api.schemas.home import DocumentSummary


class ModelBlockInsertRequest(ContractModel):
    """POST /documents/{id}/model-blocks body (If-Match carries the CAS).

    ``model_run_id`` must reference a published immutable ``app.model_runs``
    row (the picker lists the public catalog; the server re-verifies inside
    the save transaction). ``dataset_version_id`` is the approved public
    dataset version the interpretation reads against — an unapproved one is
    rejected, never substituted with latest. ``after_block_id`` positions the
    new block after an existing top-level block of the document; without it
    the block is appended last.
    """

    model_run_id: UUID
    dataset_version_id: UUID
    interpretation: RichTextBody
    after_block_id: UUID | None = None

    @field_validator("interpretation", mode="before")
    @classmethod
    def _canonical_body(cls, value: object) -> list[dict]:
        return canonical_rich_body_json(value, path="interpretation")


class ModelBlockValue(ContractModel):
    """The inserted block identity (API_SPECIFICATION ``MutationResult`` value)."""

    block_id: UUID


class ModelBlockMutationResponse(ContractModel):
    """``MutationResult<{block_id}>``: the new revision summary plus the block.

    The new revision's content and resolved contexts (including the frozen
    ``ModelContext`` of the inserted block, keyed by ``block_id``) are
    fetchable through ``GET /documents/{id}`` — the response never makes the
    client guess the new revision (the ETag carries it).
    """

    document: DocumentSummary
    value: ModelBlockValue
