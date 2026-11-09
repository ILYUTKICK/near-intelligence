"""Resolve evidence's shared targets against their immutable public catalogs."""

from sqlalchemy import Connection, select

from near_api.db.models import Artifact, ModelRun
from near_api.documents.schema import CanonicalDocument, ReferenceInvalid
from near_api.pagination import encode_page_cursor
from near_api.schemas.document_evidence import (
    EvidenceTarget,
    EvidenceTargetListResponse,
    PublicEvidenceTargetKind,
)

_PUBLIC_RUNS = select(ModelRun.run_id).where(ModelRun.status == "published")
_PUBLIC_CITATIONS = select(Artifact.id).where(Artifact.scope == "public")


def validate_public_targets(connection: Connection, canonical: CanonicalDocument) -> None:
    """Batch-check public references. The parser already checks private links."""
    for kind, id_column, query in (
        ("model_run", ModelRun.run_id, _PUBLIC_RUNS),
        ("citation", Artifact.id, _PUBLIC_CITATIONS),
    ):
        ids = {item.target_id for item in canonical.evidence if item.target_kind == kind}
        if ids and ids != set(connection.scalars(query.where(id_column.in_(ids)))):
            raise ReferenceInvalid(
                "Evidence target does not reference a public immutable artifact",
                [("content", f"dangling_{kind}_target")])


def list_public_targets(connection: Connection, target_kind: PublicEvidenceTargetKind, *,
                        offset: int, limit: int) -> EvidenceTargetListResponse:
    """Select only safe display fields and read at most one row past the page."""
    if target_kind == "model_run":
        query = _PUBLIC_RUNS.add_columns(ModelRun.spec_id, ModelRun.spec_version).order_by(
            ModelRun.published_at.desc(), ModelRun.run_id)
        rows = connection.execute(query.offset(offset).limit(limit + 1)).all()
        # spec_id is a bounded ASCII slug enforced by the published registry.
        items = tuple(EvidenceTarget(id=run_id, label=f"{spec_id} v{version} · {run_id}")
                      for run_id, spec_id, version in rows[:limit])
    else:
        query = _PUBLIC_CITATIONS.order_by(Artifact.created_at.desc(), Artifact.id)
        rows = connection.execute(query.offset(offset).limit(limit + 1)).all()
        # The artifact registry has no public title. Storage keys stay internal.
        items = tuple(EvidenceTarget(id=artifact_id, label=f"Public citation · {artifact_id}")
                      for (artifact_id,) in rows[:limit])
    next_cursor = encode_page_cursor(offset + limit) if len(rows) > limit else None
    return EvidenceTargetListResponse(items=items, next_cursor=next_cursor)
