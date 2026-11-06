"""NI-036: insight/hypothesis/evidence projection tables for document revisions.

Completes the private document chain of DATABASE_SCHEMA.md ("Identity and
private documents"): ``insights``, ``hypotheses`` and ``evidence_links`` are
validated per-revision projections of the canonical
``document_versions.content`` JSON (NI-036 revision service) and inherit its
ownership model — every row carries the (version, document, owner) composite
FK introduced by 0002_private_documents, plus a same-version block FK and (for
evidence) a same-version hypothesis FK, so a projection can never reference a
foreign owner, a foreign document or a different revision even with raw SQL.

Policies and grants follow the 0002 pattern exactly (no existing policy is
duplicated): runtime rows are visible/writable only through the
transaction-local verified owner while the account is active; the runtime role
can INSERT and DELETE (revision regeneration and owner-checked document
deletion cascade) but never UPDATE a projection — projections are re-derived
from immutable revision content, so the truth never lives here; the operator
role keeps only the narrow purge DELETE. No policies exist for near_migrator
or near_public.

The polymorphic evidence target (target_kind model_run/citation) is NOT a
database FK: the revision service validates it against the allowed typed
targets (same-revision insight/chart block or public immutable artifact).
"""

from alembic import op

revision = "0005_document_projections"
down_revision = "0004_dataset_staging"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE app.insights (
            document_version_id uuid NOT NULL,
            insight_id uuid NOT NULL,
            document_id uuid NOT NULL,
            owner_id uuid NOT NULL,
            block_id uuid NOT NULL,
            type varchar(40) NOT NULL,
            classification varchar(40) NOT NULL,
            body jsonb NOT NULL,
            context jsonb NOT NULL,
            authored_at timestamptz NOT NULL,
            modified_at timestamptz NOT NULL,
            hypothesis_id uuid,
            CONSTRAINT pk_insights PRIMARY KEY (document_version_id, insight_id),
            CONSTRAINT fk_insights_version_id FOREIGN KEY
                (document_version_id, document_id, owner_id)
                REFERENCES app.document_versions (id, document_id, owner_id) ON DELETE CASCADE,
            CONSTRAINT fk_insights_block FOREIGN KEY
                (document_version_id, block_id)
                REFERENCES app.document_blocks (document_version_id, block_id) ON DELETE CASCADE
        );
        CREATE INDEX ix_insights_document_owner_modified
            ON app.insights (document_id, owner_id, modified_at DESC);

        CREATE TABLE app.hypotheses (
            document_version_id uuid NOT NULL,
            hypothesis_id uuid NOT NULL,
            document_id uuid NOT NULL,
            owner_id uuid NOT NULL,
            block_id uuid NOT NULL,
            statement text NOT NULL,
            assessment varchar(40) NOT NULL,
            authored_at timestamptz NOT NULL,
            modified_at timestamptz NOT NULL,
            CONSTRAINT pk_hypotheses PRIMARY KEY (document_version_id, hypothesis_id),
            CONSTRAINT ck_hypotheses_assessment CHECK (assessment IN
                ('untested','supported','mixed','weakened','insufficient_data')),
            CONSTRAINT fk_hypotheses_version_id FOREIGN KEY
                (document_version_id, document_id, owner_id)
                REFERENCES app.document_versions (id, document_id, owner_id) ON DELETE CASCADE,
            CONSTRAINT fk_hypotheses_block FOREIGN KEY
                (document_version_id, block_id)
                REFERENCES app.document_blocks (document_version_id, block_id) ON DELETE CASCADE
        );

        CREATE TABLE app.evidence_links (
            document_version_id uuid NOT NULL,
            evidence_id uuid NOT NULL,
            document_id uuid NOT NULL,
            owner_id uuid NOT NULL,
            block_id uuid NOT NULL,
            hypothesis_id uuid NOT NULL,
            classification varchar(40) NOT NULL,
            target_kind varchar(40) NOT NULL,
            target_id uuid NOT NULL,
            explanation text NOT NULL,
            CONSTRAINT pk_evidence_links PRIMARY KEY (document_version_id, evidence_id),
            CONSTRAINT ck_evidence_links_classification CHECK (classification IN
                ('supporting','contradicting','uncertain')),
            CONSTRAINT ck_evidence_links_target_kind CHECK (target_kind IN
                ('insight','chart_block','model_run','citation')),
            CONSTRAINT fk_evidence_links_version_id FOREIGN KEY
                (document_version_id, document_id, owner_id)
                REFERENCES app.document_versions (id, document_id, owner_id) ON DELETE CASCADE,
            CONSTRAINT fk_evidence_links_block FOREIGN KEY
                (document_version_id, block_id)
                REFERENCES app.document_blocks (document_version_id, block_id) ON DELETE CASCADE,
            CONSTRAINT fk_evidence_links_hypothesis FOREIGN KEY
                (document_version_id, hypothesis_id)
                REFERENCES app.hypotheses (document_version_id, hypothesis_id) ON DELETE CASCADE
        );
        CREATE INDEX ix_evidence_links_document_owner
            ON app.evidence_links (document_id, owner_id);

        ALTER TABLE app.insights ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.insights FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.hypotheses ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.hypotheses FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.evidence_links ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.evidence_links FORCE ROW LEVEL SECURITY;

        -- Runtime role: only the transaction-local verified owner, and only
        -- while that account is not disabled (0002_private_documents pattern).
        CREATE POLICY insights_self_select ON app.insights FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY insights_self_insert ON app.insights FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY insights_self_delete ON app.insights FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY hypotheses_self_select ON app.hypotheses FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY hypotheses_self_insert ON app.hypotheses FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY hypotheses_self_delete ON app.hypotheses FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY evidence_links_self_select ON app.evidence_links FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY evidence_links_self_insert ON app.evidence_links FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY evidence_links_self_delete ON app.evidence_links FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());

        -- Operator role: purge DELETE only, no read access to private content.
        CREATE POLICY insights_operator_delete ON app.insights FOR DELETE TO near_operator
            USING (true);
        CREATE POLICY hypotheses_operator_delete ON app.hypotheses FOR DELETE TO near_operator
            USING (true);
        CREATE POLICY evidence_links_operator_delete ON app.evidence_links
            FOR DELETE TO near_operator USING (true);

        -- No policies exist for near_migrator (DDL only) or near_public.
        GRANT SELECT, DELETE ON app.insights TO near_app;
        GRANT INSERT(document_version_id, insight_id, document_id, owner_id, block_id,
                     type, classification, body, context, authored_at, modified_at,
                     hypothesis_id)
            ON app.insights TO near_app;
        GRANT SELECT, DELETE ON app.hypotheses TO near_app;
        GRANT INSERT(document_version_id, hypothesis_id, document_id, owner_id, block_id,
                     statement, assessment, authored_at, modified_at)
            ON app.hypotheses TO near_app;
        GRANT SELECT, DELETE ON app.evidence_links TO near_app;
        GRANT INSERT(document_version_id, evidence_id, document_id, owner_id, block_id,
                     hypothesis_id, classification, target_kind, target_id, explanation)
            ON app.evidence_links TO near_app;
        GRANT DELETE ON app.insights, app.hypotheses, app.evidence_links TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.evidence_links;
        DROP TABLE app.hypotheses;
        DROP TABLE app.insights;
    """)
