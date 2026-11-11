"""NI-044 real PostgreSQL/RLS/API snapshot regressions. All identities/data synthetic."""

import datetime as dt
import json
import os
import unittest
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from near_api.auth.principal import Principal, get_principal
from near_api.charts.registry import RENDERER_VERSION, chart_by_chart_id
from near_api.db.session import user_transaction
from near_api.datasets import delivery
from near_api.main import app
import test_delivery_apis as fixtures
from test_delivery_apis import METRIC_VOLUME, observation


def without_request_id(body: bytes) -> str:
    """Strip the per-request id so two error envelopes compare by content."""
    document = json.loads(body)
    document.get("error", {}).pop("request_id", None)
    return json.dumps(document, sort_keys=True)


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use run-db-tests.py")
class SnapshotDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.DeliveryDatabaseTests.setUpClass.__func__(cls)
        cls.alice = Principal(uuid4(), "Synthetic Alice", "UTC")
        cls.bob = Principal(uuid4(), "Synthetic Bob", "UTC")
        with cls.admin.begin() as connection:
            for person in (cls.alice, cls.bob):
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"), {"id": person.id})

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_principal, None)
        fixtures.DeliveryDatabaseTests.tearDownClass.__func__(cls)

    def setUp(self):
        fixtures.DeliveryDatabaseTests.setUp(self)
        self.actor = self.alice
        app.dependency_overrides[get_principal] = lambda: self.actor
        self.client = TestClient(app, raise_server_exceptions=False)
        with self.admin.begin() as connection:
            connection.execute(text("DELETE FROM app.idempotency_records"))
            connection.execute(text("DELETE FROM app.saved_charts"))
            connection.execute(text("DELETE FROM app.research_snapshots"))
        self.dataset = fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni044.{uuid4().hex[:16]}",
            [observation(METRIC_VOLUME, dt.date(2026, 1, 1), value="123456789.123456789012345678901234",
                         dimensions={"source": "SRC-LLAMA"})], [METRIC_VOLUME],
            window=("2026-01-01", "2026-01-02"))
        self.definition_id = str(chart_by_chart_id("intents-volume").id)
        self.body = {
            "chart_definition_version_id": self.definition_id,
            "dataset_version_id": str(self.dataset.dataset_version_id),
            "selection": {"start": "2026-01-01", "end": "2026-01-02", "frequency": "day",
                          "filters": {"source": "SRC-LLAMA"}},
        }

    def freeze(self, body=None, key=None):
        response = self.client.post("/api/snapshots", json=body or self.body,
                                    headers={"Idempotency-Key": key} if key else {})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        return response.json()

    def test_freeze_list_read_delete_records_owner_scoped_storage_metadata(self):
        snapshot = self.freeze()
        self.assertRegex(snapshot["content_sha256"], r"^[0-9a-f]{64}$")
        self.assertIsNone(snapshot["artifact_id"])
        self.assertEqual(snapshot["calculation_context"]["renderer_version"], RENDERER_VERSION)
        self.assertEqual(snapshot["selection"], self.body["selection"])
        listing = self.client.get("/api/snapshots")
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(listing.headers["cache-control"], "no-store")
        self.assertEqual([item["id"] for item in listing.json()["items"]], [snapshot["id"]])
        detail = self.client.get("/api/snapshots/" + snapshot["id"])
        self.assertEqual(detail.status_code, 200, detail.text)
        document = detail.json()
        self.assertEqual(document["view"]["dataset"]["id"], str(self.dataset.dataset_version_id))
        self.assertEqual(document["view"]["series"][0]["points"][0]["value"],
                         "123456789.123456789012345678901234")
        self.assertEqual(document["snapshot"]["content_sha256"], snapshot["content_sha256"])
        self.assertEqual(document["snapshot"]["created_at"], snapshot["created_at"])
        removed = self.client.delete("/api/snapshots/" + snapshot["id"])
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(self.client.get("/api/snapshots/" + snapshot["id"]).status_code, 404)
        self.assertEqual(self.client.get("/api/snapshots").json(), {"items": [], "next_cursor": None})

    def test_freeze_regenerates_identical_hash_and_distinct_selections_differ(self):
        first = self.freeze()
        second = self.freeze()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["content_sha256"], second["content_sha256"])
        other = self.freeze({**self.body, "selection": {**self.body["selection"],
                                                        "filters": {"source": "SRC-DASHBOARD"}}})
        self.assertNotEqual(other["content_sha256"], first["content_sha256"])
        replay = self.freeze(key=str(uuid4()))
        again = self.freeze(key=str(uuid4()))
        self.assertEqual(again["content_sha256"], replay["content_sha256"])

    def test_frozen_view_survives_new_publication_and_compare_differs(self):
        snapshot = self.freeze()
        path = "/api/snapshots/" + snapshot["id"]
        before = self.client.get(path).json()
        replacement = fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni044.{uuid4().hex[:16]}",
            [observation(METRIC_VOLUME, dt.date(2026, 1, 1), value="999",
                         dimensions={"source": "SRC-LLAMA"})], [METRIC_VOLUME],
            window=("2026-01-01", "2026-01-02"))
        delivery.reset_delivery_caches()
        after = self.client.get(path).json()
        self.assertEqual(after["view"]["dataset"]["id"], str(self.dataset.dataset_version_id))
        self.assertEqual(after["view"]["series"][0]["points"][0]["value"],
                         before["view"]["series"][0]["points"][0]["value"])
        self.assertEqual(after["snapshot"], snapshot)
        comparison = self.client.get(path + "/compare-live")
        self.assertEqual(comparison.status_code, 200, comparison.text)
        document = comparison.json()
        self.assertEqual(document["frozen_view"]["dataset"]["id"], str(self.dataset.dataset_version_id))
        self.assertEqual(document["live_view"]["dataset"]["id"], str(replacement.dataset_version_id))
        self.assertTrue(document["dataset_changed"])
        self.assertEqual(document["frozen_view"]["series"][0]["points"][0]["value"],
                         "123456789.123456789012345678901234")
        self.assertEqual(document["live_view"]["series"][0]["points"][0]["value"], "999")
        # The explicit comparison never rewrote the frozen row or its view.
        self.assertEqual(self.client.get(path).json(), after)

    def test_bob_matrix_is_byte_equal_404_and_cannot_reference_or_cross_rls(self):
        snapshot = self.freeze()
        path = "/api/snapshots/" + snapshot["id"]
        self.actor = self.bob
        self.assertEqual(self.client.get("/api/snapshots").json(), {"items": [], "next_cursor": None})
        foreign = self.client.get(path)
        missing = self.client.get("/api/snapshots/" + str(uuid4()))
        for response in (foreign, missing,
                         self.client.get(path + "/compare-live"),
                         self.client.delete(path)):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(without_request_id(foreign.content), without_request_id(missing.content))
        # A foreign snapshot id is a typed 422 on save, never a dangling pin.
        saved_body = {"chart_definition_version_id": self.definition_id, "label": "Stolen",
                      "mode": "snapshot", "snapshot_id": snapshot["id"],
                      "dataset_version_id": str(self.dataset.dataset_version_id),
                      "selection": self.body["selection"]}
        response = self.client.post("/api/saved-charts", json=saved_body)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "REFERENCE_INVALID")
        # RLS: Bob sees no rows, cannot repoint ownership and cannot insert
        # a snapshot row claiming Alice's ownership.
        with user_transaction(self.runtime, self.bob.id) as connection:
            self.assertEqual(connection.execute(text(
                "SELECT count(*) FROM app.research_snapshots WHERE id=:id"),
                {"id": snapshot["id"]}).scalar_one(), 0)
        with self.assertRaises(DBAPIError):
            with user_transaction(self.runtime, self.bob.id) as connection:
                connection.execute(text(
                    "UPDATE app.research_snapshots SET owner_id=:owner WHERE id=:id"),
                    {"owner": self.bob.id, "id": snapshot["id"]})
        with self.assertRaises(DBAPIError):
            with user_transaction(self.runtime, self.bob.id) as connection:
                connection.execute(text(
                    "INSERT INTO app.research_snapshots(id, owner_id, chart_definition_version_id,"
                    " dataset_version_id, selection, calculation_context, content_sha256)"
                    " VALUES (:id, :owner, :definition, :dataset, CAST(:selection AS jsonb),"
                    " CAST(:context AS jsonb), :hash)"),
                    {"id": uuid4(), "owner": self.alice.id, "definition": self.definition_id,
                     "dataset": str(self.dataset.dataset_version_id),
                     "selection": json.dumps(self.body["selection"]),
                     "context": json.dumps({"context_hash": "0" * 64,
                                            "metric_definition_versions": [str(METRIC_VOLUME)],
                                            "renderer_version": RENDERER_VERSION}),
                     "hash": "0" * 64})

    def test_referenced_snapshot_cannot_disappear_service_409_and_db_restrict(self):
        snapshot = self.freeze()
        path = "/api/snapshots/" + snapshot["id"]
        saved = self.client.post("/api/saved-charts", json={
            "chart_definition_version_id": self.definition_id, "label": "Pinned evidence",
            "mode": "snapshot", "snapshot_id": snapshot["id"],
            "dataset_version_id": str(self.dataset.dataset_version_id),
            "selection": self.body["selection"]})
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json()["snapshot_id"], snapshot["id"])
        blocked = self.client.delete(path)
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(blocked.json()["error"]["code"], "REFERENCE_IN_USE")
        self.assertEqual(self.client.get(path).status_code, 200)
        # The database RESTRICT FK enforces the same outcome against a direct
        # runtime-role delete that bypasses the service check.
        with self.assertRaises(DBAPIError):
            with user_transaction(self.runtime, self.alice.id) as connection:
                connection.execute(text(
                    "DELETE FROM app.research_snapshots WHERE id=:id"), {"id": snapshot["id"]})
        self.assertEqual(self.client.delete("/api/saved-charts/" + saved.json()["id"]).status_code, 204)
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_snapshot_rows_are_immutable_against_every_runtime_write(self):
        snapshot = self.freeze()
        with self.assertRaises(DBAPIError):
            with user_transaction(self.runtime, self.alice.id) as connection:
                connection.execute(text(
                    "UPDATE app.research_snapshots SET content_sha256=:hash WHERE id=:id"),
                    {"hash": "f" * 64, "id": snapshot["id"]})
        self.assertEqual(self.client.get("/api/snapshots/" + snapshot["id"]).json()["snapshot"]
                         ["content_sha256"], snapshot["content_sha256"])

    def test_unapproved_dataset_unknown_definition_and_bad_selections_rejected(self):
        unpublished = fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni044.{uuid4().hex[:16]}",
            [observation(METRIC_VOLUME, dt.date(2026, 1, 1), value="5",
                         dimensions={"source": "SRC-LLAMA"})], [METRIC_VOLUME],
            window=("2026-01-01", "2026-01-02"), do_publish=False)
        for body in ({**self.body, "dataset_version_id": str(unpublished.dataset_version_id)},
                     {**self.body, "chart_definition_version_id": str(uuid4())},
                     {**self.body, "dataset_version_id": str(uuid4())},
                     {**self.body, "selection": {**self.body["selection"], "end": "2026-01-01"}},
                     {**self.body, "selection": {**self.body["selection"],
                                                 "filters": {"source": "unknown"}}}):
            response = self.client.post("/api/snapshots", json=body)
            self.assertIn(response.status_code, (404, 422), response.text)
        self.assertEqual(self.client.get("/api/snapshots").json(), {"items": [], "next_cursor": None})
