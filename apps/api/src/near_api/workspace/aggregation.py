"""Owner-scoped home aggregation (NI-022).

The workspace home needs research continuation data with bounded queries:
the principal's most recent documents (capped at 5, current revision,
`updated_at` sort) plus owner-scoped totals. One :func:`scoped_page` call
covers both — the owner predicate is a required argument applied to the same
statement as LIMIT/OFFSET, and the count runs over the same scoped query, so
the total can never include another user's rows. Two SQL statements total;
there is no per-row follow-up query (no N+1).

Pending sections (recent_charts/recent_insights/indicators) have no data
pipeline yet — saved charts arrive with NI-035, the insight contracts and
persistence with NI-046/NI-047 and public series with NI-031/NI-032. Their
response fields serialize as honest empty arrays (schemas/home.py forbids
items until the owning tasks implement the real element types); nothing here
invents rows.

Deleted targets never surface as errors: a deleted document is absent from
app.documents, so it drops out of the recent list and the totals in the same
statement. Not-owned targets are indistinguishable from absent ones; if any
future helper raises :class:`ResourceNotFound`, the contracts layer maps it
to the one generic 404.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection, select

from near_api.auth.principal import Principal
from near_api.db.models import Document
from near_api.db.security import owner_scope, scoped_page
from near_api.schemas.home import (
    RECENT_LIST_CAP,
    DocumentProgress,
    DocumentSummary,
    HomeCounts,
    HomeResponse,
)

_DOCUMENT_COLUMNS = (
    Document.id, Document.title, Document.revision, Document.schema_version,
    Document.current_version_id, Document.created_at, Document.updated_at,
)


@dataclass(frozen=True)
class RecentDocument:
    """A projected document summary row owned by the principal."""

    id: UUID
    title: str
    revision: int
    schema_version: int
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class HomeOverview:
    """Aggregated home data before response serialization."""

    recent_documents: tuple[RecentDocument, ...]
    documents_total: int

    def to_home_response(self) -> HomeResponse:
        """Serialize the overview; pending sections stay honestly empty.

        `progress` is the documented zero until the revision service
        (NI-036) and the block taxonomy of NI-041/NI-046/NI-047 define and
        populate canonical counters; see schemas/home.DocumentProgress.
        """
        return HomeResponse(
            recent_documents=tuple(
                DocumentSummary(
                    id=item.id, title=item.title, revision=item.revision,
                    schema_version=item.schema_version,
                    current_version_id=item.current_version_id,
                    created_at=item.created_at, updated_at=item.updated_at,
                    progress=DocumentProgress(headings=0, charts=0, insights=0),
                )
                for item in self.recent_documents
            ),
            counts=HomeCounts(documents=self.documents_total),
            recent_charts=(), recent_insights=(), indicators=(),
        )


def home_overview(connection: Connection, principal: Principal) -> HomeOverview:
    """Return the principal's recent documents and owner-scoped totals.

    Deleted documents drop out of both the recent list and the count without
    an error (absent rows cannot be distinguished from not-owned ones here —
    both are simply invisible). The stable private order is
    `(updated_at DESC, id)`.
    """
    query = select(*_DOCUMENT_COLUMNS).order_by(Document.updated_at.desc(), Document.id)
    page = scoped_page(connection, query,
                       owner_scope(Document.owner_id, principal.id),
                       limit=RECENT_LIST_CAP, offset=0)
    return HomeOverview(
        recent_documents=tuple(RecentDocument(**item) for item in page.items),
        documents_total=page.total,
    )
