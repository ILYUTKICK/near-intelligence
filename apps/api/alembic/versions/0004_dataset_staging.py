"""NI-028: immutable dataset staging and publication zone.

Creates the dataset zone of DATABASE_SCHEMA.md ("Shared definitions, data and
provenance"), owned by NI-028:

- ``artifacts``: immutable content-addressed artifact registry. The canonical
  dataset manifest, copied input blobs and logical references to NI-027
  imported files all live here. Bytes are written to operator storage BEFORE
  the database transaction (see ``near_api.datasets.storage``); rows are never
  updated or deleted (direct deletion of scientific artifacts is restricted).
- ``dataset_versions``: one immutable row per semantic dataset content.
  ``UNIQUE(dataset_key, content_sha256)`` is the deduplication key: identical
  semantic input always resolves to the same version. ``UNIQUE(dataset_key,
  version)`` keeps version numbers dense and queryable. Status lifecycle
  staged -> validated -> approved (+ rejected terminal) is enforced by a
  trigger whitelist; approved and rejected rows are fully frozen (history is
  never overwritten). ``supersedes_id`` is a same-key composite self FK set at
  publish time.
- ``dataset_metrics``: member metric registry per version. Every observation
  must reference a member metric (composite FK from ``metric_observations``).
  ``metric_definition_id`` is stored as an opaque registered identifier for
  now: the ``metric_definitions`` registry table arrives with the metric
  registry task (NI-031), which adds the referential FK.
- ``dataset_inputs``: raw/normalized/price/sql/config lineage per version.
  ``ingestion_run_id`` is a reserved nullable column without FK until the
  ingestion-run lifecycle table exists (NI-030).
- ``metric_observations``: half-open UTC ``[period_start, period_end)`` points
  with exact NUMERIC(78,30) values (derived-amount convention; raw-precision
  originals remain in the hash-pinned manifest artifact), canonical
  ``dimensions_hash``, explicit quality and bound semantics: missing or
  unavailable quality implies a NULL value with a reason in the row quality
  metadata, a verified zero is an explicit value, and ``bound_kind`` exists
  exactly when a value exists.
- ``active_datasets``: one approved active pointer per dataset key, switched
  only inside the single publish transaction. The composite FK guarantees the
  pointer targets a version of the same key and a trigger guarantees the
  targeted version is approved. Historical versions remain readable forever.

Roles follow the operator import zone (NI-027): near_operator writes and reads
via FORCE RLS policies; near_app gets read-only access to the scientific data
(private artifacts stay owner-scoped); near_public and near_migrator receive
nothing. Roles are never created by migrations; scripts/db/010-roles.sql
remains the only role bootstrap. Concurrent staging/publication serialize on
transaction-level advisory locks keyed by dataset key (service-side, see
``near_api.datasets.service``).
"""

from alembic import op

