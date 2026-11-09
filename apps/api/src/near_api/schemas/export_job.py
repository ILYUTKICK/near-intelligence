"""HTTP contracts of the Markdown ZIP export jobs (NI-058).

Pinned to the API_SPECIFICATION export rows: the create body names the exact
acknowledged revision and the bundle format, and the job response is the
typed lifecycle projection the editor polls — ``queued``/``running`` while
the worker holds the lease, ``succeeded`` with a ``download_path`` once the
ZIP is stored, ``failed`` with a typed ``error_code``, and ``expired`` once
the artifact TTL passed (evaluated at read time, so the state is honest even
before the documented sweep persists it).

These are the OpenAPI-visible envelope models only. The frozen export IR
(``near_api.schemas.export``) stays a service-level representation: the job
response carries its identity through the revision pins, never the plan
payload, and the bundle's own manifest records the full plan identity.
"""

from datetime import timedelta
from typing import Literal
from uuid import UUID

from pydantic import Field

from near_api.insights.schemas import ServerTimestamp
from near_api.schemas.common import ContractModel

EXPORT_FORMAT = Literal["markdown_zip", "pdf"]
"""The documented bundle formats; ``pdf`` is P1 (NI-059) and is refused as
a typed 422 FEATURE_UNAVAILABLE while the Markdown bundle is the single
reliable MVP export (docs/MVP_SCOPE.md)."""

EXPORT_STATUS = Literal["queued", "running", "succeeded", "failed", "expired"]
"""The documented lifecycle states (DATABASE_SCHEMA export_jobs)."""


class DocumentExportRequest(ContractModel):
    """POST /documents/{id}/exports body.

    ``document_version_id`` must be the document's acknowledged current
    revision at request time (API_SPECIFICATION: "Client first saves then
    uses acknowledged version ID") — the frozen plan is built only while the
    requested revision is current, so title and content always describe the
    same revision. A valid but superseded revision is a typed 409.
    """

    document_version_id: UUID
    format: EXPORT_FORMAT


class ExportJobResponse(ContractModel):
    """The typed lifecycle state of one owned export job.

    ``download_path`` is the same-origin owner-checked download route and is
    set only while the bundle is downloadable (``succeeded`` and unexpired);
    ``error_code`` is set exactly when ``status`` is ``failed``. No field of
    this response carries a server filesystem path or a credential.
    """

    id: UUID
    document_id: UUID
    document_version_id: UUID
    format: Literal["markdown_zip"]
    status: EXPORT_STATUS
    error_code: str | None = Field(default=None, min_length=1, max_length=80)
    download_path: str | None = Field(default=None, min_length=1, max_length=200)
    expires_at: ServerTimestamp


EXPORT_JOB_TTL = timedelta(hours=24)
"""Private export artifact retention (AUTHENTICATION_SECURITY target: 24h).
Applied at creation; the TTL never silently refreshes."""
