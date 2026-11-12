"""Owner-scoped repository for the private document chain (NI-019).

The reference implementation of the ownership invariants every future
repository follows: the owner is the verified principal (payload owner fields
are rejected via :func:`verified_owner_id`), nested references are checked
compositionally — a version is reachable only through an owned document, a
block only through an owned version — and list/search pagination is scoped by
owner before LIMIT/OFFSET through :func:`scoped_page`. Absent and not-owned
resources raise the same :class:`ResourceNotFound`.

Document schema/content validation, CAS revision conflict handling and
projection regeneration belong to the document revision service (NI-036);
delete cascades and scientific-data retention follow DATABASE_SCHEMA.md.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Connection, and_, delete, false, func, insert, or_, select, update
from sqlalchemy.sql.elements import ColumnElement

from near_api.auth.principal import Principal
from near_api.db.models import Document, DocumentBlock, DocumentOrganization, DocumentVersion
from near_api.db.security import (
    Page,
    ResourceNotFound,
    one_or_not_found,
    owner_scope,
    scoped_page,
    verified_owner_id,
)


@dataclass(frozen=True)
class DocumentRow:
    id: UUID
    owner_id: UUID
    title: str
    revision: int
    schema_version: int
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime
    # NI-072 organization metadata, joined from app.document_organization.
    # Honest defaults for callers that select only the base columns: a
    # document without an organization row has no tags and is not favorited.
    tags: tuple[str, ...] = ()
    favorite: bool = False


@dataclass(frozen=True)
class DocumentVersionRow:
    id: UUID
    document_id: UUID
    owner_id: UUID
    revision: int
    schema_version: int
    content: dict
    resolved_contexts: dict | None
    content_sha256: str
    created_at: datetime


@dataclass(frozen=True)
class DocumentBlockRow:
    document_version_id: UUID
    document_id: UUID
    owner_id: UUID
    block_id: UUID
    parent_block_id: UUID | None
    position: int
    block_type: str
    attrs: dict


def _document_row(mapping) -> DocumentRow:
    data = dict(mapping)
    # Organization columns (when selected) carry the LEFT JOIN's NULL for a
    # document without metadata; map them to the honest empty defaults.
    data["tags"] = tuple(data.pop("org_tags", None) or ())
    data["favorite"] = bool(data.pop("org_favorite", None) or False)
    return DocumentRow(**data)


def _version_row(mapping) -> DocumentVersionRow:
    return DocumentVersionRow(**mapping)


def _block_row(mapping) -> DocumentBlockRow:
    return DocumentBlockRow(**mapping)


_DOCUMENT_COLUMNS = (
    Document.id, Document.owner_id, Document.title, Document.revision,
    Document.schema_version, Document.current_version_id, Document.created_at, Document.updated_at,
)
_VERSION_COLUMNS = (
    DocumentVersion.id, DocumentVersion.document_id, DocumentVersion.owner_id,
    DocumentVersion.revision, DocumentVersion.schema_version, DocumentVersion.content,
    DocumentVersion.resolved_contexts, DocumentVersion.content_sha256, DocumentVersion.created_at,
)
_BLOCK_COLUMNS = (
    DocumentBlock.document_version_id, DocumentBlock.document_id, DocumentBlock.owner_id,
    DocumentBlock.block_id, DocumentBlock.parent_block_id, DocumentBlock.position,
    DocumentBlock.block_type, DocumentBlock.attrs,
)


def create_document(connection: Connection, principal: Principal, *, title: str,
                    schema_version: int, document_id: UUID | None = None,
                    owner_id: UUID | None = None) -> UUID:
    """Create a document owned by the principal; return its id.

    ``owner_id`` accepts only ``None`` or the principal's id: a request that
    tries to create rows for another user is rejected, never silently
    redirected.
    """
    owner = verified_owner_id(owner_id, principal.id)
    document_id = document_id if document_id is not None else uuid4()
    connection.execute(insert(Document).values(
        id=document_id, owner_id=owner, title=title, schema_version=schema_version))
    return document_id


def get_document(connection: Connection, principal: Principal,
                 document_id: UUID) -> DocumentRow:
    """Return the document only when it exists and is owned; else 404-equivalent."""
    row = connection.execute(
        select(*_DOCUMENT_COLUMNS).where(Document.id == document_id,
                                         owner_scope(Document.owner_id, principal.id))
    ).mappings().first()
    return _document_row(one_or_not_found(row))


def list_documents(connection: Connection, principal: Principal, *, search: str | None = None,
                   tags: Sequence[str] | None = None, favorite: bool | None = None,
                   limit: int | None = None, offset: int | None = None) -> Page:
    """List/search the principal's documents, newest first, owner-scoped.

    ``search`` is a case-insensitive substring match; wildcard characters in
    the caller's text are escaped so the pattern stays a literal substring.
    ``tags`` (NI-072) narrows to documents carrying EVERY listed tag — the
    normalized values are exact array elements, never a substring match.
    ``favorite`` filters to favorited (True) or non-favorited (False)
    documents; a document without an organization row is never favorited.
    Owner scoping and every filter are applied before pagination inside
    :func:`scoped_page`, so the count and the page share one scope.

    The list order stays ``updated_at DESC, id`` and the organization LEFT
    JOIN never reorders or multiplies rows (at most one metadata row per
    document via its primary key); metadata edits write only
    ``app.document_organization``, so tagging cannot move a document's
    position or recency.
    """
    query = select(*_DOCUMENT_COLUMNS,
                   DocumentOrganization.tags.label("org_tags"),
                   DocumentOrganization.favorite.label("org_favorite")).outerjoin(
        DocumentOrganization, DocumentOrganization.document_id == Document.id)
    if search is not None:
        query = query.where(Document.title.ilike(_literal_substring(search), escape="\\"))
    if tags:
        for tag in tags:
            query = query.where(DocumentOrganization.tags.contains([tag]))
    if favorite is not None:
        if favorite:
            query = query.where(DocumentOrganization.favorite.is_(True))
        else:
            # "Not favorited" includes documents without any metadata row.
            query = query.where(or_(DocumentOrganization.document_id.is_(None),
                                    DocumentOrganization.favorite.is_(false())))
    page = scoped_page(connection,
                       query.order_by(Document.updated_at.desc(), Document.id),
                       owner_scope(Document.owner_id, principal.id),
                       limit=limit, offset=offset)
    return Page(items=tuple(_document_row(item) for item in page.items),
                total=page.total, limit=page.limit, offset=page.offset)


def rename_document(connection: Connection, principal: Principal, document_id: UUID, *,
                    title: str) -> DocumentRow:
    """Rename an owned document; a foreign or missing id is the same 404."""
    row = connection.execute(
        update(Document)
        .where(Document.id == document_id, owner_scope(Document.owner_id, principal.id))
        .values(title=title)
        .returning(*_DOCUMENT_COLUMNS)
    ).mappings().first()
    return _document_row(one_or_not_found(row))


def delete_document(connection: Connection, principal: Principal, document_id: UUID) -> None:
    """Delete an owned document; versions and blocks cascade with it.

    Foreign and missing ids are indistinguishable (one 404); shared
    scientific data referenced by the document is untouched (RESTRICT FKs of
    the owning tasks).
    """
    row = connection.execute(
        delete(Document)
        .where(Document.id == document_id, owner_scope(Document.owner_id, principal.id))
        .returning(Document.id)
    ).first()
    if row is None:
        raise ResourceNotFound("Resource does not exist for this owner")


def create_version(connection: Connection, principal: Principal, document_id: UUID, *,
                   content: dict, content_sha256: str, resolved_contexts: dict | None = None,
                   version_id: UUID | None = None, owner_id: UUID | None = None) -> UUID:
    """Append an immutable revision to an owned document and move the pointer.

    Compositional check first: the document must be visible to this owner or
    the whole operation is a 404-equivalent. The new version inherits the
    document's revision number and schema version; the document's revision
    counter and current-version pointer advance in the same transaction. The
    composite FKs make it impossible to attach a version to a foreign
    document even with raw SQL.
    """
    owner = verified_owner_id(owner_id, principal.id)
    document = connection.execute(
        select(Document.revision, Document.schema_version)
        .where(Document.id == document_id, owner_scope(Document.owner_id, principal.id))
    ).first()
    if document is None:
        raise ResourceNotFound("Resource does not exist for this owner")
    version_id = version_id if version_id is not None else uuid4()
    connection.execute(insert(DocumentVersion).values(
        id=version_id, document_id=document_id, owner_id=owner,
        revision=document.revision, schema_version=document.schema_version,
        content=content, resolved_contexts=resolved_contexts,
        content_sha256=content_sha256))
    connection.execute(
        update(Document)
        .where(Document.id == document_id, owner_scope(Document.owner_id, principal.id))
        .values(revision=document.revision + 1, current_version_id=version_id))
    return version_id


def get_version(connection: Connection, principal: Principal, document_id: UUID,
                version_id: UUID) -> DocumentVersionRow:
    """Return a version only through its owned parent document.

    The join requires the (version, document, owner) triple to line up with
    one owned document row: knowing a version UUID grants no access, and a
    version id from another document never resolves.
    """
    row = connection.execute(
        select(*_VERSION_COLUMNS)
        .join(Document, and_(Document.id == DocumentVersion.document_id,
                             Document.owner_id == DocumentVersion.owner_id))
        .where(DocumentVersion.id == version_id,
               DocumentVersion.document_id == document_id,
               _owned_document(principal.id))
    ).mappings().first()
    return _version_row(one_or_not_found(row))


def list_versions(connection: Connection, principal: Principal, document_id: UUID, *,
                  limit: int | None = None, offset: int | None = None) -> Page:
    """List an owned document's revisions oldest-first; foreign doc is a 404."""
    get_document(connection, principal, document_id)
    query = select(*_VERSION_COLUMNS).where(DocumentVersion.document_id == document_id)
    page = scoped_page(connection,
                       query.order_by(DocumentVersion.revision),
                       owner_scope(DocumentVersion.owner_id, principal.id),
                       limit=limit, offset=offset)
    return Page(items=tuple(_version_row(item) for item in page.items),
                total=page.total, limit=page.limit, offset=page.offset)


