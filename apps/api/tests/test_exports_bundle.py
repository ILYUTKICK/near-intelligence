"""NI-058 tests, offline part: the Markdown bundle, its manifest and ZIP.

Runs everywhere (no database): the deterministic ``research.md`` renderer,
the manifest identity records, the fixed-timestamp ZIP packaging and the
acceptance verifiers (extract -> validate hashes -> resolve links). The
database lifecycle (create/poll/download, lease/retry, TTL, owner matrix)
is covered by ``test_exports_jobs.py`` under scripts/run-db-tests.py — a
skip is never successful integration evidence.

Every fixture is visibly synthetic ("(fixture)"); no research data, no
network, no provider.
"""

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from unittest import TestCase
from uuid import uuid4

from near_api.exports.bundle import (
    BUNDLE_FORMAT_VERSION,
    MAX_BUNDLE_BYTES,
    ZIP_ENTRY_TIMESTAMP,
    BundleError,
    build_bundle,
    extract_bundle,
    verify_bundle,
    verify_research_links,
)
from near_api.exports.charts import ChartRenderedChart, ChartRenderResult, safe_chart_asset_name
from near_api.exports.ir import export_ir_canonical_bytes
from near_api.exports.markdown import (
    ChartAssetFiles,
    MarkdownRenderError,
    escape_text,
    limitations_of,
    render_markdown,
)
from near_api.exports.service import ExportJobRow
from near_api.exports.worker import render_bundle
from near_api.insights.schemas import RichTextListItem, RichTextRun
from near_api.schemas.common import ErrorResponse
from near_api.schemas.export import (
    ExportAuthor,
    ExportCitationReference,
    ExportDataTableBlock,
    ExportDataTableColumn,
    ExportDividerBlock,
    ExportDocumentMeta,
    ExportEvidenceBlock,
    ExportHeadingBlock,
    ExportHypothesisBlock,
    ExportIr,
    ExportListBlock,
    ExportParagraphBlock,
    ExportRiskBlock,
)
from near_api.schemas.export_job import DocumentExportRequest, ExportJobResponse
import test_exports_charts as renderer_fixtures

SHA256 = "a" * 64
TS = "2026-11-09T12:00:00Z"


def _run(text, marks=()):
    return RichTextRun.model_validate({"type": "text", "text": text,
                                       "marks": list(marks)})


def synthetic_plan(*, chart=True) -> ExportIr:
    """One synthetic export plan covering every renderable block family."""
    citation_id = uuid4()
    blocks = [
        ExportParagraphBlock(block_type="paragraph", block_id=uuid4(),
                             runs=(_run("Synthetic intro (fixture) ",
                                        [{"type": "bold"}]),
                                   _run("with a link (fixture)",
                                        [{"type": "link",
                                          "attrs": {"href": "https://example.test/source"}}]))),
        ExportHeadingBlock(block_type="heading", block_id=uuid4(), level=2,
                           runs=(_run("Findings (fixture)"),)),
        ExportListBlock(block_type="bullet_list", block_id=uuid4(), items=(
            RichTextListItem.model_validate({"type": "list_item", "content": [
                {"type": "paragraph", "content": [_run("first (fixture)")]}]}),)),
        ExportHypothesisBlock(block_type="hypothesis", block_id=uuid4(),
                              hypothesis_id=uuid4(),
                              statement="Synthetic claim (fixture)",
                              assessment="untested",
                              authored_at=TS, modified_at=TS),
        ExportRiskBlock(block_type="risk", block_id=uuid4(),
                        title="Concentration risk (fixture)",
                        body=({"type": "paragraph", "content":
                               [_run("Synthetic risk body (fixture)")]},),
                        related_hypothesis_id=None),
        ExportDividerBlock(block_type="divider", block_id=uuid4()),
        ExportDataTableBlock(block_type="dataTable", block_id=uuid4(),
                             columns=(ExportDataTableColumn(key="metric", label="Metric",
                                                            type="string"),
                                      ExportDataTableColumn(key="share", label="Share",
                                                            type="number", unit="%")),
                             rows=(("fees (fixture)", "12.5"), (None, True)),),
        ExportEvidenceBlock(block_type="evidence", block_id=uuid4(),
                            evidence_id=uuid4(), hypothesis_id=uuid4(),
                            classification="supporting", target_kind="citation",
                            target_id=citation_id, target_block_id=None,
                            explanation="Synthetic evidence explanation (fixture)"),
    ]
    if chart:
        blocks.append(renderer_fixtures.export_chart_block())
    return ExportIr(
        ir_version=1,
        document=ExportDocumentMeta(
            document_id=uuid4(), version_id=uuid4(), revision=7, schema_version=1,
            content_sha256=SHA256, title="Synthetic export research (fixture)",
            author=ExportAuthor(owner_id=uuid4(), display_name="Synthetic Alice"),
            created_at=datetime(2026, 11, 9, tzinfo=UTC)),
        blocks=tuple(blocks),
        sources=(),
        model_runs=(),
        citations=(ExportCitationReference(artifact_id=citation_id),))


