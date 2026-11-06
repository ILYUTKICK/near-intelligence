"""NI-027: operator-zone archive import lineage (metadata only, no file bytes).

Creates the four tables the read-only archive import writes:

- ``sources``: stable SRC-* catalog aligned with the ``data_sources`` entity in
  DATABASE_SCHEMA.md (subset needed for lineage import; no secrets, license
  visibility is recorded, never assumed verified).
- ``import_batches``: one row per verified import; the manifest SHA-256 is the
  unique idempotency key, so re-importing the same manifest changes nothing.
- ``imported_files``: per-file path/hash/size/role/coverage metadata. File
  contents are never stored; the original archive stays untouched on disk.
- ``source_runs``: retrieval lineage documented by cohort manifests
  (endpoint/job identity + retrieval time), the historical counterpart of the
  ingestion runs; the live ingestion lifecycle remains NI-028/NI-030 scope.

Deliberate scope boundaries: artifacts, dataset_versions, dataset_inputs and
the publication pointer belong to NI-028 and are not created here. These
tables describe the operator import zone: near_operator writes and reads
them; near_app gets read-only access to the public ``sources`` catalog only;
near_public and near_migrator receive nothing. Roles are never created by
migrations; scripts/db/010-roles.sql remains the only role bootstrap.
"""

from alembic import op

