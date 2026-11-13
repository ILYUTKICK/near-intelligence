"""NI-072: lightweight private document organization (tags + favorite flag).

Creates the owner-scoped private metadata table defined by DATABASE_SCHEMA.md
(document_organization): exactly one row per organized document, one composite
FK into the private document chain, FORCE RLS with the 0002/0011 policy pair.
Tags and favorites are separate owner-scoped metadata — NEVER part of
document_versions.content and never a revision: the immutable research chain
(content, resolved_contexts, content_sha256, revision, documents.updated_at)
is untouched by every statement this table enables.

Bounded metadata, enforced twice (service normalizes before writing; the
database re-validates whatever reaches the table, so no path — including raw
SQL — can store an unbounded or unnormalized tag): at most 20 tags per
document, each 1..40 chars after the documented normalization (trim + lower),
already duplicate-free and already in normalized form.

Deliberate ordering decision: the document list stays ordered by
documents.updated_at DESC, id (the NI-023 list order). Metadata edits write
ONLY this table — app.documents is never updated by organization writes, so
tagging/favoriting cannot reorder the owner's list, cannot mint a revision
and cannot move a document's recency. This table's own updated_at tracks
metadata recency for bookkeeping only.
"""

from alembic import op

revision = "0014_document_organization"
down_revision = "0012_export_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE FUNCTION app.is_valid_tag_set(tags text[]) RETURNS boolean
        LANGUAGE sql STABLE AS $$
            SELECT COALESCE(array_length(tags, 1), 0) <= 20
               AND NOT EXISTS (
                    SELECT 1 FROM unnest(tags) AS element(value)
                    WHERE element.value = ''
                       OR char_length(element.value) > 40
                       OR element.value <> btrim(element.value)
                       OR element.value <> lower(element.value))
               AND (SELECT count(DISTINCT element.value) FROM unnest(tags) AS element(value))
                   = COALESCE(array_length(tags, 1), 0)
        $$;
        REVOKE ALL ON FUNCTION app.is_valid_tag_set(text[]) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION app.is_valid_tag_set(text[]) TO near_app;

        CREATE TABLE app.document_organization (
            document_id uuid NOT NULL,
            owner_id uuid NOT NULL,
            tags text[] NOT NULL DEFAULT '{}'::text[],
            favorite boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_document_organization PRIMARY KEY (document_id),
            -- The database re-validates the documented bounds on every write,
            -- even for raw SQL: bounded count, nonempty lowercase normalized
            -- elements (trim + lower), no duplicates.
            CONSTRAINT ck_document_organization_tags
                CHECK (app.is_valid_tag_set(tags)),
            CONSTRAINT uq_document_organization_id_owner UNIQUE (document_id, owner_id),
            CONSTRAINT fk_document_organization_document FOREIGN KEY (document_id, owner_id)
                REFERENCES app.documents (id, owner_id) ON DELETE CASCADE
        );

        -- Metadata recency stays inside this table; it never touches
        -- app.documents.updated_at, so list order is stable under tagging.
        CREATE FUNCTION app.touch_document_organization_updated_at() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN NEW.updated_at = clock_timestamp(); RETURN NEW; END $$;
        REVOKE ALL ON FUNCTION app.touch_document_organization_updated_at() FROM PUBLIC;
        CREATE TRIGGER document_organization_updated_at BEFORE UPDATE
            ON app.document_organization
            FOR EACH ROW
            WHEN (OLD.tags IS DISTINCT FROM NEW.tags
                  OR OLD.favorite IS DISTINCT FROM NEW.favorite)
            EXECUTE FUNCTION app.touch_document_organization_updated_at();

        ALTER TABLE app.document_organization ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.document_organization FORCE ROW LEVEL SECURITY;

        -- Runtime role: only the transaction-local verified owner, and only
        -- while that account is not disabled (0002/0011 fail-closed pattern).
        CREATE POLICY document_organization_self_select ON app.document_organization
            FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_organization_self_insert ON app.document_organization
            FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_organization_self_update ON app.document_organization
            FOR UPDATE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active())
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_organization_self_delete ON app.document_organization
            FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());

        -- Operator role: no read/write access to private metadata. DELETE is
        -- the narrow purge power; the USING(true) policy references no columns
        -- so no SELECT grant is implied (0002 pattern).
        CREATE POLICY document_organization_operator_delete ON app.document_organization
            FOR DELETE TO near_operator USING (true);

        -- No policies exist for near_migrator (DDL only) or near_public;
        -- FORCE RLS keeps both locked out even from this table.
        GRANT SELECT, DELETE ON app.document_organization TO near_app;
        GRANT INSERT(document_id, owner_id, tags, favorite)
            ON app.document_organization TO near_app;
        GRANT UPDATE(tags, favorite, updated_at) ON app.document_organization TO near_app;
        GRANT DELETE ON app.document_organization TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.document_organization;
        DROP FUNCTION app.touch_document_organization_updated_at();
        DROP FUNCTION app.is_valid_tag_set(text[]);
    """)
