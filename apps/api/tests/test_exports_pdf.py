"""NI-059 tests, offline part: the deterministic static PDF report.

Runs everywhere (no database): the ``render_pdf`` renderer of the frozen
plan, its determinism (byte-identical double builds), pagination of a long
document, the pinned captions/appendix/registries, the fail-closed guards
(unknown blocks, unembeddable charts, glyph coverage) and the worker's PDF
dispatch. The database lifecycle (PDF job create/claim/render/download,
owner matrix) is covered by ``test_exports_jobs.py`` under
scripts/run-db-tests.py — a skip is never successful integration evidence.

Structural assertions read the generated PDFs with ``pypdf`` (the recorded
dev-group test dependency): page counts and extracted text prove what a
viewer actually shows. Visual page inspection of the committed verification
artifacts (docs/verification/ni-059/) is recorded in the NI-059 task card.

Every fixture is visibly synthetic ("(fixture)"); no research data, no
network, no provider.
"""

import hashlib
import io
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import TestCase
from uuid import NAMESPACE_URL, UUID, uuid5

from pypdf import PdfReader

from near_api.exports.charts import (
    ChartRenderedChart,
    ChartRenderResult,
    chart_render_request,
    render_chart_assets,
)
from near_api.exports.ir import export_ir_canonical_bytes
from near_api.exports.pdf import PDF_FORMAT_VERSION, PdfRenderError, render_pdf
from near_api.exports.worker import render_bundle
from near_api.insights.schemas import RichTextListItem, RichTextRun
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
    ExportInsightBlock,
    ExportIr,
    ExportListBlock,
    ExportParagraphBlock,
    ExportRiskBlock,
)
import test_exports_charts as renderer_fixtures

SHA256 = "a" * 64
TS = "2026-11-09T12:00:00Z"
FIXTURE_NAMESPACE = "https://near.test/ni059-fixtures"


def _run(text, marks=()):
    return RichTextRun.model_validate({"type": "text", "text": text,
                                       "marks": list(marks)})


def _item(text):
    return RichTextListItem.model_validate({"type": "list_item", "content": [
        {"type": "paragraph", "content": [_run(text)]}]})


def _svg(title):
    """A well-formed synthetic chart SVG in the renderer's emitted shape."""
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='960' height='540'>"
            f"<rect width='960' height='540' fill='white'/>"
            f"<text x='480' y='30' font-size='14' text-anchor='middle' "
            f"font-family='Inter, ui-sans-serif, system-ui, sans-serif'>"
            f"{title}</text></svg>")


def _csv(series_label):
    return ("date,series_index,series,unit,value,value_kind,quality,"
            "quality_reasons\n"
            f"2026-11-01,0,{series_label},NEAR,"
            "123456789012345678901234567890.5,,ok,\n"
            f"2026-11-02,0,{series_label},NEAR,,,missing,"
            "no observation for the period (fixture)\n"
            f"2026-11-03,0,{series_label},NEAR,2.5,lower,ok,\n")


def synthetic_render(plan: ExportIr, *, svg_title="Synthetic export chart (fixture)") \
        -> ChartRenderResult:
    """A synthetic boundary-verified render of the plan's chart blocks."""
    charts = []
    for block in plan.blocks:
        if block.block_type != "liveChart":
            continue
        svg = _svg(svg_title)
        csv = _csv("Synthetic export metric (fixture)")
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


def _meta(title="Synthetic export research (fixture)", revision=7) -> ExportDocumentMeta:
    return ExportDocumentMeta(
        document_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/doc-{revision}"),
        version_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/version-{revision}"),
        revision=revision, schema_version=1, content_sha256=SHA256,
        title=title,
        author=ExportAuthor(
            owner_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/owner"),
            display_name="Synthetic Alice"),
        created_at=datetime(2026, 11, 9, tzinfo=UTC))