def add_block(connection: Connection, principal: Principal, document_id: UUID,
              version_id: UUID, *, block_id: UUID, block_type: str, position: int,
              parent_block_id: UUID | None = None, attrs: dict | None = None,
              owner_id: UUID | None = None) -> UUID:
    """Insert a projection block row under an owned version.

    The version is resolved compositionally first; the row's owner/document/
    version columns are taken from that verified chain, so a payload cannot
    attach a block to another user's version or document (composite FKs back
    this at the database even for raw SQL).
    """
    owner = verified_owner_id(owner_id, principal.id)
    get_version(connection, principal, document_id, version_id)
    connection.execute(insert(DocumentBlock).values(
        document_version_id=version_id, document_id=document_id, owner_id=owner,
        block_id=block_id, parent_block_id=parent_block_id, position=position,
        block_type=block_type, attrs=attrs if attrs is not None else {}))
    return block_id


def get_block(connection: Connection, principal: Principal, document_id: UUID,
              version_id: UUID, block_id: UUID) -> DocumentBlockRow:
    """Return a block only through its owned version and document."""
    row = connection.execute(
        select(*_BLOCK_COLUMNS)
        .join(DocumentVersion, and_(
            DocumentVersion.id == DocumentBlock.document_version_id,
            DocumentVersion.document_id == DocumentBlock.document_id,
            DocumentVersion.owner_id == DocumentBlock.owner_id))
        .join(Document, and_(Document.id == DocumentVersion.document_id,
                             Document.owner_id == DocumentVersion.owner_id))
        .where(DocumentBlock.document_version_id == version_id,
               DocumentBlock.block_id == block_id,
               DocumentBlock.document_id == document_id,
               _owned_document(principal.id))
    ).mappings().first()
    return _block_row(one_or_not_found(row))


def list_blocks(connection: Connection, principal: Principal, document_id: UUID,
                version_id: UUID, *, limit: int | None = None,
                offset: int | None = None) -> Page:
    """List a version's blocks in position order; foreign parents are a 404."""
    get_version(connection, principal, document_id, version_id)
    query = select(*_BLOCK_COLUMNS).where(
        DocumentBlock.document_version_id == version_id,
        DocumentBlock.document_id == document_id)
    page = scoped_page(connection,
                       query.order_by(DocumentBlock.position),
                       owner_scope(DocumentBlock.owner_id, principal.id),
                       limit=limit, offset=offset)
    return Page(items=tuple(_block_row(item) for item in page.items),
                total=page.total, limit=page.limit, offset=page.offset)


def _owned_document(principal_id: UUID) -> ColumnElement[bool]:
    return owner_scope(Document.owner_id, principal_id)


def _literal_substring(search: str) -> str:
    """Escape LIKE wildcards so user text matches as a literal substring."""
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
