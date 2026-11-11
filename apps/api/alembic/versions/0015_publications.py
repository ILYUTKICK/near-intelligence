"""NI-045: public research publications and the document attribution pin.

``app.research_publications`` holds the operator-reviewed full public
projection of a research release (DATABASE_SCHEMA.md "research_publications"):
one immutable (slug, version) row whose ``content`` is the canonical editor
document JSON that ``GET /api/publications/{slug}`` serves and the duplicate
flow clones into private IDs. Only published rows are public: the CHECK
accepts ``status = 'published'`` only, so an unreviewed projection cannot
exist as a row at all (the model_runs write-once pattern of migration 0010).
Private source-document identifiers are never serialized into the stored
content — the seed gate re-parses every projection through the canonical
validator.

Row-level security posture (public rows, not owner-scoped):

- ``near_app`` SELECTs published rows for EVERY identity — publication reads
  are public (the route opens the transaction with no identity), while a
  hypothetical non-published row is invisible the same way an absent one is.
  near_app has no INSERT/UPDATE/DELETE: publication is an operator CLI flow
  (API_SPECIFICATION), never a browser write.
- ``near_operator`` INSERTs and DELETEs (operator seeding and correction).
  There is deliberately no UPDATE for any role: a published release is
  immutable, and a correction appends a new version (UNIQUE(slug, version))
  or deletes the mistaken row entirely.
- ``near_migrator`` (DDL only) and ``near_public`` get no policies; FORCE RLS
  keeps both locked out.

``app.publication_model_runs`` binds published runs into a publication (the
public evidence manifest's model-run references, reviewed for license and
access at seed time). near_app may read a binding only while its publication
is published.

``app.documents.source_publication_id`` records which publication release a
private document was duplicated from (NULL for ordinary documents). The
release is immutable provenance, so the FK is RESTRICT: an operator cannot
silently orphan the retained attribution; a correction that must remove a
release has to account for its duplicates first. The column is written once
at duplication time inside the INSERT grant; no UPDATE grant is added.
"""

from alembic import op

revision = "0015_publications"
down_revision = "0012_export_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.research_publications (
            id uuid CONSTRAINT pk_research_publications PRIMARY KEY,
            slug varchar(80) NOT NULL,
            version integer NOT NULL,
            title varchar(200) NOT NULL,
            content jsonb NOT NULL,
            evidence_manifest jsonb NOT NULL DEFAULT '[]'::jsonb,
            content_sha256 varchar(64) NOT NULL,
            status varchar(20) NOT NULL DEFAULT 'published',
            published_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_research_publications_slug CHECK
                (slug ~ '^[a-z0-9][a-z0-9-]{0,79}$'),
            CONSTRAINT ck_research_publications_version CHECK (version >= 1),
            CONSTRAINT ck_research_publications_title_nonempty CHECK (title <> ''),
            CONSTRAINT ck_research_publications_status CHECK (status = 'published'),
            CONSTRAINT ck_research_publications_content_sha256_format
                CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            -- Defense in depth behind the seed gate's canonical parse: the
            -- stored public projection stays inside the editor content bound.
            CONSTRAINT ck_research_publications_content_size
                CHECK (octet_length(content::text) <= 2097152),
            CONSTRAINT ck_research_publications_manifest_size
                CHECK (octet_length(evidence_manifest::text) <= 65536),
            CONSTRAINT uq_research_publications_slug_version UNIQUE (slug, version)
        );
        -- The unique (slug, version) index serves the latest-version lookup.

        CREATE TABLE app.publication_model_runs (
            publication_id uuid NOT NULL,
            model_run_id uuid NOT NULL,
            CONSTRAINT pk_publication_model_runs
                PRIMARY KEY (publication_id, model_run_id),
            CONSTRAINT fk_publication_model_runs_publication
                FOREIGN KEY (publication_id) REFERENCES app.research_publications (id)
                ON DELETE CASCADE,
            -- Published runs are immutable rows (migration 0010): RESTRICT
            -- keeps a binding from outliving the run it advertises.
            CONSTRAINT fk_publication_model_runs_model_run
                FOREIGN KEY (model_run_id) REFERENCES app.model_runs (run_id)
                ON DELETE RESTRICT
        );

        ALTER TABLE app.research_publications ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.research_publications FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.publication_model_runs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.publication_model_runs FORCE ROW LEVEL SECURITY;

        -- Runtime role: published releases are public to every verified (or
        -- anonymous) runtime identity; unpublished rows do not exist by
        -- constraint but stay invisible here as defense in depth.
        CREATE POLICY research_publications_public_select ON app.research_publications
            FOR SELECT TO near_app
            USING (status = 'published');
        CREATE POLICY publication_model_runs_public_select ON app.publication_model_runs
            FOR SELECT TO near_app
            USING (EXISTS (SELECT 1 FROM app.research_publications p
                           WHERE p.id = publication_id AND p.status = 'published'));

        -- Operator role: seed and correction only. No UPDATE policy exists —
        -- a published release is immutable, corrections delete and reseed.
        CREATE POLICY research_publications_operator_insert
            ON app.research_publications FOR INSERT TO near_operator
            WITH CHECK (status = 'published');
        CREATE POLICY research_publications_operator_select
            ON app.research_publications FOR SELECT TO near_operator USING (true);
        CREATE POLICY research_publications_operator_delete
            ON app.research_publications FOR DELETE TO near_operator USING (true);
        CREATE POLICY publication_model_runs_operator_insert
            ON app.publication_model_runs FOR INSERT TO near_operator WITH CHECK (true);
        CREATE POLICY publication_model_runs_operator_select
            ON app.publication_model_runs FOR SELECT TO near_operator USING (true);
        CREATE POLICY publication_model_runs_operator_delete
            ON app.publication_model_runs FOR DELETE TO near_operator USING (true);

        GRANT SELECT ON app.research_publications TO near_app;
        GRANT SELECT ON app.publication_model_runs TO near_app;
        GRANT SELECT, INSERT, DELETE ON app.research_publications TO near_operator;
        GRANT SELECT, INSERT, DELETE ON app.publication_model_runs TO near_operator;

        -- The private duplicate carries its public source as one-time
        -- attribution metadata. RESTRICT keeps the provenance from being
        -- orphaned by an operator delete; no UPDATE grant is granted for it.
        ALTER TABLE app.documents
            ADD COLUMN source_publication_id uuid,
            ADD CONSTRAINT fk_documents_source_publication
                FOREIGN KEY (source_publication_id)
                REFERENCES app.research_publications (id) ON DELETE RESTRICT;
        GRANT INSERT(id, owner_id, title, revision, schema_version,
                     current_version_id, source_publication_id)
            ON app.documents TO near_app;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE app.documents DROP CONSTRAINT fk_documents_source_publication;
        ALTER TABLE app.documents DROP COLUMN source_publication_id;
        DROP TABLE app.publication_model_runs;
        DROP TABLE app.research_publications;
    """)
