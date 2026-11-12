"""``python -m near_api.exports.worker`` — the export worker CLI.

Processes queued export jobs (NI-058 Markdown ZIP bundles, NI-059 PDF
reports) using the operator and runtime credentials. The worker is an
operator-invoked CLI, not a daemon: scheduling stays an explicit operational
step (no scheduler exists in MVP), and every job passes through the same
lease/retry/TTL machinery whether it is processed immediately or minutes
later.

Pipeline per job:

1. CLAIM (``near_operator`` credential, cross-owner lease power): one
   ``queued`` row — or a ``running`` row whose lease expired (crash
   recovery) — is selected ``FOR UPDATE SKIP LOCKED`` and moved to
   ``running`` with a fresh lease and ``attempts + 1``. A zombie that
   already burned its attempt cap becomes a typed ``failed`` row instead of
   being re-claimed (DATABASE_SCHEMA: "worker leases, retry max 2").
2. LOAD (the job owner's transaction-local identity): the frozen plan bytes
   are read through RLS as the job's owner and verified against the
   recorded ``plan_sha256`` before anything renders. The operator
   credential never sees plan or bundle bytes.
3. RENDER: the NI-057 boundary renders the plan's chart blocks (subprocess
   with a fixed ARGV list, no shell, typed failures); then the job's format
   selects the renderer — ``markdown_zip`` builds research.md + assets +
   manifest.json and packages the deterministic ZIP (NI-058), ``pdf``
   renders the same frozen plan into the deterministic static PDF report
   (NI-059, embedded vector charts from the same NI-057 assets). A failure
   marks the job ``failed`` with a typed ``error_code`` — the worker never
   substitutes, retries forever or fabricates a partial artifact.
4. COMMIT (the job owner's identity, again per-transaction): the artifact
   bytes (ZIP or PDF; the column is named ``bundle`` for both) are stored
   with their SHA-256 and size, guarded by the lease — a worker that lost
   its lease (expired mid-render, another worker re-claimed) commits
   nothing, and the re-claimed attempt regenerates the artifact from the
   same frozen plan (idempotent by construction).

``--sweep`` is the documented cleanup path: rows past their TTL become
``expired`` and their bundle bytes are cleared (per-owner transactions), so
the stored state converges with the lazily reported typed state.

No shell is invoked anywhere; the only subprocess is the pinned NI-057
renderer invocation with its fixed ARGV list. No secret, DSN or server
filesystem path is ever written into a job row, an artifact or the manifest.
Exit codes follow the research CLI convention: 0 success, 2 usage, 4
operator failure (an invalid runtime credential; job failures are recorded
on the job rows, not the process exit).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import socket
import sys
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import create_engine, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from near_api.db.models import ExportJob as ExportJobModel
from near_api.db.session import (
    DatabaseConfigurationError,
    create_runtime_engine,
    user_transaction,
)
from near_api.exports.bundle import MAX_BUNDLE_BYTES, build_bundle
from near_api.exports.charts import ChartRendererError, chart_render_request, render_chart_assets
from near_api.exports.service import MAX_PLAN_BYTES
from near_api.schemas.export import ExportChartBlock, ExportIr

MAX_ATTEMPTS = 2
"""The attempt cap of one export job (DATABASE_SCHEMA "retry max 2"): the
first processing pass and one crash-recovery attempt; the next expired lease
fails the job typed."""

DEFAULT_LEASE_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 60.0

EXIT_OK = 0
EXIT_FAILURE = 4
EXIT_USAGE = 2


@dataclass(frozen=True)
class ClaimedJob:
    """One leased job: identity, owner (for the per-transaction identity),
    the artifact format the completion renders, and the lease guard the
    completion update is bound to."""

    job_id: UUID
    owner_id: UUID
    document_id: UUID
    document_version_id: UUID
    format: str
    revision: int
    attempts: int
    worker_id: str


class WorkerError(Exception):
    """A typed worker refusal; ``code`` becomes the job's ``error_code``."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def claim_job(operator_engine: Engine, worker_id: str, *,
              lease_seconds: int = DEFAULT_LEASE_SECONDS) -> ClaimedJob | None:
    """Lease the next claimable job (cross-owner, lease columns only).

    One operator transaction: expire the attempt-exhausted zombies, pick one
    claimable row ``FOR UPDATE SKIP LOCKED`` (queued, or running with an
    expired lease — the crash-recovery path) and move it to ``running``.
    Returns ``None`` when the queue is empty.
    """
    with operator_engine.begin() as connection:
        connection.execute(text("""
            UPDATE app.export_jobs
               SET status = 'failed', error_code = 'lease_attempts_exhausted',
                   leased_until = NULL, completed_at = now(), updated_at = now()
             WHERE id IN (
                   SELECT id FROM app.export_jobs
                    WHERE status = 'running' AND leased_until < now()
                      AND attempts >= :max_attempts
                    FOR UPDATE SKIP LOCKED)
        """), {"max_attempts": MAX_ATTEMPTS})
        claimed = connection.execute(text("""
            SELECT id, owner_id, document_id, document_version_id, format,
                   revision, attempts
              FROM app.export_jobs
             WHERE (status = 'queued'
                    OR (status = 'running' AND leased_until < now()))
               AND attempts < :max_attempts
               AND expires_at > now()
             ORDER BY created_at, id
             LIMIT 1
             FOR UPDATE SKIP LOCKED
        """), {"max_attempts": MAX_ATTEMPTS}).mappings().first()
        if claimed is None:
            return None
        connection.execute(text("""
            UPDATE app.export_jobs
               SET status = 'running', leased_by = :worker,
                   leased_until = now() + make_interval(secs => :lease),
                   attempts = attempts + 1, updated_at = now()
             WHERE id = :id
        """), {"worker": worker_id, "lease": lease_seconds, "id": claimed["id"]})
        return ClaimedJob(
            job_id=claimed["id"], owner_id=claimed["owner_id"],
            document_id=claimed["document_id"],
            document_version_id=claimed["document_version_id"],
            format=claimed["format"],
            revision=claimed["revision"], attempts=claimed["attempts"] + 1,
            worker_id=worker_id)


