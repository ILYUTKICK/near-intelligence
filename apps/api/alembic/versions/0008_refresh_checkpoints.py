"""NI-030: persistent refresh checkpoints and daily request counters.

Creates the ingestion checkpoint zone used by the bounded scheduled refresh
adapter (``near_api.ingestion.providers.finalized_header``):

- ``app.ingestion_checkpoints``: one row per source. The resume cursor is the
  last successfully validated finalized block (``last_height``/``last_block_hash``/
  ``last_header_at``) — an interrupted or failed run resumes from it and a lower
  advertised height is a regression failure, never silently published. The row
  also carries the honest operational state the monitoring contract requires
  (DATA_PIPELINE.md: "never report only 'job ran'"): ``last_request_at`` (the
  1 request/minute pacing budget of the OQ-03 approval), ``last_success_at``,
  ``last_failure_at`` and ``last_failure_kind`` (for example ``http_429``),
  and ``consecutive_failures``. The last good data itself lives in the
  approved dataset versions; a failure never advances the checkpoint height.
- ``app.ingestion_daily_counters``: per ``(source_id, UTC day)`` request
  counters persisted in the database so the <=1440 requests/day budget of the
  OQ-03 approval survives process restarts. ``success_count`` distinguishes
  successful refreshes from consumed attempts (failures = requests - successes).

Both tables are operator-owned operational state: FORCE RLS with a single
near_operator write policy (mirroring the dataset zone), near_app gets
read-only access so the API can display source freshness and failure state
(NI-032) without holding any write grant. No DELETE grant exists for any
role; the allowlist itself is NOT seeded here — ``app.sources.access_status``
stays 'documented' until an operator explicitly approves a source, so a fresh
environment has an empty effective allowlist and collection is disabled by
default.
"""

from alembic import op

revision = "0008_refresh_checkpoints"
down_revision = "0007_metric_chart_registries"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.ingestion_checkpoints (
            source_id varchar(40) CONSTRAINT pk_ingestion_checkpoints PRIMARY KEY,
            last_height bigint,
            last_block_hash varchar(44),
            last_header_at timestamptz,
            last_request_at timestamptz,
            last_success_at timestamptz,
            last_failure_at timestamptz,
            last_failure_kind varchar(40),
            consecutive_failures integer NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_ingestion_checkpoints_source FOREIGN KEY (source_id)
                REFERENCES app.sources (id) ON DELETE RESTRICT,
            CONSTRAINT ck_ingestion_checkpoints_height_nonnegative
                CHECK (last_height IS NULL OR last_height >= 0),
            CONSTRAINT ck_ingestion_checkpoints_block_hash_format
                CHECK (last_block_hash IS NULL
                       OR last_block_hash ~ '^[1-9A-HJ-NP-Za-km-z]{32,44}$'),
            CONSTRAINT ck_ingestion_checkpoints_failure_kind_nonempty
                CHECK (last_failure_kind IS NULL OR last_failure_kind <> ''),
            CONSTRAINT ck_ingestion_checkpoints_consecutive_nonnegative
                CHECK (consecutive_failures >= 0),
            -- The resume cursor is always the complete (height, hash) pair.
            CONSTRAINT ck_ingestion_checkpoints_cursor_pair CHECK (
                (last_height IS NULL) = (last_block_hash IS NULL))
        );

        CREATE TABLE app.ingestion_daily_counters (
            source_id varchar(40) NOT NULL,
            day date NOT NULL,
            request_count integer NOT NULL DEFAULT 0,
            success_count integer NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_ingestion_daily_counters
                PRIMARY KEY (source_id, day),
            CONSTRAINT fk_ingestion_daily_counters_source FOREIGN KEY (source_id)
                REFERENCES app.sources (id) ON DELETE RESTRICT,
            CONSTRAINT ck_ingestion_daily_counters_request_nonnegative
                CHECK (request_count >= 0),
            CONSTRAINT ck_ingestion_daily_counters_success_nonnegative
                CHECK (success_count >= 0),
            -- A success implies a request was made; failures = requests - successes.
            CONSTRAINT ck_ingestion_daily_counters_success_bounded
                CHECK (success_count <= request_count)
        );

        -- Operator-owned operational state: FORCE RLS keeps every role without
        -- a policy (including near_migrator and grant-less near_public) locked
        -- out; near_operator holds the only write policy and near_app a
        -- read-only policy for freshness/failure display.
        ALTER TABLE app.ingestion_checkpoints ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.ingestion_checkpoints FORCE ROW LEVEL SECURITY;
        ALTER TABLE app.ingestion_daily_counters ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.ingestion_daily_counters FORCE ROW LEVEL SECURITY;

        CREATE POLICY ingestion_checkpoints_operator ON app.ingestion_checkpoints
            TO near_operator USING (true) WITH CHECK (true);
        CREATE POLICY ingestion_checkpoints_app_read ON app.ingestion_checkpoints
            FOR SELECT TO near_app USING (true);
        CREATE POLICY ingestion_daily_counters_operator ON app.ingestion_daily_counters
            TO near_operator USING (true) WITH CHECK (true);
        CREATE POLICY ingestion_daily_counters_app_read ON app.ingestion_daily_counters
            FOR SELECT TO near_app USING (true);

        -- Checkpoints and counters are upserted, never deleted: history of the
        -- operational state is preserved (no DELETE grant for any role).
        GRANT SELECT ON app.ingestion_checkpoints TO near_app, near_operator;
        GRANT INSERT(source_id), UPDATE(last_height, last_block_hash, last_header_at,
                     last_request_at, last_success_at, last_failure_at,
                     last_failure_kind, consecutive_failures, updated_at)
            ON app.ingestion_checkpoints TO near_operator;
        GRANT SELECT ON app.ingestion_daily_counters TO near_app, near_operator;
        GRANT INSERT(source_id, day), UPDATE(request_count, success_count, updated_at)
            ON app.ingestion_daily_counters TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.ingestion_daily_counters;
        DROP TABLE app.ingestion_checkpoints;
    """)
