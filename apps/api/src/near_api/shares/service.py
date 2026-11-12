"""Owner-scoped share store and the token-gated public reader (NI-060).

The HTTP-facing service of the share capability (ADR-021). One row of
``app.document_shares`` is one share; the owner functions run inside a
transaction-local verified identity (:func:`near_api.db.security.
principal_transaction`), the public reader runs WITHOUT any identity
(:func:`near_api.db.session.user_transaction`) and resolves rows only by the
SHA-256 digest of the path token. RLS (migration 0017) independently hides
foreign rows from authenticated sessions and revoked/expired rows from the
capability plane, so absent, foreign, revoked, expired and malformed tokens
all end as one generic deny — never an oracle.

Creation freezes the publication in ONE transaction: the NI-056 export IR of
the CURRENT acknowledged revision is built (fail-closed on every pin), the
pure narrowing transform (:mod:`near_api.shares.projection`) produces the
public projection, its canonical bytes and SHA-256 are compared against the
consented preview hash, and the row is inserted with the digest of a freshly
generated high-entropy token. The raw token leaves this module exactly once
(in the create outcome) and is never persisted or logged.

Reading is honest by construction: every public request re-checks the live
state (active, unexpired, bytes present, byte identity verified) BEFORE the
stored projection is served — revocation and expiry deny on the next request
with no stale path, no signed URL and no cache to poison.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, func, insert, select, text

from near_api.auth.principal import Principal
from near_api.db.models import DocumentShare
from near_api.db.security import ResourceNotFound, principal_transaction
from near_api.db.session import user_transaction
from near_api.documents.idempotency import parse_idempotency_key
from near_api.documents.routes import _chart_csv
from near_api.exports.ir import ExportIrError, build_export_ir_in_transaction
from near_api.repositories.documents import DocumentRow, get_document
from near_api.schemas.delivery import ChartViewResponse
from near_api.schemas.share import ShareProjection
from near_api.shares.projection import (
    build_share_projection,
    share_projection_canonical_bytes,
)

SHARE_ROUTE_TEMPLATE = "POST /api/documents/{document_id}/shares"
"""The concrete-URL idempotency route identity (the NI-041 lesson)."""

MAX_PROJECTION_BYTES = 32 * 1024 * 1024
"""The stored-projection cap (mirrored by the migration CHECK): a publication
larger than this is a typed 422 at creation instead of an unbounded row."""

MAX_SHARES_PER_DOCUMENT = 100
"""A bounded share registry per document; every create is a deliberate
consent act, and the owner list stays a single bounded page."""

MAX_EXPIRY_DAYS = 365
"""A consent window beyond one year is refused rather than silently clamped."""

TOKEN_BYTES = 32
"""256 bits of capability entropy (``secrets.token_urlsafe`` -> 43 chars)."""


class ShareNotFound(LookupError):
    """The share is not available (one generic deny for every public state).

    Absent, foreign, revoked, expired, malformed-token and unreadable-bytes
    outcomes all raise (or map to) this single deny shape.
    """


class ShareCorrupt(ShareNotFound):
    """The stored projection does not match its recorded identity — denied."""


class ShareRevisionMismatch(ValueError):
    """The consented revision is not the acknowledged current one (409)."""


class SharePreviewMismatch(ValueError):
    """The consented preview hash does not match the current bytes (409)."""


class ShareScopeMismatch(ValueError):
    """The consented visible scope does not match the current revision (422)."""


class ShareProjectionTooLarge(ValueError):
    """The frozen projection exceeds the stored-projection cap (422)."""


class ShareLimitExceeded(ValueError):
    """The document already carries the maximum number of shares (422)."""


class ShareExpired(ValueError):
    """The requested expiry is invalid (422)."""


@dataclass(frozen=True)
class ShareRow:
    """The lifecycle projection of one share (no bytes, no token hash)."""

    id: UUID
    owner_id: UUID
    document_id: UUID
    document_version_id: UUID
    revision: int
    status: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None

    def reported_status(self, *, now: datetime | None = None) -> str:
        """The honest lifecycle state at read time.

        A row past its expiry reads as ``expired`` until revoked, exactly
        like the export job's read-time TTL semantics; revocation is stored
        and permanent.
        """
        if self.status == "revoked":
            return "revoked"
        if self.expires_at is not None:
            expires_at = self.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= (now or datetime.now(timezone.utc)):
                return "expired"
        return "active"


@dataclass(frozen=True)
class SharePublication:
    """The result of an idempotent share create.

    ``token`` is the raw capability secret of the NON-replay create — it is
    returned once and never stored; a replay carries ``token=None`` because
    the digest cannot give it back.
    """

    share: ShareRow
    token: str | None
    replay: bool

    def share_path(self) -> str | None:
        """The public viewer route while the capability is disclosed."""
        if self.token is None:
            return None
        return f"/share/{self.token}"


@dataclass(frozen=True)
class SharePreview:
    """The exact projection that would be published (owner dialog)."""

    document_id: UUID
    revision: int
    projection: ShareProjection
    projection_sha256: str


# --------------------------------------------------------------------------- #
# Owner plane
# --------------------------------------------------------------------------- #


def preview_share(engine: Engine, principal: Principal,
                  document_id: UUID) -> SharePreview:
    """Build the exact projection the owner is about to consent to.

    Nothing is stored; the run is the create run minus the insert, so the
    preview cannot diverge from what a create of the same revision would
    publish (the create re-verifies the recorded hash).
    """
    with principal_transaction(engine, principal) as connection:
        document = _owned_document(connection, principal, document_id)
        projection, projection_bytes = _build_projection(
            connection, principal, document)
    return SharePreview(
        document_id=document_id, revision=projection.document.revision,
        projection=projection,
        projection_sha256=hashlib.sha256(projection_bytes).hexdigest())


def create_share(engine: Engine, principal: Principal, document_id: UUID,
                 *, acknowledged_revision: int, preview_sha256: str,
                 scope: tuple[int, int, int, int], expires_at: datetime | None,
                 idempotency_key: str | None = None) -> SharePublication:
    """Create (or replay) the share of the owned acknowledged revision.

    One transaction: advisory serialization (key present), the replay check
    over the share row, the frozen projection build (fail-closed on every
    pin), the consent verification (revision, preview hash, scope counts) and
    the insert with a fresh 256-bit token (stored as digest only).
    """
    key = parse_idempotency_key(idempotency_key)
    with principal_transaction(engine, principal) as connection:
        if key is not None:
            _serialize_same_key(connection, principal.id, document_id, key)
            existing = _existing_share(connection, principal.id, document_id, key)
            if existing is not None:
                return SharePublication(share=existing, token=None, replay=True)
        document = _owned_document(connection, principal, document_id)
        if document.revision != acknowledged_revision:
            raise ShareRevisionMismatch(
                "The consented revision is not the document's current "
                "acknowledged revision; review the fresh preview and consent "
                "again")
        projection, projection_bytes = _build_projection(
            connection, principal, document)
        digest = hashlib.sha256(projection_bytes).hexdigest()
        if digest != preview_sha256:
            raise SharePreviewMismatch(
                "The consented preview does not match the revision's current "
                "publication bytes; review the fresh preview and consent again")
        if _scope_counts(projection) != scope:
            raise ShareScopeMismatch(
                "The consented visible scope does not match the revision's "
                "current publication")
        if len(projection_bytes) > MAX_PROJECTION_BYTES:
            raise ShareProjectionTooLarge(
                f"The frozen publication is {len(projection_bytes)} bytes; the "
                f"stored-projection cap is {MAX_PROJECTION_BYTES}")
        _validate_expiry(expires_at)
        _assert_share_limit(connection, principal.id, document_id)
        share_id = uuid4()
        token = secrets.token_urlsafe(TOKEN_BYTES)
        connection.execute(insert(DocumentShare).values(
            id=share_id, owner_id=principal.id, document_id=document_id,
            document_version_id=document.current_version_id,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            revision=projection.document.revision, idempotency_key=key,
            projection=projection_bytes, projection_sha256=digest,
            projection_byte_size=len(projection_bytes), expires_at=expires_at))
        return SharePublication(share=_share_row(connection, principal.id,
                                                 document_id, share_id),
                                token=token, replay=False)


def list_shares(engine: Engine, principal: Principal,
                document_id: UUID) -> tuple[ShareRow, ...]:
    """List the owned document's shares, newest first (bounded)."""
    with principal_transaction(engine, principal) as connection:
        rows = connection.execute(
            select(*_SHARE_COLUMNS)
            .where(DocumentShare.document_id == document_id,
                   DocumentShare.owner_id == principal.id)
            .order_by(DocumentShare.created_at.desc(), DocumentShare.id)
            .limit(MAX_SHARES_PER_DOCUMENT)
        ).mappings().all()
        return tuple(_row_to_share(row) for row in rows)


