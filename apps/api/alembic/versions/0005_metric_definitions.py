"""NI-029: registered metric definition registry.

Creates ``app.metric_definitions`` — the immutable, versioned registry of
metric definitions that NI-029's computations emit (DATABASE_SCHEMA.md
"Shared definitions, data and provenance"). One row per
``(metric_id, version)``: stable identity UUID (derived deterministically
from the metric id and version by ``near_api.metrics.registry``), human
name, unit, observation frequency, economic scope, the registered Python
formula key (formulas select fixed code, never SQL/eval), the primary
source, and the bounded definition/quality-rule documents.

``source_id`` is nullable on purpose: an explicitly gated metric
(``protocol_revenue_usd`` and friends) is registered honestly BEFORE any
source can produce it; a missing source is part of the recorded
unavailability, never a fabricated attribution.

The referential FK from ``dataset_metrics.metric_definition_id`` stays
absent, as documented in DATABASE_SCHEMA.md since NI-028: already-staged
datasets carry opaque identifiers and the registry join/freeze becomes a
NI-031 contract change. This table is append-only (INSERT grant for the
operator role only; no UPDATE/DELETE grants for any role), FORCE RLS with
near_operator write and near_app read policies, mirroring the dataset
zone. Registration is idempotent and content-verified in
``near_api.metrics.registry.register_definitions``.
"""

from alembic import op

revision = "0005_metric_definitions"
down_revision = "0004_dataset_staging"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.metric_definitions (
            id uuid CONSTRAINT pk_metric_definitions PRIMARY KEY,
            metric_id varchar(80) NOT NULL,
            version integer NOT NULL,
            name varchar(200) NOT NULL,
            unit varchar(40) NOT NULL,
            frequency varchar(20) NOT NULL,
            economic_scope varchar(200) NOT NULL,
            formula_key varchar(80) NOT NULL,
            source_id varchar(40),
            definition jsonb NOT NULL,
            quality_rules jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_metric_definitions_metric_version UNIQUE (metric_id, version),
            CONSTRAINT ck_metric_definitions_metric_id
                CHECK (metric_id ~ '^[a-z][a-z0-9_]{2,79}$'),
            CONSTRAINT ck_metric_definitions_version CHECK (version >= 1),
            CONSTRAINT ck_metric_definitions_name_nonempty CHECK (name <> ''),
            CONSTRAINT ck_metric_definitions_unit_nonempty CHECK (unit <> ''),
            CONSTRAINT ck_metric_definitions_frequency
                CHECK (frequency IN ('daily','weekly','monthly','snapshot')),
            CONSTRAINT ck_metric_definitions_scope_nonempty CHECK (economic_scope <> ''),
            CONSTRAINT ck_metric_definitions_formula_nonempty CHECK (formula_key <> ''),
            CONSTRAINT ck_metric_definitions_definition_size
                CHECK (octet_length(definition::text) <= 16384),
            CONSTRAINT ck_metric_definitions_quality_rules_size
                CHECK (octet_length(quality_rules::text) <= 8192),
            CONSTRAINT fk_metric_definitions_source FOREIGN KEY (source_id)
                REFERENCES app.sources (id) ON DELETE RESTRICT
        );

        -- Public scientific definitions: FORCE RLS keeps every role without a
        -- policy locked out (including the table owner and grant-less
        -- near_public); near_operator holds the only write policy and near_app
        -- a read-only policy.
        ALTER TABLE app.metric_definitions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.metric_definitions FORCE ROW LEVEL SECURITY;
        CREATE POLICY metric_definitions_operator ON app.metric_definitions
            TO near_operator USING (true) WITH CHECK (true);
        CREATE POLICY metric_definitions_app_read ON app.metric_definitions
            FOR SELECT TO near_app USING (true);

        -- Append-only registry: no UPDATE or DELETE grant exists for any
        -- role; definitions change by appending a new version row.
        GRANT SELECT ON app.metric_definitions TO near_app, near_operator;
        GRANT INSERT(id, metric_id, version, name, unit, frequency, economic_scope,
                     formula_key, source_id, definition, quality_rules)
            ON app.metric_definitions TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.metric_definitions;
    """)
