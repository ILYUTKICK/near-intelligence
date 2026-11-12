"""NI-036 canonical document schema and revision service tests.

Use scripts/run-db-tests.py for the cluster-dependent cases; direct discovery
skips them without its explicit isolated-cluster environment. A skip is never
successful integration evidence. The offline cases cover the canonical schema
fixtures for every P0 block type, duplicate/dangling identifiers, size limits
and the pure same-document reference rules. The database cases cover the
revision service guarantees: first empty revision, compare-and-set race,
invalid-content rollback (zero rows), immutable old revisions, projection
round-trip, approved-dataset/public-artifact reference checks and the
Alice/Bob isolation matrix at service and HTTP level.

All identities, titles and document contents are synthetic test fixtures,
never research data.
"""

import copy
import hashlib
import json
import os
import threading
import unittest
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
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
from near_api.auth.verification import VerifiedToken
from near_api.db.security import ResourceNotFound
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.documents import idempotency, service
from near_api.documents.projections import build_projections
from near_api.documents.schema import (
    MAX_TOP_LEVEL_BLOCKS,
    SCHEMA_VERSION,
    DocumentSchemaError,
    DocumentTooLarge,
    ReferenceInvalid,
    canonical_bytes,
    empty_document,
    parse_document,
)
from near_api.main import app
from near_api.schemas.common import ErrorResponse
import test_chart_blocks as chart_fixtures

TS = "2026-11-06T12:00:00Z"
SELECTION = {"start": "2025-01-01", "end": "2025-02-01", "frequency": "day", "filters": {}}
SHA256 = "a" * 64


def resolved_context(dataset_version_id: str | None = None) -> dict:
    return {
        "chart_definition_version_id": str(uuid4()),
        "dataset_version_id": dataset_version_id or str(uuid4()),
        "selection": copy.deepcopy(SELECTION),
        "context_hash": SHA256,
        "renderer_version": "echarts-1",
        "metric_definition_versions": [],
        "resolved_at": TS,
    }


def block(block_type: str, block_id: str | None = None, **attrs) -> dict:
    node = {"type": block_type, "attrs": {"block_id": block_id or str(uuid4())}}
    node["attrs"].update(attrs)
    return node


def text_node(text: str, marks: list | None = None) -> dict:
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def paragraph_node(text: str, marks: list | None = None) -> dict:
    return {"type": "paragraph", "content": [text_node(text, marks)]}


def hypothesis_attrs(block_id: str | None = None, **changes) -> dict:
    attrs = {
        "type": "hypothesis",
        "attrs": {
            "block_id": block_id or str(uuid4()),
            "hypothesis_id": str(uuid4()),
            "statement": "Adoption drives fee revenue within the window",
            "assessment": "untested",
            "authored_at": TS,
            "modified_at": TS,
        },
    }
    attrs["attrs"].update(changes)
    return attrs


def insight_attrs(insight_id: str | None = None, **changes) -> dict:
    attrs = {
        "type": "insight",
        "attrs": {
            "block_id": str(uuid4()),
            "insight_id": insight_id or str(uuid4()),
            "type": "observation",
            "classification": "supporting",
            "body": [paragraph_node("Observation body")],
            "context": resolved_context(),
            "authored_at": TS,
            "modified_at": TS,
        },
    }
    attrs["attrs"].update(changes)
    return attrs


def evidence_attrs(hypothesis_id: str, target_kind: str, target_id: str,
                   **changes) -> dict:
    attrs = {
        "type": "evidence",
        "attrs": {
            "block_id": str(uuid4()),
            "evidence_id": str(uuid4()),
            "hypothesis_id": hypothesis_id,
            "classification": "contradicting",
            "target_kind": target_kind,
            "target_id": target_id,
            "explanation": "Fee share moved against the claim",
        },
    }
    attrs["attrs"].update(changes)
    return attrs


def risk_attrs(hypothesis_id: str | None = None, **changes) -> dict:
    attrs = {
        "type": "risk",
        "attrs": {
            "block_id": str(uuid4()),
            "title": "Concentration risk",
            "body": [paragraph_node("A single market dominates the sample")],
        },
    }
    if hypothesis_id is not None:
        attrs["attrs"]["related_hypothesis_id"] = hypothesis_id
    attrs["attrs"].update(changes)
    return attrs


def data_table_attrs(**changes) -> dict:
    table_attrs = {
        "block_id": str(uuid4()),
        "columns": [{"key": "metric", "label": "Metric", "type": "string"},
                    {"key": "share", "label": "Share", "type": "number", "unit": "%"}],
        "rows": [["fees", "12.5"], [None, True]],
    }
    if "dataset_version_id" in changes:
        table_attrs.pop("rows")  # authored rows and a dataset ref are exclusive
    table_attrs.update(changes)
    return {"type": "dataTable", "attrs": table_attrs}


def full_document(*, insight_context: dict | None = None) -> dict:
    """One fixture containing every savable P0 block type (charts are a
    NI-031 registry gate and are exercised separately)."""
    hypothesis = hypothesis_attrs()
    hypothesis_id = hypothesis["attrs"]["hypothesis_id"]
    insight = insight_attrs(hypothesis_id=hypothesis_id,
                            context=insight_context or resolved_context())
    evidence = evidence_attrs(hypothesis_id, "insight", insight["attrs"]["insight_id"])
    return {"schema_version": SCHEMA_VERSION, "type": "doc", "content": [
        {"type": "paragraph",
         "attrs": {"block_id": str(uuid4())},
         "content": [text_node("Intro paragraph ",
                               marks=[{"type": "bold"}]),
                     text_node("with a link",
                               marks=[{"type": "link",
                                       "attrs": {"href": "https://example.com/source"}}])]},
        {"type": "heading",
         "attrs": {"block_id": str(uuid4()), "level": 2},
         "content": [text_node("Findings")]},
        {"type": "bullet_list",
         "attrs": {"block_id": str(uuid4())},
         "content": [{"type": "list_item", "content": [
             paragraph_node("first"),
             {"type": "ordered_list", "content": [
                 {"type": "list_item", "content": [paragraph_node("nested")]}]}]}]},
        hypothesis, insight, evidence, risk_attrs(hypothesis_id),
        block("divider"),
        data_table_attrs(),
    ]}


