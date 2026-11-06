"""NI-031: versioned chart definition registry and metric-binding FKs.

Creates the chart registry of DATABASE_SCHEMA.md ("Shared definitions, data
and provenance") per docs/CHART_SYSTEM.md:

- ``app.chart_definitions`` — one immutable row per ``(chart_id, version)``.
  The identity UUID is derived deterministically from the chart id and
  version by ``near_api.charts.registry`` (uuid5, same pattern as the NI-029
  metric registry). A definition fully describes what a page renders —
  visualization type, category, metric bindings, per-series units, allowed
  query ranges, the supported-filter JSON Schema, the expected update
  frequency, source lineage and the renderer version — so adding a supported
  definition needs no new page implementation. ``data_status`` is the honest
  advertisement: only ``available`` charts are advertised as live; charts
  whose metric gates have not passed (or whose model artifact does not exist
  yet) are registered ``unavailable`` with the recorded reason. Last-updated,
  data quality and actual date coverage stay with the resolved ChartView
  dataset (NI-032), never in this mutable-free definition.
- ``app.chart_metrics`` — the binding junction: every referenced metric
  definition UUID must resolve in ``app.metric_definitions`` (RESTRICT FK),
  with a bounded ``series_role`` that defines required/optional series.

It also lands the documented NI-031 contract change from the NI-028/NI-029
interpretation notes: ``dataset_metrics.metric_definition_id`` gains its
referential FK to ``app.metric_definitions(id)``. Staged datasets emitted by
``near_api.metrics`` already carry registered definition UUIDs, so metric
references in the dataset zone stop being opaque identifiers exactly here;
a staging manifest with an unregistered metric UUID is rejected by the
database (fail closed) instead of being silently accepted.

Both registry tables are append-only (INSERT grant for the operator role
only; no UPDATE/DELETE grants for any role — a changed chart appends a new
version row) and FORCE RLS with the 0005 pattern: near_operator holds the
only write policy, near_app a read-only policy, and no policy exists for
near_migrator/near_public (public exposure happens through the API, not a
second DB login). Registration is idempotent and content-verified in
``near_api.charts.registry.register_charts``.
"""

from alembic import op

