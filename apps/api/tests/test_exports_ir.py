"""NI-056 tests: the frozen document export representation.

Offline classes run everywhere (cell normalization, contract shapes, the
fail-closed mapper dispatch); the database class needs scripts/run-db-tests.py
— a skip is never successful integration evidence. Covered guarantees:

- every P0 block type maps into the typed export IR with its exact pinned
  values (runs/marks, levels, lists, statements/assessments, authored
  timestamps, frozen chart views with exact decimal-string series, data-table
  specs with exact decimal-string cells, evidence targets and risk/divider);
- the plan is FROZEN: mutating the current document (new revision, rename)
  or the underlying source catalog after the build leaves the built plan
  byte-identical, and a rebuild for the still-acknowledged revision after a
  newer dataset publication is byte-identical while the latest-pointer
  resolution is never called on the path;
- fail-closed behavior: missing pinned artifacts, unapproved/absent dataset
  references, dangling public model-run/citation references, unverifiable
  insight contexts, invalid stored content and unsupported block types raise
  the typed ExportIrError with bounded details — never a substitution, never
  a silent skip;
- ownership: the plan is reachable only through the verified principal's
  document (Alice/Bob matrix at service level), and only the acknowledged
  revision exports (title/content correspond to the same revision).

All identities, documents, datasets and the published model bundle are
synthetic fixtures (the NI-054 synthetic publication bundle — no real
research data); no provider, no network, no archive.
"""

import copy
import json
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.auth.principal import Principal
from near_api.charts.registry import chart_by_chart_id
from near_api.datasets import delivery as delivery_module
from near_api.db.security import ResourceNotFound
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.documents import service
from near_api.documents.schema import canonical_bytes, parse_document
from near_api.exports.ir import (
    ExportIrError,
    _map_block,
    build_export_ir,
    export_cell,
    export_ir_canonical_bytes,
)
from near_api.schemas.export import ExportDataTableBlock, ExportInsightBlock
import test_chart_blocks as chart_fixtures
import test_delivery_apis as data_fixture
import test_documents as document_fixtures
from test_models_publication import (
    MANIFEST_KEYS,
    bundle_dir,
    canonical_artifact_hash,
    derive_run_id,
    valid_bundle,
)

METRIC_ID = chart_fixtures.METRIC_ID
SHA256 = "a" * 64


def selection() -> dict:
    return {"start": "2026-01-01", "end": "2026-01-08", "frequency": "day",
            "filters": {}}


def _reasons(error: ExportIrError) -> list[str]:
    return [reason for _path, reason in error.details]


class ExportCellTests(unittest.TestCase):
    """Authored dataTable cells export as exact decimal strings."""

    def test_numeric_cells_export_as_exact_decimal_strings(self):
        self.assertEqual(export_cell(12), "12")
        self.assertEqual(export_cell(0), "0")
        self.assertEqual(export_cell(12.5), "12.5")
        self.assertEqual(export_cell(0.1), "0.1")
        self.assertEqual(export_cell(1e30), "1000000000000000000000000000000")
        self.assertEqual(export_cell(-2.75), "-2.75")

    def test_non_numeric_cells_export_verbatim(self):
        self.assertEqual(export_cell("12.5"), "12.5")
        self.assertIs(export_cell(True), True)
        self.assertIs(export_cell(False), False)
        self.assertIsNone(export_cell(None))
        self.assertEqual(export_cell(""), "")

    def test_unsupported_cell_type_fails_closed(self):
        with self.assertRaises(ExportIrError) as caught:
            export_cell({"nested": "object"})
        self.assertEqual(caught.exception.details,
                         (("dataTable_cell", "unsupported_cell_type"),))