class DocumentSchemaTests(unittest.TestCase):
    """Offline canonical schema matrix: fixtures, limits, IDs, canonicalization."""

    def test_01_empty_document_is_valid(self):
        parsed = parse_document(empty_document())
        self.assertEqual(parsed.blocks, ())
        self.assertEqual(parsed.insights, ())
        self.assertEqual(parsed.content_sha256,
                         hashlib.sha256(canonical_bytes(parsed.canonical)).hexdigest())
        again = parse_document(parsed.canonical)
        self.assertEqual(again.content_sha256, parsed.content_sha256)

    def test_02_every_p0_block_fixture_validates_with_projections(self):
        document = full_document()
        parsed = parse_document(document)
        self.assertEqual([item.block_type for item in parsed.blocks],
                         ["paragraph", "heading", "bullet_list", "hypothesis",
                          "insight", "evidence", "risk", "divider", "dataTable"])
        self.assertEqual(len(parsed.insights), 1)
        self.assertEqual(len(parsed.hypotheses), 1)
        self.assertEqual(len(parsed.evidence), 1)
        self.assertEqual(len(parsed.risks), 1)
        projections = build_projections(parsed)
        self.assertEqual([item.position for item in projections.blocks],
                         list(range(len(parsed.blocks))))
        self.assertEqual(projections.blocks[0].attrs,
                         parsed.blocks[0].attrs)
        self.assertEqual(projections.insights[0].insight_id,
                         parsed.insights[0].insight_id)
        self.assertEqual(projections.evidence[0].hypothesis_id,
                         parsed.evidence[0].hypothesis_id)

    def test_03_canonicalization_is_deterministic_across_spellings(self):
        document = full_document()
        # Same UUIDs, different spelling: uppercase UUIDs, offset timestamp.
        canonical_ids = {node["attrs"]["block_id"]: node["attrs"]["block_id"].upper()
                         for node in document["content"] if "block_id" in node["attrs"]}
        respelled = copy.deepcopy(document)
        for node in respelled["content"]:
            attrs = node.get("attrs", {})
            for key, value in list(attrs.items()):
                if key in ("block_id", "hypothesis_id", "insight_id", "evidence_id",
                           "target_id", "dataset_version_id",
                           "chart_definition_version_id") and value in canonical_ids:
                    attrs[key] = canonical_ids[value]
            if key_context := attrs.get("context"):
                attrs["context"] = {**key_context,
                                    "resolved_at": "2026-11-06T15:00:00+03:00"}
            if "authored_at" in attrs:
                attrs["authored_at"] = "2026-11-06T15:00:00+03:00"
                attrs["modified_at"] = "2026-11-06T15:00:00+03:00"
        first = parse_document(document)
        second = parse_document(respelled)
        self.assertEqual(first.content_sha256, second.content_sha256)
        self.assertEqual(first.canonical, second.canonical)

    def test_04_unknown_types_attributes_marks_and_html_are_rejected(self):
        base = full_document()
        cases = [
            ("unknown_block_type",
             lambda d: d["content"].append({"type": "iframe",
                                            "attrs": {"block_id": str(uuid4())}})),
            ("unknown_block_type_html",
             lambda d: d["content"].append({"type": "html_block",
                                            "attrs": {"block_id": str(uuid4()),
                                                      "html": "<script>x</script>"}})),
            ("unknown_attribute",
             lambda d: d["content"][0]["attrs"].update({"owner_id": str(uuid4())})),
            ("unknown_node_field",
             lambda d: d["content"][0].update({"src": "https://evil.example/img"})),
            ("unknown_mark",
             lambda d: d["content"][0].update({"content": [
                 text_node("x", marks=[{"type": "underline"}])]})),
            ("javascript_link",
             lambda d: d["content"][0].update({"content": [
                 text_node("x", marks=[{"type": "link",
                                        "attrs": {"href": "javascript:alert(1)"}}])]})),
            ("credentials_in_link",
             lambda d: d["content"][0].update({"content": [
                 text_node("x", marks=[{"type": "link",
                                        "attrs": {"href": "https://user:pw@example.com"}}])]})),
            ("unsupported_schema_version",
             lambda d: d.update({"schema_version": SCHEMA_VERSION + 1})),
            ("unknown_root_field",
             lambda d: d.update({"owner_id": str(uuid4())})),
            ("content_on_divider",
             lambda d: d["content"][7].update({"content": [paragraph_node("x")]})),
            ("heading_level_out_of_range",
             lambda d: d["content"][1]["attrs"].update({"level": 4})),
        ]
        for name, mutation in cases:
            with self.subTest(case=name):
                document = copy.deepcopy(base)
                mutation(document)
                with self.assertRaises(DocumentSchemaError):
                    parse_document(document)

    def test_05_duplicate_identifiers_are_rejected(self):
        base = full_document()
        duplicate_block = copy.deepcopy(base)
        duplicate_block["content"][0]["attrs"]["block_id"] = \
            base["content"][1]["attrs"]["block_id"]
        with self.assertRaises(DocumentSchemaError):
            parse_document(duplicate_block)
        duplicate_insight = copy.deepcopy(base)
        duplicate_insight["content"].append(
            insight_attrs(insight_id=base["content"][4]["attrs"]["insight_id"]))
        with self.assertRaises(DocumentSchemaError):
            parse_document(duplicate_insight)

    def test_06_dangling_same_document_links_are_rejected(self):
        base = full_document()
        dangling_evidence = copy.deepcopy(base)
        dangling_evidence["content"][5]["attrs"]["hypothesis_id"] = str(uuid4())
        with self.assertRaises(ReferenceInvalid):
            parse_document(dangling_evidence)
        dangling_insight_link = copy.deepcopy(base)
        dangling_insight_link["content"][4]["attrs"]["hypothesis_id"] = str(uuid4())
        with self.assertRaises(ReferenceInvalid):
            parse_document(dangling_insight_link)
        dangling_risk_link = copy.deepcopy(base)
        dangling_risk_link["content"][6]["attrs"]["related_hypothesis_id"] = str(uuid4())
        with self.assertRaises(ReferenceInvalid):
            parse_document(dangling_risk_link)
        dangling_target = copy.deepcopy(base)
        dangling_target["content"][5]["attrs"]["target_id"] = str(uuid4())
        with self.assertRaises(ReferenceInvalid):
            parse_document(dangling_target)
        # An evidence block whose only hypothesis was removed dangles too.
        removed_hypothesis = copy.deepcopy(base)
        removed_hypothesis["content"].pop(3)
        with self.assertRaises(ReferenceInvalid):
            parse_document(removed_hypothesis)

    def test_07_size_limits_are_enforced(self):
        with self.assertRaises(DocumentTooLarge):
            parse_document({"schema_version": SCHEMA_VERSION, "type": "doc",
                            "content": [block("divider")
                                        for _ in range(MAX_TOP_LEVEL_BLOCKS + 1)]})
        wide = {"schema_version": SCHEMA_VERSION, "type": "doc", "content": [
            {"type": "paragraph", "attrs": {"block_id": str(uuid4())},
             "content": [text_node("x" * 19_000)]} for _ in range(120)]}
        with self.assertRaises(DocumentTooLarge):
            parse_document(wide)
        document = full_document()
        document["content"].append(data_table_attrs(**{
            "columns": [{"key": f"c{index}", "label": f"C{index}", "type": "string"}
                        for index in range(10)],
            "rows": [["v"] * 10 for _ in range(101)]}))
        with self.assertRaises(DocumentSchemaError):
            parse_document(document)
        long_body = copy.deepcopy(full_document())
        long_body["content"][4]["attrs"]["body"] = [
            paragraph_node("y" * 10_001)]
        with self.assertRaises(DocumentSchemaError):
            parse_document(long_body)
        deep = copy.deepcopy(full_document())
        deep["content"][4]["attrs"]["body"] = [
            {"type": "bullet_list", "content": [
                {"type": "list_item", "content": [
                    paragraph_node("1"),
                    {"type": "bullet_list", "content": [
                        {"type": "list_item", "content": [
                            paragraph_node("2"),
                            {"type": "bullet_list", "content": [
                                {"type": "list_item", "content": [
                                    paragraph_node("3"),
                                    {"type": "bullet_list", "content": [
                                        {"type": "list_item", "content": [
                                            paragraph_node("4")]}]}]}]}]}]}]}]}]
        with self.assertRaises(DocumentSchemaError):
            parse_document(deep)  # list nesting depth 4 > 3

    def test_08_chart_and_structural_rules(self):
        base = full_document()
        missing_snapshot = copy.deepcopy(base)
        missing_snapshot["content"].append(block(
            "liveChart", chart_definition_version_id=str(uuid4()), mode="snapshot",
            selection=copy.deepcopy(SELECTION),
            observed_dataset_version_id=str(uuid4())))
        with self.assertRaises(DocumentSchemaError):
            parse_document(missing_snapshot)
        live_with_snapshot = copy.deepcopy(base)
        live_with_snapshot["content"].append(block(
            "liveChart", chart_definition_version_id=str(uuid4()), mode="live",
            selection=copy.deepcopy(SELECTION),
            observed_dataset_version_id=str(uuid4()), snapshot_id=str(uuid4())))
        with self.assertRaises(DocumentSchemaError):
            parse_document(live_with_snapshot)
        rows_and_reference = copy.deepcopy(base)
        both = data_table_attrs()
        both["attrs"]["dataset_version_id"] = str(uuid4())  # rows AND a reference
        rows_and_reference["content"].append(both)
        with self.assertRaises(DocumentSchemaError):
            parse_document(rows_and_reference)
        object_cell = copy.deepcopy(base)
        object_cell["content"].append(data_table_attrs(
            columns=[{"key": "a", "label": "A", "type": "string"}],
            rows=[[{"formula": "=1+1"}]]))
        with self.assertRaises(DocumentSchemaError):
            parse_document(object_cell)
        filtered_context = copy.deepcopy(base)
        filtered_context["content"][4]["attrs"]["context"] = {
            **resolved_context(),
            "selection": {**SELECTION, "filters": {"country": "x"}}}
        with self.assertRaises(DocumentSchemaError):
            parse_document(filtered_context)
        model_context = copy.deepcopy(base)
        model_context["content"][4]["attrs"]["context"] = {
            "model_run_id": str(uuid4()), "dataset_version_id": str(uuid4()),
            "specification_version": "spec-1", "context_hash": SHA256}
        parsed = parse_document(model_context)
        self.assertEqual(len(parsed.insights), 1)


