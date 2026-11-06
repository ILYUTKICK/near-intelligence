"""NI-022 workspace home contracts: `GET /api/home` response models.

The field set is pinned to the `GET /workspace/home` row of
API_SPECIFICATION.md so the workspace shell (NI-024) never has to reshape.
Three sections (recent_charts, recent_insights, indicators) document an
honest pending status instead of fabricating items: their tables and data
pipelines do not exist yet (saved charts arrive with NI-035, the insight
contracts/persistence with NI-046/NI-047 and public series with
NI-031/NI-032), so they serialize as empty arrays until the owning tasks
swap in SavedChart / Insight / Series.

`DocumentSummary`/`DocumentProgress` are the shared summary contract for the
owner-scoped document chain; the document CRUD endpoints (NI-037) must reuse
these models rather than maintaining duplicate DTOs.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from near_api.schemas.common import ContractModel

RECENT_LIST_CAP = 5
"""Maximum length of every recent-* list on home (TASKS.md NI-022: cap at 5)."""


class DocumentProgress(ContractModel):
    """Per-document work-completion counters (`{headings,charts,insights}`).

    Block projection regeneration is owned by the document revision service
    (NI-036) and the chart/insight block taxonomy by NI-041/NI-046/NI-047.
    Until that canonical taxonomy and projection exist, these counters are
    the documented zero; they are never guessed from a non-canonical block
    type naming. The counter semantics measure work completion only.
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


class PendingHomeSection(ContractModel):
    """Typed marker element for a home section whose data model arrives later.

    recent_charts arrives with NI-035 (persisted saved charts), recent_insights
    with NI-046/NI-047 (insight contracts and persistence) and indicators with
    NI-031/NI-032 (versioned chart/metric registries and public series APIs).
    The owning tasks replace this element type with SavedChart / Insight /
    Series per API_SPECIFICATION.md. The response schema forbids items
    (`maxItems: 0`) until then: an empty array is the honest answer and
    fabricated placeholder data can never validate.
    """

    status: Literal["pending"] = "pending"


class HomeCounts(ContractModel):
    """Owner-scoped workflow totals the workspace shell renders.

    Only the documents total exists today (it is the scoped count of the same
    statement that pages recent_documents). Sections that arrive with
    NI-035/NI-046/NI-047 extend this object instead of reshaping the response.
    """

    documents: int = Field(strict=True, ge=0)


class HomeResponse(ContractModel):
    """`GET /api/home` payload for the verified principal.

    Operator-directed addition to the specification row: `counts` exposes the
    owner-scoped totals (NI-022 "include workflow counts"). Every list is
    capped at RECENT_LIST_CAP by the query, not by slicing.
    """

    recent_documents: tuple[DocumentSummary, ...] = Field(max_length=RECENT_LIST_CAP)
    # Required fields with maxItems 0: every documented field is always present
    # in the JSON (empty arrays today, real element types once the owning
    # tasks land), so consumers never meet an optional/mushrooming contract.
    recent_charts: tuple[PendingHomeSection, ...] = Field(max_length=0)
    recent_insights: tuple[PendingHomeSection, ...] = Field(max_length=0)
    indicators: tuple[PendingHomeSection, ...] = Field(max_length=0)
    counts: HomeCounts
