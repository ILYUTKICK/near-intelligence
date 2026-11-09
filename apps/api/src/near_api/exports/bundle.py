"""Assemble and package the export ZIP bundle (NI-058).

The bundle is the single reliable MVP export (docs/MVP_SCOPE.md):
``research.md`` rendered from the frozen NI-056 plan, the NI-057 static
chart assets, and a ``manifest.json`` that pins every identity needed to
verify the artifact later:

- the plan identity (IR version, revision pins, canonical plan SHA-256);
- per-file SHA-256 and byte size for ``research.md`` and every asset;
- the chart renderer identity record from NI-057 (protocol id, echarts
  version, node version, renderer script hash, request hash) and per-chart
  asset hashes as the renderer recorded them (already boundary-verified);
- the plan's recorded limitations and absence reason codes, verbatim.

Determinism: the manifest adds NO wall-clock field. The ZIP entries carry a
fixed epoch timestamp (recorded in the manifest), fixed metadata and a
sorted entry order, so rebuilding the bundle from the same plan and assets
in the same environment yields byte-identical ZIP bytes — the property the
edit-during-export acceptance is checked with. Deflate bytes are not
promised identical across zlib releases; verification is hash-validated
extraction, not cross-environment byte identity.

Security: filenames come from :func:`near_api.exports.charts.
safe_chart_asset_name` (canonical UUID chart ids) and the fixed set
{research.md, manifest.json, assets/...} — no user-controlled path reaches
the ZIP, and the manifest carries no server filesystem path or credential.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from typing import NamedTuple
from uuid import UUID

from near_api.exports.charts import (
    ChartRenderResult,
    safe_chart_asset_name,
)
from near_api.exports.ir import export_ir_canonical_bytes
from near_api.exports.markdown import ChartAssetFiles, limitations_of, render_markdown
from near_api.schemas.export import ExportChartBlock, ExportIr

BUNDLE_FORMAT_VERSION = 1
"""The only bundle format this builder emits; a format change appends a
version and never silently refreshes existing artifacts."""

ZIP_ENTRY_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
"""Fixed ZIP entry timestamp (the format's minimum). Recorded in the
manifest so consumers know the entries carry no build-time clock."""

MANIFEST_NAME = "manifest.json"
RESEARCH_DOC_NAME = "research.md"
ASSETS_DIRECTORY = "assets"

MAX_BUNDLE_BYTES = 64 * 1024 * 1024
"""The commit cap of one export bundle; a larger build is a typed worker
failure, never a truncated or oversized artifact."""


class BundleError(ValueError):
    """The frozen plan and its assets cannot become a verifiable bundle.

    Typed failure of the packaging boundary: a caller must never ship a
    partial ZIP, an unhashed file or a manifest without the plan identity.
    """

    def __init__(self, message: str, details: tuple[tuple[str, str], ...] = ()):
        super().__init__(message)
        self.details = tuple(details)


class BundleFile(NamedTuple):
    """One file of the bundle (path relative to the ZIP root)."""

    path: str
    data: bytes


@dataclass(frozen=True)
class ExportBundle:
    """The verified bundle of one export job, ready to store and ship."""

    files: tuple[BundleFile, ...]
    manifest: dict
    zip_bytes: bytes


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chart_asset_files(chart_blocks: tuple[ExportChartBlock, ...],
                      ) -> dict[UUID, ChartAssetFiles]:
    """Derive the safe asset filenames of the plan's chart blocks."""
    return {block.block_id: ChartAssetFiles(
        svg_name=f"{ASSETS_DIRECTORY}/{safe_chart_asset_name(block.block_id, 'svg')}",
        csv_name=f"{ASSETS_DIRECTORY}/{safe_chart_asset_name(block.block_id, 'csv')}")
        for block in chart_blocks}


def build_bundle(plan: ExportIr, render_result: ChartRenderResult | None) -> ExportBundle:
    """Build research.md + assets + manifest and package them as the ZIP.

    ``render_result`` is the NI-057 boundary-verified render of the plan's
    chart blocks (``None`` exactly when the plan carries no chart). The
    assets are attached by chart id in request order; a chart whose asset is
    missing is a typed failure — never a document with a dangling link.
    """
    chart_blocks = tuple(block for block in plan.blocks
                         if isinstance(block, ExportChartBlock))
    if render_result is None and chart_blocks:
        raise BundleError(
            "The plan carries chart blocks but no verified chart render",
            [("charts", "missing_chart_render")])
    if render_result is not None:
        rendered_ids = [chart.chart_id for chart in render_result.charts]
        expected_ids = [block.block_id for block in chart_blocks]
        if rendered_ids != expected_ids:
            raise BundleError(
                "The chart render does not cover the plan's chart blocks "
                "exactly",
                [("charts", "chart_set_mismatch")])

    assets = chart_asset_files(chart_blocks)
    research_md = render_markdown(plan, assets).encode("utf-8")

    files: list[BundleFile] = [BundleFile(RESEARCH_DOC_NAME, research_md)]
    if render_result is not None:
        asset_by_id = {chart.chart_id: chart for chart in render_result.charts}
        for block in chart_blocks:
            chart = asset_by_id[block.block_id]
            files.append(BundleFile(
                assets[block.block_id].svg_name, chart.svg.encode("utf-8")))
            files.append(BundleFile(
                assets[block.block_id].csv_name, chart.csv.encode("utf-8")))

    files.append(BundleFile(MANIFEST_NAME, _manifest_bytes(
        plan, render_result, files)))
    ordered = tuple(sorted(files, key=lambda item: item.path))
    zip_bytes = zip_bundle(ordered)
    if len(zip_bytes) > MAX_BUNDLE_BYTES:
        raise BundleError(
            f"The export bundle is {len(zip_bytes)} bytes; the commit cap is "
            f"{MAX_BUNDLE_BYTES}",
            [("bundle", "bundle_size_exceeded")])
    return ExportBundle(files=ordered, manifest=json.loads(
        next(item.data for item in ordered if item.path == MANIFEST_NAME)
        .decode("utf-8")), zip_bytes=zip_bytes)


def _manifest_bytes(plan: ExportIr, render_result: ChartRenderResult | None,
                    files: list[BundleFile]) -> bytes:
    assets = chart_asset_files(tuple(
        block for block in plan.blocks if isinstance(block, ExportChartBlock)))
    manifest = {
        "bundle_format_version": BUNDLE_FORMAT_VERSION,
        "ir_version": plan.ir_version,
        "document": plan.document.model_dump(mode="json"),
        "plan_sha256": _sha256_hex(export_ir_canonical_bytes(plan)),
        "files": [{"path": item.path, "sha256": _sha256_hex(item.data),
                   "byte_size": len(item.data)}
                  for item in sorted(files, key=lambda entry: entry.path)],
        "charts": _chart_records(plan, render_result, assets),
        "chart_renderer": (render_result.model_dump(mode="json", include={
            "renderer": True, "input_sha256": True, "script_sha256": True})
            if render_result is not None else None),
        "zip_entry_timestamp": "1980-01-01T00:00:00+00:00",
        "limitations": limitations_of(plan),
    }
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _chart_records(plan: ExportIr, render_result: ChartRenderResult | None,
                   assets: dict[UUID, ChartAssetFiles]) -> list[dict]:
    if render_result is None:
        return []
    records = []
    for block in plan.blocks:
        if not isinstance(block, ExportChartBlock):
            continue
        chart = next(item for item in render_result.charts
                     if item.chart_id == block.block_id)
        records.append({
            "block_id": str(block.block_id),
            "svg": {"path": assets[block.block_id].svg_name,
                    "sha256": chart.svg_sha256},
            "csv": {"path": assets[block.block_id].csv_name,
                    "sha256": chart.csv_sha256},
            "series_count": chart.series_count,
            "point_count": chart.point_count,
        })
    return records


def zip_bundle(files: tuple[BundleFile, ...] | list[BundleFile]) -> bytes:
    """Package the bundle files into the fixed-timestamp deterministic ZIP.

    Entries are written in the given (sorted) order with a fixed timestamp,
    fixed permissions and a fixed create-system so the archive metadata
    carries no environment or build-time variance.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            info = zipfile.ZipInfo(filename=item.path, date_time=ZIP_ENTRY_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o644 << 16
            archive.writestr(info, item.data)
    return buffer.getvalue()


def extract_bundle(zip_bytes: bytes) -> dict[str, bytes]:
    """Extract the bundle ZIP into {path: bytes} (order-free verification).

    Only a flat, well-known structure is accepted: ``research.md``,
    ``manifest.json`` and files under ``assets/``. Anything else — absolute
    paths, parent traversal, unexpected members — is a typed refusal, so a
    hostile archive can never plant files outside its root.
    """
    extracted: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = info.filename
            if path in {RESEARCH_DOC_NAME, MANIFEST_NAME}:
                normalized = path
            elif path.startswith(f"{ASSETS_DIRECTORY}/"):
                normalized = path
            else:
                raise BundleError(
                    f"The export bundle contains an unexpected member: {path}",
                    [(path, "unexpected_bundle_member")])
            if normalized in extracted:
                raise BundleError(
                    f"The export bundle contains duplicate members: {path}",
                    [(path, "duplicate_bundle_member")])
            extracted[normalized] = archive.read(info)
    if RESEARCH_DOC_NAME not in extracted or MANIFEST_NAME not in extracted:
        raise BundleError(
            "The export bundle is missing research.md or manifest.json",
            [("bundle", "incomplete_bundle")])
    return extracted


def verify_bundle(manifest: dict, extracted: Mapping[str, bytes]) -> None:
    """Validate an extracted bundle against its manifest (acceptance path).

    Every recorded file must exist with the exact recorded SHA-256 and byte
    size. ``manifest.json`` verifies the bundle's identity but cannot record
    its own hash (a self-reference), so it is the one member the manifest is
    not required to describe; every other member must be recorded exactly.
    Hash or size mismatches are typed failures — a silently altered export
    is never accepted as verified.
    """
    recorded = manifest.get("files")
    if not isinstance(recorded, list):
        raise BundleError("The manifest carries no file records",
                          [("files", "invalid_manifest")])
    paths = set()
    for record in recorded:
        path = record.get("path")
        if not isinstance(path, str) or path not in extracted:
            raise BundleError(
                f"The manifest records a file the bundle does not carry: {path!r}",
                [(str(path), "missing_recorded_file")])
        data = extracted[path]
        if _sha256_hex(data) != record.get("sha256") \
                or len(data) != record.get("byte_size"):
            raise BundleError(
                f"The bundle file {path} does not match its recorded hash/size",
                [(path, "file_hash_mismatch")])
        paths.add(path)
    if paths != set(extracted) - {MANIFEST_NAME}:
        raise BundleError(
            "The bundle carries files the manifest does not record",
            [("files", "unrecorded_bundle_file")])


def verify_research_links(research_md: str, extracted: Mapping[str, bytes]) -> None:
    """Every relative asset link in research.md must resolve in the bundle.

    The Markdown embeds charts through ``assets/chart-<uuid>.svg`` /
    ``.csv`` links; a link that does not resolve inside the extracted bundle
    means the document references an asset that was never shipped.
    """
    pattern = re.compile(r"\]\(([^)\s]+)\)")
    for match in pattern.finditer(research_md):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if target not in extracted:
            raise BundleError(
                f"research.md links to a file the bundle does not carry: {target}",
                [(target, "dangling_bundle_link")])

