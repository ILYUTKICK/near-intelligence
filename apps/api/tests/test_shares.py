"""NI-060 tests, database part: the share capability lifecycle end to end.

Needs scripts/run-db-tests.py (a disposable loopback PostgreSQL cluster);
direct discovery skips the class — a skip is never successful integration
evidence. All identities, documents, datasets and amounts are synthetic
fixtures; no provider, archive or network is contacted. Covered guarantees:

- full lifecycle: preview (the EXACT projection, no private fields) -> create
  (consent naming revision + scope, token returned ONCE) -> read as anonymous
  AND as the non-owner Bob through the token -> chart view + exact CSV ->
  revoke -> projection, view and CSV all deny with ONE generic 404;
- consent enforcement: wrong revision -> 409, stale preview hash -> 409,
  wrong scope -> 422, past/beyond-bound expiry -> 422, Idempotency-Key replay
  identifies the same share and NEVER re-emits the token;
- frozen publication: a rename, a new revision and a new dataset publication
  after the create leave the public projection byte-identical;
- expiry: a past expiry denies every public path (read/view/CSV) while the
  owner list reports ``expired`` honestly, then revocation reports
  ``revoked``;
- owner matrix: Bob cannot preview, list, or revoke Alice's shares (one
  generic 404, byte-equal to the absent-resource answer);
- fail-closed content: a mutated pinned dataset observation refuses the
  preview typed (422 REFERENCE_INVALID), never a partial publication;
- capability hygiene: the raw token appears in no table column, the owner
  list carries neither token nor hash, every share response (success and
  deny, owner and public) is no-store + no-referrer;
- migration 0017 downgrade/upgrade round trip with the model mirror.
"""

