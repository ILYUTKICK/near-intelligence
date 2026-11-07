"""NI-054: published immutable model runs.

Creates ``app.model_runs`` — the write-once registry of published model runs
(DATABASE_SCHEMA.md "Models, publication and jobs"; the implemented shape is
recorded there as the NI-054 delta). One row per published run: the
content-derived ``run_id`` (UUIDv5 over the verified fit/diagnostics/readiness
manifest hashes), the preregistered specification identity, the NI-051 gate
verdict the run was admitted under, the complete manifest set as JSONB, the
per-artifact SHA-256 map, the recorded review approval, and the denormalized
identity columns (code commit, dependency lock hash, tolerances, sample
window) the public model APIs serve.

Deliberate boundaries:

- Only published runs exist here. The publication gate
  (``near_api.research.publication`` + the operator ``research publish`` CLI)
  verifies the full data/code/lock/config/design/result manifest set and the
  explicit operator approval BEFORE any row is attempted, and ``status``
  accepts only ``'published'`` — a rejected, failed or unreviewed run never
  enters the database, so it can never look like a result. There is no
  running/failed/rejected lifecycle: the NI-052 estimator already refuses
  anything the gate did not admit, and the gate verdict is recorded on the row
  it publishes.
- Write-once/append-only: no UPDATE or DELETE grant exists for any role; rows
  are immutable including their recorded review provenance. Re-publishing the
  identical bundle is a no-op on the content-derived primary key (idempotent);
  the same content under a different approval is refused as a conflict.
- FORCE RLS (0005 pattern): every role without a policy is locked out,
  including the table owner and grant-less ``near_public``. ``near_operator``
  holds the only write policy; ``near_app`` reads published rows for the
  public model APIs (NI-054) — the API routes are strictly read-only and
  import nothing from the research package, so endpoint access can never
  trigger a fit or a provider call.
- The denormalized columns are projections of the verified manifests, and the
  CHECK constraints re-assert every projection against the stored
  ``manifests`` JSONB (spec id/version, gate verdict, code commit, lock hash,
  sample window/nobs), so a row can never disagree with the manifests it
  publishes.
- ``manifests`` is bounded at 4 MiB rendered — the readiness report is the
  largest artifact of the admitted specification and stays well inside it.
"""

from alembic import op

