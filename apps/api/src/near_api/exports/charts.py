"""Render static chart assets from frozen contexts (NI-057).

The export IR (:mod:`near_api.schemas.export`) embeds the fully resolved
frozen ``ChartViewResponse`` of every liveChart block (NI-056). This module
turns those pinned payloads into portable static assets — one SVG plus one
normalized CSV per chart — by invoking the pinned Node ECharts SSR renderer
(``apps/web/scripts/render-charts.mjs``) as a subprocess. It is the single
Python/Node boundary of the export pipeline; NI-058 embeds the returned
assets (and the identity recorded here) into the ZIP.

Security and honesty contract:

- **No shell, ever.** The renderer runs through ``subprocess.run`` with an
  ARGV list; the request is passed on STDIN as strict JSON bytes — never as
  shell-interpolated arguments — and the timeout is enforced by the
  subprocess module (the child is killed on expiry).
- **No network, no code.** The renderer script is a repository file; the
  Node side accepts no URL/HTML/code field (strict typed stdin schema) and
  the Python side re-scans every returned SVG for script/foreignObject/
  remote-reference content before accepting it. A renderer that misbehaves
  fails closed instead of shipping an asset.
- **Everything is derived from validated identities.** Asset filenames are
  derived from chart block ids (canonical lowercase UUIDs) with a strict
  pattern — path traversal, shell metacharacters, control characters and
  non-canonical identifiers are rejected. No caller-supplied filesystem
  path is ever accepted; the node binary and renderer script are operator
  configuration (environment), never request data.
- **Frozen view in, exact assets out.** The view is the IR's embedded
  payload — this module never resolves a dataset, a latest pointer or any
  registry row. CSV rows carry the series' exact decimal strings verbatim
  (missing points export as empty values with their quality reason, never
  zero), so the exported assets equal the frozen view the author saw.
- **Renderer identity is recorded.** The result carries the renderer
  protocol id, the echarts version, the renderer script's SHA-256, the
  SHA-256 of the exact request bytes and of every produced asset, so an
  export manifest pins what rendered it (REPRODUCIBILITY).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable, Literal, NoReturn
from uuid import UUID

from pydantic import Field

from near_api.insights.schemas import Sha256Hex
from near_api.schemas.common import ContractModel
from near_api.schemas.delivery import ChartViewResponse
from near_api.schemas.export import ExportChartBlock

RENDERER_PROTOCOL_VERSION = 1
"""The only stdin/stdout protocol this boundary speaks; pinned in the
renderer script as ``RENDERER_PROTOCOL_VERSION``."""

RENDERER_ID = "near-export-chart-renderer@1"
"""The expected renderer identity; a different id is a corrupt result."""

RENDERER_SCRIPT_PATH = Path(__file__).resolve().parents[5] / "apps/web/scripts/render-charts.mjs"
"""The pinned renderer script of this checkout (resolved from this module's
location, never from caller input)."""

RENDERER_NODE_ENV = "NEAR_CHART_RENDERER_NODE"
RENDERER_SCRIPT_ENV = "NEAR_CHART_RENDERER_SCRIPT"
"""Operator/testing configuration seams for the node binary and the renderer
script (deployment pinning and the controlled fake renderers of the test
suite). They are environment configuration — never derived from request data."""

WIDTH_BOUNDS = (120, 2000)
HEIGHT_BOUNDS = (80, 2000)
MAX_CHARTS = 200
"""Mirrors the export IR's block bound; one request renders a whole revision."""

DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_ASSET_BYTES = 12 * 1024 * 1024
"""Byte bounds of the boundary: the Node schema enforces the same per-asset
character bound (8 MiB); the Python side re-checks the UTF-8 bytes with
headroom and caps the whole stdout read."""

_MAX_ERROR_DETAILS = 20
_MAX_ERROR_MESSAGE = 1024
_MAX_DIAGNOSTIC = 500


class ChartRendererError(ValueError):
    """The frozen chart view cannot become safe static assets.

    Typed failure of the rendering boundary: a caller must never fall back
    to a re-resolved (live) view, a partial asset set or an unverified
    renderer identity when this raises.
    """

    def __init__(self, message: str, details: tuple[tuple[str, str], ...] = (),
                 code: str = "chart_render_failed"):
        super().__init__(message)
        self.code = code
        self.details = tuple(details)[:_MAX_ERROR_DETAILS]


