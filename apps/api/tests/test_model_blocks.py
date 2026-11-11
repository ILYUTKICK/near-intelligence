"""NI-055 model-result block tests: pinned published runs, editable prose.

Offline classes run everywhere (request/route contract); the database class
needs scripts/run-db-tests.py — a skip is never successful integration
evidence. Covered guarantees:

- one confirmation appends exactly ONE valid modelResult block as ONE new
  revision through the canonical flow (projections included);
- the block stores ids + interpretation ONLY: no statistical value can enter
  the document through the insertion contract;
- the pins are server verified inside the transaction: an unknown or
  non-published run and an unapproved dataset version are typed 422s that
  leave zero rows;
- ownership is the verified principal's (Alice/Bob matrix at HTTP level);
- duplicate retries with an Idempotency-Key replay the original result and
  the same key with a different body is a typed 409;
- the frozen ModelContext survives interpretation edits verbatim (editing
  the prose can never change the pinned result) and a changed data pointer
  freezes a NEW context — the previous revision keeps the original context
  byte-identically (no refit, no silent re-pointing);
- a newer dataset publication never re-points an already-inserted block.

The published run is the synthetic NI-054 bundle (content-derived run_id,
idempotent publication — order-independent with the NI-054/NI-056 suites);
every dataset, document and identity is a synthetic fixture — no research
data, no provider access.
"""

import copy
import json
import os
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from near_api.db.session import user_transaction
from near_api.documents.context_resolver import model_context_hash
from near_api.documents.schema import canonical_context_json, parse_document
from near_api.insights.schemas import ModelContext
from near_api.main import app
from near_api.schemas.common import ErrorResponse
from near_api.schemas.model_blocks import ModelBlockInsertRequest
import test_chart_blocks as chart_fixtures
from test_models_publication import (
    MANIFEST_KEYS,
    bundle_dir,
    canonical_artifact_hash,
    derive_run_id,
    valid_bundle,
)

SHA256 = "a" * 64


