"""Relational block/insight/hypothesis/evidence projections (NI-036).

``document_versions.content`` holds the complete canonical editor JSON
(DATABASE_SCHEMA.md "Canonical content rule"); the relational tables are
validated projections of that revision, created in the SAME transaction and
never independently edited. This module is the only writer of those
projection rows: it derives them from an already validated
:class:`~near_api.documents.schema.CanonicalDocument`, so a projection can
never diverge from the canonical JSON it came from.

Projection rows are per top-level block in document order
(``parent_block_id`` is NULL for the flat P0 block list; rich text children
are part of the block's canonical content, not separate blocks). Insight,
hypothesis and evidence rows mirror the typed annotation attributes verbatim
(including the server-normalized author timestamps). Regenerating the
projections from the stored revision JSON and comparing against the persisted
rows is the projection round-trip guarantee (tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Connection, insert

from near_api.auth.principal import Principal
from near_api.db.models import DocumentBlock, EvidenceLink, Hypothesis, Insight
from near_api.documents.schema import CanonicalDocument


@dataclass(frozen=True)
class BlockProjection:
    block_id: UUID
    position: int
    block_type: str
    parent_block_id: UUID | None
    attrs: dict


@dataclass(frozen=True)
class InsightProjection:
    insight_id: UUID
    block_id: UUID
    insight_type: str
    classification: str
    body: dict
    context: dict
    authored_at: str
    modified_at: str
    hypothesis_id: UUID | None


@dataclass(frozen=True)
class HypothesisProjection:
    hypothesis_id: UUID
    block_id: UUID
    statement: str
    assessment: str
    authored_at: str
    modified_at: str


@dataclass(frozen=True)
class EvidenceProjection:
    evidence_id: UUID
    block_id: UUID
    hypothesis_id: UUID
    classification: str
    target_kind: str
    target_id: UUID
    explanation: str


@dataclass(frozen=True)
class DocumentProjections:
    blocks: tuple[BlockProjection, ...]
    insights: tuple[InsightProjection, ...]
    hypotheses: tuple[HypothesisProjection, ...]
    evidence: tuple[EvidenceProjection, ...]


def build_projections(document: CanonicalDocument) -> DocumentProjections:
    """Derive every projection row from the validated canonical document."""
    blocks = tuple(
        BlockProjection(block_id=block.block_id, position=position,
                        block_type=block.block_type, parent_block_id=None,
                        attrs=dict(block.attrs))
        for position, block in enumerate(document.blocks)
    )
    insights = tuple(
        InsightProjection(
            insight_id=item.insight_id, block_id=item.block_id,
            insight_type=item.insight_type, classification=item.classification,
            body=list(item.body_json),
            context=dict(item.context),
            authored_at=item.authored_at.isoformat(),
            modified_at=item.modified_at.isoformat(),
            hypothesis_id=item.hypothesis_id,
        )
        for item in document.insights
    )
    hypotheses = tuple(
        HypothesisProjection(
            hypothesis_id=item.hypothesis_id, block_id=item.block_id,
            statement=item.statement, assessment=item.assessment,
            authored_at=item.authored_at.isoformat(),
            modified_at=item.modified_at.isoformat(),
        )
        for item in document.hypotheses
    )
    evidence = tuple(
        EvidenceProjection(
            evidence_id=item.evidence_id, block_id=item.block_id,
            hypothesis_id=item.hypothesis_id, classification=item.classification,
            target_kind=item.target_kind, target_id=item.target_id,
            explanation=item.explanation,
        )
        for item in document.evidence
    )
    return DocumentProjections(blocks=blocks, insights=insights,
                               hypotheses=hypotheses, evidence=evidence)


def write_projections(connection: Connection, principal: Principal, *,
                      document_id: UUID, version_id: UUID,
                      projections: DocumentProjections) -> None:
    """Insert every projection row for one new revision (same transaction).

    Owner/document/version columns come from the verified revision chain, not
    from the payload: the composite foreign keys make it impossible to attach
    a projection to a foreign document even with raw SQL.
    """
    owner_id = principal.id
    if projections.blocks:
        connection.execute(insert(DocumentBlock), [
            {"document_version_id": version_id, "document_id": document_id,
             "owner_id": owner_id, "block_id": item.block_id,
             "parent_block_id": item.parent_block_id, "position": item.position,
             "block_type": item.block_type, "attrs": item.attrs}
            for item in projections.blocks
        ])
    if projections.insights:
        connection.execute(insert(Insight), [
            {"document_version_id": version_id, "document_id": document_id,
             "owner_id": owner_id, "insight_id": item.insight_id,
             "block_id": item.block_id, "type": item.insight_type,
             "classification": item.classification, "body": item.body,
             "context": item.context, "authored_at": item.authored_at,
             "modified_at": item.modified_at, "hypothesis_id": item.hypothesis_id}
            for item in projections.insights
        ])
    if projections.hypotheses:
        connection.execute(insert(Hypothesis), [
            {"document_version_id": version_id, "document_id": document_id,
             "owner_id": owner_id, "hypothesis_id": item.hypothesis_id,
             "block_id": item.block_id, "statement": item.statement,
             "assessment": item.assessment, "authored_at": item.authored_at,
             "modified_at": item.modified_at}
            for item in projections.hypotheses
        ])
    if projections.evidence:
        connection.execute(insert(EvidenceLink), [
            {"document_version_id": version_id, "document_id": document_id,
             "owner_id": owner_id, "evidence_id": item.evidence_id,
             "block_id": item.block_id, "hypothesis_id": item.hypothesis_id,
             "classification": item.classification, "target_kind": item.target_kind,
             "target_id": item.target_id, "explanation": item.explanation}
            for item in projections.evidence
        ])