class ExportContractTests(unittest.TestCase):
    """Offline contract shapes of the frozen representation."""

    def test_ni071_context_lines_print_resolved_filters(self):
        """An exported insight card shows exactly which values were selected."""
        import datetime as dt

        from near_api.exports.markdown import _context_lines
        from near_api.insights.schemas import ResolvedContext
        from near_api.schemas.chart_selection import ChartSelection
        from test_delivery_apis import RECIPIENTS

        context = ResolvedContext(
            chart_definition_version_id=uuid4(), dataset_version_id=uuid4(),
            selection=ChartSelection.model_validate({
                "start": "2026-01-01", "end": "2026-01-31", "frequency": "day",
                "filters": {"recipient": [RECIPIENTS[0], RECIPIENTS[1]]}}),
            context_hash="a" * 64, renderer_version="echarts-modular-svg@1",
            metric_definition_versions=(uuid4(),),
            resolved_at=dt.datetime.now(dt.UTC))
        lines = _context_lines(context)
        filters_lines = [line for line in lines if line.startswith("filters")]
        self.assertEqual(len(filters_lines), 1)
        self.assertEqual(filters_lines[0],
                         f"filters recipient: {RECIPIENTS[0]}, {RECIPIENTS[1]}")
        unfiltered = ResolvedContext.model_validate(context.model_dump(mode="json")
                                                    | {"selection": {
                                                        **context.selection.model_dump(
                                                            mode="json"),
                                                        "filters": {}}})
        self.assertFalse(any(line.startswith("filters")
                             for line in _context_lines(unfiltered)))

    def test_data_table_rows_and_dataset_reference_are_exclusive(self):
        columns = ({"key": "metric", "label": "Metric", "type": "string"},)
        with self.assertRaises(Exception):
            ExportDataTableBlock.model_validate({
                "block_type": "dataTable", "block_id": str(uuid4()),
                "columns": columns, "rows": [["fees"]], "dataset": {
                    "dataset_version_id": str(uuid4()), "dataset_key": "synthetic.k",
                    "version": 1, "content_sha256": SHA256}})
        with self.assertRaises(Exception):
            ExportDataTableBlock.model_validate({
                "block_type": "dataTable", "block_id": str(uuid4()),
                "columns": columns})

    def test_insight_block_rejects_unknown_fields(self):
        with self.assertRaises(Exception):
            ExportInsightBlock.model_validate({
                "block_type": "insight", "block_id": str(uuid4()),
                "insight_id": str(uuid4()), "insight_type": "observation",
                "classification": "supporting", "body": [],
                "context": {"model_run_id": str(uuid4())},
                "authored_at": "2026-11-06T12:00:00Z",
                "modified_at": "2026-11-06T12:00:00Z", "owner_id": str(uuid4())})

    def test_mapper_dispatch_fails_closed_on_contract_drift(self):
        """A block type the export contract does not know never maps silently."""
        parsed = parse_document({"schema_version": 1, "type": "doc", "content": [
            document_fixtures.block("divider")]})
        with patch.dict("near_api.exports.ir._BLOCK_MAPPERS", {}, clear=True):
            with self.assertRaises(ExportIrError) as caught:
                _map_block(None, parsed.blocks[0], {})
        self.assertEqual(caught.exception.details,
                         ((f"blocks.{parsed.blocks[0].block_id}",
                           "unsupported_block_type"),))


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ExportIrDatabaseTests(unittest.TestCase):
    """Frozen-plan guarantees on the disposable PostgreSQL cluster."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.engine = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")
        chart_fixtures.register_test_chart_catalog(cls.operator)
        cls.publish_synthetic_model_run()
        cls.citation_id = cls.insert_public_citation()

    @classmethod
    def publish_synthetic_model_run(cls):
        """One published model run from the synthetic NI-054 bundle.

        Publication is content-derived and idempotent: the identical bundle
        the NI-054 suites publish maps to the same run_id, so the suite order
        inside the shared disposable cluster never duplicates the row.
        """
        from near_api.research.publication import load_bundle, verify_bundle
        from near_api.research.publish_store import publish_run

        directory = Path(os.environ["NI_TEST_TMP_DIR"]) / "ni056-bundle"
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

    @classmethod
    def insert_public_citation(cls):
        artifact_id = uuid4()
        with cls.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256,
                       byte_size, media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/pdf', 'public', NULL,
                        'verified')
            """), {"id": artifact_id, "key": f"synthetic/{artifact_id}.pdf",
                   "sha": SHA256})
        return artifact_id

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.operator.dispose()
        cls.admin.dispose()

    def setUp(self):
        delivery_module.reset_delivery_caches()
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

    # -- fixture helpers ----------------------------------------------------- #

    def dataset_key(self, name: str) -> str:
        return f"synthetic.{uuid4().hex[:8]}.{name}"

    def ensure_stage_directory(self) -> None:
        """The lazily created staging root every stage_fixture call needs."""
        if not hasattr(self, "directory"):
            tmp = tempfile.TemporaryDirectory(prefix="ni056-",
                                              dir=os.environ["NI_TEST_TMP_DIR"])
            self.addCleanup(tmp.cleanup)
            self.directory = Path(tmp.name)
            self.storage_root = self.directory / "storage"

    def stage_volume(self, key: str, value: str) -> UUID:
        """One published synthetic dataset version for the intents chart."""
        self.ensure_stage_directory()
        dimensions = {"source": "SRC-LLAMA"}
        result = data_fixture.DeliveryDatabaseTests.stage_fixture(
            self, key,
            [data_fixture.observation(METRIC_ID, date(2026, 1, 1), value=value,
                                      bound_kind="lower", dimensions=dimensions),
             data_fixture.observation(METRIC_ID, date(2026, 1, 2), value=None,
                                      dimensions=dimensions)],
            [METRIC_ID], window=("2026-01-01", "2026-01-03"))
        return result.dataset_version_id

    def insert_dataset_row(self, dataset_key: str, status: str = "approved") -> UUID:
        """A minimal synthetic dataset version row without observations."""
        dataset_id, artifact_id = uuid4(), uuid4()
        with self.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size,
                       media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/json', 'internal', NULL,
                        'unverified')
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

    def dataset_identity(self, dataset_id: UUID) -> dict:
        with self.operator.connect() as connection:
            row = connection.execute(text("""
                SELECT dataset_key, version, content_sha256 FROM app.dataset_versions
                WHERE id = :id
            """), {"id": dataset_id}).mappings().one()
        return dict(row)

    def full_content(self, *, dataset_id: UUID, table_dataset_id: UUID) -> dict:
        """A synthetic document carrying every savable P0 block type."""
        insight_context = chart_fixtures.volume_context(self.operator, dataset_id)
        hypothesis = document_fixtures.hypothesis_attrs()
        hypothesis_id = hypothesis["attrs"]["hypothesis_id"]
        insight = document_fixtures.insight_attrs(
            hypothesis_id=hypothesis_id, context=copy.deepcopy(insight_context))
        chart_block_id = str(uuid4())
        chart = document_fixtures.block(
            "liveChart", chart_block_id, mode="live", selection=selection(),
            chart_definition_version_id=str(chart_fixtures.CHART_ID),
            observed_dataset_version_id=str(dataset_id))
        return {"schema_version": 1, "type": "doc", "content": [
            {"type": "paragraph", "attrs": {"block_id": str(uuid4())},
             "content": [document_fixtures.text_node("Synthetic intro ",
                                                     marks=[{"type": "bold"}]),
                         document_fixtures.text_node(
                             "with a source link",
                             marks=[{"type": "link",
                                     "attrs": {"href": "https://example.test/source"}}])]},
            {"type": "heading", "attrs": {"block_id": str(uuid4()), "level": 2},
             "content": [document_fixtures.text_node("Findings")]},
            {"type": "bullet_list", "attrs": {"block_id": str(uuid4())},
             "content": [{"type": "list_item", "content": [
                 document_fixtures.paragraph_node("first"),
                 {"type": "ordered_list", "content": [
                     {"type": "list_item", "content":
                      [document_fixtures.paragraph_node("nested")]}]}]}]},
            hypothesis, insight,
            document_fixtures.evidence_attrs(hypothesis_id, "insight",
                                             insight["attrs"]["insight_id"]),
            document_fixtures.evidence_attrs(hypothesis_id, "chart_block",
                                             chart_block_id),
            document_fixtures.evidence_attrs(hypothesis_id, "citation",
                                             str(self.citation_id)),
            document_fixtures.evidence_attrs(hypothesis_id, "model_run",
                                             str(self.run_id)),
            document_fixtures.risk_attrs(hypothesis_id),
            document_fixtures.block("divider"),
            document_fixtures.data_table_attrs(
                rows=[["fees", "12.5"], [None, True], [2, 12.5]]),
            document_fixtures.data_table_attrs(
                dataset_version_id=str(table_dataset_id)),
            chart,
        ]}

    def create_full_document(self, principal: Principal, *, dataset_id: UUID,
                             table_dataset_id: UUID,
                             title: str = "Synthetic export research"):
        created = service.create_document(self.engine, principal, title=title)
        content = self.full_content(dataset_id=dataset_id,
                                    table_dataset_id=table_dataset_id)
        saved = service.save_revision(self.engine, principal, created.document.id,
                                      expected_revision=1, document_payload=content)
        return created, saved

    def inject_revision(self, document_id: UUID, owner_id: UUID, content: dict,
                        *, canonicalize: bool = True) -> UUID:
        """Append a revision row directly (content the save rules would refuse).

        Used for states reachable in principle but not through the current
        save path (a mutated pin, a dangling public target, a future block
        type). The stored digest stays consistent so the builder reads the
        revision before refusing it.
        """
        if canonicalize:
            canonical = parse_document(content)
            stored, sha = canonical.canonical, canonical.content_sha256
        else:
            stored, sha = content, SHA256
        version_id = uuid4()
        with self.admin.begin() as connection:
            current = connection.execute(text(
                "SELECT revision FROM app.documents WHERE id = :id"),
                {"id": document_id}).one()
            connection.execute(text("""
                INSERT INTO app.document_versions(id, document_id, owner_id,
                       revision, schema_version, content, resolved_contexts,
                       content_sha256)
                VALUES (:id, :doc, :owner, :revision, 1,
                        CAST(:content AS jsonb), CAST('{}' AS jsonb), :sha)
            """), {"id": version_id, "doc": document_id, "owner": owner_id,
                   "revision": current.revision + 1,
                   "content": canonical_bytes(stored).decode("utf-8"), "sha": sha})
            connection.execute(text("""
                UPDATE app.documents SET revision = :revision,
                       current_version_id = :version WHERE id = :id
            """), {"revision": current.revision + 1, "version": version_id,
                   "id": document_id})
        return version_id

    def stored_insight_context(self, saved, block_id: UUID) -> dict:
        node = next(item for item in saved.content["content"]
                    if item["type"] == "insight"
                    and item["attrs"]["block_id"] == str(block_id))
        return node["attrs"]["context"]

    def stored_chart_context(self, saved, block_id: UUID) -> dict:
        return saved.resolved_contexts[str(block_id)]


    def test_ni071_multi_filter_chart_insight_export_round_trip(self):
        """Save a compared chart + insight, export twice, byte-identical IR."""
        import datetime as dt
        from decimal import Decimal

        from near_api.documents.context_resolver import build_resolved_context, \
            load_chart_definition
        from near_api.schemas.chart_selection import ChartSelection
        from test_delivery_apis import (METRIC_PAYOUTS, METRIC_PAYOUTS_V2,
                                        RECIPIENTS)

        self.ensure_stage_directory()
        filters = {"recipient": [RECIPIENTS[1], RECIPIENTS[0]]}
        selection_input = {"start": "2026-01-01", "end": "2026-01-03",
                           "frequency": "day", "filters": filters}
        canonical_selection = ChartSelection.model_validate(
            selection_input).model_dump(mode="json")
        observations = []
        for day, values_by_recipient in (
                ("2026-01-01", {RECIPIENTS[0]: "3", RECIPIENTS[1]: "2.5",
                                RECIPIENTS[2]: "0"}),
                ("2026-01-02", {RECIPIENTS[0]: "4", RECIPIENTS[1]: "2",
                                RECIPIENTS[2]: "0"})):
            instant = dt.date.fromisoformat(day)
            observations.append(data_fixture.observation(
                METRIC_PAYOUTS, instant,
                value=str(sum(Decimal(value)
                              for value in values_by_recipient.values()))))
            for account, value in values_by_recipient.items():
                observations.append(data_fixture.observation(
                    METRIC_PAYOUTS_V2, instant, value=value,
                    dimensions={"recipient": account}))
        dataset_id = data_fixture.DeliveryDatabaseTests.stage_fixture(
            self, self.dataset_key("ni071export"), observations,
            [METRIC_PAYOUTS, METRIC_PAYOUTS_V2],
            window=("2026-01-01", "2026-01-03")).dataset_version_id
        treasury_v2 = chart_by_chart_id("treasury-payouts")
        with self.operator.connect() as connection:
            definition = load_chart_definition(connection, treasury_v2.id,
                                               error_path="fixture")
        insight_context = build_resolved_context(
            definition, dataset_id,
            ChartSelection.model_validate(selection_input),
            resolved_at=dt.datetime.now(dt.UTC)).model_dump(mode="json")
        hypothesis = document_fixtures.hypothesis_attrs()
        hypothesis_id = hypothesis["attrs"]["hypothesis_id"]
        insight = document_fixtures.insight_attrs(hypothesis_id=hypothesis_id,
                                                  context=insight_context)
        chart_block_id = str(uuid4())
        content = {"schema_version": 1, "type": "doc", "content": [
            hypothesis,
            insight,
            document_fixtures.evidence_attrs(hypothesis_id, "insight",
                                             insight["attrs"]["insight_id"]),
            document_fixtures.block(
                "liveChart", chart_block_id, mode="live",
                selection=canonical_selection,
                chart_definition_version_id=str(treasury_v2.id),
                observed_dataset_version_id=str(dataset_id)),
        ]}
        created = service.create_document(self.engine, self.alice,
                                          title="Compared payouts export")
        saved = service.save_revision(self.engine, self.alice, created.document.id,
                                      expected_revision=1, document_payload=content)
        first = build_export_ir(self.engine, self.alice, created.document.id,
                                saved.version.id)
        second = build_export_ir(self.engine, self.alice, created.document.id,
                                 saved.version.id)
        self.assertEqual(export_ir_canonical_bytes(first),
                         export_ir_canonical_bytes(second))
        chart_block = next(block for block in first.blocks
                           if block.block_type == "liveChart")
        self.assertEqual(chart_block.selection.model_dump(mode="json")["filters"],
                         {"recipient": [RECIPIENTS[0], RECIPIENTS[1]]})
        self.assertEqual(chart_block.observed_dataset_version_id, dataset_id)
        self.assertEqual([series.selection.filters.model_dump()["recipient"]
                          for series in chart_block.view.series],
                         [[RECIPIENTS[0]], [RECIPIENTS[1]]])
        self.assertEqual([point.value for point in chart_block.view.series[0].points],
                         ["3", "4"])
        insight_block = next(block for block in first.blocks
                             if block.block_type == "insight")
        self.assertEqual(insight_block.context.selection.model_dump(mode="json")
                         ["filters"], {"recipient": [RECIPIENTS[0], RECIPIENTS[1]]})

    # -- every block mapper -------------------------------------------------- #

    def test_01_full_document_maps_every_p0_block(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        plan = build_export_ir(self.engine, self.alice, created.document.id,
                               saved.version.id)

        self.assertEqual(plan.ir_version, 1)
        meta = plan.document
        self.assertEqual(meta.document_id, created.document.id)
        self.assertEqual(meta.version_id, saved.version.id)
        self.assertEqual(meta.revision, 2)
        self.assertEqual(meta.title, "Synthetic export research")
        self.assertEqual(meta.author.owner_id, self.alice_id)
        self.assertEqual(meta.author.display_name, "Synthetic Alice")
        self.assertEqual(meta.content_sha256, saved.version.content_sha256)
        self.assertEqual(meta.created_at, saved.version.created_at)

        expected_types = ["paragraph", "heading", "bullet_list", "hypothesis",
                          "insight", "evidence", "evidence", "evidence",
                          "evidence", "risk", "divider", "dataTable",
                          "dataTable", "liveChart"]
        self.assertEqual([block.block_type for block in plan.blocks], expected_types)

        paragraph, heading, listing = plan.blocks[0], plan.blocks[1], plan.blocks[2]
        self.assertEqual(paragraph.runs[0].marks[0].type, "bold")
        self.assertEqual(paragraph.runs[1].marks[0].type, "link")
        self.assertEqual(paragraph.runs[1].marks[0].attrs.href,
                         "https://example.test/source")
        self.assertEqual(heading.level, 2)
        self.assertEqual(listing.block_type, "bullet_list")
        self.assertEqual(len(listing.items[0].content), 2)
        self.assertEqual(listing.items[0].content[1].type, "ordered_list")

        hypothesis_block = plan.blocks[3]
        self.assertEqual(hypothesis_block.statement,
                         "Adoption drives fee revenue within the window")
        self.assertEqual(hypothesis_block.assessment, "untested")

        insight_block = plan.blocks[4]
        self.assertEqual(insight_block.insight_type, "observation")
        self.assertEqual(insight_block.classification, "supporting")
        stored = self.stored_insight_context(saved, insight_block.block_id)
        self.assertEqual(str(insight_block.context.dataset_version_id),
                         str(dataset_id))
        self.assertEqual(insight_block.context.context_hash, stored["context_hash"])
        self.assertEqual(insight_block.context.selection.model_dump(mode="json"),
                         stored["selection"])
        self.assertEqual(insight_block.context.renderer_version,
                         stored["renderer_version"])
        self.assertEqual(insight_block.authored_at, insight_block.modified_at)
        self.assertEqual(insight_block.hypothesis_id,
                         hypothesis_block.hypothesis_id)

        (insight_evidence, chart_evidence, citation_evidence,
         run_evidence) = plan.blocks[5:9]
        self.assertEqual(insight_evidence.classification, "contradicting")
        self.assertEqual(insight_evidence.target_block_id, insight_block.block_id)
        self.assertEqual(chart_evidence.target_block_id, plan.blocks[13].block_id)
        self.assertIsNone(citation_evidence.target_block_id)
        self.assertIsNone(run_evidence.target_block_id)
        self.assertTrue(all(block.hypothesis_id == hypothesis_block.hypothesis_id
                            for block in plan.blocks[5:9]))

        risk_block = plan.blocks[9]
        self.assertEqual(risk_block.title, "Concentration risk")
        self.assertEqual(risk_block.related_hypothesis_id,
                         hypothesis_block.hypothesis_id)
        self.assertEqual(plan.blocks[10].block_type, "divider")

        authored_table = plan.blocks[11]
        self.assertEqual([column.key for column in authored_table.columns],
                         ["metric", "share"])
        self.assertEqual([column.type for column in authored_table.columns],
                         ["string", "number"])
        self.assertEqual(authored_table.columns[1].unit, "%")
        self.assertEqual(authored_table.rows,
                         (("fees", "12.5"), (None, True), ("2", "12.5")))
        self.assertIsNone(authored_table.dataset)

        identity = self.dataset_identity(dataset_id)
        reference_table = plan.blocks[12]
        self.assertIsNone(reference_table.rows)
        self.assertEqual(reference_table.dataset.dataset_version_id, dataset_id)
        self.assertEqual(reference_table.dataset.dataset_key, identity["dataset_key"])
        self.assertEqual(reference_table.dataset.version, identity["version"])
        self.assertEqual(reference_table.dataset.content_sha256,
                         identity["content_sha256"])

        chart_block = plan.blocks[13]
        self.assertEqual(chart_block.mode, "live")
        self.assertEqual(chart_block.selection.model_dump(mode="json"), selection())
        self.assertEqual(chart_block.observed_dataset_version_id, dataset_id)
        self.assertIsNone(chart_block.snapshot_id)
        view = chart_block.view
        self.assertEqual(view.dataset.id, dataset_id)
        self.assertEqual(view.series[0].points[0].value, "12.5")
        self.assertIsNone(view.series[0].points[1].value)
        self.assertEqual(view.series[0].points[0].quality.bound_kind, "lower")
        self.assertEqual(view.context_hash,
                         self.stored_chart_context(saved, chart_block.block_id)
                         ["context_hash"])
        pinned_resolved_at = datetime.fromisoformat(
            self.stored_chart_context(saved, chart_block.block_id)
            ["resolved_at"].replace("Z", "+00:00"))
        self.assertEqual(view.resolved_at, pinned_resolved_at)

        self.assertEqual([source.source_id for source in plan.sources], ["SRC-LLAMA"])
        self.assertEqual([run.run_id for run in plan.model_runs], [self.run_id])
        self.assertEqual([item.artifact_id for item in plan.citations],
                         [self.citation_id])

    def test_02_double_build_is_byte_identical(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        first = build_export_ir(self.engine, self.alice, created.document.id,
                                saved.version.id)
        second = build_export_ir(self.engine, self.alice, created.document.id,
                                 saved.version.id)
        self.assertEqual(export_ir_canonical_bytes(first),
                         export_ir_canonical_bytes(second))
        self.assertEqual(first.model_dump(mode="json"), second.model_dump(mode="json"))

    # -- frozen semantics ---------------------------------------------------- #

    def test_03_plan_frozen_when_document_moves_on(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        plan = build_export_ir(self.engine, self.alice, created.document.id,
                               saved.version.id)
        frozen = export_ir_canonical_bytes(plan)
        frozen_dump = copy.deepcopy(plan.model_dump(mode="json"))

        renamed = service.rename_document(self.engine, self.alice,
                                          created.document.id, expected_revision=2,
                                          title="Renamed synthetic research")
        self.assertEqual(renamed.document.revision, 3)
        # The held plan still describes revision 2 with its original title.
        self.assertEqual(export_ir_canonical_bytes(plan), frozen)
        self.assertEqual(plan.model_dump(mode="json"), frozen_dump)
        self.assertEqual(plan.document.title, "Synthetic export research")
        # A non-acknowledged revision is never re-exported with the current
        # title; a fresh plan comes from the new acknowledged revision.
        with self.assertRaises(ExportIrError) as caught:
            build_export_ir(self.engine, self.alice, created.document.id,
                            saved.version.id)
        self.assertEqual(caught.exception.details,
                         (("version_id", "revision_not_acknowledged"),))
        fresh = build_export_ir(self.engine, self.alice, created.document.id,
                                renamed.version.id)
        self.assertEqual(fresh.document.title, "Renamed synthetic research")
        self.assertEqual(fresh.document.revision, 3)
        self.assertEqual(fresh.document.content_sha256,
                         renamed.version.content_sha256)

    def test_04_plan_frozen_when_latest_source_moves(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        plan = build_export_ir(self.engine, self.alice, created.document.id,
                               saved.version.id)
        frozen = export_ir_canonical_bytes(plan)

        # A newer approved publication of the same metric moves the latest
        # pointer; the pinned revision must not see it.
        self.stage_volume(self.dataset_key("intents"), "99.25")
        delivery_module.reset_delivery_caches()

        def refuse_latest(*_args, **_kwargs):
            raise AssertionError("resolve_latest_version called on the export path")

        with patch.object(delivery_module, "resolve_latest_version", refuse_latest):
            rebuilt = build_export_ir(self.engine, self.alice, created.document.id,
                                      saved.version.id)
        self.assertEqual(export_ir_canonical_bytes(rebuilt), frozen)
        chart = rebuilt.blocks[-1]
        self.assertEqual(chart.view.dataset.id, dataset_id)
        self.assertEqual(chart.view.series[0].points[0].value, "12.5")

    # -- fail-closed references ---------------------------------------------- #

    def test_05_missing_pinned_artifact_fails_with_detail(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.artifacts SET sha256 = :broken
                WHERE id = (SELECT manifest_artifact_id FROM app.dataset_versions
                            WHERE id = :dataset)
            """), {"broken": "b" * 64, "dataset": dataset_id})
        with self.assertRaises(ExportIrError) as caught:
            build_export_ir(self.engine, self.alice, created.document.id,
                            saved.version.id)
        self.assertIn("could not be reconstructed", str(caught.exception))
        self.assertEqual(len(caught.exception.details), 1)
        path, reason = caught.exception.details[0]
        self.assertTrue(path.startswith("blocks."))
        self.assertEqual(reason, "pinned_artifact_unavailable")

    def test_06_unapproved_table_dataset_reference_fails(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        staged = self.insert_dataset_row(self.dataset_key("staged"),
                                         status="validated")
        content = {"schema_version": 1, "type": "doc", "content": [
            document_fixtures.data_table_attrs(
                dataset_version_id=str(staged))]}
        version_id = self.inject_revision(created.document.id, self.alice_id, content)
        with self.assertRaises(ExportIrError) as caught:
            build_export_ir(self.engine, self.alice, created.document.id, version_id)
        self.assertIn("not an approved public dataset", str(caught.exception))
        self.assertEqual(caught.exception.details,
                         (("dataTable.dataset_version_id",
                           "dangling_dataset_reference"),))

    def test_07_dangling_public_references_fail(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        hypothesis = document_fixtures.hypothesis_attrs()
        for kind, target in (("model_run", str(uuid4())),
                             ("citation", str(uuid4()))):
            with self.subTest(kind=kind):
                content = {"schema_version": 1, "type": "doc", "content": [
                    hypothesis,
                    document_fixtures.evidence_attrs(
                        hypothesis["attrs"]["hypothesis_id"], kind, target)]}
                version_id = self.inject_revision(created.document.id,
                                                  self.alice_id, content)
                with self.assertRaises(ExportIrError) as caught:
                    build_export_ir(self.engine, self.alice, created.document.id,
                                    version_id)
                self.assertIn("public evidence target", str(caught.exception))
                self.assertIn(f"dangling_{kind}_target", _reasons(caught.exception))

    def test_10_published_model_context_exports_run_reference(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        content = {"schema_version": 1, "type": "doc", "content": [
            document_fixtures.insight_attrs(context={
                "model_run_id": str(self.run_id),
                "dataset_version_id": str(dataset_id),
                "specification_version": "gross_fee_activity_v1@1",
                "context_hash": SHA256})]}
        version_id = self.inject_revision(created.document.id, self.alice_id, content)
        plan = build_export_ir(self.engine, self.alice, created.document.id,
                               version_id)
        insight = plan.blocks[0]
        self.assertEqual(insight.block_type, "insight")
        self.assertEqual(str(insight.context.model_run_id), str(self.run_id))
        self.assertEqual([run.run_id for run in plan.model_runs], [self.run_id])
        self.assertEqual([run.spec_id for run in plan.model_runs],
                         ["gross_fee_activity_v1"])
        self.assertEqual([run.spec_version for run in plan.model_runs], [1])

    def test_11_unresolvable_insight_context_fails(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        content = {"schema_version": 1, "type": "doc", "content": [
            document_fixtures.insight_attrs(context={
                **chart_fixtures.volume_context(self.operator, dataset_id),
                "dataset_version_id": str(uuid4())})]}
        version_id = self.inject_revision(created.document.id, self.alice_id, content)
        with self.assertRaises(ExportIrError) as caught:
            build_export_ir(self.engine, self.alice, created.document.id, version_id)
        self.assertIn("pins chart evidence", str(caught.exception))
        self.assertIn("dangling_dataset_reference", _reasons(caught.exception))

    def test_12_invalid_stored_content_fails_with_detail(self):
        created = service.create_document(self.engine, self.alice,
                                          title="Synthetic invalid")
        version_id = self.inject_revision(
            created.document.id, self.alice_id,
            {"schema_version": 1, "type": "doc",
             "content": [{"type": "iframe", "attrs": {"block_id": str(uuid4())}}]},
            canonicalize=False)
        with self.assertRaises(ExportIrError) as caught:
            build_export_ir(self.engine, self.alice, created.document.id, version_id)
        self.assertIn("not a valid canonical document", str(caught.exception))
        self.assertEqual(caught.exception.details,
                         (("document.content[0].type", "unsupported_block_type"),))

    # -- ownership and acknowledgment ----------------------------------------- #

    def test_08_cross_owner_access_denied(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        bob_document = service.create_document(self.engine, self.bob,
                                               title="Bob synthetic")
        with self.assertRaises(ResourceNotFound):
            build_export_ir(self.engine, self.bob, created.document.id,
                            saved.version.id)
        # Knowing a version UUID grants no access: Bob's own document with
        # Alice's version id is the same 404-equivalent.
        with self.assertRaises(ResourceNotFound):
            build_export_ir(self.engine, self.bob, bob_document.document.id,
                            saved.version.id)
        with self.assertRaises(ResourceNotFound):
            build_export_ir(self.engine, self.alice, created.document.id, uuid4())
        with self.assertRaises(ResourceNotFound):
            build_export_ir(self.engine, self.alice, uuid4(), uuid4())

    def test_09_non_acknowledged_revision_refused(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, _saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        with self.assertRaises(ExportIrError) as caught:
            build_export_ir(self.engine, self.alice, created.document.id,
                            created.version.id)
        self.assertEqual(caught.exception.details,
                         (("version_id", "revision_not_acknowledged"),))
        self.assertIn("acknowledged", str(caught.exception))