# --------------------------------------------------------------------------- #
# Typed protocol contracts (service-level render boundary — deliberately not
# registered in the OpenAPI components; the renderer script is the counterpart)
# --------------------------------------------------------------------------- #


class ChartRenderRequestChart(ContractModel):
    chart_id: UUID
    view: ChartViewResponse


class ChartRenderRequest(ContractModel):
    protocol_version: Literal[RENDERER_PROTOCOL_VERSION]
    width: int = Field(strict=True, ge=WIDTH_BOUNDS[0], le=WIDTH_BOUNDS[1])
    height: int = Field(strict=True, ge=HEIGHT_BOUNDS[0], le=HEIGHT_BOUNDS[1])
    charts: tuple[ChartRenderRequestChart, ...] = Field(min_length=1, max_length=MAX_CHARTS)


class ChartRendererIdentity(ContractModel):
    id: str = Field(min_length=1, max_length=80)
    echarts_version: str = Field(min_length=1, max_length=40)
    node_version: str = Field(min_length=1, max_length=40)


class ChartRenderedChart(ContractModel):
    chart_id: UUID
    svg: str = Field(max_length=MAX_ASSET_BYTES)
    svg_sha256: Sha256Hex
    csv: str = Field(max_length=MAX_ASSET_BYTES)
    csv_sha256: Sha256Hex
    series_count: int = Field(strict=True, ge=0)
    point_count: int = Field(strict=True, ge=0)


class ChartRendererResponse(ContractModel):
    """The strict wire contract of the renderer's successful STDOUT."""

    protocol_version: Literal[RENDERER_PROTOCOL_VERSION]
    renderer: ChartRendererIdentity
    input_sha256: Sha256Hex
    charts: tuple[ChartRenderedChart, ...] = Field(min_length=1, max_length=MAX_CHARTS)


class ChartRenderResult(ChartRendererResponse):
    """The verified render record: the wire response plus the boundary's own
    provenance (the SHA-256 of the exact renderer script bytes that produced
    the assets — computed here, never claimed by the renderer itself)."""

    script_sha256: Sha256Hex


def chart_render_request(blocks: Iterable[ExportChartBlock], *,
                         width: int = 960, height: int = 540) -> ChartRenderRequest:
    """Collect the IR's frozen chart blocks into one typed render request.

    Every ``view`` is the embedded NI-043 reconstruction — nothing here
    resolves datasets, definitions or latest data.
    """
    return ChartRenderRequest(
        protocol_version=RENDERER_PROTOCOL_VERSION, width=width, height=height,
        charts=tuple(ChartRenderRequestChart(chart_id=block.block_id, view=block.view)
                     for block in blocks))


# --------------------------------------------------------------------------- #
# Safe asset filenames (derived from validated identities only)
# --------------------------------------------------------------------------- #

_CANONICAL_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SAFE_EXTENSION = re.compile(r"^[a-z0-9]{1,8}$")


def safe_chart_asset_name(chart_id: UUID | str, extension: str) -> str:
    """Derive the export asset filename of one chart block id.

    Only canonical lowercase UUIDs (or ``UUID`` instances) and simple
    lowercase extensions are accepted; anything else — path traversal,
    separators, shell metacharacters, control characters, uppercase or
    braced UUID spellings — is a typed refusal, never a sanitized guess.
    """
    if isinstance(chart_id, UUID):
        canonical = str(chart_id)
    elif isinstance(chart_id, str) and _CANONICAL_UUID.fullmatch(chart_id):
        canonical = chart_id
    else:
        raise ChartRendererError(
            "A chart asset name must be derived from a canonical lowercase "
            "UUID block id",
            [("chart_id", "unsafe_chart_identifier")])
    if not isinstance(extension, str) or not _SAFE_EXTENSION.fullmatch(extension):
        raise ChartRendererError(
            "A chart asset extension must be a simple lowercase token",
            [(f"chart-{canonical}", "unsafe_asset_extension")])
    return f"chart-{canonical}.{extension}"


# --------------------------------------------------------------------------- #
# Static-safety re-scan (defense in depth against a misbehaving renderer)
# --------------------------------------------------------------------------- #

