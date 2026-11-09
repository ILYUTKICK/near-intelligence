"""Chart insight convenience mutations on an immutable document revision."""

from typing import Self
from uuid import UUID

from pydantic import StrictBool, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from near_api.documents.schema import canonical_rich_body_json
from near_api.insights.schemas import (
    EvidenceClassification,
    Insight,
    InsightInput,
    InsightType,
    ResolvedContext,
    RichTextBody,
)
from near_api.schemas.common import ContractModel
from near_api.schemas.documents import DocumentSaveResponse


class InsightCreateRequest(InsightInput):
    """Create a chart insight, optionally inserting it after a current block."""

    context: ResolvedContext
    after_block_id: UUID | None = None


class InsightPatchRequest(ContractModel):
    """Omission keeps a field. A null hypothesis_id removes the association."""

    type: InsightType | SkipJsonSchema[None] = None
    classification: EvidenceClassification | SkipJsonSchema[None] = None
    body: RichTextBody | SkipJsonSchema[None] = None
    context: ResolvedContext | SkipJsonSchema[None] = None
    hypothesis_id: UUID | None = None

    @field_validator("body", mode="before")
    @classmethod
    def _canonical_body(cls, value: object) -> list[dict]:
        return canonical_rich_body_json(value)

    @model_validator(mode="after")
    def _check_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply at least one field to edit")
        if any(getattr(self, field) is None
               for field in self.model_fields_set - {"hypothesis_id"}):
            raise ValueError("Only hypothesis_id can be null")
        return self


class InsightDeleteRequest(ContractModel):
    remove_evidence_links: StrictBool


class InsightMutationResponse(DocumentSaveResponse):
    value: Insight


class InsightDeleteValue(ContractModel):
    deleted_id: UUID


class InsightDeleteResponse(DocumentSaveResponse):
    value: InsightDeleteValue