def _render_result(plan: ExportIr) -> ChartRenderResult:
    """A synthetic boundary-verified render of the plan's chart blocks."""
    charts = []
    for block in plan.blocks:
        if block.block_type != "liveChart":
            continue
        svg = (f"<svg xmlns='http://www.w3.org/2000/svg'><rect width='960' "
               f"height='540'/></svg> {block.block_id} (fixture)")
        csv = ("date,series_index,series,unit,value,value_kind,quality,quality_reasons\n"
               "2026-11-01,0,Synthetic export metric (fixture),NEAR,"
               "123456789012345678901234567890.5,,ok,\n"
               "2026-11-02,0,Synthetic export metric (fixture),NEAR,,,missing,"
               "no observation for the period (fixture)\n"
               "2026-11-03,0,Synthetic export metric (fixture),NEAR,2.5,lower,ok,\n")
        charts.append(ChartRenderedChart(
            chart_id=block.block_id, svg=svg,
            svg_sha256=hashlib.sha256(svg.encode()).hexdigest(),
            csv=csv, csv_sha256=hashlib.sha256(csv.encode()).hexdigest(),
            series_count=len(block.view.series),
            point_count=sum(len(series.points) for series in block.view.series)))
    return ChartRenderResult(
        protocol_version=1,
        renderer={"id": "near-export-chart-renderer@1",
                  "echarts_version": "6.1.0 (fixture)",
                  "node_version": "v24.0.0 (fixture)"},
        input_sha256=SHA256, charts=tuple(charts), script_sha256=SHA256)


class EscapeTextTests(TestCase):
    def test_structure_characters_render_inert(self):
        escaped = escape_text("# heading\n*bold* <script>alert(1)</script> "
                              "[link](x) | cell `code` _em_ & done")
        self.assertEqual(
            escaped,
            "\\# heading \\*bold\\* &lt;script&gt;alert(1)&lt;/script&gt; "
            "\\[link\\](x) \\| cell \\`code\\` \\_em\\_ &amp; done")
        self.assertNotIn("<script>", escaped)


class MarkdownRendererTests(TestCase):
    def test_01_renders_every_block_family_deterministically(self):
        plan = synthetic_plan()
        assets = {}
        for block in plan.blocks:
            if block.block_type == "liveChart":
                assets[block.block_id] = ChartAssetFiles(
                    f"assets/{safe_chart_asset_name(block.block_id, 'svg')}",
                    f"assets/{safe_chart_asset_name(block.block_id, 'csv')}")
        first = render_markdown(plan, assets)
        self.assertEqual(first, render_markdown(plan, assets))  # double render
        self.assertIn("# Synthetic export research (fixture)", first)
        self.assertIn("**Synthetic intro (fixture) **", first)
        self.assertIn("[with a link (fixture)](https://example.test/source)", first)
        self.assertIn("### Findings (fixture)", first)  # heading level 2 -> ###
        self.assertIn("- first (fixture)", first)
        self.assertIn("**Hypothesis (untested)**", first)
        self.assertIn("**Risk: Concentration risk (fixture)**", first)
        self.assertIn("---", first)
        self.assertIn("| Metric | Share (%) |", first)
        self.assertIn("| fees (fixture) | 12.5 |", first)
        self.assertIn("|  | true |", first)
        self.assertIn("## Sources", first)
        self.assertIn("## Model runs", first)
        self.assertIn("## Citations", first)
        self.assertIn("Public citation artifact", first)
        self.assertIn("## Limitations", first)
        self.assertIn("no observation for the period (fixture)", first)
        self.assertIn("lower", first)
        for block in plan.blocks:
            if block.block_type == "liveChart":
                self.assertIn(f"assets/{safe_chart_asset_name(block.block_id, 'svg')}",
                              first)
                self.assertIn(str(block.view.resolved_at), first)

    def test_02_prose_never_injects_markdown_or_html(self):
        plan = synthetic_plan(chart=False)
        hostile_title = "# injected heading <script>alert(1)</script> (fixture)"
        hostile = plan.model_copy(update={"document": plan.document.model_copy(
            update={"title": hostile_title})})
        rendered = render_markdown(hostile, {})
        self.assertNotIn("<script>", rendered)
        # The title renders as inert text, not as an ATX heading.
        self.assertIn("# \\# injected heading", rendered)

    def test_03_ir_version_drift_fails_closed(self):
        plan = synthetic_plan(chart=False)
        drifted = plan.model_copy(update={"ir_version": 2})
        with self.assertRaises(MarkdownRenderError) as caught:
            render_markdown(drifted, {})
        self.assertIn(("ir_version", "unsupported_ir_version"),
                      [tuple(item) for item in caught.exception.details])