def interpretation_paragraph(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def insert_model_payload(run_id, **changes) -> dict:
    payload = {
        "model_run_id": str(run_id),
        "dataset_version_id": str(uuid4()),
        "interpretation": [interpretation_paragraph("Recorded result interpretation.")],
    }
    payload.update(changes)
    return payload


class ModelBlockContractTests(unittest.TestCase):
    """Offline request/route contract: no database required."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_01_request_contract_rejects_statistical_values_and_bad_bodies(self):
        run_id = str(uuid4())
        dataset_id = str(uuid4())
        valid = insert_model_payload(run_id, dataset_version_id=dataset_id)
        validated = ModelBlockInsertRequest.model_validate(valid)
        # The canonical interpretation normalization is deterministic.
        self.assertEqual(validated.model_dump(mode="json")["interpretation"],
                         [{"type": "paragraph", "content": [
                             {"type": "text", "text": "Recorded result interpretation.",
                              "marks": []}]}])
        cases = {
            "coefficients": {"coefficients": [{"name": "const", "estimate": 1.0}]},
            "estimate": {"estimate": 0.5},
            "diagnostics": {"diagnostics": {"stationarity": {}}},
            "context": {"context": {"model_run_id": run_id}},
            "block_id": {"block_id": str(uuid4())},
            "owner_id": {"owner_id": str(uuid4())},
        }
        for name, extra in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(Exception):
                    ModelBlockInsertRequest.model_validate({**valid, **extra})
        bad_bodies = {
            "empty_interpretation": {"interpretation": []},
            "missing_run": {"model_run_id": None},
            "bad_run": {"model_run_id": "not-a-uuid"},
            "bad_dataset": {"dataset_version_id": "42"},
            "bad_mark": {"interpretation": [{"type": "paragraph", "content": [
                {"type": "text", "text": "x", "marks": [{"type": "underline"}]}]}]},
        }
        for name, change in bad_bodies.items():
            with self.subTest(case=name):
                with self.assertRaises(Exception):
                    ModelBlockInsertRequest.model_validate({**valid, **change})

    def test_02_insertion_route_requires_a_verified_session(self):
        response = self.client.post(
            f"/api/documents/{uuid4()}/model-blocks",
            json=insert_model_payload(str(uuid4())))
        self.assertEqual(response.status_code, 401)
        failure = ErrorResponse.model_validate(response.json())
        self.assertEqual(failure.error.code, "AUTHENTICATION_REQUIRED")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_03_model_block_route_is_a_single_cas_post(self):
        paths = app.openapi()["paths"]
        operation = paths["/api/documents/{document_id}/model-blocks"]["post"]
        self.assertEqual(operation["operationId"], "addModelBlock")
        self.assertIn("409", operation["responses"])
        self.assertIn("428", operation["responses"])
        self.assertIn("422", operation["responses"])
        self.assertNotIn("get", paths["/api/documents/{document_id}/model-blocks"])


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ModelBlockDatabaseTests(chart_fixtures.ChartBlockDatabaseFixture,
                              unittest.TestCase):
    """Insertion guarantees on the disposable PostgreSQL cluster."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.publish_synthetic_model_run()

    @classmethod
    def publish_synthetic_model_run(cls):
        """One published model run from the synthetic NI-054 bundle.

        Publication is content-derived and idempotent: the identical bundle
        the NI-054/NI-056 suites publish maps to the same run_id, so the
        suite order inside the shared disposable cluster never duplicates
        the row.
        """
        from near_api.research.publication import load_bundle, verify_bundle
        from near_api.research.publish_store import publish_run

        directory = Path(os.environ["NI_TEST_TMP_DIR"]) / "ni055-bundle"
        directory.mkdir(parents=True, exist_ok=True)
        cls.bundle_path = bundle_dir(directory, valid_bundle())
        bundle = load_bundle(cls.bundle_path)
        report = verify_bundle(bundle)
        cls.assertTrue(report.passed, "the synthetic bundle must pass the gate")
        hashes = {key: canonical_artifact_hash(json.loads(
            (cls.bundle_path / f"{key}.json").read_text("utf-8")))
            for key in MANIFEST_KEYS}
        cls.run_id = derive_run_id(hashes)
        publish_run(os.environ["NI_TEST_OPERATOR_URL"], bundle, cls.run_id)

    def add_model(self, document_id, payload, *, revision: int = 1,
                  subject_id=None, key=None):
        subject = subject_id or self.alice_id
        headers = {"Authorization": f"Bearer t.{subject}", "If-Match": f'"{revision}"'}
        if key is not None:
            headers["Idempotency-Key"] = key
        with self.as_session(subject):
            return self.client.post(f"/api/documents/{document_id}/model-blocks",
                                    json=payload, headers=headers)

    def model_block(self, saved_content: dict) -> dict:
        return next(node for node in saved_content["content"]
                    if node["type"] == "modelResult")

    # -- insertion ------------------------------------------------------------- #

    def test_01_one_confirmation_appends_one_valid_model_block(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("model-interp"))
        payload = insert_model_payload(self.run_id, dataset_version_id=str(dataset_id))
        response = self.add_model(detail.document.id, payload)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["ETag"], '"2"')
        body = response.json()
        self.assertEqual(body["document"]["revision"], 2)
        block_id = body["value"]["block_id"]

        stored = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(stored["revision"], 2)
        parsed = parse_document(stored["content"])
        self.assertEqual([item.block_type for item in parsed.blocks], ["modelResult"])
        model = parsed.model_results[0]
        self.assertEqual(str(model.block_id), block_id)
        self.assertEqual(str(model.model_run_id), str(self.run_id))
        self.assertEqual(str(model.dataset_version_id), str(dataset_id))
        # The document JSON carries NO statistical value: only ids + prose.
        attrs = self.model_block(stored["content"])["attrs"]
        self.assertEqual(sorted(attrs), ["block_id", "dataset_version_id",
                                         "interpretation", "model_run_id"])
        # One frozen ModelContext keyed by the server-allocated block id.
        contexts = stored["resolved_contexts"]
        self.assertEqual(sorted(contexts), [block_id])
        canonical_context_json(contexts[block_id], path="resolved_contexts")
        context = ModelContext.model_validate(contexts[block_id])
        self.assertEqual(str(context.model_run_id), str(self.run_id))
        self.assertEqual(str(context.dataset_version_id), str(dataset_id))
        self.assertEqual(context.specification_version, "gross_fee_activity_v1@1")
        self.assertEqual(context.context_hash, model_context_hash(
            model.model_run_id, model.dataset_version_id, "gross_fee_activity_v1@1"))
        # Exactly one new revision with one projection row; the old revision
        # (the empty document) is byte-for-byte intact.
        counts = self.table_counts(detail.document.id)
        self.assertEqual(counts, {"document_versions": 2, "document_blocks": 1})
        with user_transaction(self.engine, self.alice_id) as connection:
            rows = connection.execute(text("""
                SELECT revision, content FROM app.document_versions
                WHERE document_id = :id ORDER BY revision
            """), {"id": detail.document.id}).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], {"schema_version": 1, "type": "doc", "content": []})
        self.assertEqual(rows[1][0], 2)

    def test_02_owner_validated_between_alice_and_bob(self):
        alice_document = self.create_document(self.alice).document.id
        dataset_id = self.insert_dataset_version(self.dataset_key("model-owner"))
        # Bob sees Alice's document as absent and cannot append to it.
        response = self.add_model(alice_document,
                                  insert_model_payload(self.run_id,
                                                       dataset_version_id=str(dataset_id)),
                                  subject_id=self.bob_id)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ErrorResponse.model_validate(response.json()).error.code,
                         "NOT_FOUND")
        self.assertEqual(self.table_counts(alice_document),
                         {"document_versions": 1, "document_blocks": 0})
        # Knowing the reference ids grants nothing: the run and dataset are
        # public scientific data, the DOCUMENT ownership is the gate. Bob
        # appends to his own document with the same ids.
        bob_document = self.create_document(self.bob).document.id
        own = self.add_model(bob_document,
                             insert_model_payload(self.run_id,
                                                  dataset_version_id=str(dataset_id)),
                             subject_id=self.bob_id)
        self.assertEqual(own.status_code, 201, own.text)
        # And Alice cannot read Bob's document afterwards.
        with self.as_session(self.alice_id):
            leaked = self.client.get(f"/api/documents/{bob_document}",
                                     headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(leaked.status_code, 404)

    def test_03_reference_failures_are_typed_and_leave_zero_rows(self):
        detail = self.create_document(self.alice)
        staged = self.insert_dataset_version(self.dataset_key("model-staged"),
                                             status="staged")
        unknown_dataset = self.insert_dataset_version(self.dataset_key("model-unknown"))
        cases = (
            ("unknown run id",
             insert_model_payload(str(uuid4()), dataset_version_id=str(unknown_dataset)),
             "dangling_model_run_reference"),
            ("non-published run identity",
             insert_model_payload(str(self.run_id).replace("a", "b", 1),
                                  dataset_version_id=str(unknown_dataset)),
             "dangling_model_run_reference"),
            ("staged dataset is not public",
             insert_model_payload(self.run_id, dataset_version_id=str(staged)),
             "dangling_dataset_reference"),
            ("unknown dataset version",
             insert_model_payload(self.run_id, dataset_version_id=str(uuid4())),
             "dangling_dataset_reference"),
            ("dangling insertion anchor",
             insert_model_payload(self.run_id,
                                  dataset_version_id=str(unknown_dataset),
                                  after_block_id=str(uuid4())),
             "dangling_after_block_reference"),
        )
        for name, payload, reason in cases:
            with self.subTest(case=name):
                response = self.add_model(detail.document.id, payload)
                self.assertEqual(response.status_code, 422, response.text)
                error = ErrorResponse.model_validate(response.json()).error
                self.assertEqual(error.code, "REFERENCE_INVALID")
                self.assertIn(reason,
                              str([item.reason for item in (error.details or ())]))
                self.assertEqual(self.table_counts(detail.document.id),
                                 {"document_versions": 1, "document_blocks": 0})

    def test_04_cas_conflict_and_idempotent_replay(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("model-replay"))
        payload = insert_model_payload(self.run_id, dataset_version_id=str(dataset_id))
        key = str(uuid4())
        first = self.add_model(detail.document.id, payload, key=key)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.headers["ETag"], '"2"')
        # Timeout-after-commit retry: the identical request replays the
        # ORIGINAL 201 — same revision, no second block.
        retry = self.add_model(detail.document.id, payload, key=key)
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(retry.json(), first.json())
        self.assertEqual(retry.headers["ETag"], '"2"')
        self.assertEqual(self.table_counts(detail.document.id),
                         {"document_versions": 2, "document_blocks": 1})
        # The same key with a different body is a collision, not a replay.
        conflict = self.add_model(detail.document.id,
                                  insert_model_payload(self.run_id,
                                                       dataset_version_id=str(uuid4())),
                                  key=key)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(ErrorResponse.model_validate(conflict.json()).error.code,
                         "IDEMPOTENCY_CONFLICT")
        # A stale If-Match without a replayable key is the honest 409 with
        # the current revision for the owner.
        stale = self.add_model(detail.document.id, payload, revision=1,
                               key=str(uuid4()))
        self.assertEqual(stale.status_code, 409)
        error = ErrorResponse.model_validate(stale.json()).error
        self.assertEqual(error.code, "REVISION_CONFLICT")
        self.assertIn("current_revision:2",
                      str([item.reason for item in (error.details or ())]))
        # A failed attempt stores nothing and the key stays retryable.
        failed_key = str(uuid4())
        failed = self.add_model(detail.document.id,
                                insert_model_payload(str(uuid4()),
                                                     dataset_version_id=str(dataset_id)),
                                revision=2, key=failed_key)
        self.assertEqual(failed.status_code, 422)
        recovered = self.add_model(detail.document.id, payload, revision=2,
                                   key=failed_key)
        self.assertEqual(recovered.status_code, 201, recovered.text)
        self.assertEqual(recovered.headers["ETag"], '"3"')
        self.assertEqual(self.table_counts(detail.document.id),
                         {"document_versions": 3, "document_blocks": 3})

    def test_05_interpretation_edit_keeps_context_and_pointer_change_freezes_new(self):
        detail = self.create_document(self.alice)
        dataset_v1 = self.insert_dataset_version(self.dataset_key("model-pointer"),
                                                 version=1)
        payload = insert_model_payload(self.run_id,
                                       dataset_version_id=str(dataset_v1))
        first = self.add_model(detail.document.id, payload)
        self.assertEqual(first.status_code, 201, first.text)
        block_id = first.json()["value"]["block_id"]
        original = self.stored_document(self.alice, detail.document.id)
        context_v1 = original["resolved_contexts"][block_id]

        # Edit ONLY the interpretation prose (revision 3): the frozen context
        # carries over VERBATIM — editing prose can never change the result.
        edited = copy.deepcopy(original["content"])
        self.model_block(edited)["attrs"]["interpretation"] = [
            interpretation_paragraph("Edited prose; same pinned run.")]
        prose_edit = self.save_document(detail.document.id, edited, revision=2)
        self.assertEqual(prose_edit.status_code, 200, prose_edit.text)
        after_prose = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(after_prose["revision"], 3)
        self.assertEqual(after_prose["resolved_contexts"][block_id], context_v1)

        # A newer approved dataset publication does NOT re-point the block:
        # one more prose-only save still carries the original context.
        dataset_v2 = self.insert_dataset_version(self.dataset_key("model-pointer"),
                                                 version=2)
        self.assertNotEqual(dataset_v2, dataset_v1)
        second_edit = copy.deepcopy(after_prose["content"])
        self.model_block(second_edit)["attrs"]["interpretation"] = [
            interpretation_paragraph("Edited prose again; still the same pin.")]
        untouched = self.save_document(detail.document.id, second_edit, revision=3)
        self.assertEqual(untouched.status_code, 200, untouched.text)
        after_publication = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(after_publication["resolved_contexts"][block_id], context_v1)

        # An explicit data-pointer change freezes a NEW context from the new
        # pin; the previous revision keeps the original context untouched.
        repointed = copy.deepcopy(after_publication["content"])
        self.model_block(repointed)["attrs"]["dataset_version_id"] = str(dataset_v2)
        pointer_edit = self.save_document(detail.document.id, repointed, revision=4)
        self.assertEqual(pointer_edit.status_code, 200, pointer_edit.text)
        after_pointer = self.stored_document(self.alice, detail.document.id)
        context_v2 = after_pointer["resolved_contexts"][block_id]
        self.assertNotEqual(context_v2, context_v1)
        parsed_v2 = ModelContext.model_validate(context_v2)
        self.assertEqual(str(parsed_v2.dataset_version_id), str(dataset_v2))
        self.assertEqual(str(parsed_v2.model_run_id), str(self.run_id))
        self.assertEqual(parsed_v2.context_hash, model_context_hash(
            parsed_v2.model_run_id, parsed_v2.dataset_version_id,
            parsed_v2.specification_version))
        # Reopening the historical revision shows the ORIGINAL frozen context.
        with user_transaction(self.engine, self.alice_id) as connection:
            rows = connection.execute(text("""
                SELECT revision, resolved_contexts FROM app.document_versions
                WHERE document_id = :id ORDER BY revision
            """), {"id": detail.document.id}).all()
        by_revision = {row[0]: row[1] for row in rows}
        self.assertEqual(by_revision[2][block_id], context_v1)
        self.assertEqual(by_revision[3][block_id], context_v1)
        self.assertEqual(by_revision[4][block_id], context_v2)

    def test_06_insertion_position_control(self):
        detail = self.create_document(self.alice)
        anchor = chart_fixtures.text_paragraph("Anchor paragraph")
        anchored = {"schema_version": 1, "type": "doc", "content": [anchor]}
        with self.as_session(self.alice_id):
            saved = self.client.post(
                f"/api/documents/{detail.document.id}/versions",
                json={"schema_version": 1, "content": anchored, "observed_contexts": []},
                headers={"Authorization": "Bearer t.alice", "If-Match": '"1"'})
        self.assertEqual(saved.status_code, 200, saved.text)
        dataset_id = self.insert_dataset_version(self.dataset_key("model-position"))
        payload = insert_model_payload(self.run_id, dataset_version_id=str(dataset_id),
                                       after_block_id=anchor["attrs"]["block_id"])
        response = self.add_model(detail.document.id, payload, revision=2)
        self.assertEqual(response.status_code, 201, response.text)
        stored = self.stored_document(self.alice, detail.document.id)
        self.assertEqual([node["type"] for node in stored["content"]["content"]],
                         ["paragraph", "modelResult"])
        # A dangling anchor is a typed zero-row refusal.
        dangling = self.add_model(
            detail.document.id,
            insert_model_payload(self.run_id, dataset_version_id=str(dataset_id),
                                 after_block_id=str(uuid4())),
            revision=3)
        self.assertEqual(dangling.status_code, 422)
        self.assertEqual(self.table_counts(detail.document.id),
                         {"document_versions": 3, "document_blocks": 2})