revision = "0003_archive_import"
down_revision = "0002_private_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.sources (
            id varchar(40) CONSTRAINT pk_sources PRIMARY KEY,
            name varchar(200) NOT NULL,
            docs_url varchar(500),
            base_url varchar(500),
            access_status varchar(20) NOT NULL DEFAULT 'documented',
            license_status varchar(20) NOT NULL DEFAULT 'unverified',
            verified_at timestamptz,
            lineage jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_sources_id_format CHECK (id ~ '^SRC-[A-Z]+(-[A-Z]+)*$'),
            CONSTRAINT ck_sources_access_status
                CHECK (access_status IN ('disabled','documented','approved')),
            CONSTRAINT ck_sources_license_status
                CHECK (license_status IN ('unknown','unverified','verified','prohibited')),
            CONSTRAINT ck_sources_lineage_size CHECK (octet_length(lineage::text) <= 4096)
        );
        CREATE FUNCTION app.touch_sources_updated_at() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN NEW.updated_at = clock_timestamp(); RETURN NEW; END $$;
        REVOKE ALL ON FUNCTION app.touch_sources_updated_at() FROM PUBLIC;
        CREATE TRIGGER sources_updated_at BEFORE UPDATE ON app.sources
            FOR EACH ROW EXECUTE FUNCTION app.touch_sources_updated_at();

        CREATE TABLE app.import_batches (
            id uuid CONSTRAINT pk_import_batches PRIMARY KEY,
            manifest_sha256 varchar(64) NOT NULL,
            registry_sha256 varchar(64) NOT NULL,
            manifest_path varchar(1024) NOT NULL,
            archive_root varchar(1024) NOT NULL,
            manifest_file_count integer NOT NULL,
            verified_bytes bigint NOT NULL,
            cohort_count integer NOT NULL,
            source_count integer NOT NULL,
            importer varchar(200) NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_import_batches_manifest UNIQUE (manifest_sha256),
            CONSTRAINT ck_import_batches_manifest_sha256_format
                CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_import_batches_registry_sha256_format
                CHECK (registry_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_import_batches_manifest_file_count_positive
                CHECK (manifest_file_count > 0),
            CONSTRAINT ck_import_batches_verified_bytes_nonnegative CHECK (verified_bytes >= 0),
            CONSTRAINT ck_import_batches_cohort_count_positive CHECK (cohort_count > 0),
            CONSTRAINT ck_import_batches_source_count_nonnegative CHECK (source_count >= 0)
        );

        CREATE TABLE app.imported_files (
            batch_id uuid NOT NULL,
            relative_path varchar(1024) NOT NULL,
            cohort varchar(80) NOT NULL,
            sha256 varchar(64) NOT NULL,
            byte_size bigint NOT NULL,
            file_role varchar(20) NOT NULL,
            coverage_scope varchar(40) NOT NULL,
            coverage_start date,
            coverage_end_exclusive date,
            source_id varchar(40),
            license_status varchar(20) NOT NULL DEFAULT 'unverified',
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT pk_imported_files PRIMARY KEY (batch_id, relative_path),
            CONSTRAINT fk_imported_files_batch_id FOREIGN KEY (batch_id)
                REFERENCES app.import_batches (id),
            CONSTRAINT fk_imported_files_source_id FOREIGN KEY (source_id)
                REFERENCES app.sources (id),
            CONSTRAINT ck_imported_files_sha256_format CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_imported_files_byte_size_nonnegative CHECK (byte_size >= 0),
            CONSTRAINT ck_imported_files_file_role
                CHECK (file_role IN ('raw','aggregate','provenance','editorial','script')),
            CONSTRAINT ck_imported_files_coverage_scope
                CHECK (coverage_scope IN ('raw_saved_response','aggregate_window',
                       'partial_raw_audit','point_in_time_snapshot','process_documentation')),
            CONSTRAINT ck_imported_files_license_status
                CHECK (license_status IN ('unknown','unverified','verified','prohibited')),
            CONSTRAINT ck_imported_files_path_relative
                CHECK (relative_path NOT LIKE '/%' AND relative_path !~ '(^|/)\.\.(/|$)'),
            CONSTRAINT ck_imported_files_cohort_format
                CHECK (cohort ~ '^[a-z0-9][a-z0-9-]{0,78}$'),
            CONSTRAINT ck_imported_files_metadata_size
                CHECK (octet_length(metadata::text) <= 4096),
            CONSTRAINT ck_imported_files_coverage_window CHECK (
                coverage_end_exclusive IS NULL OR coverage_start IS NULL
                OR coverage_end_exclusive > coverage_start)
        );
        CREATE INDEX ix_imported_files_cohort ON app.imported_files (cohort, relative_path);
        CREATE INDEX ix_imported_files_source ON app.imported_files (source_id);

        CREATE TABLE app.source_runs (
            id uuid CONSTRAINT pk_source_runs PRIMARY KEY,
            batch_id uuid NOT NULL,
            source_id varchar(40),
            query_identity varchar(1024),
            retrieval_utc timestamptz,
            byte_count bigint,
            request_count integer,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT fk_source_runs_batch_id FOREIGN KEY (batch_id)
                REFERENCES app.import_batches (id),
            CONSTRAINT fk_source_runs_source_id FOREIGN KEY (source_id)
                REFERENCES app.sources (id),
            CONSTRAINT ck_source_runs_metadata_size
                CHECK (octet_length(metadata::text) <= 4096)
        );
        CREATE INDEX ix_source_runs_batch ON app.source_runs (batch_id);
        CREATE INDEX ix_source_runs_source ON app.source_runs (source_id);

        -- Operator import zone: FORCE RLS keeps every other role (including
        -- the table owner near_migrator and grant-less near_public) locked
        -- out; near_operator holds the only policies.
        ALTER TABLE app.sources ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.sources FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.import_batches ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.import_batches FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.imported_files ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.imported_files FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.source_runs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.source_runs FORCE ROW LEVEL SECURITY;

        -- Public lineage metadata: any authenticated runtime principal may
        -- read the source catalog; contents-bearing tables stay operator-only.
        CREATE POLICY sources_app_read ON app.sources FOR SELECT TO near_app USING (true);
        CREATE POLICY sources_operator ON app.sources TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY import_batches_operator ON app.import_batches TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY imported_files_operator ON app.imported_files TO near_operator
            USING (true) WITH CHECK (true);
        CREATE POLICY source_runs_operator ON app.source_runs TO near_operator
            USING (true) WITH CHECK (true);

        GRANT SELECT ON app.sources TO near_app, near_operator;
        GRANT INSERT(id, name, docs_url, base_url, access_status, license_status,
                     verified_at, lineage), 
              UPDATE(name, docs_url, base_url, access_status, license_status,
                     verified_at, lineage, updated_at),
              DELETE ON app.sources TO near_operator;
        GRANT SELECT, INSERT(id, manifest_sha256, registry_sha256, manifest_path,
                             archive_root, manifest_file_count, verified_bytes,
                             cohort_count, source_count, importer), DELETE
            ON app.import_batches TO near_operator;
        GRANT SELECT, INSERT(batch_id, relative_path, cohort, sha256, byte_size,
                             file_role, coverage_scope, coverage_start,
                             coverage_end_exclusive, source_id, license_status,
                             metadata), DELETE
            ON app.imported_files TO near_operator;
        GRANT SELECT, INSERT(id, batch_id, source_id, query_identity, retrieval_utc,
                             byte_count, request_count, metadata), DELETE
            ON app.source_runs TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.source_runs;
        DROP TABLE app.imported_files;
        DROP TABLE app.import_batches;
        DROP TABLE app.sources;
        DROP FUNCTION app.touch_sources_updated_at();
    """)
