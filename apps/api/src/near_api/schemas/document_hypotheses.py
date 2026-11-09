"""Hypothesis convenience mutations on an immutable document revision."""

from typing import Self
from uuid import UUID

from pydantic import StrictBool, model_validator
from pydantic.json_schema import SkipJsonSchema

from near_api.insights.schemas import BoundedStatement, Hypothesis, HypothesisAssessment, HypothesisInput
from near_api.schemas.common import ContractModel
from near_api.schemas.documents import DocumentSaveResponse


class HypothesisCreateRequest(HypothesisInput):
    """Append, insert after a current block, or convert a current paragraph."""

    after_block_id: UUID | None = None


class HypothesisPatchRequest(ContractModel):
    """Edit the statement or the manually authored assessment."""

    statement: BoundedStatement | SkipJsonSchema[None] = None
    assessment: HypothesisAssessment | SkipJsonSchema[None] = None

    @model_validator(mode="after")
    def _check_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply at least one field to edit")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Statement and assessment cannot be null")
        return self


class HypothesisDeleteRequest(ContractModel):
    remove_evidence_links: StrictBool


class HypothesisMutationResponse(DocumentSaveResponse):
    value: Hypothesis


class HypothesisDeleteValue(ContractModel):
    deleted_id: UUID


class HypothesisDeleteResponse(DocumentSaveResponse):
    value: HypothesisDeleteValue
