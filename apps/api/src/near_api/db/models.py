"""Schema declarations mirroring the versioned Alembic migrations.

NI-003 owns the identity tables; NI-019 adds the private document chain
(documents, document_versions, document_blocks) that the ownership/RLS layer
operates on. Remaining domain tables belong to their owning tasks and must
keep these declarations in sync for the Alembic metadata drift check.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