def revoke_share(engine: Engine, principal: Principal, document_id: UUID,
                 share_id: UUID) -> None:
    """Revoke one owned share: the one-way active -> revoked transition.

    The same UPDATE clears the stored bytes (CHECK-enforced pairing, migration
    0017), so nothing readable remains at the row after the commit; the very
    next request through the token — projection, chart view or CSV — is the
    generic deny.
    """
    with principal_transaction(engine, principal) as connection:
        row = connection.execute(
            select(DocumentShare.status)
            .where(DocumentShare.id == share_id,
                   DocumentShare.document_id == document_id,
                   DocumentShare.owner_id == principal.id)
        ).first()
        if row is None:
            raise ShareNotFound("Share does not exist for this owner")
        if row.status == "revoked":
            return
        connection.execute(
            text("""
                UPDATE app.document_shares
                SET status = 'revoked', revoked_at = now(), updated_at = now(),
                    projection = NULL, projection_sha256 = NULL,
                    projection_byte_size = NULL
                WHERE id = :share_id AND document_id = :document_id
                  AND owner_id = :owner_id AND status = 'active'
            """),
            {"share_id": share_id, "document_id": document_id,
             "owner_id": principal.id})


# --------------------------------------------------------------------------- #
# Capability plane (no identity; token digest only)
# --------------------------------------------------------------------------- #


