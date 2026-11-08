"""Owner-scoped workspace continuation contracts (NI-022 / NI-024).

Shared DocumentSummary remains the document API contract; home fills progress
from current canonical relational projections rather than confidence scores.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from near_api.schemas.common import ContractModel
from near_api.schemas.delivery import SeriesResponse
from near_api.schemas.saved_charts import SavedChartResponse

RECENT_LIST_CAP = 5
"""Maximum length of every recent-* list on home (TASKS.md NI-022: cap at 5)."""


class DocumentProgress(ContractModel):
    """Per-document work-completion counters (`{headings,charts,insights}`).

    Block projection regeneration is owned by the document revision service
    (NI-036) and the chart/insight block taxonomy by NI-041/NI-046/NI-047.
    Home counts the canonical current-version heading/liveChart/insight
    projection types. The counter semantics measure work completion only.
    """

    headings: int = Field(strict=True, ge=0)
    charts: int = Field(strict=True, ge=0)
    insights: int = Field(strict=True, ge=0)


class DocumentSummary(ContractModel):
    """Current-revision summary of an owned document.

    `revision`/`current_version_id` come from the live app.documents row, so
    a summary always reflects the document's current revision. A document
    that has no saved revision yet carries `current_version_id: null`.
    """

    id: UUID
    title: str = Field(min_length=1, max_length=200)
    revision: int = Field(strict=True, ge=1)
    schema_version: int = Field(strict=True, ge=1)
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime
    progress: DocumentProgress


class HomeInsightSummary(ContractModel):
    """An existing canonical insight in an owned document's current revision.

    This read projection provides navigation only; NI-047 owns insight authoring.
    """

    insight_id: UUID
    document_id: UUID
    document_title: str = Field(min_length=1, max_length=200)
    block_id: UUID
    type: Literal["observation", "hypothesis", "risk", "conclusion"]
    classification: Literal["supporting", "contradicting", "uncertain"]
    modified_at: datetime
    excerpt: str = Field(max_length=280)


class HomeIndicator(ContractModel):
    """One canonical single-day series or an independently unavailable context.

    The series preserves metric/dataset versions, decimal strings, quality,
    source provenance and the exact UTC selection. No home-specific arithmetic.
    """

    chart_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    chart_version: int | None = Field(ge=1)
    status: Literal["available", "unavailable"]
    series: SeriesResponse | None
    reason: str | None

    @model_validator(mode="after")
    def honest_status(self):
        if self.status == "available":
            if self.series is None or self.chart_version is None or self.reason is not None:
                raise ValueError("available indicators require a versioned series and no failure reason")
        elif self.series is not None or not self.reason:
            raise ValueError("unavailable indicators require a reason and no series")
        return self


class HomeCounts(ContractModel):
    """Owner-scoped document total; no financial or confidence meaning."""

    documents: int = Field(strict=True, ge=0)


class HomeResponse(ContractModel):
    """`GET /api/home` payload for the verified principal.

    Operator-directed addition to the specification row: `counts` exposes the
    owner-scoped totals (NI-022 "include workflow counts"). Every list is
    capped at RECENT_LIST_CAP by the query, not by slicing.
    """

    recent_documents: tuple[DocumentSummary, ...] = Field(max_length=RECENT_LIST_CAP)
    recent_charts: tuple[SavedChartResponse, ...] = Field(max_length=RECENT_LIST_CAP)
    recent_insights: tuple[HomeInsightSummary, ...] = Field(max_length=RECENT_LIST_CAP)
    indicators: tuple[HomeIndicator, ...] = Field(max_length=3)
    counts: HomeCounts