def short_plan(*, chart=True, citation=True) -> ExportIr:
    """One synthetic plan covering every renderable block family once."""
    citation_id = uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/citation")
    blocks = [
        ExportParagraphBlock(block_type="paragraph", block_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/intro"),
            runs=(_run("Synthetic intro (fixture) ", [{"type": "bold"}]),
                  _run("with a link (fixture)",
                       [{"type": "link",
                         "attrs": {"href": "https://example.test/source"}}]))),
        ExportHeadingBlock(block_type="heading", block_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/h1"), level=1,
            runs=(_run("Findings (fixture)"),)),
        ExportListBlock(block_type="bullet_list", block_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/list"), items=(
            _item("first (fixture)"),
            _item("second (fixture)"),)),
        ExportListBlock(block_type="ordered_list", block_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/olist"), items=(
            _item("step one (fixture)"), _item("step two (fixture)"),)),
        ExportHypothesisBlock(block_type="hypothesis", block_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/hypothesis"),
            hypothesis_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/hyp-id"),
            statement="Synthetic claim (fixture)", assessment="untested",
            authored_at=TS, modified_at=TS),
        ExportRiskBlock(block_type="risk", block_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/risk"),
            title="Concentration risk (fixture)",
            body=({"type": "paragraph", "content":
                   [_run("Synthetic risk body (fixture)")]},),
            related_hypothesis_id=None),
        ExportDividerBlock(block_type="divider", block_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/divider")),
        ExportDataTableBlock(block_type="dataTable", block_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/table"),
            columns=(ExportDataTableColumn(key="metric", label="Metric",
                                           type="string"),
                     ExportDataTableColumn(key="share", label="Share",
                                           type="number", unit="%")),
            rows=(("fees (fixture)", "12.5"), (None, True), ("", False)),),
    ]
    if citation:
        blocks.append(ExportEvidenceBlock(
            block_type="evidence", block_id=uuid5(
                NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/evidence"),
            evidence_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/ev-id"),
            hypothesis_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/hyp-id"),
            classification="supporting", target_kind="citation",
            target_id=citation_id, target_block_id=None,
            explanation="Synthetic evidence explanation (fixture)"))
    if chart:
        blocks.append(renderer_fixtures.export_chart_block())
    return ExportIr(
        ir_version=1, document=_meta(), blocks=tuple(blocks),
        sources=(), model_runs=(), citations=(
            ExportCitationReference(artifact_id=citation_id),))


def long_plan() -> ExportIr:
    """A deterministic long plan: repeated sections over many pages.

    Eight repeated sections, each carrying a heading, paragraphs, a list, an
    insight card, a divider and an authored table, plus two charts — enough
    pagination that every layout path (splitting tables, page breaks around
    figures and cards) is exercised.
    """
    blocks = []
    for section in range(1, 9):
        blocks.append(ExportHeadingBlock(
            block_type="heading",
            block_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/lh-{section}"),
            level=(section % 3) + 1,
            runs=(_run(f"Section {section} (fixture)"),)))
        blocks.append(ExportParagraphBlock(
            block_type="paragraph",
            block_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/lp-{section}"),
            runs=(_run(f"Section {section} synthetic narrative paragraph "
                       f"with enough words to wrap across the printable "
                       f"width of the page (fixture).",),)))
        blocks.append(ExportListBlock(
            block_type="bullet_list",
            block_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/ll-{section}"),
            items=tuple(_item(f"point {index} of section {section} (fixture)")
                        for index in range(1, 5))))
        blocks.append(ExportInsightBlock(
            block_type="insight",
            block_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/li-{section}"),
            insight_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/li-id-{section}"),
            insight_type="observation", classification="supporting",
            body=({"type": "paragraph", "content":
                   [_run(f"Synthetic insight body for section {section} (fixture)")]},),
            context=_resolved_context(),
            authored_at=TS, modified_at=TS, hypothesis_id=None))
        blocks.append(ExportDividerBlock(
            block_type="divider",
            block_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/ld-{section}")))
        blocks.append(ExportDataTableBlock(
            block_type="dataTable",
            block_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/lt-{section}"),
            columns=(ExportDataTableColumn(key="day", label="Day", type="date"),
                     ExportDataTableColumn(key="value", label="Value",
                                           type="number", unit="NEAR"),
                     ExportDataTableColumn(key="note", label="Note",
                                           type="string")),
            rows=tuple((f"2026-11-{day:02d}", f"{day * 3}.5",
                        "synthetic (fixture)" if day % 2 else None)
                       for day in range(1, 13))))
    blocks.append(renderer_fixtures.export_chart_block())
    blocks.append(renderer_fixtures.export_chart_block().model_copy(update={
        "block_id": UUID("0f0e0d0c-0b0a-4000-8000-000000000002")}))
    return ExportIr(
        ir_version=1,
        document=_meta(title="Synthetic long export research (fixture)",
                       revision=12),
        blocks=tuple(blocks), sources=(), model_runs=(),
        citations=())


def _resolved_context():
    from near_api.insights.schemas import ResolvedContext
    from near_api.schemas.chart_selection import ChartSelection

    view = renderer_fixtures.frozen_view()
    return ResolvedContext(
        chart_definition_version_id=uuid5(
            NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/cdv"),
        dataset_version_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/dsv"),
        selection=ChartSelection(start=view.selection.start,
                                 end=view.selection.end,
                                 frequency=view.selection.frequency,
                                 filters={}),
        context_hash=SHA256,
        renderer_version="echarts-modular-svg@1 (fixture)",
        metric_definition_versions=(
            uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/mdv"),),
        resolved_at=view.resolved_at,
    )


def _stub_model_result():
    """The NI-055 ``modelResult`` shape, duck-typed (guarded on this base).

    On a tree without NI-055 the plan grammar cannot validate such a block
    and its canonical bytes cannot be produced, so the branch is exercised
    at the block renderer level (``_render_block``) — the same function
    ``render_pdf`` dispatches through. The interpretation body uses the real
    typed rich-text models.
    """
    from near_api.insights.schemas import RichTextParagraph

    return SimpleNamespace(
        block_type="modelResult",
        block_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/model-result"),
        model_run_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/run"),
        dataset_version_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/mdsv"),
        spec_id="synthetic.ols (fixture)", spec_version=3,
        interpretation=(RichTextParagraph(type="paragraph", content=(
            _run("Synthetic model interpretation (fixture)"),)),),
        summary=SimpleNamespace(
            run_id=uuid5(NAMESPACE_URL, f"{FIXTURE_NAMESPACE}/run"),
            model_id="synthetic-model", model_version="1",
            gate_verdict="pass",
            sample_start="2026-01-01", sample_end_exclusive="2026-02-01",
            nobs=31,
            coefficient_rtol="1e-8", coefficient_atol="1e-10",
            manifest_url="https://example.test/model-manifest (fixture)",
            coefficients=(
                SimpleNamespace(name="intercept", estimate="2.5",
                                std_error="0.125", t_stat="20",
                                p_value="0.0001", ci95_low="2.25",
                                ci95_high="2.75"),
                SimpleNamespace(name="slope", estimate="0.5",
                                std_error="0.0125", t_stat="40",
                                p_value="0.00001", ci95_low="0.475",
                                ci95_high="0.525"),),
            diagnostics={"nobs_check": "ok", "r2": "0.98"}),
    )


def _stub_plan(blocks) -> ExportIr:
    return ExportIr.model_construct(
        ir_version=1, document=_meta(), blocks=tuple(blocks),
        sources=(), model_runs=(), citations=())


def _full_text(pdf_bytes: bytes) -> tuple[PdfReader, str]:
    """The extracted text of every page, whitespace-normalized (extraction
    reflects line breaks that the wrapped layout legitimately produces)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    raw = "\n".join(page.extract_text() for page in reader.pages)
    return reader, " ".join(raw.split())


class ShortDocumentTests(TestCase):
    """The representative SHORT report: content, pins, appendix, registries."""

    def setUp(self):
        self.plan = short_plan()
        self.pdf_bytes = render_pdf(self.plan, synthetic_render(self.plan))
        self.reader, self.text = _full_text(self.pdf_bytes)

    def test_01_attribution_and_plan_identity_are_printed(self):
        self.assertIn("Synthetic export research (fixture)", self.text)
        self.assertIn("Exported revision 7 of document", self.text)
        self.assertIn("authored by Synthetic Alice", self.text)
        self.assertIn("created 2026-11-09", self.text)
        self.assertIn(self.plan.document.content_sha256, self.text)
        expected_plan_sha = hashlib.sha256(
            export_ir_canonical_bytes(self.plan)).hexdigest()
        self.assertIn(expected_plan_sha, self.text)
        self.assertIn(f"PDF layout version {PDF_FORMAT_VERSION}", self.text)
        # the frozen-revision statement and the manifest reference survive
        self.assertIn("frozen export of exactly this revision", self.text)
        self.assertIn("manifest.json", self.text)

    def test_02_every_block_family_renders(self):
        self.assertIn("Synthetic intro (fixture) ", self.text)
        self.assertIn("with a link (fixture)", self.text)
        self.assertIn("Findings (fixture)", self.text)
        self.assertIn("first (fixture)", self.text)
        self.assertIn("step two (fixture)", self.text)
        self.assertIn("Hypothesis (untested)", self.text)
        self.assertIn("Synthetic claim (fixture)", self.text)
        self.assertIn("Risk: Concentration risk (fixture)", self.text)
        self.assertIn("Evidence (supporting)", self.text)
        self.assertIn("public citation artifact", self.text)
        self.assertIn("Metric", self.text)
        self.assertIn("fees (fixture)", self.text)
        self.assertIn("12.5", self.text)
        self.assertIn("true", self.text)

    def test_03_chart_caption_carries_definition_dataset_pins(self):
        block = next(b for b in self.plan.blocks if b.block_type == "liveChart")
        self.assertIn(
            f"chart definition version {block.chart_definition_version_id}",
            self.text)
        self.assertIn(
            f"dataset version {block.observed_dataset_version_id}", self.text)
        self.assertIn(f"resolved {block.view.resolved_at}", self.text)
        self.assertIn("Exact values: chart-data appendix, table 1", self.text)

    def test_04_exact_value_appendix_equals_the_csv_asset(self):
        self.assertIn("Chart data (exact values)", self.text)
        self.assertIn("Figure 1 data (exact values)", self.text)
        csv = synthetic_render(self.plan).charts[0].csv
        for row in csv.strip().split("\n")[1:]:
            date, index, series, unit, value, kind, quality, reason = \
                _split_csv_row(row)
            self.assertIn(date, self.text)
            self.assertIn(series, self.text)
            if value:
                self.assertIn(value, self.text)
            self.assertIn(quality, self.text)
        # missing is never zero-filled: the missing row's value cell is
        # empty, so the unit and the quality reason are adjacent on the page
        self.assertIn("NEAR missing no observation for the period (fixture)",
                      self.text)
        self.assertIn("lower", self.text)

    def test_05_registries_and_limitations_present(self):
        self.assertIn("Sources", self.text)
        self.assertIn("Model runs", self.text)
        self.assertIn("Citations", self.text)
        self.assertIn("Public citation artifact", self.text)
        self.assertIn("Limitations", self.text)
        self.assertIn("never refreshed with current data", self.text)
        self.assertIn("no observation for the period (fixture)", self.text)

    def test_06_rendering_provenance_recorded(self):
        self.assertIn("Rendering provenance", self.text)
        self.assertIn("near-export-chart-renderer@1", self.text)
        self.assertIn("6.1.0 (fixture)", self.text)
        self.assertIn("No live data, screenshot or network access", self.text)

    def test_07_double_build_is_byte_identical(self):
        again = render_pdf(self.plan, synthetic_render(self.plan))
        self.assertEqual(again, self.pdf_bytes)

    def test_08_metadata_is_fixed_content_without_wall_clock(self):
        metadata = self.reader.metadata
        self.assertEqual(metadata.title, "Synthetic export research (fixture)")
        self.assertEqual(metadata.author, "Synthetic Alice")
        self.assertIn("NI-059", metadata.creator)
        # invariant mode pins the PDF timestamps (no wall clock anywhere)
        self.assertIn("D:20000101", str(metadata))


def _split_csv_row(row: str) -> list[str]:
    import csv as csv_module

    return next(csv_module.reader(io.StringIO(row)))


class LongDocumentTests(TestCase):
    """The representative LONG report: pagination without clipping."""

    def setUp(self):
        self.plan = long_plan()
        self.pdf_bytes = render_pdf(self.plan, synthetic_render(self.plan))
        self.reader, self.text = _full_text(self.pdf_bytes)

    def test_01_long_document_paginates(self):
        self.assertGreater(len(self.reader.pages), 6)

    def test_02_every_section_and_family_survives_pagination(self):
        for section in range(1, 9):
            self.assertIn(f"Section {section} (fixture)", self.text)
            self.assertIn(f"Synthetic insight body for section {section}",
                          self.text)
            self.assertIn(f"point 4 of section {section}", self.text)
        self.assertIn("Exported revision 12", self.text)
        self.assertIn("Chart data (exact values)", self.text)
        self.assertIn("Figure 1 data (exact values)", self.text)
        self.assertIn("Figure 2 data (exact values)", self.text)

    def test_03_double_build_is_byte_identical(self):
        again = render_pdf(self.plan, synthetic_render(self.plan))
        self.assertEqual(again, self.pdf_bytes)

    def test_04_insight_cards_carry_pinned_context(self):
        self.assertIn("Pinned context: chart definition version", self.text)
        self.assertIn("window 2026-11-01 to 2026-11-04 (day)", self.text)
        self.assertIn(f"context hash {SHA256}", self.text)


class ModelResultTests(TestCase):
    """The NI-055 modelResult branch (duck-typed; guarded on this base).

    ``render_pdf`` dispatches through ``_render_block``, so the branch is
    exercised exactly where the combined tree (with NI-055's real schema)
    will hit it; the stub never reaches the canonical-bytes pin, which only
    real validated plans produce.
    """

    def _pdf_text(self, block) -> str:
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.platypus import SimpleDocTemplate

        from near_api.exports.pdf import _ensure_fonts, _render_block, _styles

        _ensure_fonts()
        styles = _styles()
        flowables, _ = _render_block(block, chart_number=0, assets_by_id={},
                                     styles=styles)
        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=_A4, invariant=1)
        document.build(flowables)
        return " ".join(PdfReader(io.BytesIO(buffer.getvalue()))
                        .pages[0].extract_text().split())

    def test_01_model_result_renders_summary_pins_and_coefficients(self):
        block = _stub_model_result()
        text = self._pdf_text(block)
        self.assertIn("Model result", text)
        self.assertIn(f"run {block.summary.run_id}", text)
        self.assertIn("gate verdict pass", text)
        self.assertIn("Specification synthetic.ols (fixture) version 3", text)
        self.assertIn("sample 2026-01-01 to 2026-02-01 (nobs 31)", text)
        self.assertIn("rtol 1e-8, atol 1e-10", text)
        self.assertIn("Synthetic model interpretation (fixture)", text)
        self.assertIn("Coefficients (exact values)", text)
        self.assertIn("intercept", text)
        self.assertIn("0.125", text)
        self.assertIn("2.5", text)
        self.assertIn("Manifest:", text)
        self.assertIn("Diagnostics:", text)
        self.assertIn("nobs_check: ok", text)
        self.assertIn("r2: 0.98", text)

    def test_02_diagnostics_absent_renders_nothing_extra(self):
        block = _stub_model_result()
        block.summary.diagnostics = None
        block.summary.manifest_url = None
        text = self._pdf_text(block)
        self.assertIn("Model result", text)
        self.assertNotIn("Diagnostics:", text)
        self.assertNotIn("Manifest:", text)


class FailClosedTests(TestCase):
    """Typed refusals: never a partial or degraded PDF."""

    def test_01_ir_version_drift_fails_closed(self):
        plan = short_plan(chart=False).model_copy(update={"ir_version": 2})
        with self.assertRaises(PdfRenderError) as caught:
            render_pdf(plan, None)
        self.assertIn(("ir_version", "unsupported_ir_version"),
                      [tuple(item) for item in caught.exception.details])

    def test_02_unknown_block_type_cannot_reach_the_renderer(self):
        # First line of defense: the typed plan grammar refuses an unknown
        # block type outright, so a stored plan can never smuggle one past
        # validation (the worker parses plans through ExportIr first).
        from near_api.exports.ir import ExportIrError

        import json as json_module

        payload = json_module.loads(
            export_ir_canonical_bytes(short_plan(chart=False)))
        payload["blocks"] = [{"block_type": "future_block", "block_id":
                              str(uuid5(NAMESPACE_URL,
                                        f"{FIXTURE_NAMESPACE}/future"))}]
        with self.assertRaises((ExportIrError, ValueError)):
            ExportIr.model_validate_json(json_module.dumps(payload))

    def test_03_unknown_block_type_fails_closed_at_dispatch(self):
        # Second line of defense (schema/renderer skew, e.g. a plan written
        # by a newer schema than this renderer knows): the dispatch guard
        # fails closed with a typed error instead of skipping the block.
        from near_api.exports.pdf import _ensure_fonts, _render_block, _styles

        _ensure_fonts()
        foreign = SimpleNamespace(block_type="future_block", block_id="x")
        with self.assertRaises(PdfRenderError) as caught:
            _render_block(foreign, chart_number=0, assets_by_id={},
                          styles=_styles())
        self.assertIn(("blocks.x", "unsupported_block_type"),
                      [tuple(item) for item in caught.exception.details])

    def test_03_charts_without_render_fail_closed(self):
        plan = short_plan(chart=True)
        with self.assertRaises(PdfRenderError) as caught:
            render_pdf(plan, None)
        self.assertIn(("charts", "missing_chart_render"),
                      [tuple(item) for item in caught.exception.details])

    def test_04_render_of_a_different_chart_set_fails_closed(self):
        plan = short_plan(chart=True)
        other = renderer_fixtures.export_chart_block().model_copy(
            update={"block_id": "0f0e0d0c-0b0a-4000-8000-000000000003"})
        renamed = plan.model_copy(update={"blocks": (*plan.blocks[:-1], other)})
        with self.assertRaises(PdfRenderError) as caught:
            render_pdf(renamed, synthetic_render(plan))
        self.assertIn(("charts", "chart_set_mismatch"),
                      [tuple(item) for item in caught.exception.details])

    def test_05_malformed_chart_svg_fails_typed_not_clipped(self):
        plan = short_plan(chart=True)
        broken = synthetic_render(plan)
        chart = broken.charts[0].model_copy(update={
            "svg": "<svg><text>unterminated (fixture)</text>"})
        broken = broken.model_copy(update={"charts": (chart,)})
        with self.assertRaises(PdfRenderError) as caught:
            render_pdf(plan, broken)
        self.assertIn(("charts.%s.svg" % plan.blocks[-1].block_id,
                       "chart_embed_failed"),
                      [tuple(item) for item in caught.exception.details])

    def test_06_uncovered_glyph_fails_typed(self):
        # The export font (DejaVu) covers Latin/Cyrillic/Greek but not CJK;
        # the export refuses instead of shipping box/invisible characters.
        plan = short_plan(chart=False).model_copy(update={
            "document": _meta(title="Synthetic 转移量 title (fixture)")})
        with self.assertRaises(PdfRenderError) as caught:
            render_pdf(plan, None)
        self.assertIn(("document.title", "glyph_not_covered"),
                      [tuple(item) for item in caught.exception.details])

    def test_07_uncovered_glyph_in_chart_svg_text_fails_typed(self):
        plan = short_plan(chart=True)
        broken = synthetic_render(plan)
        chart = broken.charts[0].model_copy(update={
            "svg": _svg("Synthetic 转移量 chart (fixture)")})
        broken = broken.model_copy(update={"charts": (chart,)})
        with self.assertRaises(PdfRenderError) as caught:
            render_pdf(plan, broken)
        self.assertIn(("charts.%s.svg" % plan.blocks[-1].block_id,
                       "glyph_not_covered"),
                      [tuple(item) for item in caught.exception.details])

    def test_08_hostile_prose_never_injects_markup(self):
        plan = short_plan(chart=False).model_copy(update={
            "document": _meta(
                title="<b>injected</b> title & <script>alert(1)</script>")})
        pdf_bytes = render_pdf(plan, None)
        _, text = _full_text(pdf_bytes)
        # The hostile string survives as DRAWN TEXT (escaped for the markup
        # grammar, then rendered inert): it appears literally on the page
        # instead of being interpreted as bold/structure. The whole title is
        # one inert string — "injected" carries no bold structure of its own.
        self.assertIn("<b>injected</b> title & <script>alert(1)</script>", text)


class RealRendererEmbedTests(TestCase):
    """Chart fidelity: the REAL NI-057 Node renderer SVG through the embed
    path (subprocess, no network), byte-identical double build."""

    def test_01_real_renderer_svg_embeds_deterministically(self):
        plan = short_plan(chart=False)
        plan = plan.model_copy(update={"blocks": (
            *plan.blocks, renderer_fixtures.export_chart_block())})
        result = render_chart_assets(chart_render_request(
            [block for block in plan.blocks if block.block_type == "liveChart"]),
            timeout=60.0)
        pdf_bytes = render_pdf(plan, result)
        reader, text = _full_text(pdf_bytes)
        self.assertIn("Figure 1", text)
        # The frozen view's rendered content is visible in the PDF: the
        # axis unit and date labels are the real ECharts SSR SVG's text
        # nodes, embedded as vector text.
        self.assertIn("NEAR", text)
        self.assertIn("2026-11-01", text)
        self.assertIn("2026-11-03", text)
        self.assertIn("near-export-chart-renderer@1", text)
        self.assertGreater(len(reader.pages), 0)
        self.assertEqual(pdf_bytes, render_pdf(plan, result))


class WorkerDispatchTests(TestCase):
    """The worker's render_bundle dispatch (no charts: no subprocess)."""

    def test_01_pdf_dispatch_renders_pdf_bytes(self):
        plan = short_plan(chart=False)
        pdf_bytes = render_bundle(plan, format="pdf")
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        reader, text = _full_text(pdf_bytes)
        self.assertIn("Synthetic export research (fixture)", text)
        self.assertEqual(pdf_bytes, render_bundle(plan, format="pdf"))

    def test_02_markdown_zip_dispatch_unchanged(self):
        from near_api.exports.bundle import extract_bundle

        plan = short_plan(chart=False)
        zip_bytes = render_bundle(plan, format="markdown_zip")
        extracted = extract_bundle(zip_bytes)
        self.assertIn("research.md", extracted)

    def test_03_unknown_format_fails_typed(self):
        plan = short_plan(chart=False)
        with self.assertRaises(Exception) as caught:
            render_bundle(plan, format="docx")
        self.assertIn("unsupported_export_format",
                      str(getattr(caught.exception, "code", "")) + str(caught.exception))