revision = "0007_metric_chart_registries"
down_revision = "0006_document_projections"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.chart_definitions (
            id uuid CONSTRAINT pk_chart_definitions PRIMARY KEY,
            chart_id varchar(80) NOT NULL,
            version integer NOT NULL,
            title varchar(200) NOT NULL,
            description varchar(1000) NOT NULL,
            category varchar(40) NOT NULL,
            visualization_type varchar(40) NOT NULL,
            data_status varchar(20) NOT NULL,
            unavailable_reason varchar(500),
            update_frequency varchar(20) NOT NULL,
            allowed_ranges jsonb NOT NULL,
            filter_schema jsonb NOT NULL,
            unit_schema jsonb NOT NULL,
            metric_definition_ids jsonb NOT NULL,
            source_lineage jsonb NOT NULL,
            renderer_version varchar(80) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_chart_definitions_chart_version UNIQUE (chart_id, version),
            CONSTRAINT ck_chart_definitions_chart_id
                CHECK (chart_id ~ '^[a-z][a-z0-9-]{2,79}$'),
            CONSTRAINT ck_chart_definitions_version CHECK (version >= 1),
            CONSTRAINT ck_chart_definitions_title_nonempty CHECK (title <> ''),
            CONSTRAINT ck_chart_definitions_description_nonempty CHECK (description <> ''),
            CONSTRAINT ck_chart_definitions_category
                CHECK (category IN ('activity','fees','treasury','supply','model')),
            CONSTRAINT ck_chart_definitions_visualization
                CHECK (visualization_type IN ('line','area','bar','scatter','panels')),
            CONSTRAINT ck_chart_definitions_data_status
                CHECK (data_status IN ('available','unavailable')),
            CONSTRAINT ck_chart_definitions_unavailable_reason
                CHECK ((data_status = 'available') = (unavailable_reason IS NULL)
                       AND (unavailable_reason IS NULL OR unavailable_reason <> '')),
            CONSTRAINT ck_chart_definitions_frequency
                CHECK (update_frequency IN ('daily','weekly','monthly','snapshot')),
            CONSTRAINT ck_chart_definitions_renderer_nonempty
                CHECK (renderer_version <> ''),
            CONSTRAINT ck_chart_definitions_allowed_ranges_size
                CHECK (octet_length(allowed_ranges::text) <= 1024),
            CONSTRAINT ck_chart_definitions_filter_schema_size
                CHECK (octet_length(filter_schema::text) <= 4096),
            CONSTRAINT ck_chart_definitions_unit_schema_size
                CHECK (octet_length(unit_schema::text) <= 1024),
            CONSTRAINT ck_chart_definitions_metric_ids_size
                CHECK (octet_length(metric_definition_ids::text) <= 4096),
            CONSTRAINT ck_chart_definitions_source_lineage_size
                CHECK (octet_length(source_lineage::text) <= 2048)
        );

        -- Binding junction: required/optional series roles; every metric UUID
        -- must resolve to a registered definition (RESTRICT both ways).
        CREATE TABLE app.chart_metrics (
            chart_definition_version_id uuid NOT NULL,
            metric_definition_id uuid NOT NULL,
            series_role varchar(40) NOT NULL,
            CONSTRAINT pk_chart_metrics
                PRIMARY KEY (chart_definition_version_id, metric_definition_id, series_role),
            CONSTRAINT ck_chart_metrics_series_role
                CHECK (series_role IN ('required_primary','required_secondary',
                                       'required_x_axis','required_y_axis',
                                       'optional_overlay','optional_context')),
            CONSTRAINT fk_chart_metrics_chart FOREIGN KEY (chart_definition_version_id)
                REFERENCES app.chart_definitions (id) ON DELETE RESTRICT,
            CONSTRAINT fk_chart_metrics_metric FOREIGN KEY (metric_definition_id)
                REFERENCES app.metric_definitions (id) ON DELETE RESTRICT
        );
        CREATE INDEX ix_chart_metrics_metric ON app.chart_metrics (metric_definition_id);

        -- Documented NI-031 contract change: staged datasets reference
        -- registered metric definitions, not opaque identifiers.
        ALTER TABLE app.dataset_metrics
            ADD CONSTRAINT fk_dataset_metrics_metric_definition
            FOREIGN KEY (metric_definition_id)
            REFERENCES app.metric_definitions (id) ON DELETE RESTRICT;
        CREATE INDEX ix_dataset_metrics_metric_definition
            ON app.dataset_metrics (metric_definition_id);

        -- Public scientific definitions: FORCE RLS keeps every role without a
        -- policy locked out (including the table owner and grant-less
        -- near_public); near_operator holds the only write policy and near_app
        -- a read-only policy (the 0005 pattern).
        ALTER TABLE app.chart_definitions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.chart_definitions FORCE ROW LEVEL SECURITY;
        CREATE POLICY chart_definitions_operator ON app.chart_definitions
            TO near_operator USING (true) WITH CHECK (true);
        CREATE POLICY chart_definitions_app_read ON app.chart_definitions
            FOR SELECT TO near_app USING (true);

        ALTER TABLE app.chart_metrics ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.chart_metrics FORCE ROW LEVEL SECURITY;
        CREATE POLICY chart_metrics_operator ON app.chart_metrics
            TO near_operator USING (true) WITH CHECK (true);
        CREATE POLICY chart_metrics_app_read ON app.chart_metrics
            FOR SELECT TO near_app USING (true);

        -- Append-only registries: no UPDATE or DELETE grant exists for any
        -- role; a chart change appends a new version row.
        GRANT SELECT ON app.chart_definitions TO near_app, near_operator;
        GRANT INSERT(id, chart_id, version, title, description, category,
                     visualization_type, data_status, unavailable_reason,
                     update_frequency, allowed_ranges, filter_schema, unit_schema,
                     metric_definition_ids, source_lineage, renderer_version)
            ON app.chart_definitions TO near_operator;
        GRANT SELECT ON app.chart_metrics TO near_app, near_operator;
        GRANT INSERT(chart_definition_version_id, metric_definition_id, series_role)
            ON app.chart_metrics TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP INDEX app.ix_dataset_metrics_metric_definition;
        ALTER TABLE app.dataset_metrics DROP CONSTRAINT fk_dataset_metrics_metric_definition;
        DROP TABLE app.chart_metrics;
        DROP TABLE app.chart_definitions;
    """)
