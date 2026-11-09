"""NI-058: owner-scoped Markdown ZIP export jobs with forced RLS.

Creates ``app.export_jobs`` — the queue, the frozen plan store and the
artifact store of one export job — exactly as implemented by
:mod:`near_api.exports` (the implemented shape is recorded in
DATABASE_SCHEMA.md). One row is one job:

- ``plan`` holds the FROZEN export IR canonical bytes (NI-056,
  ``export_ir_canonical_bytes``) built at request time while the requested
  revision was the document's acknowledged current version. The worker renders
  the bundle ONLY from these bytes, so an edit that lands after the request
  (a new revision, a rename, a newer dataset publication) can never reach an
  already-created export. The bytes are stored verbatim (bytea), not reparsed
  into JSONB, so plan identity is the recorded ``plan_sha256``.
- ``bundle`` holds the finished ZIP bytes (research.md, assets/, manifest.json)
  with their recorded SHA-256 and size. Bytes live owner-scoped inside the
  RLS-protected row: no public artifact key, no server filesystem path, no
  signed URL (API_SPECIFICATION export rules).

Lifecycle: ``queued`` -> ``running`` -> ``succeeded`` | ``failed``; a
``succeeded`` row past its TTL reads as ``expired`` (lazy, at poll/download
time) and the documented sweep transitions it and clears the bytes. A crash
is recovered by lease expiry: the operator lease claim re-admits a
``running`` row whose ``leased_until`` passed, capped at two attempts
(DATABASE_SCHEMA "worker leases, retry max 2") before the row becomes a
typed ``failed``.

Ownership and roles:

- ``near_app`` policies are the 0002 self pattern (owner + identity): the
  runtime role inserts its own jobs, reads its own rows and — as the
  transaction-local job owner the export worker sets per transaction —
  writes the completion (bundle bytes, status, completed_at) and the
  typed failure of its own rows only.
- ``near_operator`` holds the narrow lease power over this DERIVED,
  owner-scoped state (the saved_charts operator-delete precedent): it may
  read the lifecycle columns (never ``plan``/``bundle`` bytes), claim/lease
  rows for processing and purge rows with their owner's user-row cascade.
  Content columns are written only under the job owner's transaction-local
  identity — the worker never bypasses ownership globally
  (AUTHENTICATION_SECURITY).
- No policies exist for ``near_migrator`` (DDL only) or ``near_public``;
  FORCE RLS keeps both locked out even from this table.

Document deletion cascades (NI-037 recorded the export-job cascade for this
task): the composite same-owner FKs remove a document's export jobs with it;
the scientific registries the plan references stay untouched.
"""

from alembic import op

