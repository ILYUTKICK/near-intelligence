"""NI-044 owner-scoped immutable research snapshots; saved-chart snapshot FK.

Creates ``app.research_snapshots`` (DATABASE_SCHEMA.md planned shape) and
lifts the migration-0011 P0 gate on ``app.saved_charts``: ``mode`` gains
``'snapshot'`` and ``snapshot_id`` acquires a real same-owner composite FK
into the snapshot registry. The FK pair ``(snapshot_id, owner_id) ->
research_snapshots(id, owner_id)`` enforces owner match at the database layer
and ``ON DELETE RESTRICT`` guarantees a referenced snapshot cannot disappear
behind the service's typed 409 check.

Immutability follows the NI-019 ``document_versions`` privilege pattern: the
runtime role receives INSERT (content columns only), SELECT and the narrow
owner-scoped DELETE the API needs; NO role receives UPDATE, so a snapshot row
can never change after commit. Purge remains the operator DELETE through the
users cascade.
"""

from alembic import op

revision = "0013_chart_snapshots"
down_revision = "0014_document_organization"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.research_snapshots (
            id uuid CONSTRAINT pk_research_snapshots PRIMARY KEY,
            owner_id uuid NOT NULL,
            chart_definition_version_id uuid NOT NULL,
            dataset_version_id uuid NOT NULL,
            selection jsonb NOT NULL,
            calculation_context jsonb NOT NULL,
            artifact_id uuid,
            content_sha256 varchar(64) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            -- Canonical selection keys (values are validated by the service
            -- against the pinned definition version's ranges/filter schema).
            CONSTRAINT ck_research_snapshots_selection_keys
                CHECK (selection ? 'start' AND selection ? 'end'
                       AND selection ? 'frequency' AND selection ? 'filters'),
            CONSTRAINT ck_research_snapshots_selection_size
                CHECK (octet_length(selection::text) <= 4096),
            CONSTRAINT ck_research_snapshots_context_size
                CHECK (octet_length(calculation_context::text) <= 8192),
            CONSTRAINT ck_research_snapshots_context_keys
                CHECK (calculation_context ? 'context_hash'
                       AND calculation_context ? 'metric_definition_versions'
                       AND calculation_context ? 'renderer_version'),
            CONSTRAINT ck_research_snapshots_content_hash
                CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT uq_research_snapshots_id_owner UNIQUE (id, owner_id),
            CONSTRAINT fk_research_snapshots_owner FOREIGN KEY (owner_id)
                REFERENCES app.users (id) ON DELETE CASCADE,
            -- A snapshot pins immutable public inputs; RESTRICT keeps the
            -- registry/dataset intact while any owner snapshot exists.
            CONSTRAINT fk_research_snapshots_chart_definition
                FOREIGN KEY (chart_definition_version_id)
                REFERENCES app.chart_definitions (id) ON DELETE RESTRICT,
            CONSTRAINT fk_research_snapshots_dataset FOREIGN KEY (dataset_version_id)
                REFERENCES app.dataset_versions (id) ON DELETE RESTRICT,
            -- A rendered/stored artifact reference, when present, is content
            -- addressed and immutable; RESTRICT keeps it reachable.
            CONSTRAINT fk_research_snapshots_artifact FOREIGN KEY (artifact_id)
                REFERENCES app.artifacts (id) ON DELETE RESTRICT
        );
        CREATE INDEX ix_research_snapshots_owner_created_at
            ON app.research_snapshots (owner_id, created_at DESC, id);
        CREATE INDEX ix_research_snapshots_chart_definition
            ON app.research_snapshots (chart_definition_version_id);

        ALTER TABLE app.research_snapshots ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.research_snapshots FORCE ROW LEVEL SECURITY;

        -- Runtime role: only the transaction-local verified owner, and only
        -- while that account is not disabled (0002 pattern). No UPDATE policy
        -- and no UPDATE grant exist anywhere: snapshots are immutable.
        CREATE POLICY research_snapshots_self_select ON app.research_snapshots
            FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY research_snapshots_self_insert ON app.research_snapshots
            FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY research_snapshots_self_delete ON app.research_snapshots
            FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());

        -- Operator role: no read/update access to private content. DELETE is
        -- the narrow purge power through the users cascade (USING(true)
        -- implies no SELECT grant).
        CREATE POLICY research_snapshots_operator_delete ON app.research_snapshots
            FOR DELETE TO near_operator USING (true);

        -- No policies exist for near_migrator (DDL only) or near_public;
        -- FORCE RLS keeps both locked out even from this table.
        GRANT SELECT, DELETE ON app.research_snapshots TO near_app;
        GRANT INSERT(id, owner_id, chart_definition_version_id, dataset_version_id,
                     selection, calculation_context, artifact_id, content_sha256)
            ON app.research_snapshots TO near_app;
        GRANT DELETE ON app.research_snapshots TO near_operator;

        -- Lift the NI-035 P0 gate: snapshot mode becomes a first-class saved
        -- context whose snapshot_id carries a real same-owner FK.
        ALTER TABLE app.saved_charts DROP CONSTRAINT ck_saved_charts_mode;
        ALTER TABLE app.saved_charts DROP CONSTRAINT ck_saved_charts_snapshot_pairing;
        ALTER TABLE app.saved_charts ADD CONSTRAINT ck_saved_charts_mode
            CHECK (mode IN ('live', 'snapshot'));
        -- Exactly one pairing: a live context carries no snapshot, a snapshot
        -- context carries exactly one owned snapshot reference.
        ALTER TABLE app.saved_charts ADD CONSTRAINT ck_saved_charts_snapshot_pairing
            CHECK ((mode = 'live') = (snapshot_id IS NULL));
        -- Same-owner composite FK: a saved chart can only reference its own
        -- snapshot, and RESTRICT keeps that snapshot alive while referenced.
        ALTER TABLE app.saved_charts ADD CONSTRAINT fk_saved_charts_snapshot
            FOREIGN KEY (snapshot_id, owner_id)
            REFERENCES app.research_snapshots (id, owner_id) ON DELETE RESTRICT;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE app.saved_charts DROP CONSTRAINT fk_saved_charts_snapshot;
        ALTER TABLE app.saved_charts DROP CONSTRAINT ck_saved_charts_snapshot_pairing;
        ALTER TABLE app.saved_charts DROP CONSTRAINT ck_saved_charts_mode;
        ALTER TABLE app.saved_charts ADD CONSTRAINT ck_saved_charts_mode
            CHECK (mode = 'live');
        ALTER TABLE app.saved_charts ADD CONSTRAINT ck_saved_charts_snapshot_pairing
            CHECK (snapshot_id IS NULL);
        DROP TABLE app.research_snapshots;
    """)
