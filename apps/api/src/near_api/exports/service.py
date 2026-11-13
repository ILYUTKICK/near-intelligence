"""Owner-scoped export job store: creation, polling and download.

The HTTP-facing service of the export pipeline (NI-058 Markdown ZIP, NI-059
PDF). One row of ``app.export_jobs`` is one job; every function here runs
inside a transaction-local verified identity (:func:`near_api.db.security.
principal_transaction` or the worker's per-job owner transaction), so RLS
and the compositional checks make absent and not-owned ids the same generic
404-equivalent — Bob can never create, poll, download or sweep Alice's
export.

Creation freezes the plan (the NI-056 rule): the export IR of the requested
revision is built in the SAME transaction that inserts the job, and only
while that revision is the document's acknowledged current version. The
inserted job therefore already holds the complete plan bytes — the worker
never re-resolves anything, so an edit, rename or newer dataset publication
after the request cannot reach the bundle.

Idempotency follows the NI-037/0009 patterns: an ``Idempotency-Key: UUID``
(when supplied) is unique per owner (``uq_export_jobs_owner_idempotency``),
same-key concurrent requests are serialized by a transaction-scoped advisory
lock, and a repeated identical (route, body) request replays the ORIGINAL
job instead of creating a second one. The job row itself is the replay
record — the create response is derived from it, so a replay after the
stored record would have expired still answers with the same job's honest
(lifecycle-typed) state. A key reused with a different body is a typed 409.

Reading is honest by construction: the lifecycle state is computed at read
time, so a ``succeeded`` row past its TTL reports ``expired`` and its
download is refused — never a stale file. No function here writes the
lifecycle of another user's row and no response carries a server filesystem
path, a credential or a secret.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, func, insert, select, text

from near_api.auth.principal import Principal
from near_api.db.models import ExportJob
from near_api.db.security import principal_transaction
from near_api.documents.idempotency import (
    IdempotencyConflict,
    IdempotencyKeyInvalid,
    parse_idempotency_key,
)
from near_api.exports.ir import (
    ExportIrError,
    build_export_ir_in_transaction,
    export_ir_canonical_bytes,
)
from near_api.schemas.export import ExportIr
from near_api.schemas.export_job import EXPORT_JOB_TTL

EXPORT_ROUTE_TEMPLATE = "POST /api/documents/{document_id}/exports"
"""The concrete-URL idempotency route identity (the NI-041 lesson: a
destination can never replay another destination's result)."""

MAX_PLAN_BYTES = 32 * 1024 * 1024
"""The stored-plan cap (mirrored by the migration CHECK): a frozen plan
larger than this is a typed 422 at creation instead of an unbounded row."""

_JOB_COLUMNS = (
    ExportJob.id, ExportJob.owner_id, ExportJob.document_id,
    ExportJob.document_version_id, ExportJob.format, ExportJob.status,
    ExportJob.error_code, ExportJob.expires_at, ExportJob.attempts,
)
_DOWNLOAD_COLUMNS = _JOB_COLUMNS + (
    ExportJob.bundle, ExportJob.bundle_sha256, ExportJob.bundle_byte_size,
)


class ExportJobNotFound(LookupError):
    """The job does not exist for this owner/document (one 404-equivalent)."""


class ExportFormatInvalid(ValueError):
    """The requested format is not a documented bundle format (typed 422)."""


class ExportPlanTooLarge(ValueError):
    """The frozen plan exceeds the stored-plan cap (typed 422)."""


@dataclass(frozen=True)
class ExportJobRow:
    """The lifecycle projection of one export job (no plan/bundle bytes)."""

    id: UUID
    owner_id: UUID
    document_id: UUID
    document_version_id: UUID
    format: str
    status: str
    error_code: str | None
    expires_at: datetime
    attempts: int

    def reported_status(self, *, now: datetime | None = None) -> str:
        """The honest lifecycle state at read time.

        A row past its TTL reads as ``expired`` — the export offer is over
        regardless of whether a worker swept the row yet. A ``failed`` row
        keeps its typed failure (retrying means creating a new job).
        """
        moment = now or datetime.now(timezone.utc)
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if self.status in {"queued", "running", "succeeded"} and expires_at <= moment:
            return "expired"
        return self.status

    def download_path(self) -> str | None:
        """The owner-checked download route while the bundle is live."""
        if self.reported_status() != "succeeded":
            return None
        return f"/api/documents/{self.document_id}/exports/{self.id}/download"


@dataclass(frozen=True)
class ExportDownload:
    """The stored artifact bytes of one succeeded, unexpired job (a ZIP for
    ``markdown_zip`` jobs, the PDF itself for ``pdf`` jobs — the job's
    ``format`` records the media type the download route streams)."""

    job: ExportJobRow
    bundle: bytes
    bundle_sha256: str
    bundle_byte_size: int


@dataclass(frozen=True)
class CreatedExportJob:
    """The result of an idempotent create: the job and whether it replays."""

    job: ExportJobRow
    replay: bool


def create_export_job(engine: Engine, principal: Principal, document_id: UUID,
                      version_id: UUID, *, format: str = "markdown_zip",
                      idempotency_key: str | None = None,
                      ) -> CreatedExportJob:
    """Create (or replay) the export job of the owned acknowledged revision.

    ``format`` is the documented bundle format (``markdown_zip`` or ``pdf``);
    the frozen plan is built the same way for both — the renderer difference
    belongs to the worker only. One transaction: advisory serialization (key
    present), the replay check over the job row, the frozen IR build
    (fail-closed on every pin) and the insert. Raises
    :class:`IdempotencyKeyInvalid` (422) for a malformed key,
    :class:`IdempotencyConflict` (409) for a key reused with a different
    request, and :class:`ExportIrError` for a revision the export contract
    refuses (the route maps ``revision_not_acknowledged`` to 409 and every
    other detail to 422). An unknown format is a typed :class:`ValueError`
    the route refuses as a 422 before any job row exists.
    """
    if format not in ("markdown_zip", "pdf"):
        raise ExportFormatInvalid(
            f"Unknown export format {format!r}; the documented formats are "
            "markdown_zip and pdf")
    key = parse_idempotency_key(idempotency_key)
    with principal_transaction(engine, principal) as connection:
        if key is not None:
            _serialize_same_key(connection, principal.id, document_id, key)
            existing = _existing_job(connection, principal.id, document_id, key)
            if existing is not None:
                if existing.document_version_id != version_id \
                        or existing.format != format:
                    raise IdempotencyConflict(
                        "This Idempotency-Key was already used for a different "
                        "export request; a new key is required for a new payload")
                return CreatedExportJob(job=existing, replay=True)
        plan = build_export_ir_in_transaction(connection, principal, document_id,
                                              version_id)
        plan_bytes = export_ir_canonical_bytes(plan)
        if len(plan_bytes) > MAX_PLAN_BYTES:
            raise ExportPlanTooLarge(
                f"The frozen export plan is {len(plan_bytes)} bytes; the "
                f"stored-plan cap is {MAX_PLAN_BYTES}")
        job_id = uuid4()
        connection.execute(insert(ExportJob).values(
            id=job_id, owner_id=principal.id, document_id=document_id,
            document_version_id=version_id, format=format,
            idempotency_key=key, revision=plan.document.revision,
            plan=plan_bytes,
            plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
            expires_at=func.now() + EXPORT_JOB_TTL))
        return CreatedExportJob(job=_job_row(connection, principal.id,
                                             document_id, job_id), replay=False)


def get_export_job(engine: Engine, principal: Principal, document_id: UUID,
                   job_id: UUID) -> ExportJobRow:
    """Poll one owned export job (the typed lifecycle projection).

    The job is reachable only through its owned document: absent, not-owned
    and cross-document ids are the same 404-equivalent.
    """
    with principal_transaction(engine, principal) as connection:
        return _job_row(connection, principal.id, document_id, job_id)


def get_export_download(engine: Engine, principal: Principal, document_id: UUID,
                        job_id: UUID) -> ExportDownload:
    """Return the stored artifact of one owned, succeeded, unexpired job.

    A job that is not downloadable raises a typed failure the route maps
    onto its documented status: :class:`ExportNotReady` (queued/running,
    409), :class:`ExportFailed` (failed, 409) and :class:`ExportExpired`
    (past TTL, 410). The stored bytes are re-verified against the recorded
    SHA-256 before they are returned — a corrupted row fails closed instead
    of shipping silently altered bytes.
    """
    with principal_transaction(engine, principal) as connection:
        row = connection.execute(
            select(*_DOWNLOAD_COLUMNS)
            .where(ExportJob.id == job_id, ExportJob.document_id == document_id,
                   ExportJob.owner_id == principal.id)
        ).mappings().one_or_none()
    if row is None:
        raise ExportJobNotFound("Export job does not exist for this owner")
    job = ExportJobRow(**{column.key: row[column.key] for column in _JOB_COLUMNS})
    reported = job.reported_status()
    if reported in {"queued", "running"}:
        raise ExportNotReady("The export is still being generated", reported)
    if reported == "failed":
        raise ExportFailed("The export failed on the worker", job.error_code)
    if reported == "expired" or row["bundle"] is None:
        raise ExportExpired("The export artifact has expired")
    if hashlib.sha256(row["bundle"]).hexdigest() != row["bundle_sha256"] \
            or len(row["bundle"]) != row["bundle_byte_size"]:
        raise ExportCorrupt("The stored export bundle does not match its recorded hash")
    return ExportDownload(job=job, bundle=bytes(row["bundle"]),
                          bundle_sha256=row["bundle_sha256"],
                          bundle_byte_size=row["bundle_byte_size"])


class ExportNotReady(Exception):
    """The export is queued/running (typed 409 at the download route)."""

    def __init__(self, message: str, status: str):
        super().__init__(message)
        self.status = status


class ExportFailed(Exception):
    """The export failed on the worker (typed 409 with the error code)."""

    def __init__(self, message: str, error_code: str | None):
        super().__init__(message)
        self.error_code = error_code


class ExportExpired(Exception):
    """The export artifact passed its TTL (typed 410, never a stale file)."""


class ExportCorrupt(Exception):
    """The stored bundle does not match its recorded identity (fail closed)."""


def _serialize_same_key(connection: Connection, owner_id: UUID,
                        document_id: UUID, key: UUID) -> None:
    """Advisory-lock the (owner, document, key) triple for this transaction."""
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:material, 0))"),
        {"material": f"export-job:{owner_id}:{document_id}:{key}"})