def load_plan(runtime_engine: Engine, claimed: ClaimedJob) -> ExportIr:
    """Read and verify the frozen plan bytes as the job's owner.

    The plan is parsed through the typed contract; a hash mismatch or a
    corrupt plan is a typed failure — the bundle of an unverified plan is
    never built.
    """
    with user_transaction(runtime_engine, claimed.owner_id) as connection:
        row = connection.execute(
            text("SELECT plan, plan_sha256 FROM app.export_jobs "
                 "WHERE id = :id AND owner_id = :owner"),
            {"id": claimed.job_id, "owner": claimed.owner_id}).mappings().one_or_none()
    if row is None:
        raise WorkerError("export_job_missing",
                          "The leased job row is not readable as its owner")
    plan_bytes = bytes(row["plan"])
    if hashlib.sha256(plan_bytes).hexdigest() != row["plan_sha256"]:
        raise WorkerError("export_plan_hash_mismatch",
                          "The stored export plan does not match its recorded hash")
    if len(plan_bytes) > MAX_PLAN_BYTES:
        raise WorkerError("export_plan_too_large",
                          "The stored export plan exceeds the plan-size cap")
    try:
        return ExportIr.model_validate_json(plan_bytes)
    except ValueError as error:
        raise WorkerError("export_plan_invalid",
                          "The stored export plan does not match the frozen "
                          "export contract") from error