def read_share_projection(engine: Engine, token: str) -> ShareProjection:
    """Resolve a share token to its frozen projection, or deny.

    Every failure — unknown digest, revoked, expired, corrupt bytes — raises
    :class:`ShareNotFound` (one generic deny; :class:`ShareCorrupt` refines
    it) so no oracle distinguishes the states to a holder.
    """
    projection_bytes = _live_share_bytes(engine, token)
    try:
        return ShareProjection.model_validate_json(projection_bytes)
    except ValueError as error:
        raise ShareCorrupt("Stored share projection is unreadable") from error


def read_share_chart(engine: Engine, token: str,
                     block_id: UUID) -> tuple[ChartViewResponse, str]:
    """Return the frozen chart view and its exact CSV for one shared chart.

    Both assets come from the SAME verified projection bytes (the view is the
    embedded NI-043 reconstruction; the CSV is derived deterministically from
    it), so a token holder sees exactly what the projection pinned.
    """
    projection = read_share_projection(engine, token)
    block = next((item for item in projection.blocks
                  if item.block_type == "liveChart" and item.block_id == block_id),
                 None)
    if block is None:
        raise ShareNotFound("Chart block is not part of this share")
    return block.view, _chart_csv(block.view)


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #

_SHARE_COLUMNS = (
    DocumentShare.id, DocumentShare.owner_id, DocumentShare.document_id,
    DocumentShare.document_version_id, DocumentShare.revision,
    DocumentShare.status, DocumentShare.created_at, DocumentShare.expires_at,
    DocumentShare.revoked_at,
)


def _owned_document(connection: Connection, principal: Principal,
                    document_id: UUID) -> DocumentRow:
    """The owned document whose CURRENT acknowledged revision is published."""
    document = get_document(connection, principal, document_id)
    if document.current_version_id is None:
        raise ResourceNotFound("Resource does not exist for this owner")
    return document


def _build_projection(connection: Connection, principal: Principal,
                      document: DocumentRow) -> tuple[ShareProjection, bytes]:
    """Build the verified IR of the acknowledged revision and narrow it.

    The export IR builder re-checks the acknowledged-revision rule and every
    pin; its typed pin failures propagate (the route maps them to the
    documented 422) — nothing is silently skipped or substituted.
    """
    plan = build_export_ir_in_transaction(connection, principal, document.id,
                                          document.current_version_id)
    projection = build_share_projection(plan)
    return projection, share_projection_canonical_bytes(projection)


