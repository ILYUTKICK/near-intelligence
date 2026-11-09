"""NI-047 HTTP and atomic revision checks on disposable PostgreSQL."""

import copy
import os
import unittest
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import text

from near_api.datasets import delivery
from near_api.db.security import principal_transaction
from near_api.documents import service as documents
from near_api.documents.schema import parse_document
import test_chart_blocks as chart_fixtures
import test_documents as document_fixtures


def insight_payload(context, **changes):
    return {
        "block_id": str(uuid4()), "type": "observation", "classification": "uncertain",
        "body": [document_fixtures.paragraph_node("Synthetic chart observation")],
        "context": context, **changes,
    }


def document_with(*nodes):
    return {"schema_version": 1, "type": "doc", "content": list(nodes)}


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class DocumentInsightDatabaseTests(chart_fixtures.ChartBlockDatabaseFixture, unittest.TestCase):
    def request(self, method, path, *, body=None, revision=None, key=None, subject=None, params=None):
        headers = {"Authorization": "Bearer synthetic"}
        if revision is not None:
            headers["If-Match"] = f'"{revision}"'
        if key is not None:
            headers["Idempotency-Key"] = str(key)
        with self.as_session(subject or self.alice_id):
            return self.client.request(method, path, json=body, params=params, headers=headers)

    def success(self, response, status):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        return response.json()

    def failure(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        error = response.json()["error"]
        self.assertEqual(error["code"], code, error)
        return error

    def save(self, path, revision, content):
        return self.request("POST", path + "/versions", revision=revision,
                            body={"schema_version": 1, "content": content})

    def counts(self, document_id, version_id):
        with principal_transaction(self.engine, self.alice) as connection:
            return connection.execute(text("""
                SELECT
                    (SELECT count(*) FROM app.document_versions WHERE document_id = :document),
                    (SELECT count(*) FROM app.document_blocks WHERE document_version_id = :version),
                    (SELECT count(*) FROM app.insights WHERE document_version_id = :version),
                    (SELECT count(*) FROM app.evidence_links WHERE document_version_id = :version)
            """), {"document": document_id, "version": version_id}).one()

    def test_anchored_create_edit_and_reopen_preserve_original_inspection(self):
        document_id = self.create_document(self.alice).document.id
        path = f"/api/documents/{document_id}"
        collection = path + "/insights"
        dataset_key = self.dataset_key("insight-publication")
        first = self.publish_volume(dataset_key, "12.123456789012345678901234")
        inspected = self.preview_volume(document_id, dataset_version=first.dataset_version_id)
        original = chart_fixtures.observed_context(inspected)
        block_id, document = self.chart_document(inspected)
        hypothesis = document_fixtures.hypothesis_attrs()
        document["content"].append(hypothesis)
        self.success(self.save(path, 1, document), 201)

        # An actual publication advances latest between inspection and note creation.
        second = self.publish_volume(dataset_key, "222")
        latest = self.preview_volume(document_id)
        self.assertEqual(latest["dataset"]["id"], str(second.dataset_version_id))
        self.assertNotEqual(original["context_hash"], latest["context_hash"])
        body = insight_payload(original, after_block_id=block_id,
                               hypothesis_id=hypothesis["attrs"]["hypothesis_id"])
        key = uuid4()
        before = datetime.now(UTC)
        with patch.object(delivery, "resolve_latest_version", side_effect=AssertionError("latest queried")):
            created_response = self.request("POST", collection, body=body, revision=2, key=key)
        created = self.success(created_response, 201)
        self.assertEqual(created_response.headers["ETag"], '"3"')
        self.assertEqual(created["version"]["id"], created["document"]["current_version_id"])
        value = created["value"]
        self.assertEqual({**value["context"], "resolved_at": original["resolved_at"]}, original)
        self.assertEqual(value["authored_at"], value["modified_at"])
        self.assertGreaterEqual(datetime.fromisoformat(value["authored_at"]), before)
        self.assertEqual(value["block_id"], body["block_id"])
        self.assertEqual(value["hypothesis_id"], body["hypothesis_id"])
        saved_nodes = created["version"]["content"]["content"]
        self.assertEqual([node["type"] for node in saved_nodes], ["liveChart", "insight", "hypothesis"])
        self.assertEqual(saved_nodes[1]["attrs"]["insight_id"], value["id"])
        self.assertEqual(saved_nodes[1]["attrs"]["context"], value["context"])
        self.assertEqual(self.counts(document_id, created["version"]["id"]), (3, 3, 1, 0))

        # Explicitly refresh the working chart, then edit the insight's prose and link.
        refreshed = copy.deepcopy(created["version"]["content"])
        refreshed["content"][0]["attrs"]["observed_dataset_version_id"] = str(second.dataset_version_id)
        refreshed_version = self.success(self.save(path, 3, refreshed), 201)["version"]
        self.assertEqual(refreshed_version["resolved_contexts"][block_id]["dataset_version_id"],
                         str(second.dataset_version_id))
        item = f"{collection}/{value['id']}"
        edit = {"body": [document_fixtures.paragraph_node("Edited synthetic observation")],
                "classification": "contradicting", "hypothesis_id": None}
        edit_key = uuid4()
        with patch.object(delivery, "resolve_latest_version", side_effect=AssertionError("latest queried")):
            patched = self.success(self.request("PATCH", item, body=edit, revision=4, key=edit_key), 200)
        self.assertEqual(patched["value"]["context"], value["context"])
        self.assertEqual(patched["value"]["authored_at"], value["authored_at"])
        self.assertGreater(datetime.fromisoformat(patched["value"]["modified_at"]),
                           datetime.fromisoformat(value["modified_at"]))
        self.assertIsNone(patched["value"]["hypothesis_id"])
        self.assertEqual(patched["value"]["block_id"], value["block_id"])
        self.assertEqual(patched["value"]["id"], value["id"])
        self.assertEqual(self.success(self.request("PATCH", item, body=edit, revision=4, key=edit_key), 200),
                         patched)
        self.failure(self.request("PATCH", item, body={"classification": "supporting"},
                                  revision=5, key=edit_key), 409, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.success(self.request("POST", collection, body=body, revision=2, key=key), 201),
                         created)
        self.assertEqual(self.success(self.request("GET", collection), 200), [patched["value"]])
        reopened = self.success(self.request("GET", path), 200)
        self.assertEqual(reopened["content"], patched["version"]["content"])
        historical = self.success(self.request(
            "GET", collection, params={"version_id": created["version"]["id"]}), 200)
        self.assertEqual(historical, [value])
        replacement = self.success(self.request(
            "PATCH", item, body={"context": chart_fixtures.observed_context(latest)}, revision=5), 200)
        self.assertEqual(replacement["value"]["context"]["dataset_version_id"], str(second.dataset_version_id))
        self.assertEqual(replacement["value"]["authored_at"], value["authored_at"])
        self.assertEqual(self.success(self.request(
            "GET", collection, params={"version_id": created["version"]["id"]}), 200), [value])

    def test_owner_scope_and_same_revision_anchor_and_hypothesis(self):
        alice_document = self.create_document(self.alice)
        bob_document = self.create_document(self.bob)
        alice_path = f"/api/documents/{alice_document.document.id}"
        alice_collection = alice_path + "/insights"
        bob_collection = f"/api/documents/{bob_document.document.id}/insights"
        dataset = self.publish_volume(self.dataset_key("insight-ownership"), "42")
        context = chart_fixtures.volume_context(self.operator, dataset.dataset_version_id)
        hypothesis = document_fixtures.hypothesis_attrs()
        self.success(self.save(alice_path, 1, document_with(hypothesis)), 201)
        key = uuid4()
        body = insight_payload(context)
        created = self.success(self.request("POST", alice_collection, body=body, revision=2, key=key), 201)
        value = created["value"]
        self.assertEqual([node["type"] for node in created["version"]["content"]["content"]],
                         ["hypothesis", "insight"])

        missing = self.failure(self.request(
            "GET", f"/api/documents/{uuid4()}/insights", subject=self.bob_id), 404, "NOT_FOUND")
        for method, path, payload in (
            ("GET", alice_collection, None),
            ("POST", alice_collection, body),
            ("PATCH", f"{alice_collection}/{value['id']}", {"classification": "supporting"}),
            ("DELETE", f"{alice_collection}/{value['id']}", {"remove_evidence_links": True}),
            ("PATCH", f"{bob_collection}/{value['id']}", {"classification": "supporting"}),
            ("DELETE", f"{bob_collection}/{value['id']}", {"remove_evidence_links": True}),
        ):
            with self.subTest(method=method, path=path):
                error = self.failure(self.request(method, path, body=payload, revision=1,
                                                  key=key, subject=self.bob_id), 404, "NOT_FOUND")
                self.assertEqual(error["message"], missing["message"])
                self.assertNotIn("details", error)
        self.failure(self.request("GET", bob_collection, subject=self.bob_id,
                                  params={"version_id": created["version"]["id"]}), 404, "NOT_FOUND")
        for field in ("after_block_id", "hypothesis_id"):
            foreign_id = hypothesis["attrs"][field.removeprefix("after_")]
            self.failure(self.request("POST", bob_collection, revision=1, subject=self.bob_id,
                                      body=insight_payload(context, **{field: foreign_id})),
                         422, "REFERENCE_INVALID")
        self.assertEqual(self.success(self.request("GET", bob_collection, subject=self.bob_id), 200), [])
        with principal_transaction(self.engine, self.bob) as connection:
            self.assertEqual(connection.scalar(text(
                "SELECT count(*) FROM app.insights WHERE document_id = :id"),
                {"id": alice_document.document.id}), 0)

    def test_bad_pins_and_precondition_leave_the_revision_unchanged(self):
        document_id = self.create_document(self.alice).document.id
        path = f"/api/documents/{document_id}"
        collection = path + "/insights"
        first = self.publish_volume(self.dataset_key("insight-invalid"), "8")
        inspected = self.preview_volume(document_id, dataset_version=first.dataset_version_id)
        original = chart_fixtures.observed_context(inspected)
        block_id, document = self.chart_document(inspected)
        saved = self.success(self.save(path, 1, document), 201)["version"]
        staged = self.insert_dataset_version(self.dataset_key("staged-insight"), status="staged")
        incompatible = self.insert_dataset_version(self.dataset_key("incompatible-insight"),
                                                   with_metric=False, with_observation=False)
        for context in (
            {**original, "chart_definition_version_id": str(uuid4())},
            {**original, "dataset_version_id": str(uuid4())},
            {**original, "context_hash": "0" * 64},
            {**original, "renderer_version": "wrong-renderer"},
            {**original, "metric_definition_versions": [str(uuid4())]},
            chart_fixtures.volume_context(self.operator, staged),
            chart_fixtures.volume_context(self.operator, incompatible),
        ):
            with self.subTest(context=context):
                self.failure(self.request("POST", collection, body=insight_payload(context), revision=2),
                             422, "REFERENCE_INVALID")
        wrong_selection = {**original["selection"], "filters": {"source": "unsupported"}}
        self.failure(self.request("POST", collection, revision=2,
                                  body=insight_payload({**original, "selection": wrong_selection})),
                     422, "FILTER_UNSUPPORTED")
        valid_other_selection = chart_fixtures.volume_context(self.operator, first.dataset_version_id)
        mismatch = self.failure(self.request(
            "POST", collection, revision=2, body=insight_payload(valid_other_selection, after_block_id=block_id)),
            422, "REFERENCE_INVALID")
        self.assertEqual(mismatch["details"], [{"path": "after_block_id", "reason": "chart_anchor_context_mismatch"}])
        conversion = self.failure(self.request(
            "POST", collection, revision=2, body=insight_payload(valid_other_selection, block_id=block_id)),
            422, "REFERENCE_INVALID")
        self.assertEqual(conversion["details"], [{"path": "block_id", "reason": "chart_anchor_context_mismatch"}])
        for field in ("authored_at", "modified_at", "owner_id"):
            self.failure(self.request("POST", collection, revision=2,
                                      body=insight_payload(original, **{field: "forged"})),
                         422, "VALIDATION_ERROR")
        self.failure(self.request("POST", collection, body=insight_payload(original)),
                     428, "PRECONDITION_REQUIRED")
        self.failure(self.request("POST", collection, body=insight_payload(original), revision=1),
                     409, "REVISION_CONFLICT")
        self.assertEqual(self.counts(document_id, saved["id"]), (2, 1, 0, 0))

        raw = document_with(document_fixtures.insight_attrs(context={**original, "context_hash": "0" * 64}))
        self.failure(self.save(path, 2, raw), 422, "REFERENCE_INVALID")
        key = uuid4()
        with patch.object(documents, "write_projections", side_effect=RuntimeError("synthetic projection failure")):
            self.failure(self.request("POST", collection, body=insight_payload(original), revision=2, key=key),
                         500, "INTERNAL_ERROR")
        self.assertEqual(self.counts(document_id, saved["id"]), (2, 1, 0, 0))
        self.success(self.request("POST", collection, body=insight_payload(original), revision=2, key=key), 201)
        converted = self.success(self.request(
            "POST", collection, body=insight_payload(original, block_id=block_id), revision=3), 201)
        self.assertEqual(converted["value"]["block_id"], block_id)
        self.assertEqual([node["type"] for node in converted["version"]["content"]["content"]],
                         ["insight", "insight"])

    def test_delete_requires_explicit_cleanup_and_keeps_historical_evidence(self):
        document_id = self.create_document(self.alice).document.id
        path = f"/api/documents/{document_id}"
        collection = path + "/insights"
        dataset = self.publish_volume(self.dataset_key("insight-cleanup"), "7")
        context = chart_fixtures.volume_context(self.operator, dataset.dataset_version_id)
        first = self.success(self.request("POST", collection, body=insight_payload(context), revision=1), 201)
        second = self.success(self.request("POST", collection, body=insight_payload(context), revision=2), 201)
        hypothesis = document_fixtures.hypothesis_attrs()
        hypothesis_id = hypothesis["attrs"]["hypothesis_id"]
        evidence = [
            document_fixtures.evidence_attrs(hypothesis_id, "insight", first["value"]["id"]),
            document_fixtures.evidence_attrs(hypothesis_id, "insight", first["value"]["id"]),
            document_fixtures.evidence_attrs(hypothesis_id, "insight", second["value"]["id"]),
        ]
        linked = self.success(self.save(
            path, 3, document_with(*second["version"]["content"]["content"], hypothesis, *evidence)),
            201)["version"]
        self.assertEqual(self.counts(document_id, linked["id"]), (4, 6, 2, 3))
        item = f"{collection}/{first['value']['id']}"
        key = uuid4()
        self.failure(self.request("DELETE", item, body={"remove_evidence_links": True}, revision=3),
                     409, "REVISION_CONFLICT")
        conflict = self.failure(self.request(
            "DELETE", item, body={"remove_evidence_links": False}, revision=4, key=key),
            409, "REFERENCE_IN_USE")
        self.assertEqual(conflict["details"], [{"path": "remove_evidence_links", "reason": "linked_evidence:2"}])
        self.assertEqual(self.counts(document_id, linked["id"]), (4, 6, 2, 3))
        cleanup = {"remove_evidence_links": True}
        response = self.request("DELETE", item, body=cleanup, revision=4, key=key)
        removed = self.success(response, 200)
        self.assertEqual(response.headers["ETag"], '"5"')
        self.assertEqual(removed["value"], {"deleted_id": first["value"]["id"]})
        self.assertEqual(self.counts(document_id, removed["version"]["id"]), (5, 3, 1, 1))
        self.assertEqual(self.counts(document_id, linked["id"]), (5, 6, 2, 3))
        self.assertEqual(self.success(self.request("DELETE", item, body=cleanup, revision=4, key=key), 200),
                         removed)
        self.failure(self.request("DELETE", item, body=cleanup, revision=5), 404, "NOT_FOUND")
        self.assertEqual(self.success(self.request("GET", collection), 200), [second["value"]])
        self.assertEqual(self.success(self.request(
            "GET", collection, params={"version_id": linked["id"]}), 200),
            [first["value"], second["value"]])
        kept_evidence = removed["version"]["content"]["content"][-1]["attrs"]
        self.assertEqual(kept_evidence["evidence_id"], evidence[-1]["attrs"]["evidence_id"])

    def test_legacy_contexts_and_authoritative_pins_survive_generic_saves(self):
        document_id = self.create_document(self.alice).document.id
        path = f"/api/documents/{document_id}"
        collection = path + "/insights"
        legacy = document_fixtures.insight_attrs()
        legacy_model = document_fixtures.insight_attrs(context={
            "model_run_id": str(uuid4()), "dataset_version_id": str(uuid4()),
            "specification_version": "legacy-1", "context_hash": "a" * 64,
        })
        with principal_transaction(self.engine, self.alice) as connection:
            row, _ = documents.lock_current_revision(connection, self.alice, document_id, expected_revision=1)
            previous = documents._commit_new_revision(
                connection, self.alice, row, canonical=parse_document(document_with(legacy, legacy_model)),
                resolved_contexts={})
        historical = self.success(self.request("GET", collection), 200)
        self.assertEqual(len(historical), 2)
        moved = copy.deepcopy(previous.content)
        moved["content"].reverse()
        saved = self.success(self.save(path, 2, moved), 201)
        self.assertEqual(saved["version"]["content"], moved)
        self.assertEqual(self.success(self.request("GET", collection), 200), historical[::-1])

        dataset = self.publish_volume(self.dataset_key("insight-duplicate"), "15")
        context = chart_fixtures.volume_context(self.operator, dataset.dataset_version_id)
        created = self.success(self.request("POST", collection, body=insight_payload(context), revision=3), 201)
        pending = copy.deepcopy(created["version"]["content"])
        duplicate = copy.deepcopy(pending["content"][-1])
        duplicate["attrs"].update(insight_id=str(uuid4()), block_id=str(uuid4()))
        pending["content"].append(duplicate)
        duplicated = self.success(self.save(path, 4, pending), 201)
        authoritative = duplicated["version"]["content"]["content"][-1]["attrs"]
        self.assertNotEqual(authoritative["context"]["resolved_at"], duplicate["attrs"]["context"]["resolved_at"])
        self.assertNotEqual(authoritative["authored_at"], duplicate["attrs"]["authored_at"])

        # The editor's ordinary save acknowledges the revision without replacing its
        # local JSON. A following prose save may send the pre-acknowledgement time.
        pending["content"].append(chart_fixtures.text_paragraph("Synthetic follow-up prose"))
        following = self.success(self.save(path, 5, pending), 201)
        self.assertEqual(following["version"]["content"]["content"][-2]["attrs"], authoritative)
        forged = copy.deepcopy(following["version"]["content"])
        forged["content"][-2]["attrs"]["context"]["context_hash"] = "0" * 64
        rejected = self.failure(self.save(path, 6, forged), 422, "REFERENCE_INVALID")
        self.assertEqual(rejected["details"], [{"path": "context", "reason": "insight_context_immutable"}])
        self.assertEqual(self.success(self.request(
            "GET", collection, params={"version_id": str(previous.version.id)}), 200), historical)
