"""NI-060 adversarial security matrix and RLS probes for document shares.

Needs scripts/run-db-tests.py (skips elsewhere; a skip is never successful
integration evidence). All identities, documents, datasets and tokens are
synthetic fixtures; no provider, archive or network is contacted.

The HTTP part runs the REAL dependency chain (stubbed verifier, real
RLS-backed database) and proves the capability boundary:

- anonymous reads of a live share work; the non-owner Bob reads the SAME
  frozen projection through the token; neither learns anything else;
- token guessing (wrong shape, valid shape + unknown value, another share's
  token) is ONE byte-identical generic 404 — no oracle distinguishes
  unknown/revoked/expired/malformed;
- revoked and expired shares deny every public path, and the denial is
  identical to the unknown-token denial;
- Bob cannot see, preview, list or revoke Alice's shares (one generic 404);
- no share response is cacheable and none leaks the token in a query string
  (the token exists only as a path segment; responses carry no-referrer);
- the projection carries no owner/private identifiers, so a share grants no
  draft/history/list/search/write/export access.

The database part attacks the DATABASE boundary directly (ADR-021 policy
design, migration 0017):

- the capability plane (near_app WITHOUT identity) reads ONLY live rows by
  token digest: revoked and expired rows are invisible even to raw SQL;
- the capability plane is VOIDED by any transaction-local identity: an
  authenticated session reads zero foreign share rows;
- the owner plane cannot rewrite the frozen bytes or the token hash (guard
  trigger + column grants), and revocation structurally clears the bytes;
- ``near_operator`` holds purge-only DELETE (no read of token hashes or
  bytes, no writes); ``near_public`` has nothing on schema ``app``;
- document deletion cascades shares away; RLS is FORCED even for the owner.
"""

import hashlib
import json
import os
import secrets
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from near_api.auth import principal as principal_module
from near_api.auth.principal import Principal
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.documents import service
from near_api.main import app
from near_api.schemas.common import ErrorResponse
import test_chart_blocks as chart_fixtures
import test_delivery_apis as data_fixture
import test_documents as document_fixtures

