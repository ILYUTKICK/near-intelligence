"""NI-054: the operator database write behind the publication gate.

This module is the ONLY writer of ``app.model_runs`` (migration 0010). It runs
exclusively in the operator CLI (``python -m near_api.research publish``)
with the dedicated unprivileged ``near_operator`` credential — never in the
API runtime, which only ever reads published rows through ``near_app``.

Write-once semantics: the table has no UPDATE or DELETE grant for any role and
its CHECK constraint accepts only ``publication_verdict = 'published'``, so a
rejected, failed or unreviewed run cannot exist as a row at all — it never
enters the database and therefore can never look like a result. Publication is
idempotent: the run id is derived from the verified manifest content, so
re-publishing the identical bundle is a no-op; publishing the same content
under a different approval document is refused as a conflict (model runs are
immutable, including their recorded review provenance).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from near_api.ingestion.archive import (
    OperatorDatabaseError,
    _assert_operator,
    create_operator_engine,
)
from near_api.research.publication import publication_payload

# The manifests JSONB bound matches the migration's CHECK constraint; a bundle
# beyond it is refused before any row is attempted.
MAX_MANIFESTS_BYTES = 4 * 1024 * 1024


class PublishConflictError(RuntimeError):
    """The identical run content is already published under another approval."""


@dataclass(frozen=True)
class PublishedRun:
    run_id: UUID
    spec_id: str
    published_at: str
    published_by: str
    already_published: bool


def publish_run(database_url: str, bundle: dict, run_id: UUID) -> PublishedRun:
    """Insert one verified run into ``app.model_runs`` (write-once, idempotent).

    The caller must have run :func:`near_api.research.publication.verify_bundle`
    and received a passing report; this store performs no verification of its
    own beyond the database constraints, which exist as defense in depth, not
    as the gate.
    """
    payload = publication_payload(bundle, run_id)
    manifests_bytes = len(json.dumps(payload["manifests"],
                                     ensure_ascii=False, sort_keys=True).encode("utf-8"))
    if manifests_bytes > MAX_MANIFESTS_BYTES:
        raise OperatorDatabaseError(
            f"the manifest set renders to {manifests_bytes} bytes, above the stored "
            f"bound of {MAX_MANIFESTS_BYTES}; the bundle cannot be published")
    engine = create_operator_engine(database_url)
    try:
        with engine.begin() as connection:
            _assert_operator(connection)
            inserted = connection.execute(text("""
                INSERT INTO app.model_runs (run_id, spec_id, spec_version, gate_verdict,
                                            status, manifests, artifacts,
                                            publication_approval, code_commit,
                                            dependency_lock_sha256,
                                            coefficient_rtol, coefficient_atol,
                                            sample_start, sample_end_exclusive, nobs,
                                            published_by)
                VALUES (:run_id, :spec_id, :spec_version, :gate_verdict, 'published',
                        CAST(:manifests AS jsonb), CAST(:artifacts AS jsonb),
                        CAST(:approval AS jsonb),
                        :code_commit, :dependency_lock_sha256,
                        :coefficient_rtol, :coefficient_atol,
                        CAST(:sample_start AS date), CAST(:sample_end AS date), :nobs,
                        :published_by)
                ON CONFLICT (run_id) DO NOTHING
                RETURNING published_at
            """), {
                "run_id": str(payload["run_id"]),
                "spec_id": payload["spec_id"],
                "spec_version": payload["spec_version"],
                "gate_verdict": payload["gate_verdict"],
                "manifests": json.dumps(payload["manifests"], ensure_ascii=False,
                                        sort_keys=True),
                "artifacts": json.dumps(payload["artifacts"], ensure_ascii=False,
                                        sort_keys=True),
                "approval": json.dumps(payload["approval"], ensure_ascii=False,
                                       sort_keys=True),
                "code_commit": payload["code_commit"],
                "dependency_lock_sha256": payload["dependency_lock_sha256"],
                "coefficient_rtol": payload["coefficient_rtol"],
                "coefficient_atol": payload["coefficient_atol"],
                "sample_start": payload["sample_start"],
                "sample_end": payload["sample_end_exclusive"],
                "nobs": payload["nobs"],
                "published_by": str(payload["approval"]["reviewer"])[:120],
            }).scalar_one_or_none()
            if inserted is not None:
                return PublishedRun(run_id=run_id, spec_id=payload["spec_id"],
                                    published_at=inserted.isoformat(),
                                    published_by=str(payload["approval"]["reviewer"])[:120],
                                    already_published=False)
            existing = connection.execute(text("""
                SELECT published_at, published_by, publication_approval
                FROM app.model_runs WHERE run_id = :run_id
            """), {"run_id": str(run_id)}).mappings().one()
            if existing["publication_approval"] != payload["approval"]:
                raise PublishConflictError(
                    f"run {run_id} is already published with a different approval "
                    "record; model runs are immutable, including their recorded "
                    "review provenance — publish nothing again, the recorded review "
                    "stands")
            return PublishedRun(run_id=run_id, spec_id=payload["spec_id"],
                                published_at=existing["published_at"].isoformat(),
                                published_by=existing["published_by"],
                                already_published=True)
    finally:
        engine.dispose()