class BundleTests(TestCase):
    def setUp(self):
        self.plan = synthetic_plan()
        self.render = _render_result(self.plan)
        self.bundle = build_bundle(self.plan, self.render)

    def test_01_manifest_pins_plan_file_and_renderer_identity(self):
        manifest = self.bundle.manifest
        self.assertEqual(manifest["bundle_format_version"], BUNDLE_FORMAT_VERSION)
        self.assertEqual(manifest["ir_version"], 1)
        self.assertEqual(manifest["document"]["revision"], 7)
        self.assertEqual(manifest["document"]["content_sha256"], SHA256)
        self.assertEqual(manifest["document"]["title"],
                         "Synthetic export research (fixture)")
        self.assertEqual(manifest["plan_sha256"],
                         hashlib.sha256(
                             export_ir_canonical_bytes(self.plan)).hexdigest())
        recorded = {item["path"]: item for item in manifest["files"]}
        extracted = extract_bundle(self.bundle.zip_bytes)
        # The manifest cannot record its own hash; every other member is pinned.
        self.assertEqual(set(recorded), set(extracted) - {"manifest.json"})
        for path, data in extracted.items():
            if path == "manifest.json":
                continue
            self.assertEqual(recorded[path]["sha256"],
                             hashlib.sha256(data).hexdigest())
            self.assertEqual(recorded[path]["byte_size"], len(data))
        self.assertIn("research.md", recorded)
        # The manifest cannot carry its own hash (a self-reference); it pins
        # every other member.
        self.assertNotIn("manifest.json", recorded)
        self.assertEqual(manifest["chart_renderer"]["renderer"]["id"],
                         "near-export-chart-renderer@1")
        self.assertEqual(manifest["chart_renderer"]["script_sha256"], SHA256)
        self.assertEqual(manifest["chart_renderer"]["input_sha256"], SHA256)
        # The renderer identity record carries no server path or secret.
        self.assertEqual(set(manifest["chart_renderer"]),
                         {"renderer", "input_sha256", "script_sha256"})
        charts = manifest["charts"]
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0]["series_count"], 1)
        self.assertEqual(charts[0]["point_count"], 3)
        self.assertNotIn("generated_at", json.dumps(manifest))
        self.assertEqual(manifest["zip_entry_timestamp"], "1980-01-01T00:00:00+00:00")
        self.assertTrue(manifest["limitations"])
        self.assertEqual(manifest["limitations"], limitations_of(self.plan))

    def test_02_zip_is_deterministic_fixed_timestamp_sorted(self):
        rebuilt = build_bundle(self.plan, self.render)
        self.assertEqual(rebuilt.zip_bytes, self.bundle.zip_bytes)
        with zipfile.ZipFile(io.BytesIO(self.bundle.zip_bytes)) as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            for info in archive.infolist():
                self.assertEqual(info.date_time, ZIP_ENTRY_TIMESTAMP)
                self.assertEqual(info.create_system, 0)

    def test_03_research_links_resolve_to_assets(self):
        extracted = extract_bundle(self.bundle.zip_bytes)
        verify_bundle(self.bundle.manifest, extracted)
        verify_research_links(extracted["research.md"].decode("utf-8"), extracted)

    def test_04_tampered_file_fails_hash_validation(self):
        extracted = extract_bundle(self.bundle.zip_bytes)
        key = next(path for path in extracted if path.endswith(".csv"))
        extracted[key] = extracted[key] + b"tampered\n"
        with self.assertRaises(BundleError) as caught:
            verify_bundle(self.bundle.manifest, extracted)
        self.assertEqual(caught.exception.details[-1][1], "file_hash_mismatch")

    def test_05_hostile_zip_member_is_refused(self):
        with zipfile.ZipFile(io.BytesIO(self.bundle.zip_bytes)) as archive:
            self.assertIsNone(archive.testzip())  # the real bundle is intact
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("research.md", "synthetic (fixture)")
            archive.writestr("manifest.json", "{}")
            archive.writestr("../evil.txt", "nope")
        with self.assertRaises(BundleError) as caught:
            extract_bundle(buffer.getvalue())
        self.assertEqual(caught.exception.details[-1][1], "unexpected_bundle_member")

    def test_06_incomplete_bundle_is_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("assets/chart-0f0e0d0c-0b0a-4000-8000-000000000001.svg",
                             "<svg xmlns='http://www.w3.org/2000/svg'/>")
        with self.assertRaises(BundleError):
            extract_bundle(buffer.getvalue())

    def test_07_render_mismatches_fail_typed(self):
        with self.assertRaises(BundleError):
            build_bundle(self.plan, None)  # charts without a verified render
        other_chart = self.plan.blocks[-1].model_copy(
            update={"block_id": uuid4()}) if self.plan.blocks[-1].block_type == "liveChart" \
            else renderer_fixtures.export_chart_block().model_copy(
                update={"block_id": uuid4()})
        renamed = self.plan.model_copy(
            update={"blocks": (*self.plan.blocks[:-1], other_chart)})
        with self.assertRaises(BundleError):
            # A verified render of a DIFFERENT chart id never bundles here.
            build_bundle(renamed, self.render)

    def test_08_worker_render_bundle_verifies_without_node(self):
        plan = synthetic_plan(chart=False)  # no charts: no subprocess needed
        zip_bytes = render_bundle(plan)
        extracted = extract_bundle(zip_bytes)
        verify_bundle(json.loads(extracted["manifest.json"]), extracted)
        verify_research_links(extracted["research.md"].decode("utf-8"), extracted)
        self.assertLessEqual(len(zip_bytes), MAX_BUNDLE_BYTES)