def render_bundle(plan: ExportIr, *, format: str = "markdown_zip",
                  timeout: float = DEFAULT_TIMEOUT_SECONDS,
                  node_bin: str | None = None,
                  renderer_script: str | None = None) -> bytes:
    """Render the plan's artifact (charts via NI-057, then the format's renderer).

    ``format`` selects the delivery renderer only: ``markdown_zip`` packages
    the Markdown bundle (NI-058), ``pdf`` renders the static PDF report
    (NI-059). Both embed the SAME boundary-verified chart assets; an unknown
    format is a typed worker failure, never a guessed renderer.
    """
    chart_blocks = tuple(block for block in plan.blocks
                         if isinstance(block, ExportChartBlock))
    render_result = None
    if chart_blocks:
        render_result = render_chart_assets(
            chart_render_request(chart_blocks), timeout=timeout,
            node_bin=node_bin, renderer_script=renderer_script)
    if format == "pdf":
        from near_api.exports.pdf import render_pdf

        try:
            pdf_bytes = render_pdf(plan, render_result)
        except ValueError as error:
            raise WorkerError("pdf_render_failed", str(error)) from error
        if len(pdf_bytes) > MAX_BUNDLE_BYTES:
            raise WorkerError("bundle_size_exceeded",
                              "The export artifact exceeds the artifact-size cap")
        return pdf_bytes
    if format == "markdown_zip":
        try:
            bundle = build_bundle(plan, render_result)
        except ValueError as error:
            raise WorkerError("bundle_build_failed", str(error)) from error
        if len(bundle.zip_bytes) > MAX_BUNDLE_BYTES:
            raise WorkerError("bundle_size_exceeded",
                              "The export bundle exceeds the bundle-size cap")
        return bundle.zip_bytes
    raise WorkerError("unsupported_export_format",
                      f"The job requests the undocumented format {format!r}")


def complete_job(runtime_engine: Engine, claimed: ClaimedJob,
                 bundle_bytes: bytes) -> bool:
    """Store the finished bundle as the job's owner (lease-guarded).

    Returns ``True`` when the completion committed. A lost lease (expired
    mid-render, another worker re-claimed) commits nothing and returns
    ``False`` — the frozen plan makes the re-claimed attempt reproduce the
    same bundle, so dropping these bytes is always safe.
    """
    with user_transaction(runtime_engine, claimed.owner_id) as connection:
        result = connection.execute(
            update(ExportJobModel)
            .where(ExportJobModel.id == claimed.job_id,
                   ExportJobModel.owner_id == claimed.owner_id,
                   ExportJobModel.status == "running",
                   ExportJobModel.leased_by == claimed.worker_id,
                   ExportJobModel.leased_until > text("now()"))
            .values(status="succeeded", bundle=bundle_bytes,
                    bundle_sha256=hashlib.sha256(bundle_bytes).hexdigest(),
                    bundle_byte_size=len(bundle_bytes), error_code=None,
                    leased_until=None, completed_at=text("now()"),
                    updated_at=text("now()")))
        return bool(result.rowcount)


def fail_job(runtime_engine: Engine, claimed: ClaimedJob, code: str) -> bool:
    """Mark the leased job failed with its typed error code (owner-scoped).

    A lost lease commits nothing: the re-claimer owns the outcome then.
    """
    with user_transaction(runtime_engine, claimed.owner_id) as connection:
        result = connection.execute(
            update(ExportJobModel)
            .where(ExportJobModel.id == claimed.job_id,
                   ExportJobModel.owner_id == claimed.owner_id,
                   ExportJobModel.status == "running",
                   ExportJobModel.leased_by == claimed.worker_id,
                   ExportJobModel.leased_until > text("now()"))
            .values(status="failed", error_code=code[:80], leased_until=None,
                    completed_at=text("now()"), updated_at=text("now()")))
        return bool(result.rowcount)


