"""NI-060: revocable read-only shares of one frozen document revision.

Creates ``app.document_shares`` — the capability store of one share — exactly
as implemented by :mod:`near_api.shares` (ADR-021; the implemented shape is
recorded in DATABASE_SCHEMA.md). One row is one share:

- ``projection`` holds the FROZEN allowlisted publication projection canonical
  bytes (``share_projection_version`` 1, ADR-021) built at request time while
  the revision was the document's acknowledged current version. The bytes are
  the narrowed public payload (no owner id, no author identity, no private
  UUID graph, no editorial timestamps, no evidence explanations); every read
  serves them verbatim, so an edit, rename or newer dataset publication after
  the create can never mutate what a token holder sees. Identity is the
  recorded ``projection_sha256``/``projection_byte_size`` pair.
- ``token_hash`` stores ONLY the SHA-256 digest of the share token; the raw
  token is returned once in the create response and never persisted anywhere.
- ``idempotency_key`` is unique per owner and bound to the document and
  consent body by ``idempotency_request_sha256``. A matching replay returns
  the share's current lifecycle without re-emitting the token.

Lifecycle: ``active`` -> ``revoked`` (owner revoke; the same UPDATE structurally
clears the bytes — export-sweep semantics). Expiry is a live read-time
property of ``expires_at`` (NULL = no expiry), evaluated on EVERY request by
the RLS token policy AND the service; no sweeper is needed for correctness.

Ownership and roles (ADR-021):

- ``near_app`` owner policies are the 0002 self pattern: the runtime role
  inserts/reads/revokes/deletes only its own rows with an active identity.
- ``near_app`` token policy is the NEW capability pattern: it applies only
  when NO transaction-local identity is set (``app.current_user_id() IS NULL``)
  and returns only the active, unexpired row matching the transaction-local
  token digest. An unscoped or authenticated read cannot use this policy.
- ``near_operator`` holds purge-only power (the saved_charts precedent): a
  lifecycle-columns-only SELECT (required by the purge WHERE) and DELETE —
  it cannot read token hashes or bytes and cannot write anything.
- No policies exist for ``near_migrator`` (DDL only) or ``near_public``;
  FORCE RLS keeps both locked out even from this table.

Immutability: a BEFORE UPDATE guard (the 0004 dataset_versions_guard
precedent) makes the identity columns, token hash and frozen bytes immutable
while the share is ``active`` and forbids any transition out of ``revoked``;
the pairing CHECK makes revocation clear the bytes. The only writes the
service ever makes after the insert are the owner's active->revoked transition.

Document deletion cascades: the composite same-owner FKs remove a document's
shares with it; the scientific registries the projection references stay
untouched.
"""

from alembic import op