revision = "0010_model_runs"
down_revision = "0009_idempotency_records"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.model_runs (
            run_id uuid NOT NULL,
            spec_id varchar(80) NOT NULL,
            spec_version integer NOT NULL,
            gate_verdict varchar(40) NOT NULL,
            status varchar(20) NOT NULL,
            manifests jsonb NOT NULL,
            artifacts jsonb NOT NULL,
            publication_approval jsonb NOT NULL,
            code_commit varchar(64) NOT NULL,
            dependency_lock_sha256 varchar(64) NOT NULL,
            coefficient_rtol varchar(40) NOT NULL,
            coefficient_atol varchar(40) NOT NULL,
            sample_start date NOT NULL,
            sample_end_exclusive date NOT NULL,
            nobs integer NOT NULL,
            published_by varchar(120) NOT NULL,
            published_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_model_runs PRIMARY KEY (run_id),
            CONSTRAINT ck_model_runs_spec_id CHECK (spec_id ~ '^[a-z][a-z0-9_]{2,79}$'),
            CONSTRAINT ck_model_runs_spec_version CHECK (spec_version >= 1),
            CONSTRAINT ck_model_runs_published CHECK (status = 'published'),
            CONSTRAINT ck_model_runs_gate_verdict
                CHECK (gate_verdict IN ('READY', 'READY_WITH_LIMITS')),
            CONSTRAINT ck_model_runs_code_commit
                CHECK (code_commit ~ '^[0-9a-f]{40}$|^[0-9a-f]{64}$'),
            CONSTRAINT ck_model_runs_lock_hash
                CHECK (dependency_lock_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_model_runs_tolerance_format
                CHECK (coefficient_rtol ~ '^[0-9]+(\.[0-9]+)?$'
                       AND coefficient_atol ~ '^[0-9]+(\.[0-9]+)?$'),
            CONSTRAINT ck_model_runs_sample_window CHECK (sample_end_exclusive > sample_start),
            CONSTRAINT ck_model_runs_nobs CHECK (nobs > 0),
            CONSTRAINT ck_model_runs_published_by CHECK (published_by <> ''),
            CONSTRAINT ck_model_runs_manifests_size
                CHECK (octet_length(manifests::text) <= 4194304),
            CONSTRAINT ck_model_runs_manifests_keys
                CHECK (manifests ? 'fit_manifest' AND manifests ? 'diagnostics_report'
                       AND manifests ? 'readiness_report'),
            CONSTRAINT ck_model_runs_artifacts_keys
                CHECK (artifacts ? 'fit_manifest' AND artifacts ? 'diagnostics_report'
                       AND artifacts ? 'readiness_report'
                       AND artifacts ? 'publication_approval'),
            -- The denormalized columns are projections of the verified
            -- manifests; a row can never disagree with what it publishes.
            CONSTRAINT ck_model_runs_spec_id_matches
                CHECK (spec_id = manifests->'fit_manifest'->'model'->>'model_id'),
            CONSTRAINT ck_model_runs_spec_version_matches
                CHECK (spec_version
                       = (manifests->'fit_manifest'->'model'->>'model_version')::int),
            CONSTRAINT ck_model_runs_gate_verdict_matches
                CHECK (gate_verdict
                       = manifests->'fit_manifest'->'admission'->>'verdict'),
            CONSTRAINT ck_model_runs_code_commit_matches
                CHECK (code_commit = manifests->'fit_manifest'->'inputs'->>'code_commit'),
            CONSTRAINT ck_model_runs_lock_hash_matches
                CHECK (dependency_lock_sha256
                       = manifests->'fit_manifest'->'inputs'->'dependency_lock'->>'sha256'),
            CONSTRAINT ck_model_runs_nobs_matches
                CHECK (nobs = (manifests->'fit_manifest'->'sample'->>'nobs')::int),
            CONSTRAINT ck_model_runs_sample_window_matches
                CHECK (sample_start
                       = (manifests->'fit_manifest'->'sample'->'window'->>'start')::date
                       AND sample_end_exclusive
                       = (manifests->'fit_manifest'->'sample'->'window'
                          ->>'end_exclusive')::date),
            CONSTRAINT ck_model_runs_tolerance_matches
                CHECK (coefficient_rtol
                       = manifests->'fit_manifest'->'reproduction'->>'coefficient_rtol'
                       AND coefficient_atol
                       = manifests->'fit_manifest'->'reproduction'->>'coefficient_atol')
        );

        CREATE INDEX ix_model_runs_spec_published
            ON app.model_runs (spec_id, published_at DESC);
        CREATE INDEX ix_model_runs_published_at ON app.model_runs (published_at DESC);

        -- Public scientific results: FORCE RLS keeps every role without a
        -- policy locked out (including the table owner and grant-less
        -- near_public); near_operator holds the only write policy and near_app
        -- a read-only policy over published rows.
        ALTER TABLE app.model_runs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.model_runs FORCE ROW LEVEL SECURITY;
        CREATE POLICY model_runs_operator ON app.model_runs
            TO near_operator USING (true) WITH CHECK (true);
        CREATE POLICY model_runs_app_read ON app.model_runs
            FOR SELECT TO near_app USING (true);

        -- Write-once/append-only: no UPDATE or DELETE grant exists for any
        -- role. The INSERT column list covers every non-defaulted column the
        -- publication gate writes (published_at is server-authored).
        GRANT SELECT ON app.model_runs TO near_app, near_operator;
        GRANT INSERT(run_id, spec_id, spec_version, gate_verdict, status, manifests,
                     artifacts, publication_approval, code_commit,
                     dependency_lock_sha256, coefficient_rtol, coefficient_atol,
                     sample_start, sample_end_exclusive, nobs, published_by)
            ON app.model_runs TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.model_runs;
    """)