revision = "0004_dataset_staging"
down_revision = "0003_archive_import"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.artifacts (
            id uuid CONSTRAINT pk_artifacts PRIMARY KEY,
            relative_storage_key varchar(512) NOT NULL,
            sha256 varchar(64) NOT NULL,
            byte_size bigint NOT NULL,
            media_type varchar(100) NOT NULL,
            scope varchar(20) NOT NULL DEFAULT 'internal',
            owner_id uuid,
            license_status varchar(20) NOT NULL DEFAULT 'unverified',
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_artifacts_storage_key UNIQUE (relative_storage_key),
            CONSTRAINT fk_artifacts_owner_id FOREIGN KEY (owner_id)
                REFERENCES app.users (id) ON DELETE RESTRICT,
            CONSTRAINT ck_artifacts_sha256_format CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_artifacts_byte_size_nonnegative CHECK (byte_size >= 0),
            CONSTRAINT ck_artifacts_media_type_nonempty CHECK (media_type <> ''),
            CONSTRAINT ck_artifacts_scope CHECK (scope IN ('public','private','internal')),
            CONSTRAINT ck_artifacts_license_status
                CHECK (license_status IN ('unknown','unverified','verified','prohibited')),
            CONSTRAINT ck_artifacts_owner_matches_scope CHECK (
                (scope = 'private' AND owner_id IS NOT NULL)
                OR (scope <> 'private' AND owner_id IS NULL)),
            CONSTRAINT ck_artifacts_storage_key_relative CHECK (
                relative_storage_key NOT LIKE '/%'
                AND relative_storage_key NOT LIKE '%/'
                AND relative_storage_key !~ '(^|/)\.\.(/|$)'
                AND strpos(relative_storage_key, chr(92)) = 0)
        );
        CREATE INDEX ix_artifacts_sha256 ON app.artifacts (sha256);

        CREATE TABLE app.dataset_versions (
            id uuid CONSTRAINT pk_dataset_versions PRIMARY KEY,
            dataset_key varchar(120) NOT NULL,
            version integer NOT NULL,
            status varchar(20) NOT NULL DEFAULT 'staged',
            start_date date NOT NULL,
            end_date date NOT NULL,
            frequency varchar(20) NOT NULL,
            pipeline_version varchar(80) NOT NULL,
            code_commit varchar(64),
            config_hash varchar(64),
            dependency_lock_hash varchar(64),
            manifest_artifact_id uuid NOT NULL,
            content_sha256 varchar(64) NOT NULL,
            source_as_of timestamptz,
            retrieved_at timestamptz,
            quality jsonb NOT NULL DEFAULT '{}'::jsonb,
            supersedes_id uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_dataset_versions_key_version UNIQUE (dataset_key, version),
            CONSTRAINT uq_dataset_versions_key_content UNIQUE (dataset_key, content_sha256),
            CONSTRAINT uq_dataset_versions_id_key UNIQUE (id, dataset_key),
            CONSTRAINT fk_dataset_versions_manifest_artifact FOREIGN KEY (manifest_artifact_id)
                REFERENCES app.artifacts (id) ON DELETE RESTRICT,
            CONSTRAINT fk_dataset_versions_supersedes FOREIGN KEY (supersedes_id, dataset_key)
                REFERENCES app.dataset_versions (id, dataset_key) ON DELETE RESTRICT,
            CONSTRAINT ck_dataset_versions_key_format
                CHECK (dataset_key ~ '^[a-z0-9][a-z0-9-]{0,38}(\.[a-z0-9][a-z0-9-]{0,38}){0,2}$'),
            CONSTRAINT ck_dataset_versions_version_positive CHECK (version >= 1),
            CONSTRAINT ck_dataset_versions_status
                CHECK (status IN ('staged','validated','approved','rejected')),
            CONSTRAINT ck_dataset_versions_frequency
                CHECK (frequency IN ('daily','weekly','monthly','snapshot')),
            CONSTRAINT ck_dataset_versions_window CHECK (end_date > start_date),
            CONSTRAINT ck_dataset_versions_pipeline_version_nonempty
                CHECK (pipeline_version <> ''),
            CONSTRAINT ck_dataset_versions_code_commit_format
                CHECK (code_commit IS NULL OR code_commit ~ '^[0-9a-f]{7,64}$'),
            CONSTRAINT ck_dataset_versions_config_hash_format
                CHECK (config_hash IS NULL OR config_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_dataset_versions_dependency_lock_hash_format
                CHECK (dependency_lock_hash IS NULL OR dependency_lock_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_dataset_versions_content_sha256_format
                CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_dataset_versions_quality_size
                CHECK (octet_length(quality::text) <= 32768)
        );

        -- Immutable history: identity columns never change; status may only
        -- move along the whitelist while the row is neither approved nor
        -- rejected (those rows are frozen forever, including quality).
        CREATE FUNCTION app.guard_dataset_version_update() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        BEGIN
            IF OLD.status IN ('approved','rejected') THEN
                RAISE EXCEPTION 'dataset version % is % and immutable', OLD.id, OLD.status;
            END IF;
            IF (NEW.id, NEW.dataset_key, NEW.version, NEW.content_sha256,
                NEW.manifest_artifact_id, NEW.start_date, NEW.end_date, NEW.frequency,
                NEW.pipeline_version, NEW.code_commit, NEW.config_hash,
                NEW.dependency_lock_hash, NEW.source_as_of, NEW.retrieved_at, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.dataset_key, OLD.version, OLD.content_sha256,
                OLD.manifest_artifact_id, OLD.start_date, OLD.end_date, OLD.frequency,
                OLD.pipeline_version, OLD.code_commit, OLD.config_hash,
                OLD.dependency_lock_hash, OLD.source_as_of, OLD.retrieved_at, OLD.created_at) THEN
                RAISE EXCEPTION 'identity columns of a dataset version are immutable';
            END IF;
            IF NEW.status <> OLD.status AND NOT (
                   (OLD.status = 'staged' AND NEW.status IN ('validated','rejected'))
                OR (OLD.status = 'validated' AND NEW.status IN ('approved','rejected'))) THEN
                RAISE EXCEPTION 'illegal dataset version status transition % -> %',
                    OLD.status, NEW.status;
            END IF;
            RETURN NEW;
        END $$;
        REVOKE ALL ON FUNCTION app.guard_dataset_version_update() FROM PUBLIC;
        CREATE TRIGGER dataset_versions_guard BEFORE UPDATE ON app.dataset_versions
            FOR EACH ROW EXECUTE FUNCTION app.guard_dataset_version_update();

        CREATE TABLE app.dataset_metrics (
            dataset_version_id uuid NOT NULL,
            metric_definition_id uuid NOT NULL,
            CONSTRAINT pk_dataset_metrics
                PRIMARY KEY (dataset_version_id, metric_definition_id),
            CONSTRAINT fk_dataset_metrics_version FOREIGN KEY (dataset_version_id)
                REFERENCES app.dataset_versions (id) ON DELETE RESTRICT
        );

        CREATE TABLE app.dataset_inputs (
            dataset_version_id uuid NOT NULL,
            artifact_id uuid NOT NULL,
            role varchar(20) NOT NULL,
            source_id varchar(40),
            ingestion_run_id uuid,
            query_hash varchar(64),
            CONSTRAINT pk_dataset_inputs PRIMARY KEY (dataset_version_id, artifact_id, role),
            CONSTRAINT fk_dataset_inputs_version FOREIGN KEY (dataset_version_id)
                REFERENCES app.dataset_versions (id) ON DELETE RESTRICT,
            CONSTRAINT fk_dataset_inputs_artifact FOREIGN KEY (artifact_id)
                REFERENCES app.artifacts (id) ON DELETE RESTRICT,
            CONSTRAINT fk_dataset_inputs_source FOREIGN KEY (source_id)
                REFERENCES app.sources (id),
            CONSTRAINT ck_dataset_inputs_role
                CHECK (role IN ('raw','normalized','price','sql','config')),
            CONSTRAINT ck_dataset_inputs_query_hash_format
                CHECK (query_hash IS NULL OR query_hash ~ '^[0-9a-f]{64}$')
        );
        CREATE INDEX ix_dataset_inputs_artifact ON app.dataset_inputs (artifact_id);

        CREATE TABLE app.metric_observations (
            dataset_version_id uuid NOT NULL,
            metric_definition_id uuid NOT NULL,
            period_start timestamptz NOT NULL,
            period_end timestamptz NOT NULL,
            dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
            dimensions_hash varchar(64) NOT NULL,
            value numeric(78, 30),
            quality_status varchar(20) NOT NULL,
            bound_kind varchar(20),
            source_record_ref varchar(200),
            quality jsonb NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT pk_metric_observations
                PRIMARY KEY (dataset_version_id, metric_definition_id, period_start,
                             dimensions_hash),
            CONSTRAINT fk_metric_observations_member
                FOREIGN KEY (dataset_version_id, metric_definition_id)
                REFERENCES app.dataset_metrics (dataset_version_id, metric_definition_id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_metric_observations_period CHECK (period_end > period_start),
            CONSTRAINT ck_metric_observations_quality_status
                CHECK (quality_status IN ('verified','missing','unavailable')),
            CONSTRAINT ck_metric_observations_bound_kind
                CHECK (bound_kind IN ('exact','estimate','lower','upper')),
            -- Missing/unavailable quality implies a NULL value; a present value
            -- is verified; a verified zero is an explicit value.
            CONSTRAINT ck_metric_observations_value_null_consistency CHECK (
                (quality_status IN ('missing','unavailable')) = (value IS NULL)),
            CONSTRAINT ck_metric_observations_bound_null_consistency CHECK (
                (bound_kind IS NULL) = (value IS NULL)),
            CONSTRAINT ck_metric_observations_null_reason CHECK (
                value IS NOT NULL OR quality ? 'reason'),
            CONSTRAINT ck_metric_observations_dimensions_hash_format
                CHECK (dimensions_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_metric_observations_dimensions_size
                CHECK (octet_length(dimensions::text) <= 4096),
            CONSTRAINT ck_metric_observations_quality_size
                CHECK (octet_length(quality::text) <= 4096)
        );
        CREATE INDEX ix_metric_observations_window
            ON app.metric_observations (dataset_version_id, period_start);

        CREATE TABLE app.active_datasets (
            dataset_key varchar(120) CONSTRAINT pk_active_datasets PRIMARY KEY,
            dataset_version_id uuid NOT NULL,
            published_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_active_datasets_version FOREIGN KEY (dataset_version_id, dataset_key)
                REFERENCES app.dataset_versions (id, dataset_key) ON DELETE RESTRICT,
            CONSTRAINT ck_active_datasets_key_format
                CHECK (dataset_key ~ '^[a-z0-9][a-z0-9-]{0,38}(\.[a-z0-9][a-z0-9-]{0,38}){0,2}$')
        );

        -- The active pointer may only target an approved version of the same
        -- dataset key (the composite FK enforces the key; this enforces the
        -- approved gate at switch time inside the publish transaction).
        CREATE FUNCTION app.guard_active_dataset_pointer() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        DECLARE
            v_key text;
            v_status text;
        BEGIN
            SELECT dataset_key, status INTO v_key, v_status
                FROM app.dataset_versions WHERE id = NEW.dataset_version_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'active pointer targets a missing dataset version';
            END IF;
            IF v_key IS DISTINCT FROM NEW.dataset_key THEN
                RAISE EXCEPTION 'active pointer must target a version of the same dataset key';
            END IF;
            IF v_status <> 'approved' THEN
                RAISE EXCEPTION 'active pointer requires an approved dataset version, got %',
                    v_status;
            END IF;
            RETURN NEW;
        END $$;
        REVOKE ALL ON FUNCTION app.guard_active_dataset_pointer() FROM PUBLIC;
        CREATE TRIGGER active_datasets_guard BEFORE INSERT OR UPDATE ON app.active_datasets
            FOR EACH ROW EXECUTE FUNCTION app.guard_active_dataset_pointer();

        -- Scientific data zone: FORCE RLS keeps every role without a policy
        -- (including the table owner near_migrator and grant-less near_public)
        -- locked out; near_operator holds the only write policies and near_app
        -- a read-only policy. Private artifacts are additionally owner-scoped.
        ALTER TABLE app.artifacts ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.artifacts FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.dataset_versions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.dataset_versions FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.dataset_metrics ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.dataset_metrics FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.dataset_inputs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.dataset_inputs FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.metric_observations ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.metric_observations FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.active_datasets ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.active_datasets FORCE ROW LEVEL SECURITY;

        CREATE POLICY artifacts_operator ON app.artifacts TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY artifacts_app_read ON app.artifacts FOR SELECT TO near_app
            USING (scope <> 'private' OR owner_id = app.current_user_id());
        CREATE POLICY dataset_versions_operator ON app.dataset_versions TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY dataset_versions_app_read ON app.dataset_versions FOR SELECT TO near_app
            USING (true);
        CREATE POLICY dataset_metrics_operator ON app.dataset_metrics TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY dataset_metrics_app_read ON app.dataset_metrics FOR SELECT TO near_app
            USING (true);
        CREATE POLICY dataset_inputs_operator ON app.dataset_inputs TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY dataset_inputs_app_read ON app.dataset_inputs FOR SELECT TO near_app
            USING (true);
        CREATE POLICY metric_observations_operator ON app.metric_observations TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY metric_observations_app_read ON app.metric_observations
            FOR SELECT TO near_app USING (true);
        CREATE POLICY active_datasets_operator ON app.active_datasets TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY active_datasets_app_read ON app.active_datasets FOR SELECT TO near_app
            USING (true);

        -- Artifacts and history are append-only: no UPDATE or DELETE grant
        -- exists for any runtime role. Status transitions use the narrow
        -- dataset_versions UPDATE grant; the pointer switch uses the narrow
        -- active_datasets INSERT/UPDATE grant.
        GRANT SELECT ON app.artifacts TO near_app, near_operator;
        GRANT INSERT(id, relative_storage_key, sha256, byte_size, media_type, scope,
                     owner_id, license_status) ON app.artifacts TO near_operator;
        GRANT SELECT ON app.dataset_versions TO near_app, near_operator;
        GRANT INSERT(id, dataset_key, version, status, start_date, end_date, frequency,
                     pipeline_version, code_commit, config_hash, dependency_lock_hash,
                     manifest_artifact_id, content_sha256, source_as_of, retrieved_at, quality)
            ON app.dataset_versions TO near_operator;
        GRANT UPDATE(status, quality, supersedes_id) ON app.dataset_versions TO near_operator;
        GRANT SELECT ON app.dataset_metrics TO near_app, near_operator;
        GRANT INSERT(dataset_version_id, metric_definition_id) ON app.dataset_metrics
            TO near_operator;
        GRANT SELECT ON app.dataset_inputs TO near_app, near_operator;
        GRANT INSERT(dataset_version_id, artifact_id, role, source_id, ingestion_run_id,
                     query_hash) ON app.dataset_inputs TO near_operator;
        GRANT SELECT ON app.metric_observations TO near_app, near_operator;
        GRANT INSERT(dataset_version_id, metric_definition_id, period_start, period_end,
                     dimensions, dimensions_hash, value, quality_status, bound_kind,
                     source_record_ref, quality) ON app.metric_observations TO near_operator;
        GRANT SELECT ON app.active_datasets TO near_app, near_operator;
        GRANT INSERT(dataset_key, dataset_version_id), UPDATE(dataset_version_id, published_at)
            ON app.active_datasets TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.active_datasets;
        DROP TABLE app.metric_observations;
        DROP TABLE app.dataset_inputs;
        DROP TABLE app.dataset_metrics;
        DROP TABLE app.dataset_versions;
        DROP TABLE app.artifacts;
        DROP FUNCTION app.guard_active_dataset_pointer();
        DROP FUNCTION app.guard_dataset_version_update();
    """)