def _existing_job(connection: Connection, owner_id: UUID, document_id: UUID,
                  key: UUID) -> ExportJobRow | None:
    row = connection.execute(
        select(*_JOB_COLUMNS).where(
            ExportJob.owner_id == owner_id, ExportJob.document_id == document_id,
            ExportJob.idempotency_key == key)
    ).mappings().first()
    return _row_to_job(row) if row is not None else None


def _job_row(connection: Connection, owner_id: UUID, document_id: UUID,
             job_id: UUID) -> ExportJobRow:
    row = connection.execute(
        select(*_JOB_COLUMNS)
        .where(ExportJob.id == job_id, ExportJob.document_id == document_id,
               ExportJob.owner_id == owner_id)
    ).mappings().one_or_none()
    if row is None:
        raise ExportJobNotFound("Export job does not exist for this owner")
    return _row_to_job(row)


def _row_to_job(row) -> ExportJobRow:
    return ExportJobRow(
        id=row["id"], owner_id=row["owner_id"], document_id=row["document_id"],
        document_version_id=row["document_version_id"], format=row["format"],
        status=row["status"], error_code=row["error_code"],
        expires_at=row["expires_at"], attempts=row["attempts"])


def export_ir_error_kind(error: ExportIrError) -> Literal["revision", "unavailable"]:
    """Classify an IR refusal for the route's status mapping.

    ``revision_not_acknowledged`` is the documented 409-family refusal; every
    other unresolvable pin/reference is the documented "references
    unavailable" 422.
    """
    if any(reason == "revision_not_acknowledged" for _path, reason in error.details):
        return "revision"
    return "unavailable"
