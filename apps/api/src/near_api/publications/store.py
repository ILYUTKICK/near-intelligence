"""Read-side access to published research publications (NI-045).

One read helper for both public routes: the generic 404 posture is
structural — a row that is absent, mis-slugged or not published is the same
``None`` (RLS hides non-published rows from ``near_app``; the query itself
never leaks which case occurred). Version pinning is explicit: ``version``
selects exactly that release; ``None`` resolves the latest published version
of the slug ("latest approved default", API_SPECIFICATION).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection, select

from near_api.db.models import PublicationModelRun, ResearchPublication


@dataclass(frozen=True)
class PublicationRow:
    """One published release's public projection facts."""

    id: UUID
    slug: str
    version: int
    title: str
    content: dict
    evidence_manifest: list
    content_sha256: str
    published_at: datetime


def get_published_publication(connection: Connection, slug: str, *,
                              version: int | None = None) -> PublicationRow | None:
    """The published release for one slug; None when absent/unpublished."""
    query = select(
        ResearchPublication.id, ResearchPublication.slug,
        ResearchPublication.version, ResearchPublication.title,
        ResearchPublication.content, ResearchPublication.evidence_manifest,
        ResearchPublication.content_sha256, ResearchPublication.published_at,
    ).where(ResearchPublication.slug == slug)
    if version is not None:
        query = query.where(ResearchPublication.version == version)
    else:
        query = query.order_by(ResearchPublication.version.desc())
    row = connection.execute(query.limit(1)).mappings().first()
    if row is None:
        return None
    return PublicationRow(
        id=row["id"], slug=row["slug"], version=row["version"], title=row["title"],
        content=row["content"], evidence_manifest=row["evidence_manifest"] or [],
        content_sha256=row["content_sha256"], published_at=row["published_at"])


def publication_model_run_ids(connection: Connection, publication_id: UUID) -> tuple[UUID, ...]:
    """The published runs bound to one publication (manifest lineage)."""
    return tuple(connection.scalars(
        select(PublicationModelRun.model_run_id)
        .where(PublicationModelRun.publication_id == publication_id)
        .order_by(PublicationModelRun.model_run_id)))


__all__ = ["PublicationRow", "get_published_publication", "publication_model_run_ids"]
