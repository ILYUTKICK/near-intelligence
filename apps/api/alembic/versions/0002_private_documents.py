"""NI-019: private document chain with request-scoped RLS ownership policies.

Creates the owner-scoped private tables defined by DATABASE_SCHEMA.md
(documents, document_versions, document_blocks) so centralized ownership
checks and row-level security operate on real nested private references.
Every policy pairs the owner predicate with app.identity_is_active(), so a
disabled local user loses private access even before the API dependency
rejects them (defense in depth, fail closed).

Deliberate scope boundaries: scientific/global tables (artifacts,
dataset_versions, chart_definitions), the saved_charts/research_snapshots
tables and the insight/hypothesis/evidence projections are migrations of
their owning tasks (NI-028/NI-031/NI-035/NI-036) and plug into the same
helpers. Roles are never created by migrations (near_migrator is
NOCREATEROLE by design); scripts/db/010-roles.sql remains the only
role bootstrap. Blocks are server-derived projections: near_app can insert
and cascade-delete them but never update them.
"""

from alembic import op

revision = "0002_private_documents"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION app.identity_is_active() RETURNS boolean
        LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog
        AS $$ SELECT EXISTS (SELECT 1 FROM app.users u
                             WHERE u.id = app.current_user_id() AND u.disabled_at IS NULL) $$;
        REVOKE ALL ON FUNCTION app.identity_is_active() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION app.identity_is_active() TO near_app;

        CREATE TABLE app.documents (
            id uuid CONSTRAINT pk_documents PRIMARY KEY,
            owner_id uuid NOT NULL,
            title varchar(200) NOT NULL,
            revision bigint NOT NULL DEFAULT 1,
            current_version_id uuid,
            schema_version integer NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_documents_title_nonempty CHECK (title <> ''),
            CONSTRAINT ck_documents_revision_positive CHECK (revision > 0),
            CONSTRAINT uq_documents_id_owner UNIQUE (id, owner_id),
            CONSTRAINT fk_documents_owner_id FOREIGN KEY (owner_id)
                REFERENCES app.users (id) ON DELETE CASCADE
        );
        CREATE INDEX ix_documents_owner_updated_at
            ON app.documents (owner_id, updated_at DESC, id);
        CREATE FUNCTION app.touch_documents_updated_at() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN NEW.updated_at = clock_timestamp(); RETURN NEW; END $$;
        REVOKE ALL ON FUNCTION app.touch_documents_updated_at() FROM PUBLIC;
        CREATE TRIGGER documents_updated_at BEFORE UPDATE ON app.documents
            FOR EACH ROW EXECUTE FUNCTION app.touch_documents_updated_at();

        CREATE TABLE app.document_versions (
            id uuid CONSTRAINT pk_document_versions PRIMARY KEY,
            document_id uuid NOT NULL,
            owner_id uuid NOT NULL,
            revision bigint NOT NULL,
            schema_version integer NOT NULL,
            content jsonb NOT NULL,
            resolved_contexts jsonb,
            content_sha256 varchar(64) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_document_versions_revision_positive CHECK (revision > 0),
            CONSTRAINT ck_document_versions_content_sha256_format
                CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT uq_document_versions_document_revision UNIQUE (document_id, revision),
            CONSTRAINT uq_document_versions_id_document_owner UNIQUE (id, document_id, owner_id),
            CONSTRAINT fk_document_versions_document_id FOREIGN KEY (document_id, owner_id)
                REFERENCES app.documents (id, owner_id) ON DELETE CASCADE
        );
        -- Immutable versions: no UPDATE grant or policy for the runtime role.
        -- The deferred FK from documents keeps the pointer inside the same
        -- owner; the composite FK makes cross-owner references impossible.
        ALTER TABLE app.documents
            ADD CONSTRAINT fk_documents_current_version FOREIGN KEY
                (current_version_id, id, owner_id)
                REFERENCES app.document_versions (id, document_id, owner_id)
                DEFERRABLE INITIALLY IMMEDIATE;

        CREATE TABLE app.document_blocks (
            document_version_id uuid NOT NULL,
            block_id uuid NOT NULL,
            document_id uuid NOT NULL,
            owner_id uuid NOT NULL,
            parent_block_id uuid,
            position integer NOT NULL,
            block_type varchar(40) NOT NULL,
            attrs jsonb NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT pk_document_blocks PRIMARY KEY (document_version_id, block_id),
            CONSTRAINT ck_document_blocks_position_nonnegative CHECK (position >= 0),
            CONSTRAINT ck_document_blocks_parent_not_self
                CHECK (parent_block_id IS NULL OR parent_block_id <> block_id),
            CONSTRAINT uq_document_blocks_version_parent_position
                UNIQUE NULLS NOT DISTINCT (document_version_id, parent_block_id, position),
            CONSTRAINT fk_document_blocks_version_id FOREIGN KEY
                (document_version_id, document_id, owner_id)
                REFERENCES app.document_versions (id, document_id, owner_id) ON DELETE CASCADE,
            CONSTRAINT fk_document_blocks_parent FOREIGN KEY
                (document_version_id, parent_block_id)
                REFERENCES app.document_blocks (document_version_id, block_id) ON DELETE CASCADE
        );
        CREATE INDEX ix_document_blocks_version_type
            ON app.document_blocks (document_version_id, block_type);

        ALTER TABLE app.documents ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.documents FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.document_versions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.document_versions FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.document_blocks ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.document_blocks FORCE ROW LEVEL SECURITY;

        -- Runtime role: only the transaction-local verified owner, and only
        -- while that account is not disabled. Absent and not-owned rows are
        -- the same empty set to every query.
        CREATE POLICY documents_self_select ON app.documents FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY documents_self_insert ON app.documents FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY documents_self_update ON app.documents FOR UPDATE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active())
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY documents_self_delete ON app.documents FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_versions_self_select ON app.document_versions FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_versions_self_insert ON app.document_versions FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_versions_self_delete ON app.document_versions FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_blocks_self_select ON app.document_blocks FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_blocks_self_insert ON app.document_blocks FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_blocks_self_delete ON app.document_blocks FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());

        -- Operator role: no read/write access to private content. DELETE is
        -- the narrow purge power for the operator-assisted account removal
        -- (DATABASE_SCHEMA.md); the USING(true) policy references no columns
        -- so no SELECT grant is implied. Purges flow through the users table
        -- cascade, never through content queries.
        CREATE POLICY documents_operator_delete ON app.documents FOR DELETE TO near_operator
            USING (true);
        CREATE POLICY document_versions_operator_delete ON app.document_versions
            FOR DELETE TO near_operator USING (true);
        CREATE POLICY document_blocks_operator_delete ON app.document_blocks
            FOR DELETE TO near_operator USING (true);

        -- No policies exist for near_migrator (DDL only) or near_public
        -- (separate limited context, granted nothing on schema app); FORCE
        -- RLS keeps both locked out even from their own tables.
        GRANT SELECT, DELETE ON app.documents TO near_app;
        GRANT INSERT(id, owner_id, title, revision, schema_version, current_version_id)
            ON app.documents TO near_app;
        GRANT UPDATE(title, revision, schema_version, current_version_id, updated_at)
            ON app.documents TO near_app;
        GRANT SELECT, DELETE ON app.document_versions TO near_app;
        GRANT INSERT(id, document_id, owner_id, revision, schema_version, content,
                     resolved_contexts, content_sha256) ON app.document_versions TO near_app;
        GRANT SELECT, DELETE ON app.document_blocks TO near_app;
        GRANT INSERT(document_version_id, document_id, owner_id, block_id, parent_block_id,
                     position, block_type, attrs) ON app.document_blocks TO near_app;
        GRANT DELETE ON app.documents, app.document_versions, app.document_blocks
            TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.document_blocks;
        ALTER TABLE app.documents
            DROP CONSTRAINT fk_documents_current_version;
        DROP TABLE app.document_versions;
        DROP TRIGGER documents_updated_at ON app.documents;
        DROP FUNCTION app.touch_documents_updated_at();
        DROP TABLE app.documents;
        DROP FUNCTION app.identity_is_active();
    """)
