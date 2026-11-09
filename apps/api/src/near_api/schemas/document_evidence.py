"""Evidence relationships and selectable public targets (NI-049)."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from near_api.insights.schemas import (
    BoundedExplanation,
    Evidence,
    EvidenceClassification,
    EvidenceInput,
    EvidenceTargetKind,
)
from near_api.schemas.common import ContractModel
from near_api.schemas.documents import DocumentSaveResponse

PublicEvidenceTargetKind = Literal["model_run", "citation"]


class EvidenceCreateRequest(EvidenceInput):
    """Append, insert after a current block, or convert a current paragraph."""

    after_block_id: UUID | None = None


class EvidencePatchRequest(ContractModel):
    """Edit the relationship and explanation while retaining its identity."""

    hypothesis_id: UUID | SkipJsonSchema[None] = None
    classification: EvidenceClassification | SkipJsonSchema[None] = None
    target_kind: EvidenceTargetKind | SkipJsonSchema[None] = None
    target_id: UUID | SkipJsonSchema[None] = None
    explanation: BoundedExplanation | SkipJsonSchema[None] = None

    @model_validator(mode="after")
    def _check_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply at least one field to edit")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Evidence fields cannot be null")
        return self


class EvidenceMutationResponse(DocumentSaveResponse):
    value: Evidence


class EvidenceDeleteValue(ContractModel):
    deleted_id: UUID


class EvidenceDeleteResponse(DocumentSaveResponse):
    value: EvidenceDeleteValue


class EvidenceTarget(ContractModel):
    id: UUID
    label: str = Field(min_length=1, max_length=160)


class EvidenceTargetListResponse(ContractModel):
    items: tuple[EvidenceTarget, ...]
    next_cursor: str | None
