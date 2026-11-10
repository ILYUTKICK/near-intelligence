"""NI-062 adversarial ownership matrix over every private endpoint family.

Needs scripts/run-db-tests.py (a disposable loopback PostgreSQL cluster);
direct discovery skips the class — a skip is never successful integration
evidence. All identities, documents, datasets and amounts are synthetic
fixtures; no provider, archive or network is contacted.

The matrix runs the REAL HTTP dependency chain (stubbed token verifier, real
RLS-backed database) and proves, family by family:

- READS: every private resource of Alice is invisible to Bob as the ONE
  generic 404 envelope, byte-equal to the absent-resource answer (no
  existence leak), with ``Cache-Control: no-store`` on every response;
- WRITES: Bob's mutations against Alice's resources fail 404 (never 409/428
  for a foreign id — the id is not even interpreted), while Alice's own
  stale-revision CAS still fails 409 correctly;
- IDOR: nested/cross-referenced UUIDs (another user's version id under a
  foreign document path, another user's export job id, another user's
  annotation id as an evidence target) are refused; global immutable
  scientific ids (chart definitions, datasets) are deliberately NOT private
  and stay readable by design;
- EXPORTS: the full download path is owner-scoped, serves a
  server-controlled ``application/zip`` attachment with flat UUID entry
  names, inert markdown (no executable content) and exact decimal strings;
- payload owner fields (``owner_id``/``user_id``/``subject``) can never
  override the verified identity anywhere;
- public endpoints keep their recorded caching while private responses are
  never cacheable.
"""

import io
import json
import os
import re
import unittest
import zipfile
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from unittest.mock import patch

from near_api.exports.worker import process_one
import test_chart_blocks as chart_fixtures
import test_delivery_apis as data_fixture
import test_document_insights as annotation_fixtures
import test_documents as document_fixtures
from test_documents import _StubVerifier, _verified

from near_api.auth import principal as principal_module

