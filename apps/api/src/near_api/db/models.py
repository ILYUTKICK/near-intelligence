"""Schema declarations mirroring the versioned Alembic migrations.

NI-003 owns the identity tables; NI-019 adds the private document chain
(documents, document_versions, document_blocks) that the ownership/RLS layer
operates on. NI-027 adds the operator-zone archive import tables (sources,
import_batches, imported_files, source_runs): metadata-only lineage for the
read-only research archive import — file bytes are never stored. NI-028 adds
the immutable dataset staging/publication zone (artifacts, dataset_versions,
dataset_metrics, dataset_inputs, metric_observations, active_datasets).
NI-029 adds the append-only metric definition registry (metric_definitions).
NI-031 adds the append-only chart definition registry (chart_definitions,
chart_metrics) and the dataset_metrics referential FK to metric_definitions.
NI-036 adds the per-revision document projections (insights, hypotheses,
evidence_links) derived from canonical document_versions.content.
NI-030 adds the ingestion checkpoint zone (ingestion_checkpoints,
ingestion_daily_counters) for the bounded scheduled refresh adapter.
NI-037 adds the Idempotency-Key replay store (idempotency_records) for the
document write routes.
NI-035 adds the owner-scoped saved chart instances (saved_charts) that pin
canonical analytical contexts to immutable chart definition versions.
NI-044 adds the owner-scoped immutable research snapshot registry
(research_snapshots) that saved-charts snapshot mode references through a
same-owner composite foreign key.
NI-058 adds the owner-scoped Markdown ZIP export jobs (export_jobs): the
queued/leased/TTL-bounded job rows that freeze the NI-056 export IR and hold
the finished owner-private ZIP bytes.
NI-072 adds the private document organization metadata (document_organization):
per-document private tags and favorite flag, separate from the immutable
research chain — tagging never touches document_versions or documents.
NI-045 adds the public research publication zone (research_publications,
publication_model_runs): operator-seeded immutable (slug, version) releases
whose canonical content the public read route serves and the duplicate flow
clones into private IDs, plus the documents.source_publication_id
attribution pin recorded on private duplicates.
Remaining domain tables belong to their owning tasks and must keep these
declarations in sync for the Alembic metadata drift check.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(schema="app", naming_convention={
        "pk": "pk_%(table_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s", "ix": "ix_%(table_name)s_%(column_0_name)s",
    })


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("auth_provider = 'supabase'", name="auth_provider"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    auth_provider: Mapped[str] = mapped_column(String(16), server_default=text("'supabase'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint("app.is_valid_timezone(display_timezone)", name="timezone"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("app.users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), server_default=text("''"))
    display_timezone: Mapped[str] = mapped_column(String(64), server_default=text("'UTC'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("title <> ''", name="title_nonempty"),
        CheckConstraint("revision > 0", name="revision_positive"),
        UniqueConstraint("id", "owner_id", name="uq_documents_id_owner"),
        # The current-version pointer is a composite FK into the same
        # document/owner, DEFERRABLE for the insert transaction (NI-003 schema).
        ForeignKeyConstraint(
            ["current_version_id", "id", "owner_id"],
            ["app.document_versions.id", "app.document_versions.document_id",
             "app.document_versions.owner_id"],
            name="fk_documents_current_version", deferrable=True, initially="IMMEDIATE",
            use_alter=True,
        ),
        Index("ix_documents_owner_updated_at", "owner_id", text("updated_at DESC"), "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("app.users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    current_version_id: Mapped[UUID | None]
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # NI-045 one-time attribution: the public release this document was
    # duplicated from (NULL for ordinary documents; never updated after insert).
    source_publication_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("app.research_publications.id", ondelete="RESTRICT",
                   name="fk_documents_source_publication"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentOrganization(Base):
    """NI-072 private per-document organization metadata (tags + favorite).

    Mirrors migration 0014 exactly (DATABASE_SCHEMA.md "document_organization").
    Exactly one optional row per owned document: the composite FK cascades
    with the document, so deleting a document removes its organization state
    without touching the immutable revision chain. Tags are bounded private
    text — the database CHECK re-validates the documented bounds (<= 20
    tags/document, 1..40 chars, normalized lowercase form, duplicate-free) on
    every write. Organization writes never UPDATE app.documents, so tagging
    neither creates a revision nor reorders the updated_at-DESC list; this
    table's own updated_at carries metadata recency only.
    """

    __tablename__ = "document_organization"
    __table_args__ = (
        CheckConstraint("app.is_valid_tag_set(tags)", name="tags"),
        UniqueConstraint("document_id", "owner_id", name="uq_document_organization_id_owner"),
        ForeignKeyConstraint(["document_id", "owner_id"],
                             ["app.documents.id", "app.documents.owner_id"],
                             name="fk_document_organization_document", ondelete="CASCADE"),
    )

    document_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    favorite: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        CheckConstraint("revision > 0", name="revision_positive"),
        CheckConstraint(r"content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        UniqueConstraint("document_id", "revision", name="uq_document_versions_document_revision"),
        UniqueConstraint("id", "document_id", "owner_id", name="uq_document_versions_id_document_owner"),
        # Composite FK: a version exists only for a document row of the same
        # owner, so cross-owner references fail at write time.
        ForeignKeyConstraint(["document_id", "owner_id"],
                             ["app.documents.id", "app.documents.owner_id"],
                             name="fk_document_versions_document_id", ondelete="CASCADE"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    resolved_contexts: Mapped[dict | None] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentBlock(Base):
    __tablename__ = "document_blocks"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_nonnegative"),
        # Direct self-parenting is impossible; full acyclicity and nesting depth
        # are validated by the document revision service (owning task).
        CheckConstraint("parent_block_id IS NULL OR parent_block_id <> block_id", name="parent_not_self"),
        UniqueConstraint("document_version_id", "parent_block_id", "position",
                         name="uq_document_blocks_version_parent_position",
                         postgresql_nulls_not_distinct=True),
        ForeignKeyConstraint(["document_version_id", "document_id", "owner_id"],
                             ["app.document_versions.id", "app.document_versions.document_id",
                              "app.document_versions.owner_id"],
                             name="fk_document_blocks_version_id", ondelete="CASCADE"),
        ForeignKeyConstraint(["document_version_id", "parent_block_id"],
                             ["app.document_blocks.document_version_id", "app.document_blocks.block_id"],
                             name="fk_document_blocks_parent", ondelete="CASCADE"),
        Index("ix_document_blocks_version_type", "document_version_id", "block_type"),
    )

    document_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    block_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    parent_block_id: Mapped[UUID | None]
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[str] = mapped_column(String(40), nullable=False)
    attrs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class Insight(Base):
    """Per-revision projection of one canonical insight node (NI-036)."""

    __tablename__ = "insights"
    __table_args__ = (
        ForeignKeyConstraint(["document_version_id", "document_id", "owner_id"],
                             ["app.document_versions.id", "app.document_versions.document_id",
                              "app.document_versions.owner_id"],
                             name="fk_insights_version_id", ondelete="CASCADE"),
        ForeignKeyConstraint(["document_version_id", "block_id"],
                             ["app.document_blocks.document_version_id",
                              "app.document_blocks.block_id"],
                             name="fk_insights_block", ondelete="CASCADE"),
        Index("ix_insights_document_owner_modified", "document_id", "owner_id",
              text("modified_at DESC")),
    )

    document_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    insight_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    block_id: Mapped[UUID] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hypothesis_id: Mapped[UUID | None]


class Hypothesis(Base):
    """Per-revision projection of one canonical hypothesis node (NI-036)."""

    __tablename__ = "hypotheses"
    __table_args__ = (
        CheckConstraint("assessment IN ('untested','supported','mixed','weakened',"
                        "'insufficient_data')", name="assessment"),
        ForeignKeyConstraint(["document_version_id", "document_id", "owner_id"],
                             ["app.document_versions.id", "app.document_versions.document_id",
                              "app.document_versions.owner_id"],
                             name="fk_hypotheses_version_id", ondelete="CASCADE"),
        ForeignKeyConstraint(["document_version_id", "block_id"],
                             ["app.document_blocks.document_version_id",
                              "app.document_blocks.block_id"],
                             name="fk_hypotheses_block", ondelete="CASCADE"),
    )

    document_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    hypothesis_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    block_id: Mapped[UUID] = mapped_column(nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    assessment: Mapped[str] = mapped_column(String(40), nullable=False)
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceLink(Base):
    """Per-revision projection of one canonical evidence node (NI-036).

    The polymorphic target is validated by the revision service (same-revision
    insight/chart block or public artifact); no polymorphic FK is trusted.
    """

    __tablename__ = "evidence_links"
    __table_args__ = (
        CheckConstraint("classification IN ('supporting','contradicting','uncertain')",
                        name="classification"),
        CheckConstraint("target_kind IN ('insight','chart_block','model_run','citation')",
                        name="target_kind"),
        ForeignKeyConstraint(["document_version_id", "document_id", "owner_id"],
                             ["app.document_versions.id", "app.document_versions.document_id",
                              "app.document_versions.owner_id"],
                             name="fk_evidence_links_version_id", ondelete="CASCADE"),
        ForeignKeyConstraint(["document_version_id", "block_id"],
                             ["app.document_blocks.document_version_id",
                              "app.document_blocks.block_id"],
                             name="fk_evidence_links_block", ondelete="CASCADE"),
        ForeignKeyConstraint(["document_version_id", "hypothesis_id"],
                             ["app.hypotheses.document_version_id",
                              "app.hypotheses.hypothesis_id"],
                             name="fk_evidence_links_hypothesis", ondelete="CASCADE"),
        Index("ix_evidence_links_document_owner", "document_id", "owner_id"),
    )

    document_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    block_id: Mapped[UUID] = mapped_column(nullable=False)
    hypothesis_id: Mapped[UUID] = mapped_column(nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[UUID] = mapped_column(nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)


class IdempotencyRecord(Base):
    """Stored result of one Idempotency-Key write for replay (NI-037).

    Mirrors migration 0009 exactly (DATABASE_SCHEMA.md "idempotency_records"):
    the response snapshot of a successful document write, committed in the
    same transaction as the write itself, so a repeated identical
    owner/route/body request returns the original result for 24h instead of
    creating a second document/revision. Write-once for the runtime role (no
    UPDATE grant); expired rows are replaced lazily by DELETE + INSERT.
    """

    __tablename__ = "idempotency_records"
    __table_args__ = (
        CheckConstraint("route_key <> ''", name="route_nonempty"),
        CheckConstraint(r"request_hash ~ '^[0-9a-f]{64}$'", name="request_hash_format"),
        CheckConstraint("response_status >= 200 AND response_status < 300",
                        name="response_success"),
    )

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("app.users.id", ondelete="CASCADE"), primary_key=True)
    route_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    idempotency_key: Mapped[UUID] = mapped_column(primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())


class SavedChart(Base):
    """NI-035 private context; snapshot mode pins an owned research snapshot.

    Context/label edits bump recency, resolution-only telemetry does not.
    Definition and dataset foreign keys are RESTRICT; owner deletion cascades.
    A ``snapshot`` context must carry exactly one snapshot reference and the
    composite same-owner FK (migration 0013) guarantees the referenced
    snapshot is the owner's own and cannot disappear while referenced.
    """

    __tablename__ = "saved_charts"
    __table_args__ = (
        CheckConstraint("label IS NULL OR label <> ''", name="label_nonempty"),
        CheckConstraint("mode IN ('live', 'snapshot')", name="mode"),
        CheckConstraint("(mode = 'live') = (snapshot_id IS NULL)",
                        name="snapshot_pairing"),
        CheckConstraint("selection ? 'start' AND selection ? 'end' "
                        "AND selection ? 'frequency' AND selection ? 'filters'",
                        name="selection_keys"),
        CheckConstraint("octet_length(selection::text) <= 4096", name="selection_size"),
        UniqueConstraint("id", "owner_id", name="uq_saved_charts_id_owner"),
        ForeignKeyConstraint(["owner_id"], ["app.users.id"],
                             name="fk_saved_charts_owner", ondelete="CASCADE"),
        ForeignKeyConstraint(["chart_definition_version_id"], ["app.chart_definitions.id"],
                             name="fk_saved_charts_chart_definition", ondelete="RESTRICT"),
        ForeignKeyConstraint(["last_resolved_dataset_version_id"], ["app.dataset_versions.id"],
                             name="fk_saved_charts_dataset", ondelete="RESTRICT"),
        ForeignKeyConstraint(["snapshot_id", "owner_id"],
                             ["app.research_snapshots.id", "app.research_snapshots.owner_id"],
                             name="fk_saved_charts_snapshot", ondelete="RESTRICT"),
        Index("ix_saved_charts_owner_updated_at", "owner_id", text("updated_at DESC"), "id"),
        Index("ix_saved_charts_chart_definition", "chart_definition_version_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    chart_definition_version_id: Mapped[UUID] = mapped_column(nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    selection: Mapped[dict] = mapped_column(JSONB, nullable=False)
    last_resolved_dataset_version_id: Mapped[UUID | None]
    snapshot_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())


class ResearchSnapshot(Base):
    """NI-044 owner-scoped immutable research snapshot.

    Mirrors migration 0013 exactly (DATABASE_SCHEMA.md "research_snapshots"):
    one frozen public input set — an approved dataset version plus a canonical
    selection against an immutable chart definition version — with the
    calculation context (resolved context hash, pinned metric definition
    versions, renderer version) and a deterministic content hash over those
    frozen inputs. No UPDATE grant or policy exists for any role, so a row
    can never change after commit; operator purge flows through the users
    cascade only. ``artifact_id`` stays reserved for a future rendered/data
    artifact reference (nullable; RESTRICT).
    """

    __tablename__ = "research_snapshots"
    __table_args__ = (
        CheckConstraint("selection ? 'start' AND selection ? 'end' "
                        "AND selection ? 'frequency' AND selection ? 'filters'",
                        name="selection_keys"),
        CheckConstraint("octet_length(selection::text) <= 4096", name="selection_size"),
        CheckConstraint("octet_length(calculation_context::text) <= 8192", name="context_size"),
        CheckConstraint("calculation_context ? 'context_hash' "
                        "AND calculation_context ? 'metric_definition_versions' "
                        "AND calculation_context ? 'renderer_version'",
                        name="context_keys"),
        CheckConstraint(r"content_sha256 ~ '^[0-9a-f]{64}$'", name="content_hash"),
        UniqueConstraint("id", "owner_id", name="uq_research_snapshots_id_owner"),
        ForeignKeyConstraint(["owner_id"], ["app.users.id"],
                             name="fk_research_snapshots_owner", ondelete="CASCADE"),
        ForeignKeyConstraint(["chart_definition_version_id"], ["app.chart_definitions.id"],
                             name="fk_research_snapshots_chart_definition", ondelete="RESTRICT"),
        ForeignKeyConstraint(["dataset_version_id"], ["app.dataset_versions.id"],
                             name="fk_research_snapshots_dataset", ondelete="RESTRICT"),
        ForeignKeyConstraint(["artifact_id"], ["app.artifacts.id"],
                             name="fk_research_snapshots_artifact", ondelete="RESTRICT"),
        Index("ix_research_snapshots_owner_created_at", "owner_id",
              text("created_at DESC"), "id"),
        Index("ix_research_snapshots_chart_definition", "chart_definition_version_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    chart_definition_version_id: Mapped[UUID] = mapped_column(nullable=False)
    dataset_version_id: Mapped[UUID] = mapped_column(nullable=False)
    selection: Mapped[dict] = mapped_column(JSONB, nullable=False)
    calculation_context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    artifact_id: Mapped[UUID | None]
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())


class ExportJob(Base):
    """One owner-scoped export job (NI-058 Markdown ZIP, NI-059 PDF).

    Mirrors migrations 0012 + 0016 exactly (DATABASE_SCHEMA.md
    "export_jobs", the implemented shape): ``plan`` holds the FROZEN export
    IR canonical bytes built at request time (the worker renders only from
    them, so later edits never reach the artifact), ``bundle`` holds the
    finished artifact bytes (a ZIP for ``markdown_zip``, the PDF itself for
    ``pdf``) with their SHA-256 and size, and the lifecycle columns carry the
    operator lease, the attempt cap and the TTL. Bytes live owner-scoped
    inside this RLS-protected row: no public artifact key and no server
    filesystem path.
    """

    __tablename__ = "export_jobs"
    __table_args__ = (
        CheckConstraint("format IN ('markdown_zip', 'pdf')", name="format"),
        CheckConstraint("status IN ('queued','running','succeeded','failed','expired')",
                        name="status"),
        CheckConstraint("revision > 0", name="revision"),
        CheckConstraint(r"plan_sha256 ~ '^[0-9a-f]{64}$'", name="plan_hash"),
        CheckConstraint("octet_length(plan) <= 33554432", name="plan_size"),
        CheckConstraint(r"bundle_sha256 IS NULL OR bundle_sha256 ~ '^[0-9a-f]{64}$'",
                        name="bundle_hash"),
        CheckConstraint("bundle_byte_size IS NULL OR bundle_byte_size >= 0",
                        name="bundle_size"),
        CheckConstraint("(status = 'succeeded') = (bundle IS NOT NULL) "
                        "AND (bundle IS NULL) = (bundle_sha256 IS NULL) "
                        "AND (bundle IS NULL) = (bundle_byte_size IS NULL)",
                        name="bundle_pairing"),
        CheckConstraint("(status = 'failed') = (error_code IS NOT NULL)",
                        name="error_code"),
        CheckConstraint("attempts >= 0", name="attempts"),
        CheckConstraint("status <> 'queued' OR attempts = 0", name="queued_fresh"),
        CheckConstraint("(status = 'running') = (leased_until IS NOT NULL)",
                        name="lease_pairing"),
        CheckConstraint("(attempts > 0) = (leased_by IS NOT NULL)",
                        name="worker_pairing"),
        CheckConstraint("(status NOT IN ('succeeded','failed') OR completed_at IS NOT NULL) "
                        "AND (completed_at IS NULL OR status IN ('succeeded','failed','expired'))",
                        name="completed_pairing"),
        UniqueConstraint("id", "owner_id", name="uq_export_jobs_id_owner"),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_export_jobs_owner_idempotency"),
        ForeignKeyConstraint(["owner_id"], ["app.users.id"],
                             name="fk_export_jobs_owner", ondelete="CASCADE"),
        ForeignKeyConstraint(["document_id", "owner_id"], ["app.documents.id", "app.documents.owner_id"],
                             name="fk_export_jobs_document", ondelete="CASCADE"),
        ForeignKeyConstraint(["document_version_id", "document_id", "owner_id"],
                             ["app.document_versions.id", "app.document_versions.document_id",
                              "app.document_versions.owner_id"],
                             name="fk_export_jobs_version", ondelete="CASCADE"),
        Index("ix_export_jobs_status_created", "status", "created_at", "id"),
        Index("ix_export_jobs_owner_created", "owner_id", text("created_at DESC"), "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    document_id: Mapped[UUID] = mapped_column(nullable=False)
    document_version_id: Mapped[UUID] = mapped_column(nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        server_default=text("'queued'"))
    idempotency_key: Mapped[UUID | None]
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[bytes] = mapped_column(nullable=False)
    plan_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle: Mapped[bytes | None]
    bundle_sha256: Mapped[str | None] = mapped_column(String(64))
    bundle_byte_size: Mapped[int | None] = mapped_column(BigInteger)
    error_code: Mapped[str | None] = mapped_column(String(80))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    leased_by: Mapped[str | None] = mapped_column(String(120))
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Source(Base):
    """Operator-managed source catalog (no secrets; public lineage metadata)."""

    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(r"id ~ '^SRC-[A-Z]+(-[A-Z]+)*$'", name="id_format"),
        CheckConstraint("access_status IN ('disabled','documented','approved')", name="access_status"),
        CheckConstraint(
            "license_status IN ('unknown','unverified','verified','prohibited')", name="license_status"
        ),
        CheckConstraint("octet_length(lineage::text) <= 4096", name="lineage_size"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    docs_url: Mapped[str | None] = mapped_column(String(500))
    base_url: Mapped[str | None] = mapped_column(String(500))
    access_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'documented'"))
    license_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unverified'"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lineage: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ImportBatch(Base):
    """One read-only archive import; manifest SHA-256 is the idempotency key."""

    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(r"manifest_sha256 ~ '^[0-9a-f]{64}$'", name="manifest_sha256_format"),
        CheckConstraint(r"registry_sha256 ~ '^[0-9a-f]{64}$'", name="registry_sha256_format"),
        UniqueConstraint("manifest_sha256", name="uq_import_batches_manifest"),
        CheckConstraint("manifest_file_count > 0", name="manifest_file_count_positive"),
        CheckConstraint("verified_bytes >= 0", name="verified_bytes_nonnegative"),
        CheckConstraint("cohort_count > 0", name="cohort_count_positive"),
        CheckConstraint("source_count >= 0", name="source_count_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    registry_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    archive_root: Mapped[str] = mapped_column(String(1024), nullable=False)
    manifest_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    verified_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cohort_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    importer: Mapped[str] = mapped_column(String(200), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ImportedFile(Base):
    """Verified archive file metadata: path/hash/size/role only, never bytes."""

    __tablename__ = "imported_files"
    __table_args__ = (
        CheckConstraint(r"sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        CheckConstraint("byte_size >= 0", name="byte_size_nonnegative"),
        CheckConstraint(
            "file_role IN ('raw','aggregate','provenance','editorial','script')", name="file_role"
        ),
        CheckConstraint(
            "coverage_scope IN ('raw_saved_response','aggregate_window','partial_raw_audit',"
            "'point_in_time_snapshot','process_documentation')",
            name="coverage_scope",
        ),
        CheckConstraint(
            "license_status IN ('unknown','unverified','verified','prohibited')", name="license_status"
        ),
        CheckConstraint(r"relative_path NOT LIKE '/%' AND relative_path !~ '(^|/)\.\.(/|$)'",
                        name="path_relative"),
        CheckConstraint(r"cohort ~ '^[a-z0-9][a-z0-9-]{0,78}$'", name="cohort_format"),
        CheckConstraint("octet_length(metadata::text) <= 4096", name="metadata_size"),
        CheckConstraint("coverage_end_exclusive IS NULL OR coverage_start IS NULL"
                        " OR coverage_end_exclusive > coverage_start", name="coverage_window"),
        ForeignKeyConstraint(["batch_id"], ["app.import_batches.id"], name="fk_imported_files_batch_id"),
        ForeignKeyConstraint(["source_id"], ["app.sources.id"], name="fk_imported_files_source_id"),
        Index("ix_imported_files_cohort", "cohort", "relative_path"),
        Index("ix_imported_files_source", "source_id"),
    )

    batch_id: Mapped[UUID] = mapped_column(primary_key=True)
    relative_path: Mapped[str] = mapped_column(String(1024), primary_key=True)
    cohort: Mapped[str] = mapped_column(String(80), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_role: Mapped[str] = mapped_column(String(20), nullable=False)
    coverage_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    coverage_start: Mapped[date | None] = mapped_column(Date())
    coverage_end_exclusive: Mapped[date | None] = mapped_column(Date())
    source_id: Mapped[str | None] = mapped_column(String(40))
    license_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unverified'"))
    file_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class SourceRun(Base):
    """Retrieval lineage documented by a cohort manifest for one import batch."""

    __tablename__ = "source_runs"
    __table_args__ = (
        CheckConstraint("octet_length(metadata::text) <= 4096", name="metadata_size"),
        ForeignKeyConstraint(["batch_id"], ["app.import_batches.id"], name="fk_source_runs_batch_id"),
        ForeignKeyConstraint(["source_id"], ["app.sources.id"], name="fk_source_runs_source_id"),
        Index("ix_source_runs_batch", "batch_id"),
        Index("ix_source_runs_source", "source_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    batch_id: Mapped[UUID] = mapped_column(nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(40))
    query_identity: Mapped[str | None] = mapped_column(String(1024))
    retrieval_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    byte_count: Mapped[int | None] = mapped_column(BigInteger)
    request_count: Mapped[int | None] = mapped_column(Integer)
    run_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class Artifact(Base):
    """Immutable content-addressed artifact row; bytes live in operator storage."""

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("relative_storage_key", name="uq_artifacts_storage_key"),
        CheckConstraint(r"sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        CheckConstraint("byte_size >= 0", name="byte_size_nonnegative"),
        CheckConstraint("media_type <> ''", name="media_type_nonempty"),
        CheckConstraint("scope IN ('public','private','internal')", name="scope"),
        CheckConstraint(
            "license_status IN ('unknown','unverified','verified','prohibited')", name="license_status"
        ),
        CheckConstraint(
            "(scope = 'private' AND owner_id IS NOT NULL)"
            " OR (scope <> 'private' AND owner_id IS NULL)",
            name="owner_matches_scope",
        ),
        CheckConstraint(
            r"relative_storage_key NOT LIKE '/%' AND relative_storage_key NOT LIKE '%/'"
            r" AND relative_storage_key !~ '(^|/)\.\.(/|$)'"
            r" AND strpos(relative_storage_key, chr(92)) = 0",
            name="storage_key_relative",
        ),
        ForeignKeyConstraint(["owner_id"], ["app.users.id"], name="fk_artifacts_owner_id",
                             ondelete="RESTRICT"),
        Index("ix_artifacts_sha256", "sha256"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    relative_storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'internal'"))
    owner_id: Mapped[UUID | None]
    license_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unverified'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DatasetVersion(Base):
    """One immutable semantic dataset content; the dedup key is (key, content hash)."""

    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_key", "version", name="uq_dataset_versions_key_version"),
        UniqueConstraint("dataset_key", "content_sha256", name="uq_dataset_versions_key_content"),
        UniqueConstraint("id", "dataset_key", name="uq_dataset_versions_id_key"),
        CheckConstraint(
            r"dataset_key ~ '^[a-z0-9][a-z0-9-]{0,38}(\.[a-z0-9][a-z0-9-]{0,38}){0,2}$'",
            name="key_format",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("status IN ('staged','validated','approved','rejected')", name="status"),
        CheckConstraint("frequency IN ('daily','weekly','monthly','snapshot')", name="frequency"),
        CheckConstraint("end_date > start_date", name="window"),
        CheckConstraint("pipeline_version <> ''", name="pipeline_version_nonempty"),
        CheckConstraint(r"code_commit IS NULL OR code_commit ~ '^[0-9a-f]{7,64}$'",
                        name="code_commit_format"),
        CheckConstraint(r"config_hash IS NULL OR config_hash ~ '^[0-9a-f]{64}$'",
                        name="config_hash_format"),
        CheckConstraint(r"dependency_lock_hash IS NULL OR dependency_lock_hash ~ '^[0-9a-f]{64}$'",
                        name="dependency_lock_hash_format"),
        CheckConstraint(r"content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        CheckConstraint("octet_length(quality::text) <= 32768", name="quality_size"),
        ForeignKeyConstraint(["manifest_artifact_id"], ["app.artifacts.id"],
                             name="fk_dataset_versions_manifest_artifact", ondelete="RESTRICT"),
        ForeignKeyConstraint(["supersedes_id", "dataset_key"],
                             ["app.dataset_versions.id", "app.dataset_versions.dataset_key"],
                             name="fk_dataset_versions_supersedes", ondelete="RESTRICT"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    dataset_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'staged'"))
    start_date: Mapped[date] = mapped_column(Date(), nullable=False)
    end_date: Mapped[date] = mapped_column(Date(), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(80), nullable=False)
    code_commit: Mapped[str | None] = mapped_column(String(64))
    config_hash: Mapped[str | None] = mapped_column(String(64))
    dependency_lock_hash: Mapped[str | None] = mapped_column(String(64))
    manifest_artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    supersedes_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DatasetMetric(Base):
    """Member metric registry for a version; observations may only reference members.

    NI-031 binds the member metric UUID to its registered definition: an
    unregistered metric id is rejected by the referential FK.
    """

    __tablename__ = "dataset_metrics"
    __table_args__ = (
        ForeignKeyConstraint(["dataset_version_id"], ["app.dataset_versions.id"],
                             name="fk_dataset_metrics_version", ondelete="RESTRICT"),
        ForeignKeyConstraint(["metric_definition_id"], ["app.metric_definitions.id"],
                             name="fk_dataset_metrics_metric_definition", ondelete="RESTRICT"),
        Index("ix_dataset_metrics_metric_definition", "metric_definition_id"),
    )

    dataset_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    metric_definition_id: Mapped[UUID] = mapped_column(primary_key=True)


class DatasetInput(Base):
    """raw/normalized/price/sql/config lineage; ingestion_run FK arrives with NI-030."""

    __tablename__ = "dataset_inputs"
    __table_args__ = (
        CheckConstraint("role IN ('raw','normalized','price','sql','config')", name="role"),
        CheckConstraint(r"query_hash IS NULL OR query_hash ~ '^[0-9a-f]{64}$'",
                        name="query_hash_format"),
        ForeignKeyConstraint(["dataset_version_id"], ["app.dataset_versions.id"],
                             name="fk_dataset_inputs_version", ondelete="RESTRICT"),
        ForeignKeyConstraint(["artifact_id"], ["app.artifacts.id"],
                             name="fk_dataset_inputs_artifact", ondelete="RESTRICT"),
        ForeignKeyConstraint(["source_id"], ["app.sources.id"], name="fk_dataset_inputs_source"),
        Index("ix_dataset_inputs_artifact", "artifact_id"),
    )

    dataset_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    artifact_id: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(40))
    ingestion_run_id: Mapped[UUID | None]
    query_hash: Mapped[str | None] = mapped_column(String(64))


class MetricObservation(Base):
    """Half-open UTC period point with exact NUMERIC value and explicit quality."""

    __tablename__ = "metric_observations"
    __table_args__ = (
        CheckConstraint("period_end > period_start", name="period"),
        CheckConstraint("quality_status IN ('verified','missing','unavailable')",
                        name="quality_status"),
        CheckConstraint("bound_kind IN ('exact','estimate','lower','upper')", name="bound_kind"),
        CheckConstraint(
            "(quality_status IN ('missing','unavailable')) = (value IS NULL)",
            name="value_null_consistency",
        ),
        CheckConstraint("(bound_kind IS NULL) = (value IS NULL)", name="bound_null_consistency"),
        CheckConstraint("value IS NOT NULL OR quality ? 'reason'", name="null_reason"),
        CheckConstraint(r"dimensions_hash ~ '^[0-9a-f]{64}$'", name="dimensions_hash_format"),
        CheckConstraint("octet_length(dimensions::text) <= 4096", name="dimensions_size"),
        CheckConstraint("octet_length(quality::text) <= 4096", name="quality_size"),
        ForeignKeyConstraint(
            ["dataset_version_id", "metric_definition_id"],
            ["app.dataset_metrics.dataset_version_id", "app.dataset_metrics.metric_definition_id"],
            name="fk_metric_observations_member", ondelete="RESTRICT",
        ),
        Index("ix_metric_observations_window", "dataset_version_id", "period_start"),
    )

    dataset_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    metric_definition_id: Mapped[UUID] = mapped_column(primary_key=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    dimensions_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    value: Mapped[Decimal | None] = mapped_column(Numeric(78, 30))
    quality_status: Mapped[str] = mapped_column(String(20), nullable=False)
    bound_kind: Mapped[str | None] = mapped_column(String(20))
    source_record_ref: Mapped[str | None] = mapped_column(String(200))
    quality: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class ActiveDataset(Base):
    """Single approved active pointer per dataset key; history stays readable."""

    __tablename__ = "active_datasets"
    __table_args__ = (
        CheckConstraint(
            r"dataset_key ~ '^[a-z0-9][a-z0-9-]{0,38}(\.[a-z0-9][a-z0-9-]{0,38}){0,2}$'",
            name="key_format",
        ),
        ForeignKeyConstraint(
            ["dataset_version_id", "dataset_key"],
            ["app.dataset_versions.id", "app.dataset_versions.dataset_key"],
            name="fk_active_datasets_version", ondelete="RESTRICT",
        ),
    )

    dataset_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    dataset_version_id: Mapped[UUID] = mapped_column(nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   server_default=func.now())


class MetricDefinition(Base):
    """Immutable versioned metric definition row (NI-029 registry).

    Append-only: no UPDATE/DELETE grant exists; a definition change appends a
    new (metric_id, version). The dataset_metrics FK stays with NI-031.
    """

    __tablename__ = "metric_definitions"
    __table_args__ = (
        UniqueConstraint("metric_id", "version", name="uq_metric_definitions_metric_version"),
        CheckConstraint(r"metric_id ~ '^[a-z][a-z0-9_]{2,79}$'", name="metric_id"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("name <> ''", name="name_nonempty"),
        CheckConstraint("unit <> ''", name="unit_nonempty"),
        CheckConstraint("frequency IN ('daily','weekly','monthly','snapshot')", name="frequency"),
        CheckConstraint("economic_scope <> ''", name="scope_nonempty"),
        CheckConstraint("formula_key <> ''", name="formula_nonempty"),
        CheckConstraint("octet_length(definition::text) <= 16384", name="definition_size"),
        CheckConstraint("octet_length(quality_rules::text) <= 8192", name="quality_rules_size"),
        ForeignKeyConstraint(["source_id"], ["app.sources.id"],
                             name="fk_metric_definitions_source", ondelete="RESTRICT"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    metric_id: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    economic_scope: Mapped[str] = mapped_column(String(200), nullable=False)
    formula_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(40))
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    quality_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())


class ChartDefinition(Base):
    """Immutable versioned chart definition row (NI-031 registry).

    Append-only: no UPDATE/DELETE grant exists; a chart change appends a new
    (chart_id, version). data_status is the honest advertisement: only
    'available' charts are advertised as live; unavailable charts carry a
    recorded reason. Rendering is fully described by the definition
    (visualization, bindings, units, filters, ranges, renderer version), so a
    new supported definition needs no new page implementation.
    """

    __tablename__ = "chart_definitions"
    __table_args__ = (
        UniqueConstraint("chart_id", "version", name="uq_chart_definitions_chart_version"),
        CheckConstraint(r"chart_id ~ '^[a-z][a-z0-9-]{2,79}$'", name="chart_id"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("title <> ''", name="title_nonempty"),
        CheckConstraint("description <> ''", name="description_nonempty"),
        CheckConstraint("category IN ('activity','fees','treasury','supply','model')",
                        name="category"),
        CheckConstraint("visualization_type IN ('line','area','bar','scatter','panels')",
                        name="visualization_type"),
        CheckConstraint("data_status IN ('available','unavailable')", name="data_status"),
        CheckConstraint("(data_status = 'available') = (unavailable_reason IS NULL) "
                        "AND (unavailable_reason IS NULL OR unavailable_reason <> '')",
                        name="unavailable_reason"),
        CheckConstraint("update_frequency IN ('daily','weekly','monthly','snapshot')",
                        name="frequency"),
        CheckConstraint("renderer_version <> ''", name="renderer_nonempty"),
        CheckConstraint("octet_length(allowed_ranges::text) <= 1024", name="allowed_ranges_size"),
        CheckConstraint("octet_length(filter_schema::text) <= 4096", name="filter_schema_size"),
        CheckConstraint("octet_length(unit_schema::text) <= 1024", name="unit_schema_size"),
        CheckConstraint("octet_length(metric_definition_ids::text) <= 4096",
                        name="metric_ids_size"),
        CheckConstraint("octet_length(source_lineage::text) <= 2048", name="source_lineage_size"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    chart_id: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    visualization_type: Mapped[str] = mapped_column(String(40), nullable=False)
    data_status: Mapped[str] = mapped_column(String(20), nullable=False)
    unavailable_reason: Mapped[str | None] = mapped_column(String(500))
    update_frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    allowed_ranges: Mapped[dict] = mapped_column(JSONB, nullable=False)
    filter_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    unit_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metric_definition_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    source_lineage: Mapped[dict] = mapped_column(JSONB, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())


class ChartMetric(Base):
    """Chart/metric binding junction; required/optional series roles (NI-031)."""

    __tablename__ = "chart_metrics"
    __table_args__ = (
        CheckConstraint("series_role IN ('required_primary','required_secondary',"
                        "'required_x_axis','required_y_axis','optional_overlay',"
                        "'optional_context')", name="series_role"),
        ForeignKeyConstraint(["chart_definition_version_id"], ["app.chart_definitions.id"],
                             name="fk_chart_metrics_chart", ondelete="RESTRICT"),
        ForeignKeyConstraint(["metric_definition_id"], ["app.metric_definitions.id"],
                             name="fk_chart_metrics_metric", ondelete="RESTRICT"),
        Index("ix_chart_metrics_metric", "metric_definition_id"),
    )

    chart_definition_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    metric_definition_id: Mapped[UUID] = mapped_column(primary_key=True)
    series_role: Mapped[str] = mapped_column(String(40), primary_key=True)


class IngestionCheckpoint(Base):
    """Per-source refresh resume cursor and last-run state (NI-030)."""

    __tablename__ = "ingestion_checkpoints"
    __table_args__ = (
        CheckConstraint("last_height IS NULL OR last_height >= 0", name="height_nonnegative"),
        CheckConstraint(
            r"last_block_hash IS NULL OR last_block_hash ~ '^[1-9A-HJ-NP-Za-km-z]{32,44}$'",
            name="block_hash_format"),
        CheckConstraint("last_failure_kind IS NULL OR last_failure_kind <> ''",
                        name="failure_kind_nonempty"),
        CheckConstraint("consecutive_failures >= 0", name="consecutive_nonnegative"),
        CheckConstraint("(last_height IS NULL) = (last_block_hash IS NULL)",
                        name="cursor_pair"),
        ForeignKeyConstraint(["source_id"], ["app.sources.id"], name="fk_ingestion_checkpoints_source", ondelete="RESTRICT"),
    )

    source_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_height: Mapped[int | None] = mapped_column(BigInteger)
    last_block_hash: Mapped[str | None] = mapped_column(String(44))
    last_header_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_kind: Mapped[str | None] = mapped_column(String(40))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False,
                                                      server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())


class IngestionDailyCounter(Base):
    """Persisted per-source daily request counters for the day budget (NI-030)."""

    __tablename__ = "ingestion_daily_counters"
    __table_args__ = (
        CheckConstraint("request_count >= 0", name="request_nonnegative"),
        CheckConstraint("success_count >= 0", name="success_nonnegative"),
        CheckConstraint("success_count <= request_count", name="success_bounded"),
        ForeignKeyConstraint(["source_id"], ["app.sources.id"], name="fk_ingestion_daily_counters_source", ondelete="RESTRICT"),
    )

    source_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 server_default=func.now())


class ModelRun(Base):
    """One published immutable model run (NI-054).

    Mirrors migration 0010 exactly (DATABASE_SCHEMA.md "model_runs", the
    recorded NI-054 implemented shape): write-once rows written only by the
    operator publication gate, published-only by CHECK, with the full manifest
    set as JSONB and the denormalized identity columns re-asserted by CHECK
    constraints against the stored manifests. near_operator writes; near_app
    reads for the public model APIs; no UPDATE/DELETE grant exists for any
    role.
    """

    __tablename__ = "model_runs"
    __table_args__ = (
        CheckConstraint(r"spec_id ~ '^[a-z][a-z0-9_]{2,79}$'", name="spec_id"),
        CheckConstraint("spec_version >= 1", name="spec_version"),
        CheckConstraint("status = 'published'", name="published"),
        CheckConstraint("gate_verdict IN ('READY','READY_WITH_LIMITS')", name="gate_verdict"),
        CheckConstraint(r"code_commit ~ '^[0-9a-f]{40}$|^[0-9a-f]{64}$'", name="code_commit"),
        CheckConstraint(r"dependency_lock_sha256 ~ '^[0-9a-f]{64}$'", name="lock_hash"),
        CheckConstraint(r"coefficient_rtol ~ '^[0-9]+(\.[0-9]+)?$' "
                        r"AND coefficient_atol ~ '^[0-9]+(\.[0-9]+)?$'",
                        name="tolerance_format"),
        CheckConstraint("sample_end_exclusive > sample_start", name="sample_window"),
        CheckConstraint("nobs > 0", name="nobs"),
        CheckConstraint("published_by <> ''", name="published_by"),
        CheckConstraint("octet_length(manifests::text) <= 4194304", name="manifests_size"),
        CheckConstraint("manifests ? 'fit_manifest' AND manifests ? 'diagnostics_report' "
                        "AND manifests ? 'readiness_report'", name="manifests_keys"),
        CheckConstraint("artifacts ? 'fit_manifest' AND artifacts ? 'diagnostics_report' "
                        "AND artifacts ? 'readiness_report' "
                        "AND artifacts ? 'publication_approval'", name="artifacts_keys"),
        CheckConstraint("spec_id = manifests->'fit_manifest'->'model'->>'model_id'",
                        name="spec_id_matches"),
        CheckConstraint("spec_version = "
                        "(manifests->'fit_manifest'->'model'->>'model_version')::int",
                        name="spec_version_matches"),
        CheckConstraint("gate_verdict = "
                        "manifests->'fit_manifest'->'admission'->>'verdict'",
                        name="gate_verdict_matches"),
        CheckConstraint("code_commit = "
                        "manifests->'fit_manifest'->'inputs'->>'code_commit'",
                        name="code_commit_matches"),
        CheckConstraint("dependency_lock_sha256 = "
                        "manifests->'fit_manifest'->'inputs'->'dependency_lock'->>'sha256'",
                        name="lock_hash_matches"),
        CheckConstraint("nobs = (manifests->'fit_manifest'->'sample'->>'nobs')::int",
                        name="nobs_matches"),
        CheckConstraint("sample_start = (manifests->'fit_manifest'->'sample'->'window'"
                        "->>'start')::date AND sample_end_exclusive = "
                        "(manifests->'fit_manifest'->'sample'->'window'"
                        "->>'end_exclusive')::date", name="sample_window_matches"),
        CheckConstraint("coefficient_rtol = manifests->'fit_manifest'->'reproduction'"
                        "->>'coefficient_rtol' AND coefficient_atol = "
                        "manifests->'fit_manifest'->'reproduction'"
                        "->>'coefficient_atol'", name="tolerance_matches"),
        Index("ix_model_runs_spec_published", "spec_id", "published_at"),
        Index("ix_model_runs_published_at", "published_at"),
    )

    run_id: Mapped[UUID] = mapped_column(primary_key=True)
    spec_id: Mapped[str] = mapped_column(String(80), nullable=False)
    spec_version: Mapped[int] = mapped_column(Integer, nullable=False)
    gate_verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    manifests: Mapped[dict] = mapped_column(JSONB, nullable=False)
    artifacts: Mapped[dict] = mapped_column(JSONB, nullable=False)
    publication_approval: Mapped[dict] = mapped_column(JSONB, nullable=False)
    code_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_lock_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    coefficient_rtol: Mapped[str] = mapped_column(String(40), nullable=False)
    coefficient_atol: Mapped[str] = mapped_column(String(40), nullable=False)
    sample_start: Mapped[date] = mapped_column(Date, nullable=False)
    sample_end_exclusive: Mapped[date] = mapped_column(Date, nullable=False)
    nobs: Mapped[int] = mapped_column(Integer, nullable=False)
    published_by: Mapped[str] = mapped_column(String(120), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   nullable=False, server_default=func.now())


class ResearchPublication(Base):
    """One operator-seeded public research release (NI-045).

    Mirrors migration 0015 exactly (DATABASE_SCHEMA.md "research_publications",
    the implemented shape): an immutable (slug, version) row whose ``content``
    is the canonical editor document JSON the public read route serves and the
    duplicate flow clones into fresh private IDs. Only published rows exist
    (CHECK ``status = 'published'``); near_app reads them with no owner
    predicate, near_operator seeds and deletes, and no role can UPDATE —
    a correction appends a new version or removes the row.
    """

    __tablename__ = "research_publications"
    __table_args__ = (
        CheckConstraint(r"slug ~ '^[a-z0-9][a-z0-9-]{0,79}$'", name="slug"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("title <> ''", name="title_nonempty"),
        CheckConstraint("status = 'published'", name="status"),
        CheckConstraint(r"content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        CheckConstraint("octet_length(content::text) <= 2097152", name="content_size"),
        CheckConstraint("octet_length(evidence_manifest::text) <= 65536",
                        name="manifest_size"),
        UniqueConstraint("slug", "version", name="uq_research_publications_slug_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False,
                                                    server_default=text("'[]'::jsonb"))
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        server_default=text("'published'"))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False, server_default=func.now())


class PublicationModelRun(Base):
    """Binding of one published model run into one publication (NI-045).

    Both sides are published rows; the run FK is RESTRICT because published
    runs are immutable (migration 0010). near_app may read a binding only
    while its publication is published (RLS policy of migration 0015).
    """

    __tablename__ = "publication_model_runs"
    __table_args__ = (
        ForeignKeyConstraint(["publication_id"], ["app.research_publications.id"],
                             name="fk_publication_model_runs_publication",
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["model_run_id"], ["app.model_runs.run_id"],
                             name="fk_publication_model_runs_model_run",
                             ondelete="RESTRICT"),
    )


    publication_id: Mapped[UUID] = mapped_column(primary_key=True)
    model_run_id: Mapped[UUID] = mapped_column(primary_key=True)