class LifecycleStateTests(TestCase):
    """The read-time lifecycle projection (pure, no database)."""

    def _row(self, status: str, *, expires_in: timedelta) -> ExportJobRow:
        return ExportJobRow(
            id=uuid4(), owner_id=uuid4(), document_id=uuid4(),
            document_version_id=uuid4(), format="markdown_zip", status=status,
            error_code=None,
            expires_at=datetime.now(UTC) + expires_in, attempts=0)

    def test_01_past_ttl_reads_expired_even_when_stored_succeeded(self):
        row = self._row("succeeded", expires_in=timedelta(hours=-1))
        self.assertEqual(row.reported_status(), "expired")
        self.assertIsNone(row.download_path())

    def test_02_live_succeeded_reports_download_path(self):
        row = self._row("succeeded", expires_in=timedelta(hours=1))
        self.assertEqual(row.reported_status(), "succeeded")
        self.assertTrue(row.download_path().endswith(f"/exports/{row.id}/download"))

    def test_03_failed_stays_failed_even_past_ttl(self):
        row = self._row("failed", expires_in=timedelta(hours=-1))
        self.assertEqual(row.reported_status(), "failed")

    def test_04_contract_models_reject_unknown_fields(self):
        with self.assertRaises(ValueError):
            DocumentExportRequest.model_validate({
                "document_version_id": str(uuid4()), "format": "markdown_zip",
                "owner_id": str(uuid4())})
        with self.assertRaises(ValueError):
            ExportJobResponse.model_validate({
                "id": str(uuid4()), "document_id": str(uuid4()),
                "document_version_id": str(uuid4()), "format": "markdown_zip",
                "status": "queued", "error_code": None, "download_path": None,
                "expires_at": TS, "bundle_path": "/secret/path (fixture)"})
        parsed = ErrorResponse.model_validate(
            {"error": {"code": "EXPORT_EXPIRED", "message": "expired",
                       "request_id": str(uuid4()), "retryable": False}})
        self.assertEqual(parsed.error.code, "EXPORT_EXPIRED")