def _scope_counts(projection: ShareProjection) -> tuple[int, int, int, int]:
    return (
        sum(1 for block in projection.blocks if block.block_type == "liveChart"),
        sum(1 for block in projection.blocks if block.block_type == "dataTable"),
        sum(1 for block in projection.blocks if block.block_type == "insight"),
        len(projection.sources),
    )


def _validate_expiry(expires_at: datetime | None) -> None:
    if expires_at is None:
        return
    moment = expires_at if expires_at.tzinfo is not None \
        else expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if moment <= now:
        raise ShareExpired("The share expiry must be in the future")
    if moment - now > timedelta(days=MAX_EXPIRY_DAYS):
        raise ShareExpired(
            f"The share expiry cannot exceed {MAX_EXPIRY_DAYS} days")


def _assert_share_limit(connection: Connection, owner_id: UUID,
                        document_id: UUID) -> None:
    count = connection.execute(
        select(func.count())
        .select_from(DocumentShare)
        .where(DocumentShare.owner_id == owner_id,
               DocumentShare.document_id == document_id)
    ).scalar_one()
    if count >= MAX_SHARES_PER_DOCUMENT:
        raise ShareLimitExceeded(
            f"A document carries at most {MAX_SHARES_PER_DOCUMENT} shares")


def _serialize_same_key(connection: Connection, owner_id: UUID,
                        document_id: UUID, key: UUID) -> None:
    """Advisory-lock the (owner, document, key) triple for this transaction."""
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:material, 0))"),
        {"material": f"document-share:{owner_id}:{document_id}:{key}"})


def _existing_share(connection: Connection, owner_id: UUID, document_id: UUID,
                    key: UUID) -> ShareRow | None:
    row = connection.execute(
        select(*_SHARE_COLUMNS).where(
            DocumentShare.owner_id == owner_id,
            DocumentShare.document_id == document_id,
            DocumentShare.idempotency_key == key)
    ).mappings().first()
    return _row_to_share(row) if row is not None else None


def _share_row(connection: Connection, owner_id: UUID, document_id: UUID,
               share_id: UUID) -> ShareRow:
    row = connection.execute(
        select(*_SHARE_COLUMNS)
        .where(DocumentShare.id == share_id,
               DocumentShare.document_id == document_id,
               DocumentShare.owner_id == owner_id)
    ).mappings().one_or_none()
    if row is None:
        raise ShareNotFound("Share does not exist for this owner")
    return _row_to_share(row)


def _row_to_share(row) -> ShareRow:
    return ShareRow(
        id=row["id"], owner_id=row["owner_id"], document_id=row["document_id"],
        document_version_id=row["document_version_id"],
        revision=row["revision"], status=row["status"],
        created_at=row["created_at"], expires_at=row["expires_at"],
        revoked_at=row["revoked_at"])


def _live_share_bytes(engine: Engine, token: str) -> bytes:
    """Resolve one token digest to live stored bytes, or deny.

    The RLS token policy (no identity, active, unexpired) filters first; the
    explicit checks below re-state the same contract for the service layer
    and verify the byte identity against the recorded hash/size before
    anything is served.
    """
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with user_transaction(engine, None) as connection:
        row = connection.execute(
            select(DocumentShare.projection, DocumentShare.projection_sha256,
                   DocumentShare.projection_byte_size, DocumentShare.status,
                   DocumentShare.expires_at)
            .where(DocumentShare.token_hash == digest)
        ).mappings().first()
    if row is None or row["projection"] is None or row["status"] != "active":
        raise ShareNotFound("Share is not available")
    if row["expires_at"] is not None:
        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise ShareNotFound("Share is not available")
    projection_bytes = bytes(row["projection"])
    if hashlib.sha256(projection_bytes).hexdigest() != row["projection_sha256"] \
            or len(projection_bytes) != row["projection_byte_size"]:
        raise ShareCorrupt("Stored share projection does not match its identity")
    return projection_bytes
