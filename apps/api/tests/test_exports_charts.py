"""NI-057 tests: the static chart asset rendering boundary.

Fully offline (no database, no cluster, no network): the Node renderer is
exercised as a real subprocess exactly as the export pipeline invokes it,
and the boundary's fail-closed behavior is additionally driven by controlled
fake renderer scripts written at test runtime. Covered guarantees:

- the frozen view renders into a verified record: SVG + normalized CSV whose
  rows equal the pinned series byte-exactly (exact decimal strings, units,
  bound kinds, gaps with reasons — missing is never zero), with the renderer
  identity, script hash, request hash and asset hashes recorded;
- determinism: the same frozen request renders byte-identical assets;
- the subprocess boundary: ARGV list invocation without a shell, payload on
  STDIN, honest typed errors for a missing node binary, timeout expiry
  (controlled slow renderer), corrupt/oversized output, hash tampering,
  identity mismatch, chart-set mismatch and a missing renderer script;
- safe filenames: canonical lowercase UUID block ids only — traversal,
  separators, shell metacharacters, control characters and bad extensions
  are typed refusals, never sanitized guesses.

Every fixture is visibly synthetic ("(fixture)"); no research data.
"""

import json
import os
import subprocess
import tempfile
import time
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from near_api.exports import charts as charts_module
from near_api.exports.charts import (
    RENDERER_ID,
    RENDERER_SCRIPT_PATH,
    ChartRenderedChart,
    ChartRenderRequest,
    ChartRendererError,
    ChartRenderRequestChart,
    ChartRenderResult,
    chart_render_request,
    render_chart_assets,
    safe_chart_asset_name,
)
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.delivery import (
    ChartDefinitionResponse,
    ChartViewResponse,
    DatasetResponse,
    MetricResponse,
    Observation,
    ResolvedSelection,
    ResolvedSelectionFilters,
    SeriesResponse,
)
from near_api.schemas.export import ExportChartBlock

HUGE_DECIMAL = "123456789012345678901234567890.5"
SHA256 = "a" * 64
BLOCK_ID = "0f0e0d0c-0b0a-4000-8000-000000000001"


# --------------------------------------------------------------------------- #
# Synthetic frozen view (visibly labeled fixture, NI-032 contract shapes)
# --------------------------------------------------------------------------- #


def _quality(status="ok", bound_kind=None, reasons=()):
    return {"status": status, "bound_kind": bound_kind, "reasons": list(reasons),
            "coverage": {"observed": 2, "expected": 3}, "freshness_target_seconds": 86400}


def _observation(day, value):
    return Observation.model_validate({
        "start": f"2026-11-{day:02d}T00:00:00Z",
        "end": f"2026-11-{day + 1:02d}T00:00:00Z",
        "value": value,
        "quality": _quality() if value is not None else _quality(
            "missing", None, ["no observation for the period (fixture)"]),
    })


def _observation_with_bound(day, value, bound_kind):
    point = json.loads(_observation(day, value).model_dump_json())
    point["quality"] = _quality("ok", bound_kind)
    return Observation.model_validate(point)


def frozen_view() -> ChartViewResponse:
    """One synthetic line chart: exact decimal, a gap, a lower bound."""
    metric = MetricResponse(
        id=uuid4(), metric_id="synthetic.metric", version=1,
        title="Synthetic export metric (fixture)",
        definition="Synthetic metric definition for export tests (fixture).",
        formula="synthetic_sum (fixture)", unit="NEAR", frequency="daily",
        source_id="SRC-FIXTURE", economic_scope="Synthetic scope (fixture).",
        availability="A", limitations=["Synthetic fixture — never published data."])
    dataset = DatasetResponse(
        id=uuid4(), dataset_key="synthetic.export-fixture", version=1,
        status="approved", start=date(2026, 11, 1), end=date(2026, 11, 4),
        source_as_of=None, retrieved_at=None, pipeline_version="synthetic-pipeline@1 (fixture)",
        content_sha256=SHA256, quality=_quality(), manifest_url=None, supersedes_id=None)
    definition = ChartDefinitionResponse(
        id=uuid4(), chart_id="synthetic-export-fixture", version=1,
        title="Synthetic export chart (fixture)",
        description="Synthetic chart for export renderer tests (fixture).",
        category="activity", metric_definition_ids=[metric.id],
        visualization_type="line", units={"synthetic.metric": "NEAR"},
        filter_schema={}, available_ranges={"presets_days": [7, 30], "max_days": 366},
        renderer_version="echarts-modular-svg@1", update_frequency="daily",
        data_status="available", unavailable_reason=None,
        source_lineage={"sources": ["SRC-FIXTURE"], "note": "Synthetic lineage (fixture)."})
    series = SeriesResponse(
        metric=metric, dataset=dataset,
        selection=ResolvedSelection(
            start=date(2026, 11, 1), end=date(2026, 11, 4), frequency="day",
            filters=ResolvedSelectionFilters()),
        points=(
            _observation(1, HUGE_DECIMAL),
            _observation(2, None),
            _observation_with_bound(3, "2.5", "lower"),
        ),
        sources=())
    return ChartViewResponse(
        definition=definition, selection=series.selection, dataset=dataset,
        series=(series,), resolved_at=datetime(2026, 11, 4, tzinfo=timezone.utc),
        context_hash=SHA256, quality=_quality())


