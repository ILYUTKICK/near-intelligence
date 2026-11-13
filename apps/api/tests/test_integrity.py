"""NI-065 deterministic integrity oracle cases over the disposable cluster.

Needs scripts/run-db-tests.py (a disposable loopback PostgreSQL cluster);
direct discovery skips the class — a skip is never successful integration
evidence. Every document, dataset, artifact and identity is a synthetic
fixture; no provider, archive or network is contacted.

The oracle family (ADR-022): each test builds a document with KNOWN
conditions and asserts the exact findings — a clean document reports zero,
each planted condition reports exactly its typed finding with the correct
block/entity/dataset/definition references, and nothing is ever mutated by a
check (the stored revision is byte-identical before and after).
"""

import copy
import json
import os
import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from near_api.main import app
from near_api.schemas.integrity import IntegrityReport
import test_chart_blocks as chart_fixtures
import test_document_insights as annotation_fixtures


def integrity_response_ok(response) -> IntegrityReport:
    """The typed 200 report contract: no-store, validated model."""
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    return IntegrityReport.model_validate(response.json())


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class IntegrityOracleTests(chart_fixtures.ChartBlockDatabaseFixture, unittest.TestCase):
    """Deterministic findings for known document conditions."""

    def setUp(self):
        super().setUp()  # the fixture already provides the TestClient
        # Oracle cases assert only 200 paths; surfacing unexpected exceptions
        # directly keeps a regression's real traceback in the test output.
        self.client = TestClient(app, raise_server_exceptions=True)

    def fetch(self, document_id, *, subject=None, version_id=None):
        params = {} if version_id is None else {"version_id": str(version_id)}
        subject = subject or self.alice_id
        with self.as_session(subject):
            return self.client.get(f"/api/documents/{document_id}/integrity",
                                   params=params,
                                   headers={"Authorization": f"Bearer t.{subject}"})

    def add_hypothesis(self, document_id, *, revision):
        with self.as_session(self.alice_id):
            response = self.client.post(f"/api/documents/{document_id}/hypotheses",
                                        json=annotation_fixtures.hypothesis_payload(),
                                        headers={"Authorization": f"Bearer t.{self.alice_id}",
                                                 "If-Match": f'"{revision}"'})
        assert response.status_code == 201, response.text
        return response.json()

    def add_evidence(self, document_id, *, revision, hypothesis_id, target_id,
                     target_kind="chart_block"):
        with self.as_session(self.alice_id):
            response = self.client.post(f"/api/documents/{document_id}/evidence",
                                        json=annotation_fixtures.evidence_payload(
                                            hypothesis_id, target_kind, str(target_id)),
                                        headers={"Authorization": f"Bearer t.{self.alice_id}",
                                                 "If-Match": f'"{revision}"'})
        assert response.status_code == 201, response.text
        return response.json()

    def cited_chart_document(self, *, dataset_version_id=None):
        """A document whose liveChart is cited by an evidence link (clean)."""
        detail = self.create_document(self.alice)
        document_id = detail.document.id
        payload = chart_fixtures.insert_payload()
        if dataset_version_id is not None:
            payload["dataset_version_id"] = str(dataset_version_id)
        added = self.add_chart(document_id, payload)
        assert added.status_code == 201, added.text
        block_id = added.json()["value"]["block_id"]
        hypothesis = self.add_hypothesis(document_id, revision=2)
        evidence = self.add_evidence(document_id, revision=3,
                                     hypothesis_id=hypothesis["value"]["id"],
                                     target_id=block_id)
        return {"document_id": document_id, "chart_block_id": block_id,
                "hypothesis_id": hypothesis["value"]["id"],
                "evidence_id": evidence["value"]["id"],
                "revision": evidence["document"]["revision"]}

    def test_01_clean_document_reports_zero_findings(self):
        dataset = self.publish_volume(self.dataset_key("integrity-clean"), "12.5")
        fixtures = self.cited_chart_document(dataset_version_id=dataset.dataset_version_id)
        report = integrity_response_ok(self.fetch(fixtures["document_id"]))
        self.assertTrue(report.is_acknowledged)
        self.assertEqual(report.findings, ())
        self.assertEqual(report.counts, ())

    def test_02_newer_approved_dataset_is_one_stale_finding_with_exact_refs(self):
        key = self.dataset_key("integrity-stale")
        first = self.publish_volume(key, "12.5")
        fixtures = self.cited_chart_document(dataset_version_id=first.dataset_version_id)
        # Zero findings before the newer publication (the pin IS the newest).
        before = integrity_response_ok(self.fetch(fixtures["document_id"]))
        self.assertEqual(before.findings, ())
        second = self.publish_volume(key, "222")
        self.assertNotEqual(second.dataset_version_id, first.dataset_version_id)
        report = integrity_response_ok(self.fetch(fixtures["document_id"]))
        self.assertEqual([finding.check_id for finding in report.findings], ["stale_chart_context"])
        finding = report.findings[0]
        self.assertEqual(finding.severity, "advisory")
        self.assertEqual(finding.block_id, UUID(fixtures["chart_block_id"]))
        self.assertEqual(finding.dataset_version_id, first.dataset_version_id)
        self.assertEqual(finding.latest_dataset_version_id, second.dataset_version_id)
        self.assertEqual(finding.jump, "block")
        self.assertTrue(finding.context_hash)
        self.assertEqual([count.check_id for count in report.counts], ["stale_chart_context"])
        # The check mutated nothing: the stored pin and context are verbatim.
        stored = self.stored_document(self.alice, fixtures["document_id"])
        context = stored["resolved_contexts"][fixtures["chart_block_id"]]
        self.assertEqual(context["dataset_version_id"], str(first.dataset_version_id))

    def test_03_uncited_pinned_chart_is_advisory(self):
        dataset = self.publish_volume(self.dataset_key("integrity-uncited"), "12.5")
        detail = self.create_document(self.alice)
        added = self.add_chart(detail.document.id, chart_fixtures.insert_payload(
            dataset_version_id=str(dataset.dataset_version_id)))
        assert added.status_code == 201, added.text
        block_id = added.json()["value"]["block_id"]
        report = integrity_response_ok(self.fetch(detail.document.id))
        self.assertEqual([finding.check_id for finding in report.findings],
                         ["uncited_pinned_chart"])
        self.assertEqual(report.findings[0].severity, "advisory")
        self.assertEqual(report.findings[0].block_id, UUID(block_id))
        self.assertEqual(report.findings[0].dataset_version_id, dataset.dataset_version_id)

    def test_04_missing_frozen_context_is_a_reported_corruption_signal(self):
        dataset = self.publish_volume(self.dataset_key("integrity-corrupt"), "12.5")
        detail = self.create_document(self.alice)
        added = self.add_chart(detail.document.id, chart_fixtures.insert_payload(
            dataset_version_id=str(dataset.dataset_version_id)))
        assert added.status_code == 201, added.text
        block_id = added.json()["value"]["block_id"]
        stored = self.stored_document(self.alice, detail.document.id)
        # Simulate stored corruption directly (the runtime role has no UPDATE
        # grant; the test admin does). Nothing in the service can do this.
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.document_versions SET resolved_contexts = '{}'::jsonb "
                "WHERE id = :id"), {"id": stored["id"]})
        report = integrity_response_ok(self.fetch(detail.document.id))
        self.assertEqual({finding.check_id for finding in report.findings},
                         {"missing_chart_context", "uncited_pinned_chart"})
        missing = next(finding for finding in report.findings
                       if finding.check_id == "missing_chart_context")
        self.assertEqual(missing.severity, "warning")
        self.assertEqual(missing.block_id, UUID(block_id))
        self.assertEqual(missing.jump, "block")

    def test_valid_shape_context_corruption_is_reported_without_mutation(self):
        dataset = self.publish_volume(self.dataset_key("integrity-hash-corruption"), "12.5")
        fixtures = self.cited_chart_document(dataset_version_id=dataset.dataset_version_id)
        stored = self.stored_document(self.alice, fixtures["document_id"])
        contexts = copy.deepcopy(stored["resolved_contexts"])
        contexts[fixtures["chart_block_id"]]["context_hash"] = "f" * 64
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.document_versions SET resolved_contexts = CAST(:contexts AS jsonb) "
                "WHERE id = :id"), {"id": stored["id"], "contexts": json.dumps(contexts)})
        report = integrity_response_ok(self.fetch(fixtures["document_id"]))
        self.assertEqual([finding.check_id for finding in report.findings], ["invalid_chart_context"])
        self.assertEqual(report.findings[0].severity, "warning")
        self.assertEqual(report.findings[0].block_id, UUID(fixtures["chart_block_id"]))
        self.assertEqual(self.stored_document(self.alice, fixtures["document_id"])["resolved_contexts"],
                         contexts)

    def test_05_public_citation_drift_is_reported_not_raised(self):
        artifact_id = uuid4()
        with self.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size,
                       media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/pdf', 'public', NULL,
                        'unverified')
            """), {"id": artifact_id, "key": f"synthetic/{artifact_id}.pdf",
                   "sha": chart_fixtures.SHA256})
        detail = self.create_document(self.alice)
        hypothesis = self.add_hypothesis(detail.document.id, revision=1)
        evidence = self.add_evidence(detail.document.id, revision=2,
                                     hypothesis_id=hypothesis["value"]["id"],
                                     target_id=artifact_id, target_kind="citation")
        before = integrity_response_ok(self.fetch(detail.document.id))
        self.assertEqual(before.findings, ())
        # The registry drifts afterwards. Artifacts are SELECT-only for both
        # runtime roles (immutable by grant), so only the test admin (the
        # initdb superuser) can simulate the out-of-band change the check
        # exists to surface.
        with self.admin.begin() as connection:
            connection.execute(text("UPDATE app.artifacts SET scope = 'internal' WHERE id = :id"),
                               {"id": artifact_id})
        report = integrity_response_ok(self.fetch(detail.document.id))
        self.assertEqual([finding.check_id for finding in report.findings],
                         ["evidence_target_unavailable"])
        finding = report.findings[0]
        self.assertEqual(finding.severity, "advisory")
        self.assertEqual(finding.target_kind, "citation")
        self.assertEqual(finding.entity_id, UUID(evidence["value"]["id"]))
        self.assertEqual(finding.jump, "block")

    def test_06_dataset_pin_leaving_approved_state_is_reported(self):
        dataset = self.publish_volume(self.dataset_key("integrity-revoke"), "12.5")
        fixtures = self.cited_chart_document(dataset_version_id=dataset.dataset_version_id)
        # Approved dataset versions are immutable (the app guard trigger
        # refuses any status change), so the admin simulates the out-of-band
        # revocation with the trigger disabled for this transaction only.
        with self.admin.begin() as connection:
            connection.execute(text("SET LOCAL session_replication_role = replica"))
            updated = connection.execute(text(
                "UPDATE app.dataset_versions SET status = 'rejected' WHERE id = :id"),
                {"id": dataset.dataset_version_id})
            self.assertEqual(updated.rowcount, 1)
        report = integrity_response_ok(self.fetch(fixtures["document_id"]))
        # The fallback may be older than this revoked pin. Report the
        # unavailable pin without claiming that an older dataset is newer.
        self.assertEqual({finding.check_id for finding in report.findings},
                         {"dataset_pin_unavailable"})
        revoked = next(finding for finding in report.findings
                       if finding.check_id == "dataset_pin_unavailable")
        self.assertEqual(revoked.severity, "advisory")
        self.assertEqual(revoked.dataset_version_id, dataset.dataset_version_id)

    def test_07_historical_check_is_labeled_non_acknowledged(self):
        dataset = self.publish_volume(self.dataset_key("integrity-history"), "12.5")
        detail = self.create_document(self.alice)
        added = self.add_chart(detail.document.id, chart_fixtures.insert_payload(
            dataset_version_id=str(dataset.dataset_version_id)))
        assert added.status_code == 201, added.text
        stored = self.stored_document(self.alice, detail.document.id)
        historical_version = stored["id"]
        with self.as_session(self.alice_id):
            renamed = self.client.patch(f"/api/documents/{detail.document.id}",
                                        json={"title": "Synthetic integrity rename"},
                                        headers={"Authorization": f"Bearer t.{self.alice_id}",
                                                 "If-Match": '"2"'})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        report = integrity_response_ok(self.fetch(detail.document.id,
                                                  version_id=historical_version))
        self.assertFalse(report.is_acknowledged)
        self.assertEqual(report.version_id, historical_version)
        # The historical revision holds the same uncited-chart advisory; the
        # report stays read-only and labeled, never refused.
        self.assertEqual([finding.check_id for finding in report.findings],
                         ["uncited_pinned_chart"])
        current = integrity_response_ok(self.fetch(detail.document.id))
        self.assertTrue(current.is_acknowledged)

    def test_08_checks_never_change_the_stored_revision(self):
        dataset = self.publish_volume(self.dataset_key("integrity-readonly"), "12.5")
        fixtures = self.cited_chart_document(dataset_version_id=dataset.dataset_version_id)
        self.publish_volume(self.dataset_key("integrity-readonly-2"), "999")
        before = self.stored_document(self.alice, fixtures["document_id"])
        integrity_response_ok(self.fetch(fixtures["document_id"]))
        integrity_response_ok(self.fetch(fixtures["document_id"],
                                         version_id=before["id"]))
        after = self.stored_document(self.alice, fixtures["document_id"])
        self.assertEqual(json.dumps(before, sort_keys=True, default=str),
                         json.dumps(after, sort_keys=True, default=str))

    def test_09_misconfigured_commentary_preserves_owner_boundary(self):
        from near_api.settings import SettingsError
        document_id = self.create_document(self.alice).document.id
        payload = {"block_ids": [str(uuid4())], "question": "Synthetic selected context"}
        with patch("near_api.ai.routes.get_ai_commentary",
                   side_effect=SettingsError("Synthetic invalid adapter configuration")) as settings, \
                patch("near_api.ai.routes._provider_transport",
                      side_effect=AssertionError("No provider call is permitted")):
            with self.as_session(self.alice_id):
                owned = self.client.post(f"/api/documents/{document_id}/grounded-commentary",
                                         json=payload,
                                         headers={"Authorization": f"Bearer t.{self.alice_id}"})
            self.assertEqual(owned.status_code, 200, owned.text)
            self.assertEqual(owned.json()["state"], "failed")
            self.assertEqual(owned.json()["reason"], "adapter_misconfigured")
            settings.assert_called_once()
            settings.reset_mock()
            denied = []
            with self.as_session(self.bob_id):
                for target in (document_id, uuid4()):
                    response = self.client.post(f"/api/documents/{target}/grounded-commentary",
                                                json=payload,
                                                headers={"Authorization": f"Bearer t.{self.bob_id}"})
                    self.assertEqual(response.status_code, 404, response.text)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    error = response.json()["error"]
                    denied.append({key: error.get(key) for key in ("code", "message", "details")})
            self.assertEqual(denied[0], denied[1])
            settings.assert_not_called()


class IntegrityCorruptionBoundaryTests(unittest.TestCase):
    """Offline corruption oracles; every input and registry response is synthetic."""

    def report(self, content, contexts, *, unapproved=(), public_runs=(), definition=None):
        from near_api.documents.schema import parse_document
        from near_api.integrity.checks import build_integrity_report
        canonical = parse_document({"schema_version": 1, "type": "doc", "content": content})
        document = SimpleNamespace(id=uuid4())
        version = SimpleNamespace(id=uuid4(), revision=1, schema_version=1,
                                  content=canonical.canonical, content_sha256=canonical.content_sha256,
                                  resolved_contexts=contexts)
        with patch("near_api.integrity.checks._public_targets", return_value=(set(public_runs), set())), \
                patch("near_api.integrity.checks._unapproved_datasets", return_value=set(unapproved)), \
                patch("near_api.integrity.checks._latest_version", return_value=None), \
                patch("near_api.integrity.checks.load_chart_definition", return_value=definition):
            return build_integrity_report(MagicMock(), document, version, is_acknowledged=True)

    def chart(self, *, definition_id=None, dataset_id=None):
        return {"type": "liveChart", "attrs": {
            "block_id": str(uuid4()), "mode": "live", "snapshot_id": None,
            "chart_definition_version_id": str(definition_id or chart_fixtures.CHART_ID),
            "observed_dataset_version_id": str(dataset_id or uuid4()),
            "selection": chart_fixtures.selection()}}

    def test_all_200_blocks_can_report_four_findings_without_overflow(self):
        from near_api.documents.schema import MAX_TOP_LEVEL_BLOCKS, ReferenceInvalid
        from near_api.integrity.checks import build_integrity_report
        from near_api.documents.schema import parse_document
        charts = [self.chart() for _ in range(MAX_TOP_LEVEL_BLOCKS)]
        canonical = parse_document({"schema_version": 1, "type": "doc", "content": charts})
        version = SimpleNamespace(id=uuid4(), revision=1, schema_version=1,
                                  content=canonical.canonical, content_sha256=canonical.content_sha256,
                                  resolved_contexts=[])
        datasets = {chart.observed_dataset_version_id for chart in canonical.live_charts}
        with patch("near_api.integrity.checks._public_targets", return_value=(set(), set())), \
                patch("near_api.integrity.checks._unapproved_datasets", return_value=datasets), \
                patch("near_api.integrity.checks.load_chart_definition",
                      side_effect=ReferenceInvalid("Synthetic missing definition", [])):
            report = build_integrity_report(MagicMock(), SimpleNamespace(id=uuid4()), version,
                                            is_acknowledged=True)
        self.assertEqual(len(report.findings), MAX_TOP_LEVEL_BLOCKS * 4 + 1)
        self.assertEqual(sum(count.count for count in report.counts), len(report.findings))

    def test_valid_shape_chart_pin_and_hash_corruption_are_reported(self):
        from datetime import datetime, timezone
        from near_api.documents.context_resolver import ChartDefinitionRow, build_resolved_context
        from near_api.schemas.chart_selection import ChartSelection
        chart = self.chart()
        attrs = chart["attrs"]
        definition = ChartDefinitionRow(
            id=UUID(attrs["chart_definition_version_id"]), chart_id="synthetic", version=1,
            data_status="available", unavailable_reason=None, renderer_version="synthetic@1",
            max_days=366, filter_schema={}, metric_definition_versions=(), required_metric_versions=())
        context = build_resolved_context(
            definition, UUID(attrs["observed_dataset_version_id"]),
            ChartSelection.model_validate(attrs["selection"]),
            resolved_at=datetime(2026, 11, 13, tzinfo=timezone.utc)).model_dump(mode="json")
        for change in ({"context_hash": "f" * 64}, {"dataset_version_id": str(uuid4())},
                       {"chart_definition_version_id": str(uuid4())},
                       {"selection": {**attrs["selection"], "end": "2026-01-09"}},
                       {"renderer_version": "different@1"}):
            with self.subTest(change=change):
                report = self.report([chart], {attrs["block_id"]: {**context, **change}},
                                     definition=definition)
                self.assertEqual({finding.check_id for finding in report.findings},
                                 {"invalid_chart_context", "uncited_pinned_chart"})

    def test_absent_dataset_rows_are_unavailable(self):
        from near_api.integrity.checks import _unapproved_datasets
        approved, absent = uuid4(), uuid4()
        connection = MagicMock()
        connection.scalars.return_value = [approved]
        self.assertEqual(_unapproved_datasets(connection, {approved, absent}), {absent})

    def test_model_block_reports_missing_context_and_unavailable_run_and_dataset(self):
        block_id, run_id, dataset_id = uuid4(), uuid4(), uuid4()
        model = {"type": "modelResult", "attrs": {
            "block_id": str(block_id), "model_run_id": str(run_id),
            "dataset_version_id": str(dataset_id), "interpretation": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Synthetic model."}]}]}}
        report = self.report([model], {}, unapproved={dataset_id})
        self.assertEqual({finding.check_id for finding in report.findings},
                         {"missing_model_context", "model_run_unavailable", "dataset_pin_unavailable"})
        for finding in report.findings:
            self.assertEqual(finding.block_id, block_id)
            self.assertEqual(finding.entity_id, run_id)
            self.assertEqual(finding.dataset_version_id, dataset_id)

    def test_model_context_hash_corruption_is_reported_and_clean_pin_stays_clean(self):
        from near_api.documents.context_resolver import PublishedRunRow, build_model_context
        block_id, run_id, dataset_id = uuid4(), uuid4(), uuid4()
        model = {"type": "modelResult", "attrs": {
            "block_id": str(block_id), "model_run_id": str(run_id),
            "dataset_version_id": str(dataset_id), "interpretation": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Synthetic model."}]}]}}
        run = PublishedRunRow(run_id=run_id, spec_id="synthetic", spec_version=1)
        context = build_model_context(run, dataset_id).model_dump(mode="json")
        with patch("near_api.integrity.checks.load_published_run", return_value=run):
            clean = self.report([model], {str(block_id): context}, public_runs={run_id})
            self.assertEqual(clean.findings, ())
            corrupt = self.report([model], {str(block_id): {**context, "context_hash": "f" * 64}},
                                  public_runs={run_id})
        self.assertEqual([finding.check_id for finding in corrupt.findings], ["invalid_model_context"])
        self.assertEqual(corrupt.findings[0].block_id, block_id)


class IntegrityRouteContractTests(unittest.TestCase):
    """Offline route contract: authentication and the documented availability."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_integrity_and_commentary_require_a_verified_session(self):
        for path in (f"/api/documents/{uuid4()}/integrity",
                     f"/api/documents/{uuid4()}/grounded-commentary"):
            with self.subTest(path=path):
                response = self.client.get(path) if path.endswith("integrity") \
                    else self.client.post(path, json={"block_ids": [str(uuid4())],
                                                      "question": "Synthetic question"})
                self.assertEqual(response.status_code, 401, response.text)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                from near_api.schemas.common import ErrorResponse
                failure = ErrorResponse.model_validate(response.json())
                self.assertEqual(failure.error.code, "AUTHENTICATION_REQUIRED")

    def test_commentary_request_contract_bounds(self):
        from near_api.schemas.integrity import GroundedCommentaryRequest
        request = GroundedCommentaryRequest(block_ids=[str(uuid4())], question="Synthetic?")
        self.assertEqual(len(request.block_ids), 1)
        for changes in ({"block_ids": []},
                        {"block_ids": [str(uuid4()) for _ in range(11)]},
                        {"question": ""},
                        {"question": "x" * 2001},
                        {"endpoint": "https://attacker.example.test"},
                        {"owner_id": str(uuid4())}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                GroundedCommentaryRequest.model_validate(
                    {**{"block_ids": [str(uuid4())], "question": "q"}, **changes})

    def test_response_states_are_honest_and_cannot_fake_success(self):
        from near_api.schemas.integrity import COMMENTARY_NOTICE, GroundedCommentaryResponse
        document_id, version_id = uuid4(), uuid4()
        unavailable = GroundedCommentaryResponse.model_validate({
            "document_id": str(document_id), "version_id": str(version_id), "revision": 3,
            "state": "unavailable", "reason": "adapter_disabled",
            "message": "Grounded commentary is not enabled on this server",
            "advisory": True, "notice": COMMENTARY_NOTICE, "items": []})
        self.assertEqual(unavailable.state, "unavailable")
        ok = GroundedCommentaryResponse.model_validate({
            "document_id": str(document_id), "version_id": str(version_id), "revision": 3,
            "state": "ok", "advisory": True, "notice": COMMENTARY_NOTICE,
            "items": [{"block_id": str(uuid4()), "context_hash": chart_fixtures.SHA256,
                       "text": "Advisory note (quoted: 12.5)."}]})
        self.assertIsNone(ok.reason)
        for payload in (
            # A fake successful commentary without items is a contract violation.
            {"state": "ok", "items": []},
            # A success carrying a failure reason is a contradiction.
            {"state": "ok", "reason": "adapter_disabled",
             "items": [{"block_id": str(uuid4()), "context_hash": chart_fixtures.SHA256,
                        "text": "text"}]},
            # An unavailable state that is not the disabled adapter is undefined.
            {"state": "unavailable", "reason": "provider_http_status", "items": []},
            # A failure without a typed reason is unactionable.
            {"state": "failed", "items": []},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                GroundedCommentaryResponse.model_validate({
                    "document_id": str(document_id), "version_id": str(version_id),
                    "revision": 3, "advisory": True, "notice": COMMENTARY_NOTICE,
                    **payload})


if __name__ == "__main__":
    unittest.main()