revision = "0012_export_jobs"
down_revision = "0011_saved_charts"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.export_jobs (
            id uuid CONSTRAINT pk_export_jobs PRIMARY KEY,
            owner_id uuid NOT NULL,
            document_id uuid NOT NULL,
            document_version_id uuid NOT NULL,
            format varchar(20) NOT NULL,
            status varchar(20) NOT NULL DEFAULT 'queued',
            idempotency_key uuid,
            revision integer NOT NULL,
            plan bytea NOT NULL,
            plan_sha256 varchar(64) NOT NULL,
            bundle bytea,
            bundle_sha256 varchar(64),
            bundle_byte_size bigint,
            error_code varchar(80),
            attempts integer NOT NULL DEFAULT 0,
            leased_by varchar(120),
            leased_until timestamptz,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz,
            -- MVP export is the Markdown bundle (docs/MVP_SCOPE.md); PDF is
            -- P1 (NI-059) and stays out of the database until it ships.
            CONSTRAINT ck_export_jobs_format CHECK (format = 'markdown_zip'),
            CONSTRAINT ck_export_jobs_status CHECK (
                status IN ('queued','running','succeeded','failed','expired')),
            CONSTRAINT ck_export_jobs_revision CHECK (revision > 0),
            CONSTRAINT ck_export_jobs_plan_hash CHECK (plan_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_export_jobs_plan_size CHECK (octet_length(plan) <= 33554432),
            CONSTRAINT ck_export_jobs_bundle_hash
                CHECK (bundle_sha256 IS NULL OR bundle_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_export_jobs_bundle_size
                CHECK (bundle_byte_size IS NULL OR bundle_byte_size >= 0),
            -- A finished bundle always carries its identity; a bundle column
            -- set never appears without its hash and size.
            CONSTRAINT ck_export_jobs_bundle_pairing CHECK (
                (status = 'succeeded') = (bundle IS NOT NULL)
                AND (bundle IS NULL) = (bundle_sha256 IS NULL)
                AND (bundle IS NULL) = (bundle_byte_size IS NULL)),
            -- error_code is the typed failure of a terminal worker refusal;
            -- succeeded/expired rows carry none.
            CONSTRAINT ck_export_jobs_error_code CHECK (
                (status = 'failed') = (error_code IS NOT NULL)),
            -- The first attempt starts at the claim; a queued row was never
            -- touched by a worker. (An expired row that was swept while
            -- still queued legitimately keeps attempts = 0.)
            CONSTRAINT ck_export_jobs_attempts CHECK (attempts >= 0),
            CONSTRAINT ck_export_jobs_queued_fresh CHECK (
                status <> 'queued' OR attempts = 0),
            CONSTRAINT ck_export_jobs_lease_pairing CHECK (
                (status = 'running') = (leased_until IS NOT NULL)),
            CONSTRAINT ck_export_jobs_worker_pairing CHECK (
                (attempts > 0) = (leased_by IS NOT NULL)),
            -- completed_at marks the attempt that reached a terminal worker
            -- result (succeeded/failed always carry it); a row that expires
            -- while queued/running keeps NULL, and a row that completed and
            -- LATER expired keeps its recorded completion.
            CONSTRAINT ck_export_jobs_completed_pairing CHECK (
                (status NOT IN ('succeeded','failed')
                 OR completed_at IS NOT NULL)
                AND (completed_at IS NULL
                     OR status IN ('succeeded','failed','expired'))),
            CONSTRAINT uq_export_jobs_id_owner UNIQUE (id, owner_id),
            CONSTRAINT uq_export_jobs_owner_idempotency UNIQUE (owner_id, idempotency_key),
            -- Same-owner composite references (NI-036 pattern): a job exists
            -- only for a revision of the same document and owner, and dies
            -- with its document.
            CONSTRAINT fk_export_jobs_owner FOREIGN KEY (owner_id)
                REFERENCES app.users (id) ON DELETE CASCADE,
            CONSTRAINT fk_export_jobs_document FOREIGN KEY (document_id, owner_id)
                REFERENCES app.documents (id, owner_id) ON DELETE CASCADE,
            CONSTRAINT fk_export_jobs_version
                FOREIGN KEY (document_version_id, document_id, owner_id)
                REFERENCES app.document_versions (id, document_id, owner_id)
                ON DELETE CASCADE
        );
        CREATE INDEX ix_export_jobs_status_created
            ON app.export_jobs (status, created_at, id);
        CREATE INDEX ix_export_jobs_owner_created
            ON app.export_jobs (owner_id, created_at DESC, id);

        ALTER TABLE app.export_jobs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.export_jobs FORCE ROW LEVEL SECURITY;

        -- Runtime role: only the transaction-local verified owner, and only
        -- while that account is not disabled (0002 pattern; fail closed on
        -- account disable/re-enable boundaries).
        CREATE POLICY export_jobs_self_select ON app.export_jobs
            FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY export_jobs_self_insert ON app.export_jobs
            FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY export_jobs_self_update ON app.export_jobs
            FOR UPDATE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active())
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY export_jobs_self_delete ON app.export_jobs
            FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());

        -- Operator lease power over the derived lifecycle (never the content
        -- columns; see the migration docstring). SELECT/UPDATE span all rows
        -- because a queue is cross-owner by definition; DELETE is the narrow
        -- purge power shared with saved_charts.
        CREATE POLICY export_jobs_operator_select ON app.export_jobs
            FOR SELECT TO near_operator USING (true);
        CREATE POLICY export_jobs_operator_update ON app.export_jobs
            FOR UPDATE TO near_operator USING (true) WITH CHECK (true);
        CREATE POLICY export_jobs_operator_delete ON app.export_jobs
            FOR DELETE TO near_operator USING (true);

        -- No policies exist for near_migrator (DDL only) or near_public;
        -- FORCE RLS keeps both locked out even from this table.

        -- near_app writes every column of its own rows through the service
        -- (INSERT covers the plan pin; UPDATE covers completion/failure).
        GRANT SELECT, INSERT, UPDATE, DELETE ON app.export_jobs TO near_app;
        GRANT INSERT(id, owner_id, document_id, document_version_id, format,
                     idempotency_key, revision, plan, plan_sha256, expires_at)
            ON app.export_jobs TO near_app;
        GRANT UPDATE(status, bundle, bundle_sha256, bundle_byte_size, error_code,
                     leased_until, completed_at, updated_at)
            ON app.export_jobs TO near_app;
        -- near_operator: lifecycle columns only; the plan/bundle bytes are
        -- neither readable nor writable through the lease credential.
        GRANT SELECT(id, owner_id, document_id, document_version_id, format, status,
                     idempotency_key, revision, error_code, attempts, leased_by,
                     leased_until, expires_at, created_at, updated_at, completed_at)
            ON app.export_jobs TO near_operator;
        GRANT UPDATE(status, attempts, leased_by, leased_until, error_code,
                     completed_at, updated_at)
            ON app.export_jobs TO near_operator;
        GRANT DELETE ON app.export_jobs TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.export_jobs;
    """)