def chart_request() -> ChartRenderRequest:
    return ChartRenderRequest(
        protocol_version=1, width=960, height=540,
        charts=(ChartRenderRequestChart(chart_id=BLOCK_ID, view=frozen_view()),))


def expected_csv() -> str:
    title = "Synthetic export metric (fixture)"
    return (
        "date,series_index,series,unit,value,value_kind,quality,quality_reasons\n"
        f"2026-11-01,0,{title},NEAR,{HUGE_DECIMAL},,ok,\n"
        f"2026-11-02,0,{title},NEAR,,,missing,no observation for the period (fixture)\n"
        f"2026-11-03,0,{title},NEAR,2.5,lower,ok,\n"
    )


def export_chart_block() -> ExportChartBlock:
    return ExportChartBlock(
        block_type="liveChart", block_id=BLOCK_ID,
        chart_definition_version_id=uuid4(), mode="live",
        selection=ChartSelection(start=date(2026, 11, 1), end=date(2026, 11, 4),
                                 frequency="day", filters={}),
        observed_dataset_version_id=uuid4(), snapshot_id=None, view=frozen_view())


def write_fake_renderer(directory: Path, body: str) -> str:
    """A controlled fake renderer script (the boundary's configured seam)."""
    script = directory / f"fake-renderer-{uuid4().hex}.mjs"
    script.write_text(body, encoding="utf-8")
    return str(script)


FAITHFUL_FAKE = '''
import { createHash } from "node:crypto";
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const raw = Buffer.concat(chunks);
const request = JSON.parse(raw.toString("utf8"));
const svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>';
const csv = "date,series_index,series,unit,value,value_kind,quality,quality_reasons\\n";
const hash = (text) => createHash("sha256").update(text, "utf8").digest("hex");
process.stdout.write(JSON.stringify({
  protocol_version: 1,
  renderer: { id: "near-export-chart-renderer@1", echarts_version: "0.0.0-fake",
              node_version: process.versions.node },
  input_sha256: createHash("sha256").update(raw).digest("hex"),
  charts: request.charts.map((chart) => ({
    chart_id: chart.chart_id, svg, svg_sha256: hash(svg), csv, csv_sha256: hash(csv),
    series_count: chart.view.series.length,
    point_count: chart.view.series.reduce((sum, s) => sum + s.points.length, 0),
  })),
}) + "\\n");
'''