_UNSAFE_SVG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"<script", re.IGNORECASE), "script element"),
    (re.compile(r"<foreignobject", re.IGNORECASE), "foreignObject element"),
    (re.compile(r"<image", re.IGNORECASE), "image element"),
    (re.compile(r"javascript:", re.IGNORECASE), "javascript URL"),
    (re.compile(r"""href\s*=\s*["']?\s*(?:https?:)?//""", re.IGNORECASE), "remote reference"),
    (re.compile(r"""url\(\s*["']?\s*(?:https?:)?//""", re.IGNORECASE), "remote reference"),
    (re.compile(r"data:text/html", re.IGNORECASE), "HTML data URL"),
    (re.compile(r"""\son[a-z]+\s*=\s*["']""", re.IGNORECASE), "event handler attribute"),
)


def _assert_static_svg(svg: str, path: str) -> None:
    """Refuse any SVG that carries scripts, HTML hosts or remote references.

    The ``xmlns="http://www.w3.org/2000/svg"`` namespace identifier is not a
    reference and does not match these patterns.
    """
    for pattern, label in _UNSAFE_SVG_PATTERNS:
        if pattern.search(svg):
            raise ChartRendererError(
                f"The renderer returned an SVG containing a forbidden {label}",
                [(path, "unsafe_svg_output")], code="renderer_output_corrupt")


def _assert_asset_size(asset: str, path: str) -> None:
    if len(asset.encode("utf-8")) > MAX_ASSET_BYTES:
        raise ChartRendererError(
            f"The rendered asset at {path} exceeds the {MAX_ASSET_BYTES} byte bound",
            [(path, "asset_size_exceeded")], code="renderer_output_size")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
# The subprocess boundary
# --------------------------------------------------------------------------- #


def _renderer_invocation(node_bin: str | None, renderer_script: str | None,
                         ) -> tuple[str, Path, bytes]:
    script = Path(renderer_script or os.environ.get(RENDERER_SCRIPT_ENV)
                  or RENDERER_SCRIPT_PATH)
    try:
        script_bytes = script.read_bytes()
    except OSError as error:
        raise ChartRendererError(
            f"The pinned chart renderer script is unavailable: {script}",
            [("renderer_script", "renderer_unavailable")],
            code="renderer_unavailable") from error
    node = node_bin or os.environ.get(RENDERER_NODE_ENV) or "node"
    return node, script, script_bytes