SHA256 = "a" * 64


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class SecurityOwnershipMatrixTests(chart_fixtures.ChartBlockDatabaseFixture,
                                   unittest.TestCase):
    """Alice/Bob over documents, annotations, exports, saved charts, home, me."""

    def setUp(self):
        super().setUp()
        # Public delivery routes build their engine through the same lazy
        # helper; point it at the disposable cluster's runtime connection for
        # the whole class so the recorded public caching is checkable here.
        self.engine_patcher = patch.object(principal_module, "_get_engine",
                                           return_value=self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        self.bearer_alice = {"Authorization": f"Bearer t.{self.alice_id}"}
        self.bearer_bob = {"Authorization": f"Bearer t.{self.bob_id}"}

    # -- session helpers ----------------------------------------------------- #

    def as_alice(self):
        verifier = _StubVerifier(_verified(self.alice_id))
        context = self.enterContext(_patched_engine(verifier, self.engine))
        return context

    def as_bob(self):
        verifier = _StubVerifier(_verified(self.bob_id))
        context = self.enterContext(_patched_engine(verifier, self.engine))
        return context

    # -- fixture builders ---------------------------------------------------- #

    def build_annotated_document(self):
        """Alice's document with a chart, insight, hypothesis and evidence."""
        document_id = self.create_document(self.alice).document.id
        path = f"/api/documents/{document_id}"
        dataset = self.publish_volume(self.dataset_key("audit-matrix"),
                                      "123456789.123456789012345678901234")
        preview = self.preview_volume(document_id,
                                      dataset_version=str(dataset.dataset_version_id))
        context = chart_fixtures.observed_context(preview)
        block_id, document = self.chart_document(preview)
        hypothesis = document_fixtures.hypothesis_attrs()
        document["content"].append(hypothesis)
        with self.as_alice():
            saved = self.client.post(f"{path}/versions",
                                     json={"schema_version": 1, "content": document},
                                     headers={**self.bearer_alice, "If-Match": '"1"'})
        self.assertEqual(saved.status_code, 201, saved.text)
        revision = saved.json()["version"]["id"]
        with self.as_alice():
            insight = self.client.post(f"{path}/insights",
                                       json=annotation_fixtures.insight_payload(
                                           context, after_block_id=block_id),
                                       headers={**self.bearer_alice, "If-Match": '"2"'})
            self.assertEqual(insight.status_code, 201, insight.text)
            insight_id = insight.json()["value"]["id"]
            evidence = self.client.post(f"{path}/evidence",
                                        json=annotation_fixtures.evidence_payload(
                                            hypothesis["attrs"]["hypothesis_id"],
                                            "insight", insight_id),
                                        headers={**self.bearer_alice,
                                                 "If-Match": f'"{insight.json()["document"]["revision"]}"'})
            self.assertEqual(evidence.status_code, 201, evidence.text)
            listing = self.client.get(f"{path}/insights", headers=self.bearer_alice)
            self.assertEqual(listing.status_code, 200, listing.text)
            current_revision = evidence.json()["document"]["revision"]
            saved_chart = self.client.post("/api/saved-charts", json={
                "chart_definition_version_id": str(chart_fixtures.CHART_ID),
                "label": "Synthetic audit chart", "mode": "live",
                "dataset_version_id": str(dataset.dataset_version_id),
                "selection": {"start": "2026-01-01", "end": "2026-01-02",
                              "frequency": "day", "filters": {"source": "SRC-LLAMA"}},
            }, headers=self.bearer_alice)
        self.assertEqual(saved_chart.status_code, 201, saved_chart.text)
        return {
            "document_id": document_id, "path": path,
            "version_id": UUID(revision),
            "insight_id": insight_id,
            "hypothesis_id": hypothesis["attrs"]["hypothesis_id"],
            "evidence_id": evidence.json()["value"]["id"],
            "saved_chart_id": saved_chart.json()["id"],
            "revision": current_revision,
        }

    def foreign_404(self, response, baseline: dict, where: str):
        """One generic 404 envelope, identical to the absent-resource answer."""
        self.assertEqual(response.status_code, 404, f"{where}: {response.text}")
        self.assertEqual(response.headers["Cache-Control"], "no-store", where)
        error = response.json()["error"]
        self.assertEqual(error["code"], baseline["code"], where)
        self.assertEqual(error["message"], baseline["message"], where)
        self.assertEqual(error.get("details"), baseline.get("details"), where)

    def absent_baseline(self) -> dict:
        with self.as_bob():
            missing = self.client.get(f"/api/documents/{uuid4()}",
                                      headers=self.bearer_bob)
        self.assertEqual(missing.status_code, 404)
        error = missing.json()["error"]
        return {"code": error["code"], "message": error["message"],
                "details": error.get("details")}

    # -- the matrix ----------------------------------------------------------- #

    def test_01_reads_of_every_private_family_are_one_generic_404(self):
        fixtures = self.build_annotated_document()
        baseline = self.absent_baseline()
        document_path = fixtures["path"]
        with self.as_bob():
            reads = (
                (self.client.get(document_path, headers=self.bearer_bob), "document"),
                (self.client.get(f"{document_path}/versions", headers=self.bearer_bob),
                 "versions"),
                (self.client.get(f"{document_path}/versions/{fixtures['version_id']}",
                                 headers=self.bearer_bob), "version detail"),
                (self.client.get("/api/documents", params={"q": "Synthetic"},
                                 headers=self.bearer_bob), "search"),
                (self.client.get(f"{document_path}/chart-view", params={
                    "chart_definition_version_id": str(chart_fixtures.CHART_ID),
                    "start": "2026-01-01", "end": "2026-01-04",
                    "dataset_version": str(uuid4())}, headers=self.bearer_bob),
                 "chart view"),
                (self.client.get(f"{document_path}/insights", headers=self.bearer_bob),
                 "insights"),
                (self.client.get(f"{document_path}/hypotheses", headers=self.bearer_bob),
                 "hypotheses"),
                (self.client.get(f"{document_path}/evidence", headers=self.bearer_bob),
                 "evidence"),
                (self.client.get(f"{document_path}/evidence-targets", params={
                    "target_kind": "model_run"}, headers=self.bearer_bob),
                 "evidence targets"),
                (self.client.get("/api/saved-charts", headers=self.bearer_bob),
                 "saved charts list"),
                (self.client.get(f"/api/saved-charts/{fixtures['saved_chart_id']}",
                                 headers=self.bearer_bob), "saved chart"),
                (self.client.get("/api/home", headers=self.bearer_bob), "home"),
                (self.client.get("/api/me", headers=self.bearer_bob), "me"),
            )
        for response, where in reads:
            if where in {"home", "me", "search", "saved charts list"}:
                self.assertEqual(response.status_code, 200, f"{where}: {response.text}")
            else:
                self.foreign_404(response, baseline, where)
            self.assertEqual(response.headers["Cache-Control"], "no-store", where)
        # Bob's own collections carry none of Alice's content (the responses
        # captured inside Bob's session above).
        bob_home, bob_listing, bob_saved = reads[-3][0], None, None
        with self.as_bob():
            bob_home = self.client.get("/api/home", headers=self.bearer_bob)
            bob_listing = self.client.get("/api/documents", headers=self.bearer_bob)
            bob_saved = self.client.get("/api/saved-charts", headers=self.bearer_bob)
        self.assertEqual(bob_home.json()["counts"]["documents"], 0)
        self.assertEqual(bob_listing.json()["items"], [])
        self.assertEqual(bob_saved.json()["items"], [])
        alice_content = json.dumps(bob_home.json()) + json.dumps(bob_listing.json()) \
            + json.dumps(bob_saved.json())
        self.assertNotIn("Synthetic", alice_content)

    def test_02_writes_of_every_private_family_are_refused_for_bob(self):
        fixtures = self.build_annotated_document()
        baseline = self.absent_baseline()
        path = fixtures["path"]
        with self.as_bob():
            writes = (
                (self.client.post(f"{path}/versions", json={
                    "schema_version": 1,
                    "content": {"type": "doc", "content": []}},
                    headers={**self.bearer_bob, "If-Match": f'"{fixtures["revision"]}"'}),
                 "save foreign document"),
                (self.client.patch(path, json={"title": "Stolen"},
                                   headers={**self.bearer_bob, "If-Match": f'"{fixtures["revision"]}"'}),
                 "rename foreign document"),
                (self.client.delete(path, headers={**self.bearer_bob,
                                                   "If-Match": f'"{fixtures["revision"]}"'}),
                 "delete foreign document"),
                (self.client.post(f"{path}/chart-blocks", json={
                    "chart_definition_version_id": str(chart_fixtures.CHART_ID),
                    "selection": chart_fixtures.selection(), "mode": "live",
                    "dataset_version_id": str(uuid4())},
                    headers={**self.bearer_bob, "If-Match": f'"{fixtures["revision"]}"'}),
                 "chart block foreign document"),
                (self.client.post(f"{path}/insights", json=annotation_fixtures.insight_payload({
                    "chart_definition_version_id": str(chart_fixtures.CHART_ID),
                    "dataset_version_id": str(uuid4()),
                    "selection": chart_fixtures.selection(),
                    "context_hash": SHA256,
                    "renderer_version": "echarts-modular-svg@1",
                    "metric_definition_versions": [],
                    "resolved_at": "2026-01-02T00:00:00Z"}),
                    headers={**self.bearer_bob, "If-Match": f'"{fixtures["revision"]}"'}),
                 "insight foreign document"),
                (self.client.patch(f"{path}/insights/{fixtures['insight_id']}",
                                   json={"classification": "supporting"},
                                   headers={**self.bearer_bob,
                                            "If-Match": f'"{fixtures["revision"]}"'}),
                 "patch foreign insight"),
                (self.client.request("DELETE", f"{path}/insights/{fixtures['insight_id']}",
                                     json={"remove_evidence_links": False},
                                     headers={**self.bearer_bob,
                                              "If-Match": f'"{fixtures["revision"]}"'}),
                 "delete foreign insight"),
                (self.client.patch(f"{path}/hypotheses/{fixtures['hypothesis_id']}",
                                   json={"assessment": "supported"},
                                   headers={**self.bearer_bob,
                                            "If-Match": f'"{fixtures["revision"]}"'}),
                 "patch foreign hypothesis"),
                (self.client.delete(f"{path}/evidence/{fixtures['evidence_id']}",
                                    headers={**self.bearer_bob,
                                             "If-Match": f'"{fixtures["revision"]}"'}),
                 "delete foreign evidence"),
                (self.client.patch(f"{path}/evidence/{fixtures['evidence_id']}",
                                   json={"explanation": "Rewritten"},
                                   headers={**self.bearer_bob,
                                            "If-Match": f'"{fixtures["revision"]}"'}),
                 "patch foreign evidence"),
                (self.client.post(f"{path}/exports", json={
                    "document_version_id": str(fixtures["version_id"]),
                    "format": "markdown_zip"}, headers=self.bearer_bob),
                 "create foreign export"),
                (self.client.get(f"{path}/exports/{uuid4()}", headers=self.bearer_bob),
                 "poll foreign export"),
                (self.client.get(f"{path}/exports/{uuid4()}/download",
                                 headers=self.bearer_bob), "download foreign export"),
                (self.client.patch(f"/api/saved-charts/{fixtures['saved_chart_id']}",
                                   json={"label": "Stolen"}, headers=self.bearer_bob),
                 "patch foreign saved chart"),
                (self.client.delete(f"/api/saved-charts/{fixtures['saved_chart_id']}",
                                    headers=self.bearer_bob), "delete foreign saved chart"),
            )
        for response, where in writes:
            self.foreign_404(response, baseline, where)
        # Nothing changed for Alice: the document and its saved chart survive.
        with self.as_alice():
            detail = self.client.get(path, headers=self.bearer_alice)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["revision"], fixtures["revision"])
            chart = self.client.get(f"/api/saved-charts/{fixtures['saved_chart_id']}",
                                    headers=self.bearer_alice)
            self.assertEqual(chart.status_code, 200)
            self.assertEqual(chart.json()["saved_chart"]["label"], "Synthetic audit chart")

    def test_03_owner_stale_revision_is_409_while_foreign_is_404(self):
        fixtures = self.build_annotated_document()
        baseline = self.absent_baseline()
        path = fixtures["path"]
        # Alice's own stale CAS is a real conflict (the id is hers).
        with self.as_alice():
            stale = self.client.patch(path, json={"title": "Synthetic rename"},
                                      headers={**self.bearer_alice, "If-Match": '"1"'})
            self.assertEqual(stale.status_code, 409, stale.text)
            self.assertEqual(stale.json()["error"]["code"], "REVISION_CONFLICT")
            missing_revision = self.client.post(f"{path}/versions", json={
                "schema_version": 1, "content": {"type": "doc", "content": []}},
                headers={**self.bearer_alice, "If-Match": '"999"'})
            self.assertEqual(missing_revision.status_code, 409)
        # Bob with Alice's CORRECT revision still gets the generic 404 — the
        # revision value leaks nothing.
        with self.as_bob():
            current = self.client.patch(path, json={"title": "Stolen"},
                                        headers={**self.bearer_bob,
                                                 "If-Match": f'"{fixtures["revision"]}"'})
        self.foreign_404(current, baseline, "rename with current revision")
        # Missing precondition: 428 for the owner. For Bob the 428 is the
        # SAME answer an absent document gives (the precondition is checked
        # before any id resolution), so it leaks no existence information —
        # the distinguishing 404 only appears once Bob supplies an If-Match.
        with self.as_alice():
            no_precondition = self.client.patch(path, json={"title": "Synthetic rename"},
                                                headers=self.bearer_alice)
            self.assertEqual(no_precondition.status_code, 428)
        with self.as_bob():
            foreign_no_precondition = self.client.patch(
                path, json={"title": "Stolen"}, headers=self.bearer_bob)
            absent_no_precondition = self.client.patch(
                f"/api/documents/{uuid4()}", json={"title": "Stolen"},
                headers=self.bearer_bob)
        self.assertEqual(foreign_no_precondition.status_code, 428)
        self.assertEqual(
            {key: value for key, value in foreign_no_precondition.json()["error"].items()
             if key != "request_id"},
            {key: value for key, value in absent_no_precondition.json()["error"].items()
             if key != "request_id"},
            "428 without precondition must be identical for foreign and absent ids")

    def test_04_cross_referenced_uuids_cannot_be_reused_across_owners(self):
        fixtures = self.build_annotated_document()
        baseline = self.absent_baseline()
        bob_document = self.create_document(self.bob).document.id
        bob_path = f"/api/documents/{bob_document}"
        with self.as_bob():
            cases = (
                (self.client.get(f"{bob_path}/versions/{fixtures['version_id']}",
                                 headers=self.bearer_bob), "Alice version under Bob doc"),
                (self.client.get(f"{bob_path}/exports/{uuid4()}",
                                 headers=self.bearer_bob), "unknown job under Bob doc"),
                (self.client.get(f"/api/documents/{uuid4()}/exports/{uuid4()}/download",
                                 headers=self.bearer_bob), "cross document download"),
            )
        for response, where in cases:
            self.foreign_404(response, baseline, where)
        # Bob cannot point his evidence at Alice's private insight: the
        # target must live in his own revision or a public catalog.
        with self.as_bob():
            evidence = self.client.post(f"{bob_path}/evidence", json={
                **annotation_fixtures.evidence_payload(str(uuid4()), "insight",
                                                       str(fixtures["insight_id"])),
            }, headers={**self.bearer_bob, "If-Match": '"1"'})
            self.assertEqual(evidence.status_code, 422, evidence.text)
            self.assertEqual(evidence.json()["error"]["code"], "REFERENCE_INVALID")

    def test_05_payload_owner_fields_never_override_the_verified_identity(self):
        with self.as_bob():
            document = self.client.post("/api/documents", json={
                "title": "Synthetic owner injection", "owner_id": str(self.alice_id)},
                headers=self.bearer_bob)
            self.assertEqual(document.status_code, 422, document.text)
            profile = self.client.patch("/api/me", json={
                "display_name": "Injected", "user_id": str(self.alice_id)},
                headers=self.bearer_bob)
            self.assertEqual(profile.status_code, 422, profile.text)
            me = self.client.get("/api/me", headers=self.bearer_bob)
        self.assertEqual(me.json()["display_name"], "Synthetic Bob")
        body = json.dumps(me.json())
        self.assertNotIn("Synthetic Alice", body)
        self.assertNotIn(str(self.alice_id), body)

    def test_06_public_endpoints_keep_recorded_caching_and_private_never_caches(self):
        with self.as_alice():
            detail = self.client.get("/api/documents", headers=self.bearer_alice)
            self.assertEqual(detail.headers["Cache-Control"], "no-store")
            # NI-062 hardening: the private profile mutations are no-store too
            # (the API does not rely on the same-origin gateway overriding it).
            profile = self.client.patch("/api/me", json={"display_name": "Synthetic Alice",
                                                          "display_timezone": "UTC"},
                                        headers=self.bearer_alice)
            self.assertEqual(profile.status_code, 200, profile.text)
            self.assertEqual(profile.headers["Cache-Control"], "no-store")
        # Public catalog responses stay cacheable by design (recorded NI-032
        # semantics); they carry no private identity.
        catalog = self.client.get("/api/charts")
        self.assertEqual(catalog.status_code, 200)
        self.assertNotEqual(catalog.headers.get("Cache-Control"), "no-store")
        self.assertIn("max-age", catalog.headers["Cache-Control"])
        metrics = self.client.get("/api/metrics")
        self.assertIn("max-age", metrics.headers["Cache-Control"])
        model_runs = self.client.get("/api/model-runs")
        self.assertIn("max-age", model_runs.headers["Cache-Control"])

    def test_07_export_download_is_owner_scoped_inert_and_exact(self):
        document_id = self.create_document(self.alice).document.id
        path = f"/api/documents/{document_id}"
        hostile_paragraph = {"type": "paragraph",
                             "attrs": {"block_id": str(uuid4())},
                             "content": [document_fixtures.text_node(
                                 "<script>alert(1)</script> [x](javascript:alert(1)) "
                                 "| fake |")]}
        content = {"type": "doc", "schema_version": 1, "content": [
            hostile_paragraph,
            document_fixtures.data_table_attrs(
                rows=[["fees", "123456789.123456789012345678901234"]]),
        ]}
        with self.as_alice():
            saved = self.client.post(f"{path}/versions",
                                     json={"schema_version": 1, "content": content},
                                     headers={**self.bearer_alice, "If-Match": '"1"'})
            self.assertEqual(saved.status_code, 201, saved.text)
            created = self.client.post(f"{path}/exports", json={
                "document_version_id": saved.json()["version"]["id"],
                "format": "markdown_zip"}, headers=self.bearer_alice)
            self.assertEqual(created.status_code, 202, created.text)
            job_id = created.json()["id"]
        processed = process_one(self.engine, self.operator, worker_id="ni062-audit",
                                lease_seconds=300, timeout=60.0, node_bin=None,
                                renderer_script=None)
        self.assertTrue(processed)
        with self.as_bob():
            baseline = self.absent_baseline()
            foreign_poll = self.client.get(f"{path}/exports/{job_id}",
                                           headers=self.bearer_bob)
            foreign_download = self.client.get(f"{path}/exports/{job_id}/download",
                                               headers=self.bearer_bob)
        self.foreign_404(foreign_poll, baseline, "Bob polls Alice's export")
        self.foreign_404(foreign_download, baseline, "Bob downloads Alice's export")
        with self.as_alice():
            poll = self.client.get(f"{path}/exports/{job_id}", headers=self.bearer_alice)
            self.assertEqual(poll.json()["status"], "succeeded", poll.text)
            download = self.client.get(poll.json()["download_path"],
                                       headers=self.bearer_alice)
        self.assertEqual(download.status_code, 200, download.text)
        self.assertEqual(download.headers["Content-Type"], "application/zip")
        self.assertEqual(download.headers["Cache-Control"], "no-store")
        self.assertIn(f'filename="near-export-{job_id}.zip"',
                      download.headers["Content-Disposition"])
        extracted = {}
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            for name in archive.namelist():
                self.assertTrue(not name.startswith("/") and ".." not in name
                                and "\\" not in name, name)
                extracted[name] = archive.read(name)
        research = extracted["research.md"].decode("utf-8")
        self.assertNotIn("<script", research.lower())
        # The javascript: payload survives only as escaped TEXT: no real
        # (unescaped) link destination may exist other than relative assets
        # (this chart-less export has none at all).
        destinations = re.findall(r"(?<!\\)\]\(([^)\n]*)\)", research)
        self.assertTrue(all(dest.startswith("assets/") for dest in destinations),
                        destinations)
        self.assertNotIn("| fake |", research)
        self.assertIn("123456789.123456789012345678901234", research)
        manifest = json.loads(extracted["manifest.json"])
        self.assertEqual(manifest["document"]["revision"],
                         saved.json()["version"]["revision"])


def _patched_engine(verifier, engine):
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch.object(principal_module, "_get_verifier",
                                     return_value=verifier))
    stack.enter_context(patch.object(principal_module, "_get_engine",
                                     return_value=engine))
    return stack


if __name__ == "__main__":
    unittest.main()