class DocumentRouteContractTests(unittest.TestCase):
    """Offline HTTP failure behavior; no database required."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_01_document_routes_are_documented_in_openapi(self):
        schema = self.client.get("/openapi.json").json()
        # The contract grows with implemented routes (NI-032 public delivery,
        # NI-054 public model routes, NI-041 chart-block insertion).
        self.assertEqual(set(schema["paths"]), {
            "/health", "/api/home", "/api/me",
                "/api/saved-charts", "/api/saved-charts/{instance_id}",
            "/api/documents", "/api/documents/{document_id}",
            "/api/documents/{document_id}/versions",
            "/api/documents/{document_id}/versions/{version_id}",
            "/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/view",
            "/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/csv",
            "/api/documents/{document_id}/chart-blocks",
            "/api/documents/{document_id}/chart-view",
            "/api/documents/{document_id}/exports",
            "/api/documents/{document_id}/exports/{job_id}",
            "/api/documents/{document_id}/exports/{job_id}/download",
            "/api/documents/{document_id}/integrity",
            "/api/documents/{document_id}/grounded-commentary",
            "/api/documents/{document_id}/insights",
            "/api/documents/{document_id}/insights/{insight_id}",
            "/api/documents/{document_id}/hypotheses",
            "/api/documents/{document_id}/hypotheses/{hypothesis_id}",
            "/api/documents/{document_id}/evidence",
            "/api/documents/{document_id}/evidence/{evidence_id}",
            "/api/documents/{document_id}/evidence-targets",
            "/api/metrics", "/api/metrics/{metric_id}",
            "/api/metrics/{metric_id}/series",
            "/api/charts", "/api/charts/{chart_id}", "/api/charts/{chart_id}/view",
            "/api/data-sources", "/api/data-sources/{source_id}",
            "/api/datasets/{version_id}", "/api/datasets/{version_id}/manifest",
            "/api/model-definitions", "/api/model-definitions/{model_id}",
            "/api/model-definitions/{model_id}/readiness",
            "/api/model-runs", "/api/model-runs/{run_id}",
            "/api/model-runs/{run_id}/manifest",
        })
        self.assertEqual(schema["paths"]["/api/documents"]["post"]["operationId"],
                         "createDocument")
        # NI-037 CRUD rows: rename/delete on the document, version list/detail.
        document_path = schema["paths"]["/api/documents/{document_id}"]
        self.assertEqual(set(document_path), {"get", "patch", "delete"})
        self.assertEqual(document_path["patch"]["operationId"], "renameDocument")
        self.assertEqual(document_path["delete"]["operationId"], "deleteDocument")
        versions_path = schema["paths"]["/api/documents/{document_id}/versions"]
        self.assertEqual(versions_path["get"]["operationId"], "listDocumentVersions")
        self.assertEqual(versions_path["post"]["operationId"], "saveDocumentVersion")
        self.assertEqual(
            schema["paths"]["/api/documents/{document_id}/versions/{version_id}"]["get"]
            ["operationId"], "getDocumentVersion")
        # NI-041 insertion row: MutationResult<{block_id}> contract.
        chart_view_path = schema["paths"]["/api/documents/{document_id}/chart-view"]
        self.assertEqual(set(chart_view_path), {"get"})
        inspection = chart_view_path["get"]
        self.assertEqual(inspection["operationId"], "getDocumentChartView")
        query = {item["name"]: item for item in inspection["parameters"]
                 if item["in"] == "query"}
        self.assertEqual(set(query), {"chart_definition_version_id", "start", "end",
                                      "dataset_version", "filters"})
        self.assertTrue(query["dataset_version"]["required"])
        self.assertTrue(all(query[key]["required"] for key in
                            ("chart_definition_version_id", "start", "end")))
        self.assertEqual(inspection["responses"]["200"]["content"]["application/json"]
                         ["schema"]["$ref"], "#/components/schemas/DocumentChartViewResponse")
        chart_blocks_path = schema["paths"]["/api/documents/{document_id}/chart-blocks"]
        self.assertEqual(set(chart_blocks_path), {"post"})
        self.assertEqual(chart_blocks_path["post"]["operationId"], "addChartBlock")
        self.assertEqual(
            chart_blocks_path["post"]["requestBody"]["content"]["application/json"]
            ["schema"],
            {"$ref": "#/components/schemas/ChartBlockInsertRequest"})
        self.assertEqual(
            chart_blocks_path["post"]["responses"]["201"]["content"]["application/json"]
            ["schema"],
            {"$ref": "#/components/schemas/ChartBlockMutationResponse"})
        # NI-058 export rows: create/poll/download live inside the document's
        # owned namespace so ownership resolves through ONE compositional chain.
        exports_path = schema["paths"]["/api/documents/{document_id}/exports"]
        self.assertEqual(set(exports_path), {"post"})
        self.assertEqual(exports_path["post"]["operationId"], "createDocumentExport")
        self.assertEqual(exports_path["post"]["responses"]["202"]["content"]
                         ["application/json"]["schema"],
                         {"$ref": "#/components/schemas/ExportJobResponse"})
        export_job_path = schema["paths"]["/api/documents/{document_id}/exports/{job_id}"]
        self.assertEqual(set(export_job_path), {"get"})
        self.assertEqual(export_job_path["get"]["operationId"], "getDocumentExport")
        export_download_path = schema["paths"][
            "/api/documents/{document_id}/exports/{job_id}/download"]
        self.assertEqual(set(export_download_path), {"get"})
        self.assertEqual(export_download_path["get"]["operationId"],
                         "downloadDocumentExport")
        for component in ("DocumentExportRequest", "ExportJobResponse"):
            self.assertIn(component, schema["components"]["schemas"])
        for component in ("DocumentRenameRequest", "VersionListResponse",
                          "VersionDetailResponse", "VersionSummaryResponse",
                          "ChartBlockInsertRequest", "ChartBlockMutationResponse",
                          "ChartBlockValue"):
            self.assertIn(component, schema["components"]["schemas"])
        self.assertIn("DocumentResponse", schema["components"]["schemas"])
        self.assertIn("DocumentSaveResponse", schema["components"]["schemas"])

    def test_02_private_document_routes_require_a_verified_session(self):
        for method, path, payload in (
            ("get", "/api/documents", None),
            ("post", "/api/documents", {"title": "Synthetic"}),
            ("get", f"/api/documents/{uuid4()}", None),
            ("patch", f"/api/documents/{uuid4()}", {"title": "Synthetic"}),
            ("delete", f"/api/documents/{uuid4()}", None),
            ("get", f"/api/documents/{uuid4()}/versions", None),
            ("get", f"/api/documents/{uuid4()}/versions/{uuid4()}", None),
            ("post", f"/api/documents/{uuid4()}/versions",
             {"schema_version": 1, "content": empty_document()}),
            ("post", f"/api/documents/{uuid4()}/chart-blocks",
             {"chart_definition_version_id": str(uuid4()),
              "selection": {"start": "2025-01-01", "end": "2025-01-08",
                            "frequency": "day", "filters": {}},
              "mode": "live", "dataset_version_id": str(uuid4())}),
            ("post", f"/api/documents/{uuid4()}/exports",
             {"document_version_id": str(uuid4()), "format": "markdown_zip"}),
            ("get", f"/api/documents/{uuid4()}/exports/{uuid4()}", None),
            ("get", f"/api/documents/{uuid4()}/exports/{uuid4()}/download", None),
            ("get", f"/api/documents/{uuid4()}/hypotheses", None),
            ("post", f"/api/documents/{uuid4()}/hypotheses",
             {"block_id": str(uuid4()), "statement": "Synthetic question", "assessment": "untested"}),
            ("patch", f"/api/documents/{uuid4()}/hypotheses/{uuid4()}", {"assessment": "mixed"}),
            ("delete", f"/api/documents/{uuid4()}/hypotheses/{uuid4()}", {"remove_evidence_links": True}),
            ("get", f"/api/documents/{uuid4()}/evidence", None),
            ("get", f"/api/documents/{uuid4()}/evidence-targets?target_kind=citation", None),
            ("post", f"/api/documents/{uuid4()}/evidence", {}),
            ("patch", f"/api/documents/{uuid4()}/evidence/{uuid4()}", {"classification": "uncertain"}),
            ("delete", f"/api/documents/{uuid4()}/evidence/{uuid4()}", None),
        ):
            with self.subTest(method=method):
                response = self.client.request(method, path, json=payload) \
                    if payload is not None else self.client.request(method, path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(ErrorResponse.model_validate(response.json()).error.code,
                                 "AUTHENTICATION_REQUIRED")
                self.assertEqual(response.headers["Cache-Control"], "no-store")


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class DocumentServiceDatabaseTests(unittest.TestCase):
    """Revision service guarantees on the disposable PostgreSQL cluster."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.engine = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.engine_b = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")
        cls.seed_insight_context()

    @classmethod
    def seed_insight_context(cls):
        chart_fixtures.register_test_chart_catalog(cls.operator)
        dataset_id = chart_fixtures.ChartBlockDatabaseFixture.insert_dataset_version(
            cls, f"synthetic.{uuid4().hex[:8]}.document-notes")
        cls.insight_context = chart_fixtures.volume_context(cls.operator, dataset_id)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.engine_b.dispose()
        cls.operator.dispose()
        cls.admin.dispose()

    def setUp(self):
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))
        self.alice_id, self.bob_id = uuid4(), uuid4()
        for subject, name in ((self.alice_id, "Synthetic Alice"),
                              (self.bob_id, "Synthetic Bob")):
            with user_transaction(self.engine, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"),
                                   {"id": subject})
                connection.execute(text("""INSERT INTO app.user_profiles(user_id, display_name)
                                          VALUES (:id, :name)"""), {"id": subject, "name": name})
        self.alice = Principal(id=self.alice_id, display_name="Synthetic Alice",
                               display_timezone="UTC")
        self.bob = Principal(id=self.bob_id, display_name="Synthetic Bob",
                             display_timezone="UTC")
        self.client = TestClient(app, raise_server_exceptions=False)

    # -- helpers ------------------------------------------------------------ #

    def full_document(self) -> dict:
        return full_document(insight_context=copy.deepcopy(self.insight_context))

    def as_session(self, subject):
        """HTTP calls run the real dependency chain with a stubbed verifier."""
        verifier = _StubVerifier(_verified(subject))
        context = ExitStack()
        context.enter_context(patch.object(principal_module, "_get_verifier",
                                           return_value=verifier))
        context.enter_context(patch.object(principal_module, "_get_engine",
                                           return_value=self.engine))
        return context

    def create_document(self, principal: Principal, title: str = "Synthetic document"):
        return service.create_document(self.engine, principal, title=title)

    def table_counts(self, document_id: UUID) -> dict:
        with self.admin.connect() as connection:
            return {
                table: connection.scalar(text(
                    f"SELECT count(*) FROM app.{table} WHERE document_id = :id"),
                    {"id": document_id})
                for table in ("document_versions", "document_blocks", "insights",
                              "hypotheses", "evidence_links")
            }

    def projection_rows(self, document_id: UUID, version_id: UUID) -> dict:
        with user_transaction(self.engine, self.alice_id) as connection:
            blocks = connection.execute(text(
                "SELECT block_id, position, block_type, parent_block_id, attrs "
                "FROM app.document_blocks WHERE document_version_id = :v "
                "ORDER BY position"), {"v": version_id}).mappings().all()
            insights = connection.execute(text(
                "SELECT insight_id, block_id, type, classification, body, context, "
                "authored_at, modified_at, hypothesis_id FROM app.insights "
                "WHERE document_version_id = :v"), {"v": version_id}).mappings().all()
            hypotheses = connection.execute(text(
                "SELECT hypothesis_id, block_id, statement, assessment, authored_at, "
                "modified_at FROM app.hypotheses WHERE document_version_id = :v"),
                {"v": version_id}).mappings().all()
            evidence = connection.execute(text(
                "SELECT evidence_id, block_id, hypothesis_id, classification, "
                "target_kind, target_id, explanation FROM app.evidence_links "
                "WHERE document_version_id = :v"), {"v": version_id}).mappings().all()
        return {"blocks": list(map(dict, blocks)), "insights": list(map(dict, insights)),
                "hypotheses": list(map(dict, hypotheses)),
                "evidence": list(map(dict, evidence))}

    def insert_dataset_version(self, dataset_key: str, status: str = "approved") -> UUID:
        """Synthetic dataset version fixture (no research data, no pipeline)."""
        dataset_id = uuid4()
        artifact_id = uuid4()
        with self.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size,
                       media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/json', 'internal', NULL, 'unverified')
            """), {"id": artifact_id, "key": f"synthetic/{dataset_id}.json",
                   "sha": SHA256})
            connection.execute(text("""
                INSERT INTO app.dataset_versions(id, dataset_key, version, status,
                       start_date, end_date, frequency, pipeline_version,
                       manifest_artifact_id, content_sha256)
                VALUES (:id, :key, 1, :status, '2025-01-01', '2025-02-01', 'daily',
                        'synthetic-pipeline-1', :artifact, :sha)
            """), {"id": dataset_id, "key": dataset_key, "status": status,
                   "artifact": artifact_id, "sha": SHA256})
        return dataset_id

    def insert_artifact(self, scope: str) -> UUID:
        artifact_id = uuid4()
        with self.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size,
                       media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/pdf', :scope, NULL, 'unverified')
            """), {"id": artifact_id, "key": f"synthetic/{artifact_id}.pdf",
                   "sha": SHA256, "scope": scope})
        return artifact_id

    # -- lifecycle ------------------------------------------------------------ #

    def test_01_create_starts_with_one_empty_revision_and_etag(self):
        detail = self.create_document(self.alice, "Synthetic first")
        self.assertEqual(detail.document.revision, 1)
        self.assertEqual(detail.document.current_version_id, detail.version.id)
        self.assertEqual(detail.content, empty_document())
        self.assertEqual(detail.version.content_sha256,
                         parse_document(empty_document()).content_sha256)
        self.assertEqual(detail.version.revision, 1)
        counts = self.table_counts(detail.document.id)
        self.assertEqual(counts, {"document_versions": 1, "document_blocks": 0,
                                  "insights": 0, "hypotheses": 0, "evidence_links": 0})

    def test_02_save_appends_immutable_revision_and_advances_pointer(self):
        detail = self.create_document(self.alice)
        first_content = detail.version.content
        first_hash = detail.version.content_sha256
        saved = service.save_revision(
            self.engine, self.alice, detail.document.id,
            expected_revision=1, document_payload=self.full_document())
        self.assertEqual(saved.document.revision, 2)
        self.assertEqual(saved.document.current_version_id, saved.version.id)
        self.assertEqual(saved.version.revision, 2)
        self.assertNotEqual(saved.version.id, detail.version.id)
        counts = self.table_counts(detail.document.id)
        self.assertEqual(counts["document_versions"], 2)
        self.assertEqual(counts["document_blocks"], 9)
        # The old revision is byte-for-byte intact.
        with user_transaction(self.engine, self.alice_id) as connection:
            old = connection.execute(text(
                "SELECT content, content_sha256, revision FROM app.document_versions "
                "WHERE id = :id"), {"id": detail.version.id}).mappings().one()
        self.assertEqual(old["content"], first_content)
        self.assertEqual(old["content_sha256"], first_hash)
        self.assertEqual(old["revision"], 1)
        # Old revisions are immutable for the runtime role (no UPDATE grant/policy).
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, self.alice_id) as connection:
                connection.execute(text(
                    "UPDATE app.document_versions SET content = '{}'::jsonb "
                    "WHERE id = :id"), {"id": detail.version.id})
        self.assertEqual(raised.exception.orig.sqlstate, "42501")

    def test_03_invalid_content_creates_zero_rows(self):
        detail = self.create_document(self.alice)
        before = self.table_counts(detail.document.id)
        pointer = detail.document.current_version_id
        revision = detail.document.revision
        duplicated_id = str(uuid4())
        invalid_payloads = {
            "unknown_block_type": {"schema_version": SCHEMA_VERSION, "type": "doc",
                                   "content": [{"type": "codeBlock",
                                                "attrs": {"block_id": str(uuid4())}}]},
            "duplicate_block_id": {"schema_version": SCHEMA_VERSION, "type": "doc",
                                   "content": [block("divider"),
                                               block("divider", block_id=duplicated_id)]},
            "dangling_evidence": None,
            "oversize": {"schema_version": SCHEMA_VERSION, "type": "doc",
                         "content": [block("divider")
                                     for _ in range(MAX_TOP_LEVEL_BLOCKS + 1)]},
        }
        dangling = self.full_document()
        dangling["content"][5]["attrs"]["hypothesis_id"] = str(uuid4())
        invalid_payloads["dangling_evidence"] = dangling
        for name, payload in invalid_payloads.items():
            with self.subTest(case=name):
                with self.assertRaises((DocumentSchemaError, DocumentTooLarge,
                                        ReferenceInvalid)):
                    service.save_revision(self.engine, self.alice, detail.document.id,
                                          expected_revision=revision,
                                          document_payload=payload["content"])
        # A simulated crash mid-save is equally row-free.
        with patch("near_api.documents.service.write_projections",
                   side_effect=RuntimeError("simulated crash during projections")):
            with self.assertRaises(RuntimeError):
                service.save_revision(self.engine, self.alice, detail.document.id,
                                      expected_revision=revision,
                                      document_payload=self.full_document())
        self.assertEqual(self.table_counts(detail.document.id), before)
        with user_transaction(self.engine, self.alice_id) as connection:
            row = connection.execute(text(
                "SELECT revision, current_version_id FROM app.documents WHERE id = :id"),
                {"id": detail.document.id}).one()
        self.assertEqual((row[0], row[1]), (revision, pointer))

    def test_04_revision_content_hash_matches_canonical_bytes(self):
        document = self.full_document()
        detail = self.create_document(self.alice)
        saved = service.save_revision(self.engine, self.alice, detail.document.id,
                                      expected_revision=1, document_payload=document)
        expected = hashlib.sha256(canonical_bytes(parse_document(saved.content).canonical)).hexdigest()
        self.assertEqual(saved.version.content_sha256, expected)
        # Resaving identical content creates a new immutable revision with the
        # same hash (no deduplication of revision history).
        again = service.save_revision(self.engine, self.alice, detail.document.id,
                                      expected_revision=2, document_payload=document)
        self.assertEqual(again.version.content_sha256, expected)
        self.assertNotEqual(again.version.id, saved.version.id)

    def test_05_concurrent_cas_race_admits_exactly_one_writer(self):
        detail = self.create_document(self.alice)
        payload_a = self.full_document()
        payload_b = empty_document()
        barrier = threading.Barrier(2)
        results: dict[int, object] = {}

        def worker(index: int, payload: dict, engine):
            barrier.wait()
            try:
                results[index] = service.save_revision(
                    engine, self.alice, detail.document.id,
                    expected_revision=1, document_payload=payload)
            except Exception as error:  # honest failure is the expected 409 path
                results[index] = error

        threads = [threading.Thread(target=worker, args=(0, payload_a, self.engine)),
                   threading.Thread(target=worker, args=(1, payload_b, self.engine_b))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        outcomes = list(results.values())
        conflicts = [item for item in outcomes if isinstance(item, service.RevisionConflict)]
        wins = [item for item in outcomes if not isinstance(item, Exception)]
        self.assertEqual(len(conflicts), 1, f"exactly one loser: {outcomes!r}")
        self.assertEqual(len(wins), 1, f"exactly one winner: {outcomes!r}")
        self.assertEqual(conflicts[0].current_revision, 2)
        with user_transaction(self.engine, self.alice_id) as connection:
            document = connection.execute(text(
                "SELECT revision, current_version_id FROM app.documents WHERE id = :id"),
                {"id": detail.document.id}).one()
            version_count = connection.scalar(text(
                "SELECT count(*) FROM app.document_versions WHERE document_id = :id"),
                {"id": detail.document.id})
            winner_versions = connection.execute(text(
                "SELECT revision FROM app.document_versions WHERE document_id = :id "
                "ORDER BY revision"), {"id": detail.document.id}).scalars().all()
        self.assertEqual(document[0], 2)
        self.assertEqual(version_count, 2)
        self.assertEqual(winner_versions, [1, 2])
        # The winner's content is the stored current version.
        winner = wins[0]
        self.assertEqual(winner.version.id, document[1])

    def test_06_projection_round_trip_matches_canonical_content(self):
        document = self.full_document()
        document["content"][4]["attrs"]["body"] = [
            paragraph_node("Observation body"),
            {"type": "ordered_list", "content": [
                {"type": "list_item", "content": [
                    paragraph_node("first"),
                    {"type": "bullet_list", "content": [
                        {"type": "list_item", "content": [paragraph_node("deep")]}]}]}]}]
        detail = self.create_document(self.alice)
        saved = service.save_revision(self.engine, self.alice, detail.document.id,
                                      expected_revision=1, document_payload=document)
        stored = self.projection_rows(detail.document.id, saved.version.id)
        regenerated = build_projections(parse_document(saved.content))
        self.assertEqual([row["block_id"] for row in stored["blocks"]],
                         [item.block_id for item in regenerated.blocks])
        self.assertEqual([row["position"] for row in stored["blocks"]],
                         [item.position for item in regenerated.blocks])
        self.assertEqual([row["block_type"] for row in stored["blocks"]],
                         [item.block_type for item in regenerated.blocks])
        for row, item in zip(stored["blocks"], regenerated.blocks):
            self.assertEqual(row["attrs"], item.attrs)
            self.assertIsNone(row["parent_block_id"])
        self.assertEqual({row["insight_id"] for row in stored["insights"]},
                         {item.insight_id for item in regenerated.insights})
        for row, item in zip(sorted(stored["insights"],
                                    key=lambda entry: entry["insight_id"]),
                             sorted(regenerated.insights,
                                    key=lambda entry: entry.insight_id)):
            self.assertEqual(row["body"], item.body)
            self.assertEqual(row["context"], item.context)
            self.assertEqual(row["authored_at"],
                             datetime.fromisoformat(item.authored_at))
            self.assertEqual(row["modified_at"],
                             datetime.fromisoformat(item.modified_at))
        self.assertEqual({row["hypothesis_id"] for row in stored["hypotheses"]},
                         {item.hypothesis_id for item in regenerated.hypotheses})
        for row, item in zip(sorted(stored["hypotheses"],
                                    key=lambda entry: entry["hypothesis_id"]),
                             sorted(regenerated.hypotheses,
                                    key=lambda entry: entry.hypothesis_id)):
            self.assertEqual(row["statement"], item.statement)
            self.assertEqual(row["assessment"], item.assessment)
        self.assertEqual({row["evidence_id"] for row in stored["evidence"]},
                         {item.evidence_id for item in regenerated.evidence})
        for row, item in zip(sorted(stored["evidence"],
                                    key=lambda entry: entry["evidence_id"]),
                             sorted(regenerated.evidence,
                                    key=lambda entry: entry.evidence_id)):
            self.assertEqual(row["target_kind"], item.target_kind)
            self.assertEqual(row["target_id"], item.target_id)
            self.assertEqual(row["explanation"], item.explanation)
        # Re-parsing the stored content reproduces the recorded hash exactly.
        self.assertEqual(parse_document(saved.content).content_sha256,
                         saved.version.content_sha256)

    def test_07_database_backed_reference_rules(self):
        approved = self.insert_dataset_version(f"synthetic-approved-{uuid4().hex[:8]}")
        staged = self.insert_dataset_version(f"synthetic-staged-{uuid4().hex[:8]}",
                                             status="staged")
        document = self.full_document()
        table_reference = data_table_attrs(dataset_version_id=str(approved))
        document["content"].append(table_reference)
        detail = self.create_document(self.alice)
        saved = service.save_revision(self.engine, self.alice, detail.document.id,
                                      expected_revision=1, document_payload=document)
        self.assertEqual(saved.document.revision, 2)
        # A staged (not public/approved) dataset is not referenceable.
        document["content"][-1] = data_table_attrs(dataset_version_id=str(staged))
        with self.assertRaises(ReferenceInvalid):
            service.save_revision(self.engine, self.alice, detail.document.id,
                                  expected_revision=2, document_payload=document)
        # A nonexistent dataset dangles.
        document["content"][-1] = data_table_attrs(dataset_version_id=str(uuid4()))
        with self.assertRaises(ReferenceInvalid):
            service.save_revision(self.engine, self.alice, detail.document.id,
                                  expected_revision=2, document_payload=document)
        # Restore the valid table reference for the citation cases below.
        document["content"][-1] = data_table_attrs(dataset_version_id=str(approved))
        # Citation evidence requires a public immutable artifact.
        internal_artifact = self.insert_artifact("internal")
        public_artifact = self.insert_artifact("public")
        hypothesis_id = document["content"][3]["attrs"]["hypothesis_id"]
        citation_internal = evidence_attrs(hypothesis_id, "citation",
                                           str(internal_artifact))
        document["content"].append(citation_internal)
        with self.assertRaises(ReferenceInvalid):
            service.save_revision(self.engine, self.alice, detail.document.id,
                                  expected_revision=2, document_payload=document)
        document["content"][-1] = evidence_attrs(hypothesis_id, "citation",
                                                 str(public_artifact))
        saved = service.save_revision(self.engine, self.alice, detail.document.id,
                                      expected_revision=2, document_payload=document)
        self.assertEqual(saved.document.revision, 3)
        # A model run absent from the published registry is not referenceable.
        model_run_evidence = evidence_attrs(hypothesis_id, "model_run", str(uuid4()))
        document["content"].append(model_run_evidence)
        with self.assertRaises(ReferenceInvalid):
            service.save_revision(self.engine, self.alice, detail.document.id,
                                  expected_revision=3, document_payload=document)
        # Chart blocks are gated until the chart definition registry lands.
        document["content"].pop()
        document["content"].append(block(
            "liveChart", chart_definition_version_id=str(uuid4()), mode="live",
            selection=copy.deepcopy(SELECTION),
            observed_dataset_version_id=str(approved)))
        with self.assertRaises(ReferenceInvalid):
            service.save_revision(self.engine, self.alice, detail.document.id,
                                  expected_revision=3, document_payload=document)

    def test_08_owner_isolation_between_alice_and_bob(self):
        detail = self.create_document(self.alice, "Alice synthetic")
        saved = service.save_revision(self.engine, self.alice, detail.document.id,
                                      expected_revision=1,
                                      document_payload=self.full_document())
        with self.assertRaises(ResourceNotFound):
            service.get_document_detail(self.engine, self.bob, detail.document.id)
        with self.assertRaises(ResourceNotFound):
            service.save_revision(self.engine, self.bob, detail.document.id,
                                  expected_revision=2,
                                  document_payload=empty_document())
        alice_page = service.list_document_details(self.engine, self.alice)
        bob_page = service.list_document_details(self.engine, self.bob)
        self.assertEqual([item.id for item in alice_page.items], [detail.document.id])
        self.assertEqual(bob_page.items, ())
        # A foreign insight id is simply not part of Bob's document: the
        # same-document rule rejects it without revealing the other document.
        bob_document = self.create_document(self.bob, "Bob synthetic")
        foreign_insight_id = saved.content["content"][4]["attrs"]["insight_id"]
        payload = {"schema_version": SCHEMA_VERSION, "type": "doc", "content": [
            hypothesis_attrs(),
            evidence_attrs(
                hypothesis_id=str(uuid4()), target_kind="insight",
                target_id=foreign_insight_id),
        ]}
        payload["content"][1]["attrs"]["hypothesis_id"] = \
            payload["content"][0]["attrs"]["hypothesis_id"]
        with self.assertRaises(ReferenceInvalid):
            service.save_revision(self.engine, self.bob, bob_document.document.id,
                                  expected_revision=1, document_payload=payload)
        # RLS: Bob's runtime transaction cannot see Alice's projection rows.
        with user_transaction(self.engine, self.bob_id) as connection:
            self.assertEqual(connection.scalar(text(
                "SELECT count(*) FROM app.insights WHERE document_id = :id"),
                {"id": detail.document.id}), 0)

    def test_09_http_save_matrix_cas_errors_and_isolation(self):
        alice_headers = {"Authorization": "Bearer t.alice"}
        with self.as_session(self.alice_id):
            created = self.client.post("/api/documents", json={"title": "Synthetic HTTP"},
                                       headers=alice_headers)
            self.assertEqual(created.status_code, 201)
            self.assertEqual(created.headers["Cache-Control"], "no-store")
            self.assertEqual(created.headers["ETag"], '"1"')
            body = created.json()
            self.assertEqual(body["revision"], 1)
            self.assertEqual(body["content"], empty_document())
            self.assertEqual(body["resolved_contexts"], {})
            document_id = body["id"]
            fetched = self.client.get(f"/api/documents/{document_id}",
                                      headers=alice_headers)
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.headers["ETag"], '"1"')
            listing = self.client.get("/api/documents", headers=alice_headers)
            self.assertEqual(listing.status_code, 200)
            self.assertEqual([item["id"] for item in listing.json()["items"]],
                             [document_id])
            self.assertIsNone(listing.json()["next_cursor"])
            # Missing If-Match is 428 before any validation side effect.
            missing = self.client.post(f"/api/documents/{document_id}/versions",
                                       json={"schema_version": SCHEMA_VERSION,
                                             "content": self.full_document()},
                                       headers=alice_headers)
            self.assertEqual(missing.status_code, 428)
            error = ErrorResponse.model_validate(missing.json())
            self.assertEqual(error.error.code, "PRECONDITION_REQUIRED")
            # Malformed If-Match is the same precondition failure.
            for header in ("", '"abc"', "W/\"1\"", "2"):
                with self.subTest(if_match=header):
                    malformed = self.client.post(
                        f"/api/documents/{document_id}/versions",
                        json={"schema_version": SCHEMA_VERSION,
                              "content": self.full_document()},
                        headers={"If-Match": header, **alice_headers})
                    self.assertEqual(malformed.status_code, 428)
            # Stale revision is 409 REVISION_CONFLICT with the current revision.
            stale = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": self.full_document()},
                headers={"If-Match": '"9"', **alice_headers})
            self.assertEqual(stale.status_code, 409)
            conflict = ErrorResponse.model_validate(stale.json())
            self.assertEqual(conflict.error.code, "REVISION_CONFLICT")
            self.assertIn("1", conflict.error.message)
            # A valid CAS save returns 201 with the new ETag and version detail.
            saved = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": self.full_document()},
                headers={"If-Match": '"1"', **alice_headers})
            self.assertEqual(saved.status_code, 201)
            self.assertEqual(saved.headers["ETag"], '"2"')
            save_body = saved.json()
            self.assertEqual(set(save_body), {"version", "document"})
            self.assertEqual(save_body["version"]["revision"], 2)
            self.assertEqual(save_body["version"]["document_id"], document_id)
            self.assertEqual(len(save_body["version"]["content_sha256"]), 64)
            self.assertEqual(save_body["document"]["revision"], 2)
            self.assertEqual(save_body["document"]["current_version_id"],
                             save_body["version"]["id"])
            # Invalid content is a typed 422 and leaves the document untouched.
            invalid = copy.deepcopy(self.full_document())
            invalid["content"].append({"type": "iframe",
                                       "attrs": {"block_id": str(uuid4())}})
            rejected = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": invalid},
                headers={"If-Match": '"2"', **alice_headers})
            self.assertEqual(rejected.status_code, 422)
            self.assertEqual(ErrorResponse.model_validate(rejected.json()).error.code,
                             "VALIDATION_ERROR")
            # Oversized content is 413.
            oversize = {"schema_version": SCHEMA_VERSION, "type": "doc",
                        "content": [{"type": "divider",
                                     "attrs": {"block_id": str(uuid4())}}
                                    for _ in range(MAX_TOP_LEVEL_BLOCKS + 1)]}
            oversized = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": oversize},
                headers={"If-Match": '"2"', **alice_headers})
            self.assertEqual(oversized.status_code, 413)
            # An observation with no matching chart is a typed reference failure.
            contexts = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION,
                      "content": empty_document(),
                      "observed_contexts": [resolved_context()]},
                headers={"If-Match": '"2"', **alice_headers})
            self.assertEqual(contexts.status_code, 422)
            self.assertEqual(ErrorResponse.model_validate(contexts.json()).error.code,
                             "REFERENCE_INVALID")
            # Template selection is feature-gated.
            template = self.client.post("/api/documents",
                                        json={"title": "T", "template_id": "investment-v1"},
                                        headers=alice_headers)
            self.assertEqual(template.status_code, 422)
            self.assertEqual(ErrorResponse.model_validate(template.json()).error.code,
                             "FEATURE_UNAVAILABLE")
            # Bob's session cannot see or save Alice's document.
        bob_headers = {"Authorization": "Bearer t.bob"}
        with self.as_session(self.bob_id):
            foreign = self.client.get(f"/api/documents/{document_id}",
                                      headers=bob_headers)
            self.assertEqual(foreign.status_code, 404)
            self.assertEqual(ErrorResponse.model_validate(foreign.json()).error.code,
                             "NOT_FOUND")
            foreign_save = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": empty_document()},
                headers={"If-Match": '"2"', **bob_headers})
            self.assertEqual(foreign_save.status_code, 404)
            bob_listing = self.client.get("/api/documents", headers=bob_headers)
            self.assertEqual(bob_listing.status_code, 200)
            self.assertEqual(bob_listing.json()["items"], [])
        # The rejected attempts created no rows.
        counts = self.table_counts(UUID(document_id))
        self.assertEqual(counts["document_versions"], 2)
        self.assertEqual(counts["document_blocks"], 9)

    def test_10_http_list_pagination_and_search(self):
        created = []
        alice_headers = {"Authorization": "Bearer t.alice"}
        for index in range(3):
            with self.as_session(self.alice_id):
                response = self.client.post(
                    "/api/documents", json={"title": f"Synthetic page {index}"},
                    headers=alice_headers)
            created.append(response.json()["id"])
        with self.as_session(self.alice_id):
            page_one = self.client.get("/api/documents", params={"limit": 2},
                                       headers=alice_headers)
            self.assertEqual(page_one.status_code, 200)
            payload = page_one.json()
            self.assertEqual(len(payload["items"]), 2)
            self.assertIsNotNone(payload["next_cursor"])
            page_two = self.client.get("/api/documents",
                                       params={"limit": 2,
                                               "cursor": payload["next_cursor"]},
                                       headers=alice_headers)
            self.assertEqual(page_two.status_code, 200)
            combined = [item["id"] for item in payload["items"]] + \
                       [item["id"] for item in page_two.json()["items"]]
            self.assertEqual(sorted(combined), sorted(created))
            self.assertIsNone(page_two.json()["next_cursor"])
            searched = self.client.get("/api/documents", params={"q": "page 1"},
                                       headers=alice_headers)
            self.assertEqual([item["id"] for item in searched.json()["items"]],
                             [created[1]])
            broken = self.client.get("/api/documents", params={"cursor": "%%%bad%%%"},
                                     headers=alice_headers)
            self.assertEqual(broken.status_code, 422)

    def test_11_projection_migration_round_trip(self):
        command.downgrade(self.config, "0004_dataset_staging")
        with self.admin.connect() as connection:
            self.assertIsNone(connection.scalar(text(
                "SELECT to_regclass('app.insights')")))
            self.assertIsNone(connection.scalar(text(
                "SELECT to_regclass('app.evidence_links')")))
        command.upgrade(self.config, "head")
        command.check(self.config)
        self.seed_insight_context()
        with self.admin.connect() as connection:
            names = connection.execute(text("""
                SELECT relname FROM pg_class c JOIN pg_namespace n
                  ON n.oid = c.relnamespace
                WHERE n.nspname = 'app'
                  AND relname IN ('insights', 'hypotheses', 'evidence_links')
            """)).scalars().all()
        self.assertEqual(sorted(names),
                         ["evidence_links", "hypotheses", "insights"])

    # -- NI-037: rename, delete, version list/detail, idempotency ------------ #

    def test_12_http_rename_creates_revision_noop_keeps_history(self):
        alice_headers = {"Authorization": "Bearer t.alice"}
        full_payload = self.full_document()
        with self.as_session(self.alice_id):
            created = self.client.post("/api/documents",
                                       json={"title": "Original title"},
                                       headers=alice_headers)
            document_id = created.json()["id"]
            saved = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": full_payload},
                headers={"If-Match": '"1"', **alice_headers})
            self.assertEqual(saved.status_code, 201)
            revision_two_id = saved.json()["version"]["id"]
            revision_two_sha = saved.json()["version"]["content_sha256"]
            revision_two_content = saved.json()["version"]["content"]
            # Missing If-Match is 428; malformed is the same precondition failure.
            missing = self.client.patch(f"/api/documents/{document_id}",
                                        json={"title": "Renamed"},
                                        headers=alice_headers)
            self.assertEqual(missing.status_code, 428)
            self.assertEqual(ErrorResponse.model_validate(missing.json()).error.code,
                             "PRECONDITION_REQUIRED")
            malformed = self.client.patch(
                f"/api/documents/{document_id}", json={"title": "Renamed"},
                headers={"If-Match": "2", **alice_headers})
            self.assertEqual(malformed.status_code, 428)
            # Stale revision is 409 without any change.
            stale = self.client.patch(
                f"/api/documents/{document_id}", json={"title": "Renamed"},
                headers={"If-Match": '"1"', **alice_headers})
            self.assertEqual(stale.status_code, 409)
            conflict = ErrorResponse.model_validate(stale.json())
            self.assertEqual(conflict.error.code, "REVISION_CONFLICT")
            self.assertIn("2", conflict.error.message)
            # A title change creates a full new revision: same content, new id.
            renamed = self.client.patch(
                f"/api/documents/{document_id}", json={"title": "Renamed title"},
                headers={"If-Match": '"2"', **alice_headers})
            self.assertEqual(renamed.status_code, 200)
            self.assertEqual(renamed.headers["ETag"], '"3"')
            self.assertEqual(renamed.headers["Cache-Control"], "no-store")
            body = renamed.json()
            self.assertEqual(body["title"], "Renamed title")
            self.assertEqual(body["revision"], 3)
            self.assertNotEqual(body["current_version_id"], revision_two_id)
            # The revision content is byte-identical; only the title moved.
            detail = self.client.get(
                f"/api/documents/{document_id}/versions/{body['current_version_id']}",
                headers=alice_headers)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["content_sha256"], revision_two_sha)
            self.assertEqual(detail.json()["content"], revision_two_content)
            # A PATCH without a title change is a no-op: no revision is created.
            noop = self.client.patch(
                f"/api/documents/{document_id}", json={"title": "Renamed title"},
                headers={"If-Match": '"3"', **alice_headers})
            self.assertEqual(noop.status_code, 200)
            self.assertEqual(noop.headers["ETag"], '"3"')
            self.assertEqual(noop.json()["current_version_id"],
                             body["current_version_id"])
            # Whitespace-only title is a typed validation error, not a rename.
            blank = self.client.patch(
                f"/api/documents/{document_id}", json={"title": "   "},
                headers={"If-Match": '"3"', **alice_headers})
            self.assertEqual(blank.status_code, 422)
            self.assertEqual(ErrorResponse.model_validate(blank.json()).error.code,
                             "VALIDATION_ERROR")
        # Bob cannot rename Alice's document (one generic 404).
        with self.as_session(self.bob_id):
            foreign = self.client.patch(
                f"/api/documents/{document_id}", json={"title": "Bob was here"},
                headers={"If-Match": '"3"',
                         "Authorization": "Bearer t.bob"})
            self.assertEqual(foreign.status_code, 404)
        counts = self.table_counts(UUID(document_id))
        # rev1 empty; rev2 full content; rev3 identical rename content. The
        # no-op and rejected attempts created no rows.
        self.assertEqual(counts, {"document_versions": 3, "document_blocks": 18,
                                  "insights": 2, "hypotheses": 2, "evidence_links": 2})

    def test_13_delete_cascades_children_and_retains_shared_scientific_data(self):
        dataset_id = self.insert_dataset_version("synthetic-delete-retention")
        content = self.full_document()
        content["content"][-1] = data_table_attrs(dataset_version_id=str(dataset_id))
        alice_headers = {"Authorization": "Bearer t.alice"}
        with self.as_session(self.alice_id):
            created = self.client.post("/api/documents", json={"title": "Doomed"},
                                       headers=alice_headers)
            document_id = UUID(created.json()["id"])
            saved = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": content},
                headers={"If-Match": '"1"', **alice_headers})
            self.assertEqual(saved.status_code, 201)
        before = self._scientific_counts(dataset_id)
        children_before = sum(self.table_counts(document_id).values())
        self.assertEqual(before, {"dataset_versions": 1, "manifest_artifacts": 1,
                                  "documents": 1})
        self.assertGreater(children_before, 0)
        # Missing/stale If-Match and a foreign session delete nothing.
        with self.as_session(self.alice_id):
            missing = self.client.delete(f"/api/documents/{document_id}",
                                         headers=alice_headers)
            self.assertEqual(missing.status_code, 428)
            stale = self.client.delete(f"/api/documents/{document_id}",
                                       headers={"If-Match": '"1"', **alice_headers})
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(ErrorResponse.model_validate(stale.json()).error.code,
                             "REVISION_CONFLICT")
        with self.as_session(self.bob_id):
            foreign = self.client.delete(f"/api/documents/{document_id}",
                                         headers={"If-Match": '"2"',
                                                  "Authorization": "Bearer t.bob"})
            self.assertEqual(foreign.status_code, 404)
        self.assertEqual(self._scientific_counts(dataset_id), before)
        self.assertEqual(sum(self.table_counts(document_id).values()), children_before)
        # The owner's delete is a 204 with no body; private children cascade.
        with self.as_session(self.alice_id):
            deleted = self.client.delete(f"/api/documents/{document_id}",
                                         headers={"If-Match": '"2"', **alice_headers})
            self.assertEqual(deleted.status_code, 204)
            self.assertEqual(deleted.content, b"")
            self.assertEqual(deleted.headers["Cache-Control"], "no-store")
            gone = self.client.get(f"/api/documents/{document_id}",
                                   headers=alice_headers)
            self.assertEqual(gone.status_code, 404)
            versions = self.client.get(f"/api/documents/{document_id}/versions",
                                       headers=alice_headers)
            self.assertEqual(versions.status_code, 404)
            repeat = self.client.delete(f"/api/documents/{document_id}",
                                        headers={"If-Match": '"2"', **alice_headers})
            self.assertEqual(repeat.status_code, 404)
        after = self._scientific_counts(dataset_id)
        self.assertEqual(after["dataset_versions"], 1)
        self.assertEqual(after["manifest_artifacts"], 1)
        self.assertEqual(after["documents"], 0)
        with self.admin.connect() as connection:
            remaining = connection.execute(text("""
                SELECT (SELECT count(*) FROM app.document_versions
                         WHERE document_id = :id) +
                       (SELECT count(*) FROM app.document_blocks
                         WHERE document_id = :id) +
                       (SELECT count(*) FROM app.insights
                         WHERE document_id = :id) +
                       (SELECT count(*) FROM app.hypotheses
                         WHERE document_id = :id) +
                       (SELECT count(*) FROM app.evidence_links
                         WHERE document_id = :id)
            """), {"id": document_id}).scalar_one()
        self.assertEqual(remaining, 0)

    def test_14_version_list_order_cursor_and_detail(self):
        alice_headers = {"Authorization": "Bearer t.alice"}
        with self.as_session(self.alice_id):
            created = self.client.post("/api/documents",
                                       json={"title": "Versioned"},
                                       headers=alice_headers)
            document_id = created.json()["id"]
            first_version_id = created.json()["current_version_id"]
            second_payload = self.full_document()
            for payload in (second_payload, empty_document()):
                saved = self.client.post(
                    f"/api/documents/{document_id}/versions",
                    json={"schema_version": SCHEMA_VERSION, "content": payload},
                    headers={"If-Match": '"1"' if payload is second_payload else '"2"',
                             **alice_headers})
                self.assertEqual(saved.status_code, 201)
            third_version_id = saved.json()["version"]["id"]
            page_one = self.client.get(f"/api/documents/{document_id}/versions",
                                       params={"limit": 2}, headers=alice_headers)
            self.assertEqual(page_one.status_code, 200)
            payload = page_one.json()
            self.assertEqual([item["revision"] for item in payload["items"]], [3, 2])
            self.assertIsNotNone(payload["next_cursor"])
            for item in payload["items"]:
                self.assertNotIn("content", item)
                self.assertNotIn("resolved_contexts", item)
                self.assertEqual(len(item["content_sha256"]), 64)
            page_two = self.client.get(
                f"/api/documents/{document_id}/versions",
                params={"limit": 2, "cursor": payload["next_cursor"]},
                headers=alice_headers)
            self.assertEqual([item["revision"] for item in page_two.json()["items"]],
                             [1])
            self.assertIsNone(page_two.json()["next_cursor"])
            broken = self.client.get(f"/api/documents/{document_id}/versions",
                                     params={"cursor": "%%%bad%%%"},
                                     headers=alice_headers)
            self.assertEqual(broken.status_code, 422)
            # Version detail returns the immutable canonical content.
            detail = self.client.get(
                f"/api/documents/{document_id}/versions/{first_version_id}",
                headers=alice_headers)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["content"], empty_document())
            self.assertEqual(detail.json()["revision"], 1)
            self.assertEqual(detail.json()["resolved_contexts"], {})
            second_detail = self.client.get(
                f"/api/documents/{document_id}/versions/{third_version_id}",
                headers=alice_headers)
            self.assertEqual(second_detail.json()["content"], empty_document())
        # A version id from another document never resolves (compositional 404).
        with self.as_session(self.alice_id):
            other = self.client.post("/api/documents", json={"title": "Other"},
                                     headers=alice_headers)
            other_id = other.json()["id"]
            cross = self.client.get(
                f"/api/documents/{other_id}/versions/{first_version_id}",
                headers=alice_headers)
            self.assertEqual(cross.status_code, 404)
        with self.as_session(self.bob_id):
            foreign_list = self.client.get(f"/api/documents/{document_id}/versions",
                                           headers={"Authorization": "Bearer t.bob"})
            self.assertEqual(foreign_list.status_code, 404)
            foreign_detail = self.client.get(
                f"/api/documents/{document_id}/versions/{first_version_id}",
                headers={"Authorization": "Bearer t.bob"})
            self.assertEqual(foreign_detail.status_code, 404)

    def test_15_http_idempotent_create_timeout_after_commit_replay(self):
        key = str(uuid4())
        alice_headers = {"Authorization": "Bearer t.alice", "Idempotency-Key": key}
        with self.as_session(self.alice_id):
            first = self.client.post("/api/documents",
                                     json={"title": "Idempotent create"},
                                     headers=alice_headers)
            self.assertEqual(first.status_code, 201)
            self.assertEqual(first.headers["ETag"], '"1"')
            # The response was "lost": the identical retry replays the ORIGINAL
            # result — same document, no second revision.
            retry = self.client.post("/api/documents",
                                     json={"title": "Idempotent create"},
                                     headers=alice_headers)
            self.assertEqual(retry.status_code, 201)
            self.assertEqual(retry.json(), first.json())
            self.assertEqual(retry.headers["ETag"], '"1"')
            counts = self.table_counts(UUID(first.json()["id"]))
            self.assertEqual(counts["document_versions"], 1)
            # A different body with the same key is a collision, not a replay.
            conflict = self.client.post("/api/documents",
                                        json={"title": "Different body"},
                                        headers=alice_headers)
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(ErrorResponse.model_validate(conflict.json()).error.code,
                             "IDEMPOTENCY_CONFLICT")
            # A malformed key is a typed validation error, never ignored.
            malformed = self.client.post(
                "/api/documents", json={"title": "Malformed key"},
                headers={"Authorization": "Bearer t.alice",
                         "Idempotency-Key": "not-a-uuid"})
            self.assertEqual(malformed.status_code, 422)
            # A failed create stores nothing: the key stays usable for the
            # corrected retry (whitespace title 422, then a valid 201).
            retryable_key = str(uuid4())
            failed = self.client.post(
                "/api/documents", json={"title": "   "},
                headers={"Authorization": "Bearer t.alice",
                         "Idempotency-Key": retryable_key})
            self.assertEqual(failed.status_code, 422)
            recovered = self.client.post(
                "/api/documents", json={"title": "Recovered"},
                headers={"Authorization": "Bearer t.alice",
                         "Idempotency-Key": retryable_key})
            self.assertEqual(recovered.status_code, 201)
        # Keys are owner-scoped: Bob's use of the same UUID is independent.
        with self.as_session(self.bob_id):
            bob_create = self.client.post(
                "/api/documents", json={"title": "Bob independent"},
                headers={"Authorization": "Bearer t.bob", "Idempotency-Key": key})
            self.assertEqual(bob_create.status_code, 201)
            self.assertNotEqual(bob_create.json()["id"], first.json()["id"])
        with self.admin.connect() as connection:
            documents = connection.execute(text(
                "SELECT count(*) FROM app.documents WHERE owner_id = :owner"),
                {"owner": self.alice_id}).scalar_one()
        # Alice: the idempotent create + the recovered create = 2 documents.
        self.assertEqual(documents, 2)

    def test_16_http_idempotent_save_replay_prevents_second_revision(self):
        key = str(uuid4())
        alice_headers = {"Authorization": "Bearer t.alice"}
        save_headers = {"If-Match": '"1"', "Idempotency-Key": key, **alice_headers}
        payload = {"schema_version": SCHEMA_VERSION, "content": self.full_document()}
        with self.as_session(self.alice_id):
            created = self.client.post("/api/documents", json={"title": "Autosave"},
                                       headers=alice_headers)
            document_id = UUID(created.json()["id"])
            first_save = self.client.post(
                f"/api/documents/{document_id}/versions", json=payload,
                headers=save_headers)
            self.assertEqual(first_save.status_code, 201)
            self.assertEqual(first_save.headers["ETag"], '"2"')
            version_id = first_save.json()["version"]["id"]
            # Timeout-after-commit retry: same key, same body — the replay
            # returns the stored original result and creates NO third revision.
            retry = self.client.post(
                f"/api/documents/{document_id}/versions", json=payload,
                headers=save_headers)
            self.assertEqual(retry.status_code, 201)
            self.assertEqual(retry.json(), first_save.json())
            self.assertEqual(retry.headers["ETag"], '"2"')
            # The same body with a refreshed If-Match is the same logical
            # request (identity is owner/route/body): it replays the result.
            refreshed = self.client.post(
                f"/api/documents/{document_id}/versions", json=payload,
                headers={**save_headers, "If-Match": '"2"'})
            self.assertEqual(refreshed.status_code, 201)
            self.assertEqual(refreshed.json()["version"]["id"], version_id)
            # A different body with the same key is a 409 collision.
            conflict = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION,
                      "content": empty_document()},
                headers=save_headers)
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(ErrorResponse.model_validate(conflict.json()).error.code,
                             "IDEMPOTENCY_CONFLICT")
            # A different key never replays: plain CAS against revision 1 is
            # now stale and the conflict is the honest 409.
            stale = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": self.full_document()},
                headers={"If-Match": '"1"', "Idempotency-Key": str(uuid4()),
                         **alice_headers})
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(ErrorResponse.model_validate(stale.json()).error.code,
                             "REVISION_CONFLICT")
            # Saves without a key keep the plain CAS behavior.
            plain = self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": SCHEMA_VERSION, "content": empty_document()},
                headers={"If-Match": '"2"', **alice_headers})
            self.assertEqual(plain.status_code, 201)
            self.assertEqual(plain.headers["ETag"], '"3"')
        counts = self.table_counts(document_id)
        self.assertEqual(counts, {"document_versions": 3, "document_blocks": 9,
                                  "insights": 1, "hypotheses": 1, "evidence_links": 1})

    def test_version_replay_is_scoped_to_the_concrete_document(self):
        first = service.create_document(self.engine, self.alice, title="Synthetic first")
        second = service.create_document(self.engine, self.alice, title="Synthetic second")
        foreign = service.create_document(self.engine, self.bob, title="Synthetic Bob")
        payload = {"schema_version": SCHEMA_VERSION, "content": empty_document()}
        headers = {"Authorization": "Bearer t.alice", "If-Match": '\"1\"',
                   "Idempotency-Key": str(uuid4())}
        with self.as_session(self.alice_id):
            a = self.client.post(f"/api/documents/{first.document.id}/versions", json=payload, headers=headers)
            self.assertEqual(a.status_code, 201, a.text)
            denied = self.client.post(f"/api/documents/{foreign.document.id}/versions", json=payload, headers=headers)
            self.assertEqual(denied.status_code, 404, denied.text)
            b = self.client.post(f"/api/documents/{second.document.id}/versions", json=payload, headers=headers)
            self.assertEqual(b.status_code, 201, b.text)
            self.assertEqual(b.json()["document"]["id"], str(second.document.id))
            self.assertNotEqual(a.json()["version"]["id"], b.json()["version"]["id"])
            for document, result in ((first, a), (second, b)):
                replay = self.client.post(f"/api/documents/{document.document.id}/versions", json=payload,
                                          headers={**headers, "If-Match": '\"2\"'})
                self.assertEqual(replay.json(), result.json())
                self.assertEqual(self.table_counts(document.document.id)["document_versions"], 2)

    def test_17_idempotent_create_concurrent_same_key_single_document(self):
        key = uuid4()
        route = idempotency.ROUTE_CREATE_DOCUMENT
        fingerprint = idempotency.request_fingerprint(route, self.alice_id,
                                                      {"title": "Race create"})
        barrier = threading.Barrier(2)
        outcomes = {}

        def run(engine, tag):
            barrier.wait()
            outcomes[tag] = idempotency.execute_idempotent(
                engine, self.alice, route_key=route, idempotency_key=key,
                request_hash=fingerprint,
                operation=lambda connection: (
                    201, {"document_id": str(
                        service.create_document_in_transaction(
                            connection, self.alice, title="Race create").document.id)}))

        threads = [threading.Thread(target=run, args=(self.engine, "a")),
                   threading.Thread(target=run, args=(self.engine_b, "b"))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual({outcome.status for outcome in outcomes.values()}, {201})
        document_ids = {outcome.body["document_id"] for outcome in outcomes.values()}
        self.assertEqual(document_ids, {outcomes["a"].body["document_id"]})
        self.assertTrue(outcomes["a"].replay != outcomes["b"].replay)
        with self.admin.connect() as connection:
            created = connection.execute(text(
                "SELECT count(*) FROM app.documents WHERE title = 'Race create'"
            )).scalar_one()
            versions = connection.execute(text("""
                SELECT count(*) FROM app.document_versions v
                  JOIN app.documents d ON d.id = v.document_id
                 WHERE d.title = 'Race create'
            """)).scalar_one()
        self.assertEqual((created, versions), (1, 1))

    def test_18_disabled_account_is_403_on_crud_routes(self):
        alice_headers = {"Authorization": "Bearer t.alice"}
        with self.as_session(self.alice_id):
            created = self.client.post("/api/documents", json={"title": "Gate"},
                                       headers=alice_headers)
            document_id = created.json()["id"]
            version_id = created.json()["current_version_id"]
        with self.operator.begin() as connection:
            connection.execute(text(
                "UPDATE app.users SET disabled_at = now() WHERE id = :id"),
                {"id": self.alice_id})
        with self.as_session(self.alice_id):
            for method, path, payload, headers in (
                ("patch", f"/api/documents/{document_id}", {"title": "x"},
                 {"If-Match": '"1"', **alice_headers}),
                ("delete", f"/api/documents/{document_id}", None,
                 {"If-Match": '"1"', **alice_headers}),
                ("get", f"/api/documents/{document_id}/versions", None, alice_headers),
                ("get", f"/api/documents/{document_id}/versions/{version_id}",
                 None, alice_headers),
            ):
                response = self.client.request(method, path, json=payload,
                                               headers=headers) \
                    if payload is not None else self.client.request(method, path,
                                                                    headers=headers)
                with self.subTest(method=method):
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(
                        ErrorResponse.model_validate(response.json()).error.code,
                        "FORBIDDEN")
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
        with self.operator.begin() as connection:
            connection.execute(text(
                "UPDATE app.users SET disabled_at = NULL WHERE id = :id"),
                {"id": self.alice_id})
        with self.as_session(self.alice_id):
            recovered = self.client.get(f"/api/documents/{document_id}/versions",
                                        headers=alice_headers)
            self.assertEqual(recovered.status_code, 200)

    def _scientific_counts(self, dataset_id: UUID) -> dict:
        with self.admin.connect() as connection:
            return {
                "dataset_versions": connection.execute(text(
                    "SELECT count(*) FROM app.dataset_versions WHERE id = :id"),
                    {"id": dataset_id}).scalar_one(),
                "manifest_artifacts": connection.execute(text(
                    "SELECT count(*) FROM app.artifacts a "
                    "JOIN app.dataset_versions dv ON dv.manifest_artifact_id = a.id "
                    "WHERE dv.id = :id"), {"id": dataset_id}).scalar_one(),
                "documents": connection.execute(text(
                    "SELECT count(*) FROM app.documents")).scalar_one(),
            }


class _StubVerifier:
    """Stubbed token verifier so no provider or JWKS is ever contacted."""

    def __init__(self, result):
        self.result = result

    def verify(self, token):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _verified(subject) -> VerifiedToken:
    return VerifiedToken(subject=subject, expires_at=datetime.now(UTC) + timedelta(minutes=5),
                         issued_at=datetime.now(UTC))


if __name__ == "__main__":
    unittest.main()