class ContractTests(unittest.TestCase):
    """Offline contract shapes: safe filenames and the typed request."""

    def test_safe_asset_name_accepts_canonical_identities(self):
        self.assertEqual(safe_chart_asset_name(BLOCK_ID, "svg"), f"chart-{BLOCK_ID}.svg")
        self.assertEqual(safe_chart_asset_name("0f0e0d0c-0b0a-4000-8000-000000000002", "csv"),
                         "chart-0f0e0d0c-0b0a-4000-8000-000000000002.csv")
        from uuid import UUID as _UUID
        self.assertEqual(safe_chart_asset_name(_UUID(BLOCK_ID), "svg"),
                         f"chart-{BLOCK_ID}.svg")

    def test_safe_asset_name_rejects_traversal_injection_and_control_chars(self):
        hostile = [
            "../evil", "../../etc/passwd", "a/b", "a\\b", "..", ".", "chart id",
            "chart\tid", "chart\nid", "chart\x00id", "$(touch /tmp/ni057-pwn)",
            "`id`", "; rm -rf /", "${jndi:ldap://x}", "%2e%2e%2f", "chart-<id>",
            "0F0E0D0C-0B0A-4000-8000-000000000001",
            "{0f0e0d0c-0b0a-4000-8000-000000000001}",
            "0f0e0d0c0b0a40008000000000000abc", "x" * 100, "",
        ]
        for chart_id in hostile:
            with self.assertRaises(ChartRendererError, msg=repr(chart_id)) as caught:
                safe_chart_asset_name(chart_id, "svg")
            self.assertEqual(caught.exception.code, "chart_render_failed")
            self.assertIn(("chart_id", "unsafe_chart_identifier"),
                          caught.exception.details)

    def test_safe_asset_name_rejects_bad_extensions(self):
        for extension in ["SVG", "Html", "", "a" * 9, "js/x", "..", "j\tb", "svg;rm"]:
            with self.assertRaises(ChartRendererError, msg=repr(extension)) as caught:
                safe_chart_asset_name(BLOCK_ID, extension)
            self.assertEqual(
                caught.exception.details, ((f"chart-{BLOCK_ID}", "unsafe_asset_extension"),))

    def test_request_from_export_blocks_carries_the_frozen_views(self):
        block = export_chart_block()
        request = chart_render_request([block], width=800, height=450)
        self.assertEqual(request.protocol_version, 1)
        self.assertEqual(request.width, 800)
        self.assertEqual(request.height, 450)
        self.assertEqual(len(request.charts), 1)
        self.assertEqual(request.charts[0].chart_id, block.block_id)
        self.assertEqual(request.charts[0].view, block.view)

    def test_payload_is_strict_json_with_exact_decimal_strings(self):
        payload = charts_module._renderer_payload(chart_request())
        text = payload.decode("utf-8")
        self.assertIn(HUGE_DECIMAL, text)
        self.assertIn('"protocol_version":1', text.replace(" ", ""))
        reparsed = json.loads(text)
        self.assertEqual(reparsed["charts"][0]["view"]["series"][0]["points"][0]["value"],
                         HUGE_DECIMAL)

    def test_oversized_payload_is_refused(self):
        with patch.object(charts_module, "MAX_INPUT_BYTES", 10):
            with self.assertRaises(ChartRendererError) as caught:
                charts_module._renderer_payload(chart_request())
        self.assertEqual(caught.exception.code, "renderer_output_size")
        self.assertEqual(caught.exception.details, (("request", "invalid_payload_size"),))


class InvocationTests(unittest.TestCase):
    """The subprocess seam: ARGV list, no shell, STDIN payload."""

    def test_invocation_uses_argv_list_stdin_and_no_shell(self):
        observed = {}

        def fake_run(argv, **kwargs):
            observed["argv"] = argv
            observed.update(kwargs)
            payload = kwargs["input"]
            envelope = {
                "protocol_version": 1,
                "renderer": {"id": RENDERER_ID, "echarts_version": "6.1.0",
                             "node_version": "test"},
                "input_sha256": charts_module._sha256_hex(payload),
                "charts": [{
                    "chart_id": BLOCK_ID,
                    "svg": "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
                    "svg_sha256": charts_module._sha256_hex(
                        "<svg xmlns='http://www.w3.org/2000/svg'></svg>".encode()),
                    "csv": "header\n",
                    "csv_sha256": charts_module._sha256_hex(b"header\n"),
                    "series_count": 1, "point_count": 3,
                }],
            }
            return subprocess.CompletedProcess(argv, 0,
                                               stdout=json.dumps(envelope).encode(),
                                               stderr=b"")

        with patch.object(charts_module.subprocess, "run", fake_run):
            result = render_chart_assets(chart_request(), node_bin="node-test-bin")
        argv = observed["argv"]
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[0], "node-test-bin")
        self.assertEqual(argv[1], "--no-warnings")
        self.assertTrue(argv[-1].endswith("render-charts.mjs"))
        self.assertNotIn("shell", observed)
        self.assertIsInstance(observed["input"], bytes)
        self.assertIn(HUGE_DECIMAL.encode(), observed["input"])
        self.assertNotIsInstance(result, type(None))

    def test_missing_node_binary_is_a_typed_honest_error(self):
        absent = tempfile.gettempdir() / "ni057-absent-node" if False else os.path.join(
            tempfile.gettempdir(), "ni057-absent-node-binary")
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), node_bin=absent)
        self.assertEqual(caught.exception.code, "renderer_unavailable")
        self.assertIn("node", str(caught.exception).lower())

    def test_missing_renderer_script_is_a_typed_honest_error(self):
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(),
                                renderer_script="/nonexistent/ni057/missing.mjs")
        self.assertEqual(caught.exception.code, "renderer_unavailable")
        self.assertEqual(caught.exception.details,
                         (("renderer_script", "renderer_unavailable"),))

    def test_timeout_expiry_is_a_typed_killed_child(self):
        with patch.object(charts_module.subprocess, "run") as run:
            run.side_effect = subprocess.TimeoutExpired(cmd=["node"], timeout=0.25)
            with self.assertRaises(ChartRendererError) as caught:
                render_chart_assets(chart_request(), timeout=0.25)
        self.assertEqual(caught.exception.code, "renderer_timeout")
        self.assertEqual(caught.exception.details, (("renderer", "renderer_timeout"),))