def _renderer_payload(request: ChartRenderRequest) -> bytes:
    try:
        payload = json.dumps(request.model_dump(mode="json"), ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ChartRendererError(
            "The render request could not be serialized as strict JSON",
            [("request", "invalid_payload")]) from error
    if len(payload) > MAX_INPUT_BYTES:
        raise ChartRendererError(
            f"The render request is {len(payload)} bytes; the boundary accepts "
            f"at most {MAX_INPUT_BYTES}",
            [("request", "invalid_payload_size")], code="renderer_output_size")
    return payload


def render_chart_assets(request: ChartRenderRequest, *,
                        timeout: float = DEFAULT_TIMEOUT_SECONDS,
                        node_bin: str | None = None,
                        renderer_script: str | None = None) -> ChartRenderResult:
    """Render the request's frozen chart views into verified static assets.

    The invocation is a fixed ARGV list (no shell anywhere); the payload
    travels on STDIN, the typed response is read from STDOUT. Every failure
    mode — unavailable node/script, timeout, corrupt or oversized output,
    hash mismatch, unsafe SVG — raises :class:`ChartRendererError` and
    nothing is returned partially.
    """
    node, script, script_bytes = _renderer_invocation(node_bin, renderer_script)
    payload = _renderer_payload(request)
    script_sha256 = _sha256_hex(script_bytes)
    # windowsHide is a Windows-only Popen kwarg; POSIX builds reject it.
    windows_options = {"windowsHide": True} if os.name == "nt" else {}
    try:
        completed = subprocess.run(
            [node, "--no-warnings", str(script)],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, check=False, **windows_options)
    except subprocess.TimeoutExpired as error:
        raise ChartRendererError(
            f"The chart renderer did not finish within {timeout} seconds and "
            "was killed",
            [("renderer", "renderer_timeout")], code="renderer_timeout") from error
    except OSError as error:
        raise ChartRendererError(
            f"The node runtime is unavailable for the chart renderer ({error})",
            [("renderer", "renderer_unavailable")],
            code="renderer_unavailable") from error
    return _verified_result(completed, request, payload, script_sha256)


def _verified_result(completed: subprocess.CompletedProcess[bytes],
                     request: ChartRenderRequest, payload: bytes,
                     script_sha256: str) -> ChartRenderResult:
    if completed.returncode != 0:
        _renderer_failure(completed)
    if len(completed.stdout) > MAX_OUTPUT_BYTES:
        raise ChartRendererError(
            f"The renderer returned {len(completed.stdout)} bytes of output; "
            f"the boundary accepts at most {MAX_OUTPUT_BYTES}",
            [("renderer", "renderer_output_size")], code="renderer_output_size")
    try:
        response = ChartRendererResponse.model_validate_json(completed.stdout)
    except ValueError as error:
        raise ChartRendererError(
            "The renderer returned an output that does not match the typed "
            "render contract",
            [("renderer", "renderer_output_corrupt")],
            code="renderer_output_corrupt") from error
    if response.renderer.id != RENDERER_ID:
        raise ChartRendererError(
            f"The renderer identified itself as {response.renderer.id!r}; this "
            f"boundary speaks to {RENDERER_ID!r} only",
            [("renderer", "renderer_identity_mismatch")],
            code="renderer_output_corrupt")
    if response.input_sha256 != _sha256_hex(payload):
        raise ChartRendererError(
            "The renderer's recorded request hash does not match the bytes "
            "this boundary sent",
            [("renderer", "input_hash_mismatch")],
            code="renderer_output_corrupt")
    expected_ids = [item.chart_id for item in request.charts]
    returned_ids = [chart.chart_id for chart in response.charts]
    if returned_ids != expected_ids:
        raise ChartRendererError(
            "The renderer returned a different chart set than the frozen "
            "request requested",
            [("renderer", "chart_set_mismatch")],
            code="renderer_output_corrupt")
    views = {item.chart_id: item.view for item in request.charts}
    for chart in response.charts:
        view = views[chart.chart_id]
        _assert_asset_size(chart.svg, f"charts.{chart.chart_id}.svg")
        _assert_asset_size(chart.csv, f"charts.{chart.chart_id}.csv")
        _assert_static_svg(chart.svg, f"charts.{chart.chart_id}.svg")
        if chart.svg_sha256 != _sha256_hex(chart.svg.encode("utf-8")):
            raise ChartRendererError(
                f"The SVG of chart {chart.chart_id} does not match its "
                "recorded hash",
                [(f"charts.{chart.chart_id}.svg", "asset_hash_mismatch")],
                code="renderer_output_corrupt")
        if chart.csv_sha256 != _sha256_hex(chart.csv.encode("utf-8")):
            raise ChartRendererError(
                f"The CSV of chart {chart.chart_id} does not match its "
                "recorded hash",
                [(f"charts.{chart.chart_id}.csv", "asset_hash_mismatch")],
                code="renderer_output_corrupt")
        if (chart.series_count != len(view.series)
                or chart.point_count != sum(len(series.points) for series in view.series)):
            raise ChartRendererError(
                f"The rendered asset of chart {chart.chart_id} does not cover "
                "the pinned series exactly",
                [(f"charts.{chart.chart_id}", "series_coverage_mismatch")],
                code="renderer_output_corrupt")
    return ChartRenderResult(script_sha256=script_sha256, **response.model_dump())


def _renderer_failure(completed: subprocess.CompletedProcess[bytes]) -> NoReturn:
    """Surface the renderer's typed error envelope; garbage becomes corrupt."""
    try:
        envelope = json.loads(completed.stdout.decode("utf-8"))
        error = envelope["error"]
        code = error["code"]
        message = str(error["message"])[:_MAX_ERROR_MESSAGE]
        details = tuple(
            (f"renderer.{index}", str(reason)[:_MAX_DIAGNOSTIC])
            for index, reason in enumerate(error.get("details", ()))
        )
        raise ChartRendererError(
            f"The chart renderer refused the request ({code}): {message}",
            details, code="renderer_refused")
    except ChartRendererError:
        raise
    except (ValueError, KeyError, TypeError) as error:
        diagnostic = completed.stderr.decode("utf-8", errors="replace")[:_MAX_DIAGNOSTIC]
        raise ChartRendererError(
            f"The chart renderer exited with code {completed.returncode} and "
            "no typed error",
            [("renderer", diagnostic or "renderer_output_corrupt")],
            code="renderer_output_corrupt") from error
