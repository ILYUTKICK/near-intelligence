"""NI-037: stored results for Idempotency-Key write replay.

Creates ``app.idempotency_records`` exactly as specified by DATABASE_SCHEMA.md
("idempotency_records"): the owner-scoped record of one completed write keyed
``(owner_id, route_key, idempotency_key)``. The document routes that accept an
``Idempotency-Key`` header (NI-037: document create and whole-document save)
execute the business operation and store the response snapshot in the SAME
transaction, so a client that loses the response (timeout after commit) can
repeat the identical request and receive the original result without a second
document or revision. The record shape and lifetime follow API_SPECIFICATION:
repeated identical owner/route/body requests replay the original result for
24h; the same key with a different body is a 409 idempotency collision.

Deliberate boundaries:

- Only successful (2xx) results are stored — a CHECK constraint enforces it —
  so a failed or rejected write is always retryable with the same key.
- Records are write-once for the runtime role (no UPDATE grant or policy);
  replacing an expired key happens as DELETE + INSERT inside the next request's
  transaction. Rows are harmless after expiry; expired rows are removed lazily
  when the same key is reused (no scheduled cleanup job in P0).
- FORCE RLS with owner + identity_is_active() policies (0002 pattern) keeps
  every other user and every role without a policy locked out; the operator
  purge path is the users-table FK cascade (ON DELETE CASCADE), so no operator
  policy exists — these records are operational cache, never content.
- ``response_body`` duplicates the owner's own response (bounded by the
  document payload limits) so the replay is the exact original result even if
  the document is renamed afterwards; the record expires in 24h and is
  readable only by its owner through RLS.
"""

from alembic import op

revision = "0009_idempotency_records"
down_revision = "0008_refresh_checkpoints"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.idempotency_records (
            owner_id uuid NOT NULL,
            route_key varchar(120) NOT NULL,
            idempotency_key uuid NOT NULL,
            request_hash varchar(64) NOT NULL,
            response_status integer NOT NULL,
            response_body jsonb NOT NULL,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_idempotency_records
                PRIMARY KEY (owner_id, route_key, idempotency_key),
            CONSTRAINT fk_idempotency_records_owner FOREIGN KEY (owner_id)
                REFERENCES app.users (id) ON DELETE CASCADE,
            CONSTRAINT ck_idempotency_records_route_nonempty CHECK (route_key <> ''),
            CONSTRAINT ck_idempotency_records_request_hash_format
                CHECK (request_hash ~ '^[0-9a-f]{64}$'),
            -- Only successful results are replayable; failures stay retryable.
            CONSTRAINT ck_idempotency_records_response_success
                CHECK (response_status >= 200 AND response_status < 300)
        );

        ALTER TABLE app.idempotency_records ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.idempotency_records FORCE ROW LEVEL SECURITY;

        CREATE POLICY idempotency_records_self_select ON app.idempotency_records
            FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY idempotency_records_self_insert ON app.idempotency_records
            FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY idempotency_records_self_delete ON app.idempotency_records
            FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());

        -- Write-once for the runtime role: no UPDATE grant or policy. The
        -- INSERT column list covers every non-defaulted column the service
        -- writes; owner purge flows through the users FK cascade.
        GRANT SELECT, DELETE ON app.idempotency_records TO near_app;
        GRANT INSERT(owner_id, route_key, idempotency_key, request_hash,
                     response_status, response_body, expires_at)
            ON app.idempotency_records TO near_app;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.idempotency_records;
    """)
