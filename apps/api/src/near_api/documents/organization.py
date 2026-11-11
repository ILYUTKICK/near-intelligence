"""Private document organization metadata (NI-072): tags and favorite flag.

Lightweight organization OUTSIDE the scientific content: bounded private tags
and one favorite flag per owned document, stored in the owner-scoped
``app.document_organization`` table (migration 0014) — never inside
``document_versions.content`` and never through the revision service, so a
metadata edit mints no revision, rewrites no frozen evidence hash and never
touches ``documents.updated_at`` (the list order stays stable under tagging;
this module's writes cannot reorder, re-version or re-date a document).

Tag normalization rule (documented in API_SPECIFICATION.md and tested):
whitespace-trim, then lowercase (Python ``str.lower``), then
duplicate-collapse preserving first occurrence. After normalization a tag is
1..40 chars; a document carries at most :data:`MAX_TAGS_PER_DOCUMENT` tags.
The database CHECK (``app.is_valid_tag_set``) re-validates the same bounds on
every write, so even a raw-SQL path cannot store an unbounded/unnormalized
tag set.

Ownership follows the NI-019 invariants: the organization of a document is
reachable only through the owned document row (compositional check via
:func:`near_api.repositories.documents.get_document`); absent and not-owned
documents raise the same :class:`ResourceNotFound` (one generic 404). Every
statement runs inside the caller's ``principal_transaction`` so RLS
independently scopes the rows.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Connection, select

from near_api.auth.principal import Principal
from near_api.db.models import DocumentOrganization
from near_api.db.security import ResourceNotFound
from near_api.documents.schema import DocumentSchemaError
from near_api.repositories.documents import get_document

MAX_TAGS_PER_DOCUMENT = 20
"""Hard cap on tags stored per document (checked again by the DB CHECK)."""

MAX_TAG_LENGTH = 40
"""Hard cap on one normalized tag's length in characters."""

MAX_FILTER_TAGS = 5
"""Hard cap on tags combined in one list filter request (AND semantics)."""


class OrganizationValidationError(DocumentSchemaError):
    """A tag payload violates the bounded normalized rules (HTTP 422)."""


@dataclass(frozen=True)
class DocumentOrganizationState:
    """The verified owner's organization metadata for one document.

    ``updated_at`` is this metadata row's own recency (app.document_
    organization), never the document's: organization edits cannot reorder
    the updated_at-ordered document list.
    """

    document_id: UUID
    tags: tuple[str, ...]
    favorite: bool
    updated_at: datetime


def normalize_tags(raw_tags: list[str]) -> tuple[str, ...]:
    """Normalize, validate and dedupe raw tag text (trim + lower + dedupe).

    Whitespace-only text is rejected explicitly (never silently dropped), so
    a client cannot mistake a dropped tag for a stored one.
    """
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw_tags:
        tag = raw_tag.strip().lower()
        if not tag:
            raise OrganizationValidationError(
                "Tags must contain a nonempty value after trimming whitespace",
                [("tags", "empty_tag")])
        if len(tag) > MAX_TAG_LENGTH:
            raise OrganizationValidationError(
                f"Each tag must be at most {MAX_TAG_LENGTH} characters after "
                "normalization",
                [("tags", "tag_too_long")])
        if tag not in seen:
            normalized.append(tag)
            seen.add(tag)
    if len(normalized) > MAX_TAGS_PER_DOCUMENT:
        raise OrganizationValidationError(
            f"A document carries at most {MAX_TAGS_PER_DOCUMENT} distinct tags",
            [("tags", "too_many_tags")])
    return tuple(normalized)


def get_organization(connection: Connection, principal: Principal,
                     document_id: UUID) -> DocumentOrganizationState:
    """Return the owned document's organization state (empty when unset).

    The document must exist and be owned, or the same generic 404-equivalent
    is raised; a document without organization rows carries no tags and is
    not favorited (honest defaults, never fabricated metadata).
    """
    get_document(connection, principal, document_id)
    return _load_state(connection, principal, document_id)


def update_organization(connection: Connection, principal: Principal, document_id: UUID, *,
                        tags: list[str] | None = None,
                        favorite: bool | None = None) -> DocumentOrganizationState:
    """Merge organization metadata on an owned document (PATCH semantics).

    ``tags``/``favorite`` set exactly the provided fields; ``None`` leaves a
    field unchanged, so a favorite toggle never needs to resend tags and a
    tag edit never needs to resend the favorite. Passing ``tags=[]`` clears
    the tags. The upsert is one statement on the caller's open principal
    transaction (RETURNING carries the stored state including the row's own
    updated_at after any metadata-recency touch); RLS and the composite FK
    independently keep the row owner-scoped and document-bound. No statement
    here touches ``app.documents``, so no revision and no list reorder can
    result from organization metadata.
    """
    get_document(connection, principal, document_id)
    current = _load_state(connection, principal, document_id)
    new_tags = normalize_tags(tags) if tags is not None else current.tags
    new_favorite = current.favorite if favorite is None else favorite
    row = connection.execute(
        DocumentOrganization.__table__.insert()
        .values(document_id=document_id, owner_id=principal.id,
                tags=list(new_tags), favorite=new_favorite)
        .on_conflict_do_update(
            index_elements=[DocumentOrganization.document_id],
            set_={"tags": list(new_tags), "favorite": new_favorite})
        .returning(DocumentOrganization.tags, DocumentOrganization.favorite,
                   DocumentOrganization.updated_at)
    ).first()
    if row is None:  # pragma: no cover - RETURNING after a verified upsert
        raise ResourceNotFound("Resource does not exist for this owner")
    return DocumentOrganizationState(document_id=document_id, tags=tuple(row.tags),
                                     favorite=bool(row.favorite), updated_at=row.updated_at)


def _load_state(connection: Connection, principal: Principal,
                document_id: UUID) -> DocumentOrganizationState:
    row = connection.execute(
        select(DocumentOrganization.tags, DocumentOrganization.favorite,
               DocumentOrganization.updated_at)
        .where(DocumentOrganization.document_id == document_id,
               DocumentOrganization.owner_id == principal.id)
    ).first()
    if row is None:
        return DocumentOrganizationState(document_id=document_id, tags=(), favorite=False,
                                         updated_at=datetime.now(UTC))
    return DocumentOrganizationState(document_id=document_id, tags=tuple(row.tags),
                                     favorite=bool(row.favorite), updated_at=row.updated_at)