def sweep_expired(runtime_engine: Engine, operator_engine: Engine) -> int:
    """Expire every row past its TTL and clear the stored bytes (cleanup).

    The documented persistence step of the lazily reported ``expired``
    state: one owner-scoped transaction per row clears the bundle bytes and
    settles the status, so the artifact storage converges with what the
    poll/download routes already report honestly. Returns the swept count.
    """
    with operator_engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT id, owner_id FROM app.export_jobs
             WHERE status IN ('queued', 'running', 'succeeded')
               AND expires_at <= now()
             ORDER BY created_at, id
        """)).mappings().all()
    swept = 0
    for row in rows:
        with user_transaction(runtime_engine, row["owner_id"]) as connection:
            result = connection.execute(
                update(ExportJobModel)
                .where(ExportJobModel.id == row["id"],
                       ExportJobModel.owner_id == row["owner_id"],
                       ExportJobModel.status.in_(("queued", "running", "succeeded")),
                       ExportJobModel.expires_at <= text("now()"))
                .values(status="expired", bundle=None, bundle_sha256=None,
                        bundle_byte_size=None, error_code=None, leased_until=None,
                        updated_at=text("now()")))
            swept += int(result.rowcount or 0)
    return swept


def default_worker_id() -> str:
    """The audit-only lease owner recorded on claimed jobs."""
    return f"export-worker-{socket.gethostname()}-{os.getpid() % 100000:05d}"


def process_one(runtime_engine: Engine, operator_engine: Engine, *,
                worker_id: str, lease_seconds: int,
                timeout: float, node_bin: str | None,
                renderer_script: str | None) -> bool:
    """Claim and process exactly one job; returns ``False`` when none."""
    claimed = claim_job(operator_engine, worker_id, lease_seconds=lease_seconds)
    if claimed is None:
        return False
    try:
        plan = load_plan(runtime_engine, claimed)
        bundle_bytes = render_bundle(plan, format=claimed.format, timeout=timeout,
                                     node_bin=node_bin,
                                     renderer_script=renderer_script)
    except (WorkerError, ChartRendererError) as error:
        code = error.code if isinstance(error, (WorkerError, ChartRendererError)) \
            else "export_worker_error"
        fail_job(runtime_engine, claimed, code)
        print(f"export job {claimed.job_id} failed: {code}: {error}", file=sys.stderr)
        return True
    except Exception as error:  # noqa: BLE001 - the worker records the failure typed
        fail_job(runtime_engine, claimed, "export_worker_error")
        print(f"export job {claimed.job_id} failed: export_worker_error: {error!r}",
              file=sys.stderr)
        return True
    if not complete_job(runtime_engine, claimed, bundle_bytes):
        print(f"export job {claimed.job_id} lease lost; the attempt's bytes were "
              "dropped and the retry regenerates them from the same frozen plan",
              file=sys.stderr)
        return True
    print(f"export job {claimed.job_id} succeeded "
          f"({len(bundle_bytes)} bytes, revision {claimed.revision})")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m near_api.exports.worker",
        description="Process queued export jobs (Markdown ZIP bundles, PDF "
                    "reports; NI-058/NI-059).")
    parser.add_argument("--database-url", required=True,
                        help="near_app runtime credential (job-owner transactions)")
    parser.add_argument("--operator-database-url", required=True,
                        help="near_operator credential (lease claim and sweep)")
    parser.add_argument("--worker-id", default=None,
                        help="lease owner recorded on the job (audit only)")
    parser.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS,
                        help="chart renderer subprocess timeout in seconds")
    parser.add_argument("--max-jobs", type=int, default=0,
                        help="stop after N jobs (0 = until the queue is empty)")
    parser.add_argument("--sweep", action="store_true",
                        help="expire past-TTL rows, clear their bytes and exit")
    parser.add_argument("--node-bin", default=None,
                        help="node binary for the chart renderer (defaults to PATH)")
    parser.add_argument("--renderer-script", default=None,
                        help="pinned renderer script override (testing seam)")
    args = parser.parse_args(argv)
    if args.lease_seconds <= 0 or args.timeout <= 0 or args.max_jobs < 0:
        parser.error("--lease-seconds/--timeout must be positive and "
                     "--max-jobs non-negative")
    worker_id = args.worker_id or default_worker_id()
    try:
        runtime_engine = create_runtime_engine(args.database_url, pool_size=2)
        operator_engine = create_engine(args.operator_database_url,
                                        poolclass=NullPool, hide_parameters=True)
    except DatabaseConfigurationError as error:
        print(f"Invalid runtime credential: {error}", file=sys.stderr)
        return EXIT_FAILURE
    try:
        if args.sweep:
            swept = sweep_expired(runtime_engine, operator_engine)
            print(f"swept {swept} expired export job(s)")
            return EXIT_OK
        processed = 0
        while args.max_jobs == 0 or processed < args.max_jobs:
            if not process_one(runtime_engine, operator_engine,
                               worker_id=worker_id, lease_seconds=args.lease_seconds,
                               timeout=args.timeout, node_bin=args.node_bin,
                               renderer_script=args.renderer_script):
                break
            processed += 1
        print(f"processed {processed} export job(s)")
        return EXIT_OK
    finally:
        runtime_engine.dispose()
        operator_engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
