"""NI-035 real PostgreSQL/RLS/API regressions. All identities/data synthetic."""

import datetime as dt
import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from near_api.auth.principal import Principal, get_principal
from near_api.charts.registry import chart_by_chart_id
from near_api.db.session import user_transaction
from near_api.datasets import delivery
from near_api.main import app
import test_delivery_apis as fixtures
from test_delivery_apis import METRIC_VOLUME, observation


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use run-db-tests.py")
class SavedChartsDatabaseTests(unittest.TestCase):
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
        self.dataset = fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni035.{uuid4().hex[:16]}",
            [observation(METRIC_VOLUME, dt.date(2026, 1, 1), value="123456789.123456789012345678901234",
                         dimensions={"source": "SRC-LLAMA"})], [METRIC_VOLUME],
            window=("2026-01-01", "2026-01-02"))
        self.body = {
            "chart_definition_version_id": str(chart_by_chart_id("intents-volume").id),
            "label": "Synthetic saved volume", "mode": "live",
            "dataset_version_id": str(self.dataset.dataset_version_id),
            "selection": {"start": "2026-01-01", "end": "2026-01-02", "frequency": "day",
                          "filters": {"source": "SRC-LLAMA"}},
        }

    def create(self, body=None, key=None):
        response = self.client.post("/api/saved-charts", json=body or self.body,
                                    headers={"Idempotency-Key": key} if key else {})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        return response.json()

    def test_save_reopen_edit_delete_preserves_definition_and_exact_values(self):
        saved = self.create()
        path = "/api/saved-charts/" + saved["id"]
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        detail = response.json()
        self.assertEqual(detail["saved_chart"]["selection"], self.body["selection"])
        self.assertEqual(detail["view"]["series"][0]["points"][0]["value"],
                         "123456789.123456789012345678901234")
        self.assertFalse(detail["dataset_changed"])
        renamed = self.client.patch(path, json={"label": "Renamed"})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(self.client.get("/api/saved-charts", params={"q": "Renamed"}).json()["items"][0]["id"], saved["id"])
        self.assertEqual(self.client.patch(path, json={"label": None}).json()["label"], None)
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)
        with self.runtime.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT count(*) FROM app.chart_definitions WHERE id=:id"),
                                               {"id": self.body["chart_definition_version_id"]}).scalar_one(), 1)

    def test_bob_cannot_enumerate_read_mutate_or_use_alice_key(self):
        key = str(uuid4())
        saved = self.create(key=key)
        self.actor = self.bob
        listing = self.client.get("/api/saved-charts", params={"limit": 1})
        self.assertEqual(listing.json(), {"items": [], "next_cursor": None})
        path = "/api/saved-charts/" + saved["id"]
        for verb in ("get", "patch", "delete"):
            kwargs = {"json": {"label": "Stolen"}} if verb == "patch" else {}
            response = getattr(self.client, verb)(path, **kwargs)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.headers["cache-control"], "no-store")
        other = self.create(key=key)
        self.assertNotEqual(other["id"], saved["id"])
        with user_transaction(self.runtime, self.bob.id) as connection:
            self.assertEqual(connection.execute(text("SELECT count(*) FROM app.saved_charts WHERE id=:id"),
                                               {"id": saved["id"]}).scalar_one(), 0)
        with self.assertRaises(DBAPIError):
            with user_transaction(self.runtime, self.bob.id) as connection:
                connection.execute(text("UPDATE app.saved_charts SET owner_id=:owner WHERE id=:id"),
                                   {"owner": self.bob.id, "id": saved["id"]})

    def test_retry_replays_once_collision_is_409_and_owner_injection_rejected(self):
        key = str(uuid4())
        first = self.create(key=key)
        self.assertEqual(first, self.create(key=key))
        collision = self.client.post("/api/saved-charts", json={**self.body, "label": "Different"},
                                     headers={"Idempotency-Key": key})
        self.assertEqual(collision.status_code, 409)
        self.assertEqual(len(self.client.get("/api/saved-charts").json()["items"]), 1)
        for body in ({**self.body, "owner_id": str(self.bob.id)},
                     {**self.body, "selection": {**self.body["selection"], "end": "2026-01-01"}},
                     {**self.body, "selection": {**self.body["selection"], "filters": {"owner": "Bob"}}},
                     {**self.body, "mode": "snapshot", "snapshot_id": str(uuid4())}):
            response = self.client.post("/api/saved-charts", json=body)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.post("/api/saved-charts", json={**self.body,
                          "dataset_version_id": str(uuid4())}).status_code, 404)

    def test_explicit_context_edit_validates_and_reopens(self):
        saved = self.create()
        path = "/api/saved-charts/" + saved["id"]
        selection = {**self.body["selection"], "end": "2026-01-03"}
        response = self.client.patch(path, json={"selection": selection,
                                                "dataset_version_id": str(self.dataset.dataset_version_id)})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(path).json()["saved_chart"]["selection"], selection)
        for body in ({"mode": None}, {"selection": None}, {"dataset_version_id": None},
                     {"selection": {**selection, "filters": {"source": "unknown"}}}):
            self.assertEqual(self.client.patch(path, json=body).status_code, 422)
        self.assertEqual(self.client.get(path).json()["saved_chart"]["selection"], selection)

    def test_live_changed_badge_and_resolution_does_not_reorder_list(self):
        saved = self.create()
        path = "/api/saved-charts/" + saved["id"]
        replacement = fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni035.{uuid4().hex[:16]}",
            [observation(METRIC_VOLUME, dt.date(2026, 1, 1), value="999",
                         dimensions={"source": "SRC-LLAMA"})], [METRIC_VOLUME],
            window=("2026-01-01", "2026-01-02"))
        delivery.reset_delivery_caches()
        replacement_id = str(replacement.dataset_version_id)
        response = self.client.get(path, params={"preview": "true"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        preview = response.json()
        self.assertTrue(preview["dataset_changed"])
        self.assertEqual(preview["saved_chart"], saved)
        self.assertEqual(preview["view"]["dataset"]["id"], replacement_id)
        self.assertEqual(preview["view"]["series"][0]["points"][0]["value"], "999")
        self.assertEqual(self.client.get("/api/saved-charts").json()["items"], [saved])

        self.actor = self.bob
        forbidden = self.client.get(path, params={"preview": "true"})
        self.assertEqual(forbidden.status_code, 404, forbidden.text)
        self.assertEqual(forbidden.headers["cache-control"], "no-store")
        self.actor = self.alice

        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        detail = response.json()
        self.assertTrue(detail["dataset_changed"])
        self.assertEqual(detail["view"]["dataset"]["id"], replacement_id)
        self.assertEqual(detail["saved_chart"]["last_resolved_dataset_version_id"], replacement_id)
        self.assertEqual(detail["saved_chart"]["updated_at"], saved["updated_at"])
        self.assertEqual(detail["saved_chart"]["selection"], saved["selection"])
        self.assertFalse(self.client.get(path).json()["dataset_changed"])

    def test_ni071_multi_value_selection_round_trips_save_reopen_edit(self):
        """The compared selection persists byte-exactly and re-resolves."""
        from test_delivery_apis import METRIC_PAYOUTS, METRIC_PAYOUTS_V2, RECIPIENTS
        days = ("2026-01-01", "2026-01-02")
        observations = [
            fixtures.observation(METRIC_PAYOUTS, dt.date.fromisoformat(days[0]),
                                 value="5.5"),
            fixtures.observation(METRIC_PAYOUTS_V2, dt.date.fromisoformat(days[0]),
                                 value="3", dimensions={"recipient": RECIPIENTS[0]}),
            fixtures.observation(METRIC_PAYOUTS_V2, dt.date.fromisoformat(days[0]),
                                 value="2.5", dimensions={"recipient": RECIPIENTS[1]}),
            fixtures.observation(METRIC_PAYOUTS_V2, dt.date.fromisoformat(days[0]),
                                 value="0", dimensions={"recipient": RECIPIENTS[2]}),
            fixtures.observation(METRIC_PAYOUTS, dt.date.fromisoformat(days[1]),
                                 value="6"),
            fixtures.observation(METRIC_PAYOUTS_V2, dt.date.fromisoformat(days[1]),
                                 value="4", dimensions={"recipient": RECIPIENTS[0]}),
            fixtures.observation(METRIC_PAYOUTS_V2, dt.date.fromisoformat(days[1]),
                                 value="2", dimensions={"recipient": RECIPIENTS[1]}),
            fixtures.observation(METRIC_PAYOUTS_V2, dt.date.fromisoformat(days[1]),
                                 value="0", dimensions={"recipient": RECIPIENTS[2]}),
        ]
        dataset = fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni071.saved.{uuid4().hex[:16]}", observations,
            [METRIC_PAYOUTS, METRIC_PAYOUTS_V2], window=(days[0], "2026-01-03"))
        body = {
            "chart_definition_version_id": str(chart_by_chart_id("treasury-payouts").id),
            "label": "Compared payouts", "mode": "live",
            "dataset_version_id": str(dataset.dataset_version_id),
            "selection": {"start": days[0], "end": "2026-01-03", "frequency": "day",
                          "filters": {"recipient": [RECIPIENTS[2], RECIPIENTS[0]]}},
        }
        saved = self.create(body)
        self.assertEqual(saved["selection"]["filters"],
                         {"recipient": [RECIPIENTS[0], RECIPIENTS[2]]})
        path = "/api/saved-charts/" + saved["id"]
        detail = self.client.get(path).json()
        self.assertEqual(detail["saved_chart"]["selection"]["filters"],
                         {"recipient": [RECIPIENTS[0], RECIPIENTS[2]]})
        self.assertEqual(len(detail["view"]["series"]), 2)
        self.assertEqual([series["selection"]["filters"]["recipient"]
                          for series in detail["view"]["series"]],
                         [RECIPIENTS[0], RECIPIENTS[2]])
        self.assertEqual([point["value"] for point in detail["view"]["series"][0]["points"]],
                         ["3", "4"])
        snapshot = self.freeze({key: body[key] for key in (
            "chart_definition_version_id", "dataset_version_id", "selection")})
        self.assertEqual(snapshot["selection"], detail["view"]["selection"])
        self.assertEqual(snapshot["calculation_context"]["context_hash"],
                         detail["view"]["context_hash"])
        frozen = self.client.get("/api/snapshots/" + snapshot["id"])
        self.assertEqual(frozen.status_code, 200, frozen.text)
        self.assertEqual(frozen.json()["view"]["series"], detail["view"]["series"])
        # editing the selection to the full declared universe resolves three
        # compared series and persists the exact canonical multi-selection
        patched = self.client.patch(path, json={
            "selection": {**body["selection"],
                          "filters": {"recipient": list(RECIPIENTS)}}})
        self.assertEqual(patched.status_code, 200, patched.text)
        reopened = self.client.get(path).json()
        self.assertEqual(reopened["saved_chart"]["selection"]["filters"],
                         {"recipient": list(RECIPIENTS)})
        self.assertEqual(len(reopened["view"]["series"]), 3)
        # the frozen insight context carries the exact multi-selection too
        context = detail["view"]["selection"]
        self.assertEqual(context["filters"], {"recipient": [RECIPIENTS[0], RECIPIENTS[2]]})

    def freeze(self, body=None):
        """NI-044 helper: freeze one snapshot for the current actor."""
        snapshot_body = {
            "chart_definition_version_id": self.body["chart_definition_version_id"],
            "dataset_version_id": str(self.dataset.dataset_version_id),
            "selection": self.body["selection"],
        }
        response = self.client.post("/api/snapshots", json=body or snapshot_body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_snapshot_mode_save_reopen_keeps_frozen_evidence_and_validates_references(self):
        snapshot = self.freeze()
        pinned = self.create({**self.body, "mode": "snapshot", "snapshot_id": snapshot["id"]})
        self.assertEqual(pinned["mode"], "snapshot")
        self.assertEqual(pinned["snapshot_id"], snapshot["id"])
        path = "/api/saved-charts/" + pinned["id"]
        document = self.client.get(path).json()
        self.assertEqual(document["view"]["dataset"]["id"], snapshot["dataset_version_id"])
        self.assertFalse(document["dataset_changed"])
        # A later publication never moves a snapshot context off its pin.
        fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni035.{uuid4().hex[:16]}",
            [observation(METRIC_VOLUME, dt.date(2026, 1, 1), value="999",
                         dimensions={"source": "SRC-LLAMA"})], [METRIC_VOLUME],
            window=("2026-01-01", "2026-01-02"))
        delivery.reset_delivery_caches()
        response = self.client.get(path, params={"preview": "true"})
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        self.assertEqual(preview["saved_chart"], pinned)
        self.assertEqual(preview["view"]["dataset"]["id"], snapshot["dataset_version_id"])
        self.assertEqual(preview["view"]["series"][0]["points"][0]["value"],
                         "123456789.123456789012345678901234")
        self.assertFalse(preview["dataset_changed"])
        frozen = self.client.get(path).json()
        self.assertEqual(frozen["view"]["dataset"]["id"], snapshot["dataset_version_id"])
        self.assertFalse(frozen["dataset_changed"])
        # Invalid/foreign/absent references stay typed 422 REFERENCE_INVALID.
        for body in ({**self.body, "mode": "snapshot", "snapshot_id": str(uuid4())},
                     {**self.body, "mode": "snapshot", "snapshot_id": None},
                     {**self.body, "mode": "live", "snapshot_id": snapshot["id"]}):
            response = self.client.post("/api/saved-charts", json=body)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(response.json()["error"]["code"], "REFERENCE_INVALID")
        # Context edits must keep the frozen snapshot's dataset and selection.
        drifted = {**self.body["selection"], "end": "2026-01-03"}
        self.assertEqual(self.client.patch(path, json={"selection": drifted}).status_code, 422)
        self.assertEqual(self.client.patch(path, json={
            "dataset_version_id": str(uuid4())}).status_code, 422)
        self.assertEqual(self.client.get(path).json()["saved_chart"]["selection"], pinned["selection"])
        # An explicit un-pin returns the context to live resolution.
        released = self.client.patch(path, json={"mode": "live", "snapshot_id": None})
        self.assertEqual(released.status_code, 200, released.text)
        self.assertIsNone(released.json()["snapshot_id"])
        self.assertEqual(self.client.get(path).json()["dataset_changed"], True)

    def test_foreign_snapshot_reference_is_typed_422_never_a_dangling_pin(self):
        self.actor = self.bob
        snapshot = self.freeze()
        self.actor = self.alice
        response = self.client.post("/api/saved-charts", json={
            **self.body, "mode": "snapshot", "snapshot_id": snapshot["id"]})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "REFERENCE_INVALID")

    def test_unauthenticated_reads_stay_401_no_store(self):
        app.dependency_overrides.pop(get_principal)
        response = self.client.get("/api/saved-charts")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["cache-control"], "no-store")