revision = "0017_document_shares"
down_revision = "0019_merge_pdf_publications"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(r"""
        CREATE TABLE app.document_shares (
            id uuid CONSTRAINT pk_document_shares PRIMARY KEY,
            owner_id uuid NOT NULL,
            document_id uuid NOT NULL,
            document_version_id uuid NOT NULL,
            token_hash varchar(64) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'active',
            revision integer NOT NULL,
            idempotency_key uuid,
            idempotency_request_sha256 varchar(64),
            -- All three projection columns are nullable BY DESIGN: the
            -- pairing CHECK below is the invariant (an active share always
            -- carries all three; a revoked one none of them), and the
            -- revocation transition writes NULLs.
            projection bytea,
            projection_sha256 varchar(64),
            projection_byte_size bigint,
            expires_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            revoked_at timestamptz,
            -- Only a live share is published; a revoked row keeps the
            -- lifecycle record but never its bytes (export-sweep semantics).
            CONSTRAINT ck_document_shares_status CHECK (status IN ('active','revoked')),
            CONSTRAINT ck_document_shares_revision CHECK (revision > 0),
            CONSTRAINT ck_document_shares_token_hash CHECK (token_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_document_shares_idempotency_request_hash CHECK (
                idempotency_request_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_document_shares_idempotency_pairing CHECK (
                (idempotency_key IS NULL) = (idempotency_request_sha256 IS NULL)),
            CONSTRAINT ck_document_shares_projection_hash
                CHECK (projection_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_document_shares_projection_size CHECK (
                projection_byte_size >= 0 AND projection_byte_size <= 33554432),
            -- A stored projection always carries its identity; a share with
            -- no bytes can only be a revoked one.
            CONSTRAINT ck_document_shares_projection_pairing CHECK (
                (status = 'revoked') = (projection IS NULL)
                AND (projection IS NULL) = (projection_sha256 IS NULL)
                AND (projection IS NULL) = (projection_byte_size IS NULL)
                AND (status = 'revoked') = (revoked_at IS NOT NULL)),
            CONSTRAINT uq_document_shares_id_owner UNIQUE (id, owner_id),
            CONSTRAINT uq_document_shares_owner_idempotency UNIQUE (owner_id, idempotency_key),
            -- Same-owner composite references (0012 pattern): a share exists
            -- only for a revision of the same document and owner, and dies
            -- with its document.
            CONSTRAINT fk_document_shares_owner FOREIGN KEY (owner_id)
                REFERENCES app.users (id) ON DELETE CASCADE,
            CONSTRAINT fk_document_shares_document FOREIGN KEY (document_id, owner_id)
                REFERENCES app.documents (id, owner_id) ON DELETE CASCADE,
            CONSTRAINT fk_document_shares_version
                FOREIGN KEY (document_version_id, document_id, owner_id)
                REFERENCES app.document_versions (id, document_id, owner_id)
                ON DELETE CASCADE
        );
        -- Capability lookup: the public token path queries by digest only.
        CREATE UNIQUE INDEX ix_document_shares_token_hash
            ON app.document_shares (token_hash);
        CREATE INDEX ix_document_shares_owner_created
            ON app.document_shares (owner_id, created_at DESC, id);

        -- Frozen identity/projection bytes are immutable while the share is
        -- live; revocation is the one-way active -> revoked transition that
        -- clears the bytes (the CHECK above makes the pairing mandatory).
        -- expires_at is NOT in the guard: the owner has no UPDATE grant on it
        -- (the consent window is fixed at create for the application plane),
        -- while the operator credential retains the narrow operational power
        -- to correct the recorded window directly.
        CREATE FUNCTION app.guard_document_share_update() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$
        BEGIN
            IF (NEW.token_hash, NEW.owner_id, NEW.document_id,
                NEW.document_version_id, NEW.revision, NEW.idempotency_key,
                NEW.idempotency_request_sha256, NEW.created_at)
               IS DISTINCT FROM
               (OLD.token_hash, OLD.owner_id, OLD.document_id,
                OLD.document_version_id, OLD.revision, OLD.idempotency_key,
                OLD.idempotency_request_sha256, OLD.created_at) THEN
                RAISE EXCEPTION 'identity columns of a document share are immutable';
            END IF;
            IF NEW.status = 'active' AND (
                NEW.projection IS DISTINCT FROM OLD.projection
                OR NEW.projection_sha256 IS DISTINCT FROM OLD.projection_sha256
                OR NEW.projection_byte_size IS DISTINCT FROM OLD.projection_byte_size) THEN
                RAISE EXCEPTION 'the frozen projection bytes of an active share are immutable';
            END IF;
            IF NEW.status <> OLD.status AND NOT (
                   OLD.status = 'active' AND NEW.status = 'revoked') THEN
                RAISE EXCEPTION 'illegal document share status transition % -> %',
                    OLD.status, NEW.status;
            END IF;
            RETURN NEW;
        END $$;
        REVOKE ALL ON FUNCTION app.guard_document_share_update() FROM PUBLIC;
        CREATE TRIGGER document_shares_guard BEFORE UPDATE ON app.document_shares
            FOR EACH ROW EXECUTE FUNCTION app.guard_document_share_update();

        CREATE FUNCTION app.touch_document_shares_updated_at() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog
        AS $$ BEGIN NEW.updated_at = clock_timestamp(); RETURN NEW; END $$;
        REVOKE ALL ON FUNCTION app.touch_document_shares_updated_at() FROM PUBLIC;
        CREATE TRIGGER document_shares_updated_at BEFORE UPDATE ON app.document_shares
            FOR EACH ROW
            WHEN (OLD.status IS DISTINCT FROM NEW.status
                  OR OLD.revoked_at IS DISTINCT FROM NEW.revoked_at)
            EXECUTE FUNCTION app.touch_document_shares_updated_at();

        ALTER TABLE app.document_shares ENABLE ROW LEVEL SECURITY;
        ALTER TABLE app.document_shares FORCE ROW LEVEL SECURITY;

        -- Runtime role, owner plane: only the transaction-local verified
        -- owner, and only while that account is not disabled (0002 pattern).
        CREATE POLICY document_shares_self_select ON app.document_shares
            FOR SELECT TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_shares_self_insert ON app.document_shares
            FOR INSERT TO near_app
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_shares_self_update ON app.document_shares
            FOR UPDATE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active())
            WITH CHECK (owner_id = app.current_user_id() AND app.identity_is_active());
        CREATE POLICY document_shares_self_delete ON app.document_shares
            FOR DELETE TO near_app
            USING (owner_id = app.current_user_id() AND app.identity_is_active());

        -- Runtime role, capability plane (ADR-021): WITHOUT a transaction
        -- local identity, only the active, unexpired share matching the
        -- transaction's verified token digest is readable. A missing setting
        -- is NULL; a malformed digest cannot match the constrained column.
        CREATE POLICY document_shares_token_read ON app.document_shares
            FOR SELECT TO near_app
            USING (app.current_user_id() IS NULL
                   AND token_hash = current_setting('app.share_token_sha256', true)
                   AND status = 'active'
                   AND (expires_at IS NULL OR expires_at > now()));

        -- Operator purge power only (saved_charts precedent): the SELECT
        -- policy exposes rows to the narrow lifecycle-columns grant below
        -- (the purge WHERE needs it); token hashes and bytes carry no
        -- operator grant, and no operator UPDATE/INSERT exists.
        CREATE POLICY document_shares_operator_select ON app.document_shares
            FOR SELECT TO near_operator USING (true);
        CREATE POLICY document_shares_operator_purge ON app.document_shares
            FOR DELETE TO near_operator USING (true);

        -- No policies exist for near_migrator (DDL only) or near_public;
        -- FORCE RLS keeps both locked out even from this table.

        -- near_app writes its own rows: INSERT covers the frozen projection
        -- pin; UPDATE is scoped to the revocation transition columns (the
        -- guard trigger and CHECK make revocation clear the bytes); DELETE
        -- covers owner cleanup. There is deliberately NO table-wide UPDATE
        -- grant: token_hash and the identity columns carry none, so a stray
        -- UPDATE of them is a permission denial, not a silent no-op.
        GRANT SELECT ON app.document_shares TO near_app;
        GRANT INSERT(id, owner_id, document_id, document_version_id, token_hash,
                     revision, idempotency_key, idempotency_request_sha256,
                     projection, projection_sha256,
                     projection_byte_size, expires_at)
            ON app.document_shares TO near_app;
        GRANT UPDATE(status, revoked_at, projection, projection_sha256,
                     projection_byte_size, updated_at)
            ON app.document_shares TO near_app;
        GRANT DELETE ON app.document_shares TO near_app;
        -- near_operator: purge power over lifecycle metadata only. SELECT is
        -- required by the WHERE clause of the purge; the token digests and
        -- the stored bytes carry no operator grant.
        GRANT SELECT(id, owner_id, document_id, document_version_id, status,
                     revision, expires_at, created_at, updated_at, revoked_at)
            ON app.document_shares TO near_operator;
        GRANT DELETE ON app.document_shares TO near_operator;
    """)


def downgrade():
    op.execute("""
        DROP TABLE app.document_shares;
        DROP FUNCTION app.touch_document_shares_updated_at();
        DROP FUNCTION app.guard_document_share_update();
    """)