class RendererSubprocessTests(unittest.TestCase):
    """Real subprocess runs: the pinned renderer and controlled fakes.

    These tests depend on a node runtime on PATH (the same dependency the
    web CI job has); when node is genuinely absent they fail with the typed
    renderer_unavailable error instead of silently skipping.
    """

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="ni057-renderer-")

    def test_render_produces_verified_assets_equal_to_the_frozen_series(self):
        request = chart_request()  # one frozen request; the fixtures mint fresh ids per call
        result = render_chart_assets(request)
        self.assertEqual(result.protocol_version, 1)
        self.assertEqual(result.renderer.id, RENDERER_ID)
        self.assertEqual(result.renderer.echarts_version, "6.1.0")
        self.assertTrue(result.renderer.node_version)
        self.assertEqual(result.script_sha256,
                         charts_module._sha256_hex(RENDERER_SCRIPT_PATH.read_bytes()))
        self.assertEqual(len(result.charts), 1)
        asset = result.charts[0]
        self.assertEqual(str(asset.chart_id), BLOCK_ID)
        self.assertTrue(asset.svg.startswith("<svg"))
        self.assertEqual(asset.series_count, 1)
        self.assertEqual(asset.point_count, 3)
        self.assertEqual(asset.csv, expected_csv())
        self.assertIn(HUGE_DECIMAL, asset.csv)
        charts_module._assert_static_svg(asset.svg, "test")  # must not raise
        self.assertEqual(charts_module._sha256_hex(asset.svg.encode("utf-8")),
                         asset.svg_sha256)
        self.assertEqual(charts_module._sha256_hex(asset.csv.encode("utf-8")),
                         asset.csv_sha256)
        payload = charts_module._renderer_payload(request)
        self.assertEqual(result.input_sha256, charts_module._sha256_hex(payload))
        self.assertIsInstance(result, ChartRenderResult)

    def test_render_is_deterministic(self):
        first = render_chart_assets(chart_request())
        second = render_chart_assets(chart_request())
        self.assertEqual(first.charts[0].svg, second.charts[0].svg)
        self.assertEqual(first.charts[0].csv, second.charts[0].csv)
        self.assertEqual(first.charts[0].svg_sha256, second.charts[0].svg_sha256)
        self.assertEqual(first.charts[0].csv_sha256, second.charts[0].csv_sha256)

    def test_refuses_a_chart_pinned_to_a_foreign_renderer(self):
        request = chart_request()
        drifted = request.charts[0].view.model_dump()
        drifted["definition"]["renderer_version"] = "other-renderer@9"
        drifted_request = ChartRenderRequest(
            protocol_version=1, width=960, height=540,
            charts=(ChartRenderRequestChart(chart_id=BLOCK_ID,
                                            view=ChartViewResponse.model_validate(drifted)),))
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(drifted_request)
        self.assertEqual(caught.exception.code, "renderer_refused")
        self.assertIn("unsupported_renderer", str(caught.exception))

    def test_timeout_expires_with_a_controlled_slow_renderer(self):
        slow = write_fake_renderer(
            Path(self.directory),
            'await new Promise((resolve) => setTimeout(resolve, 5000));\n')
        started = time.monotonic()
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), timeout=0.5, renderer_script=slow)
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.code, "renderer_timeout")
        self.assertLess(elapsed, 4.0, "the timed-out child must actually be killed")

    def test_corrupt_stdout_fails_safely(self):
        garbage = write_fake_renderer(Path(self.directory), 'process.stdout.write("garbage");\n')
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), renderer_script=garbage)
        self.assertEqual(caught.exception.code, "renderer_output_corrupt")

        failing = write_fake_renderer(
            Path(self.directory),
            'process.exitCode = 1;\nprocess.stdout.write("not the error envelope");\n')
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), renderer_script=failing)
        self.assertEqual(caught.exception.code, "renderer_output_corrupt")

    def test_typed_refusal_of_the_renderer_is_surfaced(self):
        refusing = write_fake_renderer(
            Path(self.directory),
            'process.exitCode = 3;\nprocess.stdout.write(JSON.stringify({error: {'
            'protocol_version: 1, code: "unsupported_renderer", '
            'message: "chart pinned to another renderer", details: []}}));\n')
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), renderer_script=refusing)
        self.assertEqual(caught.exception.code, "renderer_refused")
        self.assertIn("unsupported_renderer", str(caught.exception))

    def test_identity_and_input_hash_tampering_is_refused(self):
        impostor = FAITHFUL_FAKE.replace("near-export-chart-renderer@1", "impostor@9")
        script = write_fake_renderer(Path(self.directory), impostor)
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), renderer_script=script)
        self.assertEqual(caught.exception.details,
                         (("renderer", "renderer_identity_mismatch"),))

        hash_liar = FAITHFUL_FAKE.replace(
            'createHash("sha256").update(raw).digest("hex")', '"' + "b" * 64 + '"')
        script = write_fake_renderer(Path(self.directory), hash_liar)
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), renderer_script=script)
        self.assertEqual(caught.exception.details,
                         (("renderer", "input_hash_mismatch"),))

    def test_asset_hash_tampering_is_refused(self):
        tampered = FAITHFUL_FAKE.replace(
            "svg_sha256: hash(svg)", 'svg_sha256: "' + "c" * 64 + '"')
        script = write_fake_renderer(Path(self.directory), tampered)
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), renderer_script=script)
        self.assertEqual(caught.exception.code, "renderer_output_corrupt")
        self.assertEqual(
            caught.exception.details,
            ((f"charts.{BLOCK_ID}.svg", "asset_hash_mismatch"),))

    def test_chart_set_mismatch_is_refused(self):
        dropper = FAITHFUL_FAKE.replace(
            "chart_id: chart.chart_id",
            'chart_id: "ffffffff-ffff-4fff-8fff-ffffffffffff"')
        script = write_fake_renderer(Path(self.directory), dropper)
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), renderer_script=script)
        self.assertEqual(caught.exception.details,
                         (("renderer", "chart_set_mismatch"),))

    def test_unsafe_svg_output_is_refused_by_the_boundary(self):
        hostile = FAITHFUL_FAKE.replace(
            "const svg = '<svg",
            'const svg = \'<svg onload="alert(1)" xmlns="http://www.w3.org/2000/svg"')
        script = write_fake_renderer(Path(self.directory), hostile)
        with self.assertRaises(ChartRendererError) as caught:
            render_chart_assets(chart_request(), renderer_script=script)
        self.assertEqual(caught.exception.code, "renderer_output_corrupt")
        self.assertEqual(
            caught.exception.details,
            ((f"charts.{BLOCK_ID}.svg", "unsafe_svg_output"),))

    def test_oversized_output_is_refused(self):
        with patch.object(charts_module, "MAX_OUTPUT_BYTES", 100):
            with self.assertRaises(ChartRendererError) as caught:
                render_chart_assets(chart_request())
        self.assertEqual(caught.exception.code, "renderer_output_size")

    def test_faithful_fake_passes_the_full_verification_chain(self):
        """The controlled fake proves every verification step except node's
        real rendering, which the pinned-script tests above cover."""
        script = write_fake_renderer(Path(self.directory), FAITHFUL_FAKE)
        result = render_chart_assets(chart_request(), renderer_script=script)
        self.assertIsInstance(result, ChartRenderResult)
        self.assertEqual(result.renderer.echarts_version, "0.0.0-fake")
        self.assertIsInstance(result.charts[0], ChartRenderedChart)


if __name__ == "__main__":
    unittest.main()