SHA256 = "a" * 64


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ShareSecurityMatrixTests(chart_fixtures.ChartBlockDatabaseFixture,
                               unittest.TestCase):
    """Alice/Bob/anonymous over the share capability surface (HTTP)."""

    def setUp(self):
        super().setUp()
        self.engine_patcher = patch.object(principal_module, "_get_engine",
                                           return_value=self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        self.alice_document_id, self.token, self.alice_share_id = self.alice_share()

    # -- fixture helpers ----------------------------------------------------- #

    def dataset_key(self, name: str) -> str:
        return f"synthetic.{uuid4().hex[:8]}.{name}"

    def stage_volume(self, key: str, value: str) -> UUID:
        if not hasattr(self, "directory"):
            tmp = tempfile.TemporaryDirectory(prefix="ni060sec-",
                                              dir=os.environ["NI_TEST_TMP_DIR"])
            self.addCleanup(tmp.cleanup)
            self.directory = Path(tmp.name)
            self.storage_root = self.directory / "storage"
        dimensions = {"source": "SRC-LLAMA"}
        result = data_fixture.DeliveryDatabaseTests.stage_fixture(
            self, key,
            [data_fixture.observation(chart_fixtures.METRIC_ID, date(2026, 1, 1),
                                      value=value, dimensions=dimensions),
             data_fixture.observation(chart_fixtures.METRIC_ID, date(2026, 1, 2),
                                      value=None, dimensions=dimensions)],
            [chart_fixtures.METRIC_ID], window=("2026-01-01", "2026-01-03"))
        return result.dataset_version_id

    def alice_share(self) -> tuple[UUID, str, UUID]:
        dataset_id = self.stage_volume(self.dataset_key("security"), "8.25")
        created = service.create_document(self.engine, self.alice,
                                          title="Synthetic shared research (fixture)")
        content = {"schema_version": 1, "type": "doc", "content": [
            {"type": "paragraph", "attrs": {"block_id": str(uuid4())},
             "content": [document_fixtures.text_node("Synthetic shared body")]},
            document_fixtures.block("liveChart", str(uuid4()), mode="live",
                                    selection=chart_fixtures.selection(),
                                    chart_definition_version_id=str(chart_fixtures.CHART_ID),
                                    observed_dataset_version_id=str(dataset_id)),
        ]}
        saved = service.save_revision(self.engine, self.alice, created.document.id,
                                      expected_revision=1, document_payload=content)
        with self.as_session(self.alice_id):
            preview = self.client.get(
                f"/api/documents/{created.document.id}/shares/preview",
                headers={"Authorization": f"Bearer t.{self.alice_id}"})
            self.assertEqual(preview.status_code, 200, preview.text)
            shown = preview.json()
            response = self.client.post(
                f"/api/documents/{created.document.id}/shares",
                headers={"Authorization": f"Bearer t.{self.alice_id}"},
                json={"acknowledged_revision": shown["revision"],
                      "preview_sha256": shown["projection_sha256"],
                      "visible_scope": shown["scope"]})
        self.assertEqual(response.status_code, 201, response.text)
        return created.document.id, response.json()["share_token"], UUID(response.json()["id"])

    def foreign_404(self, response, baseline: dict, where: str):
        self.assertEqual(response.status_code, 404, f"{where}: {response.text}")
        self.assertEqual(response.headers["Cache-Control"], "no-store", where)
        error = response.json()["error"]
        self.assertEqual(error["code"], baseline["code"], where)
        self.assertEqual(error["message"], baseline["message"], where)
        self.assertEqual(error.get("details"), baseline.get("details"), where)

    def deny_baseline(self) -> dict:
        unknown = self.client.get(f"/api/shares/{secrets.token_urlsafe(32)}")
        self.assertEqual(unknown.status_code, 404)
        error = unknown.json()["error"]
        return {"code": error["code"], "message": error["message"],
                "details": error.get("details")}

    # -- the matrix ----------------------------------------------------------- #

    def test_01_anonymous_and_bob_read_the_same_frozen_projection(self):
        anonymous = self.client.get(f"/api/shares/{self.token}")
        self.assertEqual(anonymous.status_code, 200)
        with self.as_session(self.bob_id):
            as_bob = self.client.get(f"/api/shares/{self.token}",
                                     headers={"Authorization": f"Bearer t.{self.bob_id}"})
        self.assertEqual(as_bob.status_code, 200)
        self.assertEqual(anonymous.json(), as_bob.json())
        blob = json.dumps(anonymous.json())
        for private in (str(self.alice_id), str(self.alice_document_id), "owner_id",
                        "author", "display_name", "document_id", "insight_id",
                        "hypothesis_id", "evidence_id", "target_id", "snapshot_id",
                        "authored_at", "modified_at", "explanation"):
            self.assertNotIn(private, blob, f"projection leaked {private}")
        # Exact-key walk: no private identifier KEY may exist anywhere in the
        # payload (substring pins like chart_definition_version_id are the
        # public-safe registries, kept by design).
        keys = set()

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    keys.add(key)
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(anonymous.json())
        self.assertEqual(keys & {"document_id", "version_id", "owner_id", "author",
                                 "insight_id", "hypothesis_id", "evidence_id",
                                 "target_id", "snapshot_id", "authored_at",
                                 "modified_at", "explanation"}, set())

    def test_02_token_guessing_is_one_generic_deny(self):
        from urllib.parse import quote
        baseline = self.deny_baseline()
        candidates = (
            "short", "wrong-length-token-" + "a" * 40,
            quote("illegal characters !!! not urlsafe +++"),
            secrets.token_urlsafe(32),  # valid shape, unknown
            self.token + "x",  # near-miss
            "a" * 64,  # a sha256-shaped string is still just an unknown token
        )
        for candidate in candidates:
            for suffix in ("", f"/charts/{uuid4()}/view", f"/charts/{uuid4()}/csv"):
                path = f"/api/shares/{candidate}{suffix}"
                self.foreign_404(self.client.get(path), baseline, path[:60])
        # Every deny carries the identical envelope fields and no details —
        # no oracle distinguishes unknown/revoked/expired/malformed.
        first = self.client.get(f"/api/shares/{secrets.token_urlsafe(32)}")
        second = self.client.get(f"/api/shares/{secrets.token_urlsafe(32)}")
        for response in (first, second):
            error = response.json()["error"]
            self.assertEqual(error["code"], "NOT_FOUND")
            self.assertEqual(error["message"], baseline["message"])
            self.assertIsNone(error.get("details"))

    def test_03_revoked_and_expired_denies_equal_the_unknown_deny(self):
        baseline = self.deny_baseline()

        def envelope_fields(response) -> dict:
            error = response.json()["error"]
            return {"code": error["code"], "message": error["message"],
                    "details": error.get("details")}

        # Revoke Alice's share through her own session.
        with self.as_session(self.alice_id):
            revoked = self.client.delete(
                f"/api/documents/{self.alice_document_id}/shares/{self.alice_share_id}",
                headers={"Authorization": f"Bearer t.{self.alice_id}"})
        self.assertEqual(revoked.status_code, 204)
        unknown_fields = envelope_fields(
            self.client.get(f"/api/shares/{secrets.token_urlsafe(32)}"))
        revoked_deny = self.client.get(f"/api/shares/{self.token}")
        self.foreign_404(revoked_deny, baseline, "revoked")
        self.assertEqual(envelope_fields(revoked_deny), unknown_fields,
                         "revoked must be indistinguishable from unknown")
        # An expired share denies identically; build a fresh share for it.
        token2, share2, _document2 = self.fresh_share()
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.document_shares SET expires_at = now() - interval '1 hour'"
                " WHERE id = :id"), {"id": share2})
        expired_deny = self.client.get(f"/api/shares/{token2}")
        self.assertEqual(envelope_fields(expired_deny), unknown_fields,
                         "expired must be indistinguishable from unknown")
        # Every asset path of a dead share denies too.
        self.assertEqual(self.client.get(
            f"/api/shares/{self.token}/charts/{uuid4()}/view").status_code, 404)
        self.assertEqual(self.client.get(
            f"/api/shares/{self.token}/charts/{uuid4()}/csv").status_code, 404)

    def fresh_share(self) -> tuple[str, UUID, UUID]:
        dataset_id = self.stage_volume(self.dataset_key("security2"), "3")
        created = service.create_document(self.engine, self.alice,
                                          title="Synthetic second share (fixture)")
        content = {"schema_version": 1, "type": "doc", "content": [
            document_fixtures.block("liveChart", str(uuid4()), mode="live",
                                    selection=chart_fixtures.selection(),
                                    chart_definition_version_id=str(chart_fixtures.CHART_ID),
                                    observed_dataset_version_id=str(dataset_id))]}
        service.save_revision(self.engine, self.alice, created.document.id,
                              expected_revision=1, document_payload=content)
        with self.as_session(self.alice_id):
            preview = self.client.get(
                f"/api/documents/{created.document.id}/shares/preview",
                headers={"Authorization": f"Bearer t.{self.alice_id}"})
            shown = preview.json()
            response = self.client.post(
                f"/api/documents/{created.document.id}/shares",
                headers={"Authorization": f"Bearer t.{self.alice_id}"},
                json={"acknowledged_revision": shown["revision"],
                      "preview_sha256": shown["projection_sha256"],
                      "visible_scope": shown["scope"]})
        self.assertEqual(response.status_code, 201, response.text)
        return (response.json()["share_token"], UUID(response.json()["id"]),
                created.document.id)

    def test_04_bob_cannot_manage_or_even_see_alices_shares(self):
        baseline = self.absent_document_baseline()
        with self.as_session(self.bob_id):
            headers = {"Authorization": f"Bearer t.{self.bob_id}"}
            preview = self.client.get(
                f"/api/documents/{self.alice_document_id}/shares/preview",
                headers=headers)
            listing = self.client.get(
                f"/api/documents/{self.alice_document_id}/shares", headers=headers)
            revoke = self.client.delete(
                f"/api/documents/{self.alice_document_id}/shares/{self.alice_share_id}",
                headers=headers)
        for label, response in (("preview", preview), ("list", listing),
                                ("revoke", revoke)):
            self.foreign_404(response, baseline, label)

    def absent_document_baseline(self) -> dict:
        with self.as_session(self.bob_id):
            missing = self.client.get(f"/api/documents/{uuid4()}",
                                      headers={"Authorization": f"Bearer t.{self.bob_id}"})
        error = missing.json()["error"]
        return {"code": error["code"], "message": error["message"],
                "details": error.get("details")}

    def test_05_share_surface_grants_no_private_access_and_never_caches(self):
        # The share response set is no-store + no-referrer on success AND deny.
        for response in (
                self.client.get(f"/api/shares/{self.token}"),
                self.client.get(f"/api/shares/{secrets.token_urlsafe(32)}"),
                self.client.get(
                    f"/api/shares/{self.token}/charts/{uuid4()}/view"),
                self.client.get(
                    f"/api/shares/{self.token}/charts/{uuid4()}/csv")):
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")
            self.assertEqual(response.headers.get("Referrer-Policy"), "no-referrer")
        # The token is a PATH segment only: there is no query-string variant
        # and no redirect that could carry it into a referrer.
        stray = self.client.get("/api/shares", params={"token": self.token})
        self.assertEqual(stray.status_code, 404)
        # Private families stay closed to the anonymous holder of a token.
        self.assertEqual(self.client.get("/api/documents?q=synthetic").status_code, 401)
        self.assertEqual(self.client.get(
            f"/api/documents/{self.alice_document_id}").status_code, 401)
        self.assertEqual(self.client.get(
            f"/api/documents/{self.alice_document_id}/versions").status_code, 401)
        self.assertEqual(self.client.post(
            f"/api/documents/{self.alice_document_id}/exports",
            json={"document_version_id": str(uuid4()),
                  "format": "markdown_zip"}).status_code, 401)


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ShareRlsProbeTests(unittest.TestCase):
    """Direct database probes on the ADR-021 policy design (migration 0017)."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[4]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"],
                                     poolclass=NullPool, hide_parameters=True)
        cls.public = create_engine(os.environ["NI_TEST_PUBLIC_URL"],
                                   poolclass=NullPool, hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"],
                                  poolclass=NullPool, hide_parameters=True)
        command.upgrade(cls.config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.runtime.dispose()
        cls.operator.dispose()
        cls.public.dispose()
        cls.admin.dispose()

    def setUp(self):
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))
        self.alice_id, self.bob_id = uuid4(), uuid4()
        for subject in (self.alice_id, self.bob_id):
            with user_transaction(self.runtime, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"),
                                   {"id": subject})
        self.alice = Principal(id=self.alice_id, display_name="Synthetic Alice",
                               display_timezone="UTC")
        self.bob = Principal(id=self.bob_id, display_name="Synthetic Bob",
                             display_timezone="UTC")
        self.document_id, self.version_id = self._alice_document()
        self.share_id, self.token, self.token_hash = self._alice_share()

    def _alice_document(self) -> tuple[UUID, UUID]:
        document_id, version_id = uuid4(), uuid4()
        with user_transaction(self.runtime, self.alice_id) as connection:
            connection.execute(text("SET CONSTRAINTS ALL DEFERRED"))
            connection.execute(text("""
                INSERT INTO app.documents(id, owner_id, title, revision,
                       current_version_id, schema_version)
                VALUES (:id, :owner, 'Synthetic share probe', 1, :version, 1)
            """), {"id": document_id, "owner": self.alice_id, "version": version_id})
            connection.execute(text("""
                INSERT INTO app.document_versions(id, document_id, owner_id, revision,
                       schema_version, content, content_sha256)
                VALUES (:id, :document, :owner, 1, 1,
                        CAST('{\"type\":\"doc\",\"content\":[]}' AS jsonb), :sha)
            """), {"id": version_id, "document": document_id, "owner": self.alice_id,
                   "sha": SHA256})
        return document_id, version_id

    def _alice_share(self) -> tuple[UUID, str, str]:
        share_id = uuid4()
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        # The projection JSON travels as a bound parameter: an inline literal
        # would let SQLAlchemy text() read the JSON's `":1"` as a bind name.
        projection_json = json.dumps({"share_projection_version": 1})
        with self.admin.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.document_shares(id, owner_id, document_id,
                       document_version_id, token_hash, revision, projection,
                       projection_sha256, projection_byte_size)
                VALUES (:id, :owner, :document, :version, :hash, 1,
                        CAST(:projection AS bytea), :sha,
                        octet_length(CAST(:projection AS bytea)))
            """), {"id": share_id, "owner": self.alice_id, "document": self.document_id,
                   "version": self.version_id, "hash": token_hash, "sha": SHA256,
                   "projection": projection_json})
        return share_id, token, token_hash

    # -- the capability plane (no identity) ----------------------------------- #

    def test_capability_plane_reads_live_rows_only_by_digest(self):
        with self.runtime.connect() as connection:
            # A live row is readable by its digest...
            live = connection.execute(text(
                "SELECT count(*) FROM app.document_shares WHERE token_hash = :hash"),
                {"hash": self.token_hash}).scalar_one()
            self.assertEqual(live, 1)
            # ...and a no-identity session can enumerate ONLY live rows.
            total = connection.execute(text(
                "SELECT count(*) FROM app.document_shares")).scalar_one()
            self.assertEqual(total, 1)
        # A revoked row is invisible even to raw no-identity SQL.
        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.document_shares
                   SET status = 'revoked', revoked_at = now(), updated_at = now(),
                       projection = NULL, projection_sha256 = NULL,
                       projection_byte_size = NULL
                 WHERE id = :id
            """), {"id": self.share_id})
        with self.runtime.connect() as connection:
            dead = connection.execute(text(
                "SELECT count(*) FROM app.document_shares WHERE token_hash = :hash"),
                {"hash": self.token_hash}).scalar_one()
            self.assertEqual(dead, 0, "a revoked row must be invisible")
            total = connection.execute(text(
                "SELECT count(*) FROM app.document_shares")).scalar_one()
            self.assertEqual(total, 0)

    def test_capability_plane_is_voided_by_any_identity(self):
        # An authenticated session (Bob) cannot read Alice's share even with
        # the digest in hand: the token policy requires NO identity.
        with user_transaction(self.runtime, self.bob_id) as connection:
            rows = connection.execute(text(
                "SELECT count(*) FROM app.document_shares WHERE token_hash = :hash"),
                {"hash": self.token_hash}).scalar_one()
            self.assertEqual(rows, 0, "an identity must void the token policy")

    def test_expired_rows_are_invisible_to_the_capability_plane(self):
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.document_shares SET expires_at = now() - interval '1 minute'"
                " WHERE id = :id"), {"id": self.share_id})
        with self.runtime.connect() as connection:
            rows = connection.execute(text(
                "SELECT count(*) FROM app.document_shares WHERE token_hash = :hash"),
                {"hash": self.token_hash}).scalar_one()
        self.assertEqual(rows, 0)

    # -- the owner plane (identity-bound, immutable bytes) --------------------- #

    def test_owner_cannot_rewrite_frozen_bytes_or_token(self):
        with self.assertRaises(DBAPIError) as caught, \
                user_transaction(self.runtime, self.alice_id) as connection:
            connection.execute(text("""
                UPDATE app.document_shares SET projection = 'x'::bytea
                 WHERE id = :id
            """), {"id": self.share_id})
        self.assertIn("immutable", str(caught.exception.orig))
        with self.assertRaises(DBAPIError) as caught, \
                user_transaction(self.runtime, self.alice_id) as connection:
            connection.execute(text("""
                UPDATE app.document_shares SET token_hash = :hash WHERE id = :id
            """), {"id": self.share_id, "hash": "e" * 64})
        self.assertEqual(caught.exception.orig.sqlstate, "42501",
                         "token_hash carries no UPDATE grant")
        with self.assertRaises(DBAPIError) as caught, \
                user_transaction(self.runtime, self.alice_id) as connection:
            connection.execute(text("""
                UPDATE app.document_shares SET status = 'revoked' WHERE id = :id
            """), {"id": self.share_id})
        self.assertEqual(caught.exception.orig.sqlstate, "23514",
                         "revocation without clearing bytes violates the pairing")

    def test_owner_revoke_clears_bytes_and_denies_capability(self):
        with user_transaction(self.runtime, self.alice_id) as connection:
            connection.execute(text("""
                UPDATE app.document_shares
                   SET status = 'revoked', revoked_at = now(), updated_at = now(),
                       projection = NULL, projection_sha256 = NULL,
                       projection_byte_size = NULL
                 WHERE id = :id
            """), {"id": self.share_id})
        with self.runtime.connect() as connection:
            rows = connection.execute(text(
                "SELECT count(*) FROM app.document_shares WHERE token_hash = :hash"),
                {"hash": self.token_hash}).scalar_one()
        self.assertEqual(rows, 0)

    def test_bob_cannot_insert_update_or_delete_alices_share(self):
        with self.assertRaises(DBAPIError) as caught, \
                user_transaction(self.runtime, self.bob_id) as connection:
            connection.execute(text("""
                INSERT INTO app.document_shares(id, owner_id, document_id,
                       document_version_id, token_hash, revision, projection,
                       projection_sha256, projection_byte_size)
                VALUES (:id, :owner, :document, :version, :hash, 1, 'x'::bytea,
                        :sha, 1)
            """), {"id": uuid4(), "owner": self.alice_id,
                   "document": self.document_id, "version": self.version_id,
                   "hash": "d" * 64, "sha": SHA256})
        self.assertEqual(caught.exception.orig.sqlstate, "42501")
        hidden = (
            ("UPDATE app.document_shares SET status = 'revoked' WHERE id = :id",
             {"id": self.share_id}, "update foreign share"),
            ("DELETE FROM app.document_shares WHERE id = :id",
             {"id": self.share_id}, "delete foreign share"),
        )
        for statement, params, where in hidden:
            with user_transaction(self.runtime, self.bob_id) as connection:
                rowcount = connection.execute(text(statement), params).rowcount
            self.assertEqual(rowcount, 0, where)

    def test_operator_has_purge_only_power(self):
        # Lifecycle metadata is readable through the narrow column grant (the
        # purge WHERE needs it); token digests and bytes are not granted.
        with self.operator.connect() as connection:
            row = connection.execute(text(
                "SELECT id, owner_id, status FROM app.document_shares "
                "WHERE id = :id"), {"id": self.share_id}).one()
            self.assertEqual(str(row[0]), str(self.share_id))
        for statement in ("SELECT token_hash FROM app.document_shares",
                          "SELECT projection FROM app.document_shares",
                          "SELECT projection_sha256 FROM app.document_shares",
                          "SELECT projection_byte_size FROM app.document_shares",
                          "UPDATE app.document_shares SET status = 'revoked'"):
            with self.assertRaises(DBAPIError) as caught, \
                    self.operator.connect() as connection:
                connection.execute(text(statement))
            self.assertEqual(caught.exception.orig.sqlstate, "42501", statement)
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.document_shares WHERE id = :id"),
                               {"id": self.share_id})
        with self.admin.connect() as connection:
            rows = connection.execute(text(
                "SELECT count(*) FROM app.document_shares WHERE id = :id"),
                {"id": self.share_id}).scalar_one()
        self.assertEqual(rows, 0)

    def test_public_role_has_nothing_and_rls_is_forced(self):
        with self.assertRaises(DBAPIError), self.public.connect() as connection:
            connection.execute(text("SELECT count(*) FROM app.document_shares"))
        with self.assertRaises(DBAPIError) as caught, \
                self.runtime.connect() as connection:
            connection.execute(text("SET row_security = off"))
            connection.execute(text(
                "SELECT count(*) FROM app.document_shares WHERE id = :id"),
                {"id": self.share_id})
        self.assertEqual(caught.exception.orig.sqlstate, "42501")

    def test_document_deletion_cascades_shares_away(self):
        with user_transaction(self.runtime, self.alice_id) as connection:
            connection.execute(text("DELETE FROM app.documents WHERE id = :id"),
                               {"id": self.document_id})
        with self.admin.connect() as connection:
            rows = connection.execute(text(
                "SELECT count(*) FROM app.document_shares WHERE id = :id"),
                {"id": self.share_id}).scalar_one()
        self.assertEqual(rows, 0)


if __name__ == "__main__":
    unittest.main()