import copy
import hashlib
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
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
NO_SHARE_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ShareDatabaseTests(chart_fixtures.ChartBlockDatabaseFixture, unittest.TestCase):
    """The owned share lifecycle on the disposable cluster."""

    def setUp(self):
        super().setUp()
        # Public share routes build their engine through the same lazy helper;
        # point it at the disposable cluster's runtime connection for the
        # whole class so anonymous token reads hit the real RLS capability
        # plane (no identity, exactly like production).
        self.engine_patcher = patch.object(principal_module, "_get_engine",
                                           return_value=self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)

    # -- fixture helpers (mirroring the export-job suite) --------------------- #

    def bearer(self, subject) -> dict:
        return {"Authorization": f"Bearer t.{subject}"}

    def dataset_key(self, name: str) -> str:
        return f"synthetic.{uuid4().hex[:8]}.{name}"

    def stage_volume(self, key: str, value: str) -> UUID:
        """One published synthetic dataset version for the chart."""
        if not hasattr(self, "directory"):
            tmp = tempfile.TemporaryDirectory(prefix="ni060-",
                                              dir=os.environ["NI_TEST_TMP_DIR"])
            self.addCleanup(tmp.cleanup)
            self.directory = Path(tmp.name)
            self.storage_root = self.directory / "storage"
        dimensions = {"source": "SRC-LLAMA"}
        result = data_fixture.DeliveryDatabaseTests.stage_fixture(
            self, key,
            [data_fixture.observation(chart_fixtures.METRIC_ID, date(2026, 1, 1),
                                      value=value, bound_kind="lower",
                                      dimensions=dimensions),
             data_fixture.observation(chart_fixtures.METRIC_ID, date(2026, 1, 2),
                                      value=None, dimensions=dimensions)],
            [chart_fixtures.METRIC_ID], window=("2026-01-01", "2026-01-03"))
        return result.dataset_version_id

    def full_content(self, *, dataset_id: UUID, table_dataset_id: UUID) -> dict:
        """A synthetic document with chart, table, cards, evidence and prose."""
        insight_context = chart_fixtures.volume_context(self.operator, dataset_id)
        hypothesis = document_fixtures.hypothesis_attrs()
        hypothesis_id = hypothesis["attrs"]["hypothesis_id"]
        insight = document_fixtures.insight_attrs(
            hypothesis_id=hypothesis_id, context=copy.deepcopy(insight_context))
        chart_block_id = str(uuid4())
        chart = document_fixtures.block(
            "liveChart", chart_block_id, mode="live", selection=chart_fixtures.selection(),
            chart_definition_version_id=str(chart_fixtures.CHART_ID),
            observed_dataset_version_id=str(dataset_id))
        return {"schema_version": 1, "type": "doc", "content": [
            {"type": "paragraph", "attrs": {"block_id": str(uuid4())},
             "content": [document_fixtures.text_node("Synthetic shared research ")]},
            {"type": "heading", "attrs": {"block_id": str(uuid4()), "level": 2},
             "content": [document_fixtures.text_node("Findings")]},
            document_fixtures.data_table_attrs(
                rows=[["fees", "12.5"], [None, True], [2, 12.5]]),
            document_fixtures.data_table_attrs(
                dataset_version_id=str(table_dataset_id)),
            hypothesis, insight,
            document_fixtures.evidence_attrs(hypothesis_id, "insight",
                                             insight["attrs"]["insight_id"]),
            document_fixtures.risk_attrs(hypothesis_id),
            document_fixtures.block("divider"),
            chart,
        ]}

    def create_full_document(self, principal: Principal, *, dataset_id: UUID,
                             table_dataset_id: UUID,
                             title: str = "Synthetic shared research (fixture)"):
        created = service.create_document(self.engine, principal, title=title)
        content = self.full_content(dataset_id=dataset_id,
                                    table_dataset_id=table_dataset_id)
        saved = service.save_revision(self.engine, principal, created.document.id,
                                      expected_revision=1, document_payload=content)
        return created, saved

    def preview(self, document_id: UUID, *, subject=None) -> dict:
        with self.as_session(subject or self.alice_id):
            response = self.client.get(
                f"/api/documents/{document_id}/shares/preview",
                headers=self.bearer(subject or self.alice_id))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(response.headers.get("Referrer-Policy"), "no-referrer")
        return response.json()

    def consent_payload(self, document_id: UUID, *, subject=None,
                        revision: int | None = None, preview_sha256: str | None = None,
                        scope: dict | None = None, expires_at: str | None = None) -> dict:
        shown = self.preview(document_id, subject=subject)
        payload = {
            "acknowledged_revision": shown["revision"] if revision is None else revision,
            "preview_sha256": shown["projection_sha256"] if preview_sha256 is None
            else preview_sha256,
            "visible_scope": shown["scope"] if scope is None else scope,
        }
        if expires_at is not None:
            payload["expires_at"] = expires_at
        return payload

    def create_share(self, document_id: UUID, *, subject=None, key: str | None = None,
                     **payload_changes) -> "TestClient.response":
        payload = self.consent_payload(document_id, subject=subject, **payload_changes)
        headers = {**self.bearer(subject or self.alice_id)}
        if key is not None:
            headers["Idempotency-Key"] = key
        with self.as_session(subject or self.alice_id):
            return self.client.post(f"/api/documents/{document_id}/shares",
                                    headers=headers, json=payload)

    def share_row(self, share_id: UUID) -> dict:
        with self.admin.connect() as connection:
            row = connection.execute(text("""
                SELECT id, owner_id, document_id, document_version_id, token_hash,
                       status, revision,
                       projection IS NOT NULL AS has_projection,
                       projection_sha256, projection_byte_size, expires_at, revoked_at
                  FROM app.document_shares WHERE id = :id
            """), {"id": share_id}).mappings().one()
        return dict(row)

    def expire(self, share_id: UUID, *, hours: float = -1.0):
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.document_shares SET expires_at = now() + make_interval"
                "(secs => :secs) WHERE id = :id"),
                {"secs": hours * 3600, "id": share_id})

    def absent_baseline(self) -> dict:
        with self.as_session(self.bob_id):
            missing = self.client.get(f"/api/documents/{uuid4()}",
                                      headers=self.bearer(self.bob_id))
        self.assertEqual(missing.status_code, 404)
        error = missing.json()["error"]
        return {"code": error["code"], "message": error["message"],
                "details": error.get("details")}

    def assert_generic_deny(self, response, baseline: dict, where: str):
        self.assertEqual(response.status_code, 404, f"{where}: {response.text}")
        self.assertEqual(response.headers.get("Cache-Control"), "no-store", where)
        error = response.json()["error"]
        self.assertEqual(error["code"], baseline["code"], where)
        self.assertEqual(error["message"], baseline["message"], where)
        self.assertEqual(error.get("details"), baseline.get("details"), where)

    # -- the lifecycle -------------------------------------------------------- #

    def test_01_preview_create_read_revoke_deny_full_matrix(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)

        # PREVIEW: the exact projection, visibly without private fields.
        shown = self.preview(created.document.id)
        self.assertEqual(shown["revision"], 2)
        projection = shown["projection"]
        self.assertEqual(projection["document"]["title"],
                         "Synthetic shared research (fixture)")
        self.assertEqual(projection["document"]["revision"], 2)
        self.assertEqual(projection["document"]["content_sha256"],
                         saved.version.content_sha256)
        blob = json.dumps(projection)
        for private in ("document_id", "owner_id", "author", "display_name",
                        "insight_id", "hypothesis_id", "evidence_id", "target_id",
                        "snapshot_id", "authored_at", "modified_at", "explanation",
                        str(self.alice_id)):
            self.assertNotIn(private, blob, f"preview leaked {private}")
        block_types = [block["block_type"] for block in projection["blocks"]]
        self.assertEqual(block_types.count("liveChart"), 1)
        self.assertEqual(block_types.count("dataTable"), 2)
        self.assertEqual(shown["scope"]["chart_blocks"], 1)
        self.assertEqual(shown["scope"]["source_references"], 1)

        # CREATE: consent names revision + scope; the token appears once.
        created_share = self.create_share(created.document.id)
        self.assertEqual(created_share.status_code, 201, created_share.text)
        share = created_share.json()
        token = share["share_token"]
        self.assertTrue(token and len(token) >= 32)
        self.assertEqual(share["share_path"], f"/share/{token}")
        self.assertEqual(share["status"], "active")
        self.assertEqual(created_share.headers.get("Cache-Control"), "no-store")
        self.assertEqual(created_share.headers.get("Referrer-Policy"), "no-referrer")

        # The stored row holds ONLY the digest; the raw token is nowhere.
        row = self.share_row(UUID(share["id"]))
        self.assertEqual(row["token_hash"],
                         hashlib.sha256(token.encode()).hexdigest())
        self.assertEqual(row["status"], "active")
        self.assertTrue(row["has_projection"])
        with self.admin.connect() as connection:
            raw_hits = connection.execute(text("""
                SELECT count(*) FROM app.document_shares
                 WHERE token_hash = :token OR projection::text LIKE :token
            """), {"token": token}).scalar_one()
        self.assertEqual(raw_hits, 0, "the raw token must never be stored")

        # READ as anonymous (no Authorization header at all).
        anonymous = self.client.get(f"/api/shares/{token}")
        self.assertEqual(anonymous.status_code, 200, anonymous.text)
        self.assertEqual(anonymous.json(), projection)
        self.assertEqual(anonymous.headers.get("Cache-Control"), "no-store")
        self.assertEqual(anonymous.headers.get("Referrer-Policy"), "no-referrer")

        # READ as the non-owner Bob (a session exists but the token is the
        # only credential; the projection is the same frozen bytes).
        with self.as_session(self.bob_id):
            as_bob = self.client.get(f"/api/shares/{token}",
                                     headers=self.bearer(self.bob_id))
        self.assertEqual(as_bob.status_code, 200)
        self.assertEqual(as_bob.json(), projection)

        # ASSETS: the frozen chart view and its exact CSV.
        chart_block_id = next(block["block_id"] for block in projection["blocks"]
                              if block["block_type"] == "liveChart")
        with self.as_session(self.bob_id):
            view = self.client.get(f"/api/shares/{token}/charts/{chart_block_id}/view",
                                   headers=self.bearer(self.bob_id))
            csv = self.client.get(f"/api/shares/{token}/charts/{chart_block_id}/csv")
        self.assertEqual(view.status_code, 200, view.text)
        self.assertEqual(view.json()["context_hash"],
                         next(block["view"]["context_hash"] for block in projection["blocks"]
                              if block["block_type"] == "liveChart"))
        self.assertEqual(csv.status_code, 200)
        self.assertEqual(csv.headers.get("Cache-Control"), "no-store")
        self.assertIn("attachment", csv.headers.get("Content-Disposition", ""))
        self.assertIn("12.5", csv.text)

        # REVOKE: the owner deletes the publication; everything denies.
        with self.as_session(self.alice_id):
            revoked = self.client.delete(
                f"/api/documents/{created.document.id}/shares/{share['id']}",
                headers=self.bearer(self.alice_id))
        self.assertEqual(revoked.status_code, 204)
        self.assertEqual(revoked.headers.get("Cache-Control"), "no-store")
        row = self.share_row(UUID(share["id"]))
        self.assertEqual(row["status"], "revoked")
        self.assertFalse(row["has_projection"], "revocation must clear the bytes")
        self.assertIsNone(row["projection_sha256"])

        baseline = self.absent_baseline()
        for label, response in (
                ("projection", self.client.get(f"/api/shares/{token}")),
                ("view", self.client.get(
                    f"/api/shares/{token}/charts/{chart_block_id}/view")),
                ("csv", self.client.get(
                    f"/api/shares/{token}/charts/{chart_block_id}/csv"))):
            self.assert_generic_deny(response, baseline, label)

        # The owner list keeps the lifecycle record.
        with self.as_session(self.alice_id):
            listing = self.client.get(f"/api/documents/{created.document.id}/shares",
                                      headers=self.bearer(self.alice_id))
        self.assertEqual(listing.status_code, 200)
        records = listing.json()["items"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "revoked")
        self.assertNotIn("share_token", records[0])
        self.assertNotIn("token_hash", json.dumps(records[0]))

    def test_02_idempotent_replay_never_reemits_the_token(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "9")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        key = str(uuid4())
        first = self.create_share(created.document.id, key=key)
        self.assertEqual(first.status_code, 201)
        token = first.json()["share_token"]
        self.assertIsNotNone(token)
        second = self.create_share(created.document.id, key=key)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["id"], first.json()["id"])
        self.assertIsNone(second.json()["share_token"],
                          "a replay cannot re-emit the capability")
        with self.admin.connect() as connection:
            count = connection.scalar(text(
                "SELECT count(*) FROM app.document_shares WHERE owner_id = :owner"),
                {"owner": self.alice_id})
        self.assertEqual(count, 1)
        # Malformed key -> 422 at the route.
        bad_key = self.create_share(created.document.id, key="not-a-uuid")
        self.assertEqual(bad_key.status_code, 422)
        self.assertEqual(ErrorResponse.model_validate(bad_key.json()).error.code,
                         "VALIDATION_ERROR")
        # A fresh key creates an independent share.
        third = self.create_share(created.document.id, key=str(uuid4()))
        self.assertEqual(third.status_code, 201)
        self.assertIsNotNone(third.json()["share_token"])
        self.assertNotEqual(third.json()["id"], first.json()["id"])

    def test_03_consent_mismatches_are_refused(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "7.25")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        shown = self.preview(created.document.id)
        # Wrong revision -> typed 409.
        refused = self.create_share(created.document.id, revision=shown["revision"] + 1)
        self.assertEqual(refused.status_code, 409, refused.text)
        self.assertEqual(ErrorResponse.model_validate(refused.json()).error.code,
                         "REVISION_NOT_ACKNOWLEDGED")
        # Stale preview hash -> typed 409.
        stale = self.create_share(created.document.id,
                                  preview_sha256="f" * 64)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(ErrorResponse.model_validate(stale.json()).error.code,
                         "PREVIEW_MISMATCH")
        # Wrong scope -> typed 422.
        wrong_scope = dict(shown["scope"], chart_blocks=99)
        mismatch = self.create_share(created.document.id, scope=wrong_scope)
        self.assertEqual(mismatch.status_code, 422, mismatch.text)
        self.assertEqual(ErrorResponse.model_validate(mismatch.json()).error.code,
                         "SCOPE_MISMATCH")
        # Past expiry and beyond the one-year consent bound -> 422.
        past = self.create_share(created.document.id,
                                 expires_at="2026-01-01T00:00:00Z")
        self.assertEqual(past.status_code, 422)
        far = self.create_share(created.document.id,
                                expires_at=(datetime.now(timezone.utc)
                                            + timedelta(days=366)).isoformat())
        self.assertEqual(far.status_code, 422)
        # A valid bounded future expiry is accepted.
        soon = self.create_share(
            created.document.id,
            expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat())
        self.assertEqual(soon.status_code, 201, soon.text)
        self.assertIsNotNone(soon.json()["expires_at"])

    def test_04_publication_is_frozen_across_edit_and_dataset_refresh(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "6.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        response = self.create_share(created.document.id)
        self.assertEqual(response.status_code, 201)
        token = response.json()["share_token"]
        digest_before = self.share_row(UUID(response.json()["id"]))["projection_sha256"]
        before = self.client.get(f"/api/shares/{token}")
        self.assertEqual(before.status_code, 200)
        frozen = before.json()

        # The owner renames, saves a NEW revision and publishes a NEW dataset
        # version: none of it may reach the already-consented publication.
        renamed = service.rename_document(self.engine, self.alice, created.document.id,
                                          expected_revision=saved.document.revision,
                                          title="Synthetic shared research v2 (fixture)")
        new_dataset = self.stage_volume(self.dataset_key("intents-refresh"), "99")
        content = self.full_content(dataset_id=new_dataset,
                                    table_dataset_id=dataset_id)
        new_saved = service.save_revision(self.engine, self.alice, created.document.id,
                                          expected_revision=renamed.document.revision,
                                          document_payload=content)
        after = self.client.get(f"/api/shares/{token}")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.json(), frozen,
                         "an edit/dataset refresh must never mutate the share")
        self.assertEqual(after.json()["document"]["revision"], saved.document.revision)
        self.assertEqual(after.json()["document"]["title"],
                         "Synthetic shared research (fixture)")

        # The owner's fresh preview reflects the NEW revision; the stored
        # share digest does not move (no silent refresh, REPRODUCIBILITY).
        row = self.share_row(UUID(response.json()["id"]))
        self.assertEqual(row["projection_sha256"], digest_before)
        fresh = self.preview(created.document.id)
        self.assertEqual(fresh["revision"], new_saved.document.revision)
        self.assertNotEqual(fresh["projection_sha256"], row["projection_sha256"])

    def test_05_expired_share_denies_and_the_owner_list_reports_it(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "5")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        response = self.create_share(created.document.id)
        token = response.json()["share_token"]
        share_id = UUID(response.json()["id"])
        self.expire(share_id, hours=-1.0)

        baseline = self.absent_baseline()
        self.assert_generic_deny(self.client.get(f"/api/shares/{token}"),
                                 baseline, "expired projection")
        projection = self.preview(created.document.id)
        chart_block_id = next(block["block_id"] for block in projection["projection"]["blocks"]
                              if block["block_type"] == "liveChart")
        self.assert_generic_deny(
            self.client.get(f"/api/shares/{token}/charts/{chart_block_id}/view"),
            baseline, "expired view")
        self.assert_generic_deny(
            self.client.get(f"/api/shares/{token}/charts/{chart_block_id}/csv"),
            baseline, "expired csv")

        with self.as_session(self.alice_id):
            listing = self.client.get(f"/api/documents/{created.document.id}/shares",
                                      headers=self.bearer(self.alice_id))
        self.assertEqual(listing.json()["items"][0]["status"], "expired")

        # Revoking an expired share still clears and finalizes it.
        with self.as_session(self.alice_id):
            revoked = self.client.delete(
                f"/api/documents/{created.document.id}/shares/{share_id}",
                headers=self.bearer(self.alice_id))
        self.assertEqual(revoked.status_code, 204)
        with self.as_session(self.alice_id):
            listing = self.client.get(f"/api/documents/{created.document.id}/shares",
                                      headers=self.bearer(self.alice_id))
        self.assertEqual(listing.json()["items"][0]["status"], "revoked")

    def test_06_foreign_share_management_is_one_generic_404(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "4.5")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        response = self.create_share(created.document.id)
        share_id = response.json()["id"]
        baseline = self.absent_baseline()
        with self.as_session(self.bob_id):
            preview = self.client.get(
                f"/api/documents/{created.document.id}/shares/preview",
                headers=self.bearer(self.bob_id))
            listing = self.client.get(f"/api/documents/{created.document.id}/shares",
                                      headers=self.bearer(self.bob_id))
            revoke = self.client.delete(
                f"/api/documents/{created.document.id}/shares/{share_id}",
                headers=self.bearer(self.bob_id))
        for label, item in (("preview", preview), ("list", listing),
                            ("revoke", revoke)):
            self.assert_generic_deny(item, baseline, label)
        # Bob's own document shares nothing of Alice's.
        bob_created, _bob_saved = self.create_full_document(
            self.bob, dataset_id=dataset_id, table_dataset_id=dataset_id,
            title="Bob synthetic research (fixture)")
        with self.as_session(self.bob_id):
            bob_list = self.client.get(f"/api/documents/{bob_created.document.id}/shares",
                                       headers=self.bearer(self.bob_id))
        self.assertEqual(bob_list.status_code, 200)
        self.assertEqual(bob_list.json()["items"], [])

    def test_07_a_share_grants_no_private_access(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "3.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        response = self.create_share(created.document.id)
        token = response.json()["share_token"]
        projection = self.client.get(f"/api/shares/{token}").json()
        # No private identifier routes out of the projection: the public
        # payload cannot be turned into draft/history/write/export access.
        self.assertNotIn(str(created.document.id), json.dumps(projection))
        self.assertNotIn(str(saved.version.id), json.dumps(projection))
        # The token is not an auth credential anywhere else.
        unauthenticated = self.client.get("/api/documents")
        self.assertEqual(unauthenticated.status_code, 401)
        bob_document = self.client.get(
            f"/api/documents/{created.document.id}",
            headers={"Authorization": f"Bearer share-{token}"})
        self.assertEqual(bob_document.status_code, 401)
        # Anonymous hit on the private document route stays 401.
        self.assertEqual(self.client.get(
            f"/api/documents/{created.document.id}/versions").status_code, 401)
        # Anonymous hit on the export plane stays 401.
        self.assertEqual(self.client.post(
            f"/api/documents/{created.document.id}/exports",
            json={"document_version_id": str(saved.version.id),
                  "format": "markdown_zip"}).status_code, 401)

    def test_08_broken_pin_fails_the_publication_closed(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "2.5")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        # A valid preview before the corruption: the create payload reuses it.
        shown = self.preview(created.document.id)
        # Corrupt the pinned dataset's stored observation via admin SQL: the
        # reconstruction verifies the staged digest and must fail CLOSED.
        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.metric_observations
                   SET value = '999999'
                 WHERE dataset_version_id = :dataset
                   AND value IS NOT NULL
            """), {"dataset": dataset_id})
        with self.as_session(self.alice_id):
            preview = self.client.get(
                f"/api/documents/{created.document.id}/shares/preview",
                headers=self.bearer(self.alice_id))
        self.assertEqual(preview.status_code, 422, preview.text)
        self.assertEqual(ErrorResponse.model_validate(preview.json()).error.code,
                         "REFERENCE_INVALID")
        # A create attempt refuses typed as well (the payload here is built
        # manually because the preview route itself is the refusal under test).
        payload = {"acknowledged_revision": shown["revision"],
                   "preview_sha256": shown["projection_sha256"],
                   "visible_scope": shown["scope"]}
        with self.as_session(self.alice_id):
            refused_create = self.client.post(
                f"/api/documents/{created.document.id}/shares",
                headers=self.bearer(self.alice_id), json=payload)
        self.assertEqual(refused_create.status_code, 422, refused_create.text)
        self.assertEqual(ErrorResponse.model_validate(refused_create.json()).error.code,
                         "REFERENCE_INVALID")

    def test_09_share_headers_and_no_caching_on_every_response(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "1.5")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        response = self.create_share(created.document.id)
        token = response.json()["share_token"]
        share_id = response.json()["id"]
        with self.as_session(self.alice_id):
            listing = self.client.get(f"/api/documents/{created.document.id}/shares",
                                      headers=self.bearer(self.alice_id))
            revoke = self.client.delete(
                f"/api/documents/{created.document.id}/shares/{share_id}",
                headers=self.bearer(self.alice_id))
        for item in (response, listing, revoke,
                     self.client.get(f"/api/shares/{token}"),
                     self.client.get(f"/api/shares/{token}x")):
            self.assertEqual(item.headers.get("Cache-Control"), "no-store")
            self.assertEqual(item.headers.get("Referrer-Policy"), "no-referrer")

    def test_10_migration_round_trip_and_mirror(self):
        command.downgrade(self.config, "0012_export_jobs")
        with self.admin.connect() as connection:
            missing = connection.execute(text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='app' AND table_name='document_shares'")).scalar_one()
        self.assertEqual(missing, 0)
        command.upgrade(self.config, "head")
        command.check(self.config)  # the SQLAlchemy mirror matches the migration
        with self.admin.connect() as connection:
            columns = {row["column_name"] for row in connection.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='app' AND table_name='document_shares'")).mappings()}
        self.assertEqual(columns, {
            "id", "owner_id", "document_id", "document_version_id", "token_hash",
            "status", "revision", "idempotency_key", "projection",
            "projection_sha256", "projection_byte_size", "expires_at",
            "created_at", "updated_at", "revoked_at"})


if __name__ == "__main__":
    unittest.main()
