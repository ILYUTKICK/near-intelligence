"""NI-035 owner-scoped saved charts with forced RLS.

A global chart definition and approved dataset reference remain intact when
an instance is deleted. P0 permits live views only; snapshot ids are blocked
in the database until NI-044 introduces real owner-matched snapshot FKs.
Context/label edits advance recency; dataset resolution telemetry does not.
"""

from alembic import op

revision = "0011_saved_charts"
down_revision = "0010_model_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.saved_charts (
            id uuid CONSTRAINT pk_saved_charts PRIMARY KEY,
            owner_id uuid NOT NULL,
            chart_definition_version_id uuid NOT NULL,
            label varchar(200),
            mode varchar(16) NOT NULL,
            selection jsonb NOT NULL,
            last_resolved_dataset_version_id uuid,
            snapshot_id uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_saved_charts_label_nonempty
                CHECK (label IS NULL OR label <> ''),
            CONSTRAINT ck_saved_charts_mode
                CHECK (mode = 'live'),
            -- P1 snapshot writes stay closed until a real ownership FK exists.
            CONSTRAINT ck_saved_charts_snapshot_pairing
                CHECK (snapshot_id IS NULL),
            -- Canonical selection keys (the service validates the values
            -- against the pinned definition version's ranges/filter schema).
            CONSTRAINT ck_saved_charts_selection_keys
                CHECK (selection ? 'start' AND selection ? 'end'
                       AND selection ? 'frequency' AND selection ? 'filters'),
            CONSTRAINT ck_saved_charts_selection_size
                CHECK (octet_length(selection::text) <= 4096),
            CONSTRAINT uq_saved_charts_id_owner UNIQUE (id, owner_id),
            CONSTRAINT fk_saved_charts_owner FOREIGN KEY (owner_id)
                REFERENCES app.users (id) ON DELETE CASCADE,
            -- A saved instance references an immutable global definition;
            -- RESTRICT keeps the registry intact while instances exist and
            -- instance deletion never touches definitions.
            CONSTRAINT fk_saved_charts_chart_definition
                FOREIGN KEY (chart_definition_version_id)
                REFERENCES app.chart_definitions (id) ON DELETE RESTRICT,
            CONSTRAINT fk_saved_charts_dataset FOREIGN KEY (last_resolved_dataset_version_id)
                REFERENCES app.dataset_versions (id) ON DELETE RESTRICT
        );
        CREATE INDEX ix_saved_charts_owner_updated_at
            ON app.saved_charts (owner_id, updated_at DESC, id);
        CREATE INDEX ix_saved_charts_chart_definition
            ON app.saved_charts (chart_definition_version_id);

        -- Recency tracks metadata edits only; the view-resolution telemetry
        -- write (last_resolved_dataset_version_id) must not reorder the
        -- owner's stable list.
        CREATE FUNCTION app.touch_saved_charts_updated_at() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN NEW.updated_at = clock_timestamp(); RETURN NEW; END $$;
        REVOKE ALL ON FUNCTION app.touch_saved_charts_updated_at() FROM PUBLIC;
        CREATE TRIGGER saved_charts_updated_at BEFORE UPDATE ON app.saved_charts
            FOR EACH ROW
            WHEN (OLD.label IS DISTINCT FROM NEW.label
                  OR OLD.mode IS DISTINCT FROM NEW.mode
                  OR OLD.selection IS DISTINCT FROM NEW.selection)
            EXECUTE FUNCTION app.touch_saved_charts_updated_at();

        ALTER TABLE app.saved_charts ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.saved_charts FORCE ROW LEVEL SECURITY;

        -- Runtime role: only the transaction-local verified owner, and only
        -- while that account is not disabled (fail closed on account
        -- disable/re-enable boundaries; 0002 pattern).
        CREATE POLICY saved_charts_self_select ON app.saved_charts
            FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY saved_charts_self_insert ON app.saved_charts
            FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY saved_charts_self_update ON app.saved_charts
            FOR UPDATE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active())
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY saved_charts_self_delete ON app.saved_charts
            FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());

        -- Operator role: no read/update access to private content. DELETE is
        -- the narrow purge power for the operator-assisted account removal;
        -- purges flow through the users table cascade, never through content
        -- queries (USING(true) implies no SELECT grant).
        CREATE POLICY saved_charts_operator_delete ON app.saved_charts
            FOR DELETE TO near_operator USING (true);

        -- No policies exist for near_migrator (DDL only) or near_public;
        -- FORCE RLS keeps both locked out even from this table.
        GRANT SELECT, UPDATE(label, mode, selection, last_resolved_dataset_version_id,
                             snapshot_id, updated_at), DELETE
            ON app.saved_charts TO near_app;
        GRANT INSERT(id, owner_id, chart_definition_version_id, label, mode,
                     selection, last_resolved_dataset_version_id, snapshot_id)
            ON app.saved_charts TO near_app;
        GRANT DELETE ON app.saved_charts TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.saved_charts;
        DROP FUNCTION app.touch_saved_charts_updated_at();
    """)
