"""Deterministic PDF rendering of the frozen export plan (NI-059).

Renders the NI-056 ``ExportIr`` of ONE immutable revision into a static PDF
report — the same evidence the Markdown bundle carries, paginated as a
polished document. The renderer is a pure function of the plan and the
boundary-verified chart assets: no clock, no registry lookup, no latest
pointer, no network, and — per the NI-059 acceptance — NO screenshot or
browser path anywhere: figures are the NI-057 SSR SVG assets embedded as
vector drawings through svglib, so a chart can never fetch anything at view
time.

Honesty rules carried over from the Markdown renderer (``markdown.py``):

- Every value comes from the plan and the verified assets. Missing chart
  points stay missing: the chart-data appendix renders the CSV asset's rows
  exactly (empty value with its recorded reason, never zero). Bounds stay
  bounds: ``value_kind`` travels with every exact value.
- Attribution is the revision's own: title, author, revision number, content
  hash and the revision's recorded creation time. Nothing is refreshed.
- Unrenderable content does not exist here: every block the plan can carry
  is mapped exhaustively, and a block outside the renderer's knowledge fails
  closed with a typed error — never a silent skip. (The ``modelResult``
  branch of NI-055 is implemented duck-typed against that block's recorded
  shape so the combined tree renders it; on a tree without it the branch is
  simply unreachable.)
- User text is rendered inert: text goes through ReportLab's Paragraph
  markup with ``&``/``<``/``>`` escaped, so prose can never inject markup,
  and the SVG chart assets were already static-safety-scanned by the NI-057
  boundary before they reach this module.

No clipped charts or tables:

- Figures are scaled to the printable width (and a page-height cap) with
  their aspect ratio preserved; a chart asset that cannot be embedded at all
  is a typed failure — the export never crops silently.
- Tables are built from wrapping paragraph cells with repeating header rows,
  so rows grow and tables split across pages instead of clipping; wide
  columns wrap their exact values line-by-line rather than truncating them.

Determinism (the repo's byte-identical-artifact ethos): ReportLab's
``invariant`` mode pins the document ID and the PDF timestamps, the document
metadata is fixed content (no wall clock), and the fonts are the DejaVu
TTFs bundled INSIDE the frozen dependency set (``matplotlib/mpl-data``),
registered explicitly — the container ships no system fonts and nothing is
downloaded. Rendering the same plan and assets twice yields byte-identical
PDF bytes (test-enforced). A glyph outside the registered font's coverage is
a typed failure (``glyph_not_covered``): the export refuses instead of
shipping invisible/box characters.

The chart-data appendix decision: the Markdown bundle links each chart's
CSV; the PDF carries the same rows as an exact-value table per figure
(mono-spaced, verbatim strings), so a printed PDF still carries every exact
value. The verification identity (plan SHA-256, content hash, chart renderer
record) is printed in the document so the artifact stays verifiable without
the ZIP's ``manifest.json`` — which remains the reference record of the
Markdown bundle of the same revision.
"""

from __future__ import annotations

import csv as csv_module
import hashlib
import io
import re
import xml.etree.ElementTree as ElementTree
from importlib.util import find_spec
from pathlib import Path
from uuid import UUID

from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import ParagraphStyle
from svglib.svglib import svg2rlg

from near_api.exports.charts import ChartRenderResult
from near_api.exports.ir import export_ir_canonical_bytes
from near_api.exports.markdown import limitations_of
from near_api.insights.schemas import (
    ModelContext,
    RichTextListItem,
    RichTextList,
    RichTextParagraph,
    RichTextRun,
)
from near_api.schemas.export import (
    ExportBlock,
    ExportChartBlock,
    ExportDataTableBlock,
    ExportDividerBlock,
    ExportEvidenceBlock,
    ExportHeadingBlock,
    ExportHypothesisBlock,
    ExportInsightBlock,
    ExportIr,
    ExportListBlock,
    ExportParagraphBlock,
    ExportRiskBlock,
)

_BUNDLE_IR_VERSION = 1
"""The only IR version this renderer accepts (a mismatch is a typed drift
failure — the PDF of an unknown plan version is never fabricated)."""

_MAX_RENDER_ERROR_DETAILS = 20

PDF_FORMAT_VERSION = 1
"""The only PDF layout version this renderer emits; a layout change appends
a version and never silently refreshes existing artifacts."""

_FONT_FAMILY = "NEAR-DejaVu"
_FONT_REGULAR = "NEAR-DejaVu"
_FONT_BOLD = "NEAR-DejaVu-Bold"
_FONT_ITALIC = "NEAR-DejaVu-Italic"
_FONT_BOLD_ITALIC = "NEAR-DejaVu-BoldItalic"
_FONT_MONO = "NEAR-DejaVuMono"
_FONT_MONO_BOLD = "NEAR-DejaVuMono-Bold"
_SVG_FONT_FAMILY = "NEAR-DejaVu"
"""The single font family the PDF text layer uses. The TTFs come from the
matplotlib package data inside the frozen dependency set (recorded in
docs/DEPENDENCIES.md); DejaVu covers Latin/Cyrillic/Greek and common
symbols, and anything outside the coverage is a typed refusal."""

_FONT_FILES = {
    _FONT_REGULAR: "DejaVuSans.ttf",
    _FONT_BOLD: "DejaVuSans-Bold.ttf",
    _FONT_ITALIC: "DejaVuSans-Oblique.ttf",
    _FONT_BOLD_ITALIC: "DejaVuSans-BoldOblique.ttf",
    _FONT_MONO: "DejaVuSansMono.ttf",
    _FONT_MONO_BOLD: "DejaVuSansMono-Bold.ttf",
}

# --------------------------------------------------------------------------- #
# Typed failure (the drift guard)
# --------------------------------------------------------------------------- #


class PdfRenderError(ValueError):
    """The frozen plan and its assets cannot become the PDF report.

    Typed drift guard: a plan this module does not understand, an asset that
    cannot be embedded, or a character the export font does not cover fails
    closed instead of rendering a degraded document.
    """

    def __init__(self, message: str, details: tuple[tuple[str, str], ...] = ()):
        super().__init__(message)
        self.details = tuple(details)[:_MAX_RENDER_ERROR_DETAILS]


def _refuse(message: str, path: str, reason: str) -> PdfRenderError:
    return PdfRenderError(message, [(path, reason)])


# --------------------------------------------------------------------------- #
# Fonts (registered lazily, deterministic, no system or downloaded fonts)
# --------------------------------------------------------------------------- #

_FONTS_REGISTERED = False
_COVERAGE: dict[str, frozenset[str]] = {}


def _font_directory() -> Path:
    """The bundled DejaVu TTF directory of the frozen dependency set.

    Resolved from the installed ``matplotlib`` package data without executing
    matplotlib's (heavy) ``__init__``; the renderer must never rely on system
    fonts or download anything.
    """
    spec = find_spec("matplotlib")
    if spec is None or not spec.submodule_search_locations:
        raise _refuse(
            "The bundled DejaVu font directory is unavailable: matplotlib is "
            "not installed", "fonts", "fonts_unavailable")
    base = Path(next(iter(spec.submodule_search_locations)))
    directory = base / "mpl-data" / "fonts" / "ttf"
    if not directory.is_dir():
        raise _refuse(
            f"The bundled DejaVu font directory is unavailable: {directory}",
            "fonts", "fonts_unavailable")
    return directory


def _ensure_fonts() -> None:
    """Register the DejaVu TTFs once (ReportLab + the svglib font map)."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    directory = _font_directory()
    paths: dict[str, Path] = {}
    for name, filename in _FONT_FILES.items():
        path = directory / filename
        if not path.is_file():
            raise _refuse(
                f"The bundled DejaVu font file is unavailable: {path}",
                "fonts", "fonts_unavailable")
        pdfmetrics.registerFont(TTFont(name, str(path)))
        paths[name] = path
    pdfmetrics.registerFontFamily(
        _FONT_FAMILY, normal=_FONT_REGULAR, bold=_FONT_BOLD,
        italic=_FONT_ITALIC, boldItalic=_FONT_BOLD_ITALIC)
    # The svglib font map: SVG text resolves family/weight/style through it,
    # so the embedded chart SVGs use exactly the same registered faces.
    from svglib.fonts import get_global_font_map

    font_map = get_global_font_map()
    for weight, style, name in (
        ("normal", "normal", _FONT_REGULAR),
        ("bold", "normal", _FONT_BOLD),
        ("normal", "italic", _FONT_ITALIC),
        ("bold", "italic", _FONT_BOLD_ITALIC),
    ):
        font_map.register_font(_SVG_FONT_FAMILY, font_path=str(paths[name]),
                               weight=weight, style=style, rlgFontName=name)
    _COVERAGE[_FONT_REGULAR] = frozenset(
        pdfmetrics.getFont(_FONT_REGULAR).face.charToGlyph)
    _COVERAGE[_FONT_MONO] = frozenset(
        pdfmetrics.getFont(_FONT_MONO).face.charToGlyph)
    _FONTS_REGISTERED = True


def _require_glyphs(text: str, path: str, *, mono: bool = False) -> None:
    """Fail closed on characters the export font does not cover.

    A missing glyph would render as an invisible/box character — fabricated-
    looking output. The export refuses typed instead, naming the first
    uncovered codepoint (DejaVu's family coverage is uniform across the
    regular/bold/italic faces, so the regular face is the reference; exact-
    value tables use the mono face explicitly).
    """
    covered = _COVERAGE[_FONT_MONO if mono else _FONT_REGULAR]
    for char in text:
        if ord(char) not in covered:
            raise _refuse(
                "The PDF export font (DejaVu) does not cover U+"
                f"{ord(char):04X}; the export refuses instead of rendering "
                "an uncovered character",
                path, "glyph_not_covered")


# --------------------------------------------------------------------------- #
# Inert text rendering (sanitize exports)
# --------------------------------------------------------------------------- #

_FLATTEN = str.maketrans({"\n": " ", "\r": "", "\t": " "})


def escape_text(value: str) -> str:
    """Render one user-text fragment inert for the PDF text layer.

    Line breaks flatten to spaces, control characters are dropped, and the
    XML markup characters of ReportLab's Paragraph grammar are escaped — so
    user prose can never inject structure into the document.
    """
    cleaned = value.translate(_FLATTEN)
    cleaned = "".join(char for char in cleaned if ord(char) >= 0x20)
    return (cleaned.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _escape_href(href: str) -> str:
    """Escape one canonical link target for a Paragraph attribute."""
    cleaned = "".join(char for char in href if ord(char) >= 0x20)
    return (cleaned.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


_LINK_COLOR = "#1c5aa8"


def _runs_markup(runs: Iterable[RichTextRun]) -> str:
    """Render typed runs into inert Paragraph markup (bold/italic/link)."""
    parts: list[str] = []
    for run in runs:
        text = escape_text(run.text)
        if any(mark.type == "bold" for mark in run.marks):
            text = f"<b>{text}</b>"
        if any(mark.type == "italic" for mark in run.marks):
            text = f"<i>{text}</i>"
        for mark in run.marks:
            if mark.type == "link":
                text = (f'<link href="{_escape_href(mark.attrs.href)}" '
                        f'color="{_LINK_COLOR}"><u>{text}</u></link>')
        parts.append(text)
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Layout constants and styles (fixed — no environment-dependent sizes)
# --------------------------------------------------------------------------- #

_PAGE_WIDTH, _PAGE_HEIGHT = A4
_MARGIN = 48
_TOP_MARGIN = 60
_BOTTOM_MARGIN = 56
_FRAME_WIDTH = _PAGE_WIDTH - 2 * _MARGIN
_FRAME_HEIGHT = _PAGE_HEIGHT - _TOP_MARGIN - _BOTTOM_MARGIN
_MAX_FIGURE_HEIGHT = _FRAME_HEIGHT - 72
"""A figure never renders taller than this (leaving room for its caption);
the scale-to-fit uses it so a chart is never cropped."""

_CARD_BACKGROUND = colors.HexColor("#f2f3f5")
_CARD_BORDER = colors.HexColor("#9aa1a9")
_TABLE_HEADER_BACKGROUND = colors.HexColor("#eef0f2")
_GRID_COLOR = colors.HexColor("#c8ccd1")
_MUTED_TEXT = colors.HexColor("#3d434a")
_LINK_INK = colors.HexColor("#1c5aa8")


def _styles() -> dict[str, ParagraphStyle]:
    """The fixed style set (deterministic; no environment lookups)."""
    return {
        "title": ParagraphStyle(
            "title", fontName=_FONT_BOLD, fontSize=17, leading=22,
            spaceAfter=6, textColor=colors.black),
        "attribution": ParagraphStyle(
            "attribution", fontName=_FONT_REGULAR, fontSize=9, leading=13,
            spaceAfter=4, textColor=_MUTED_TEXT),
        "heading1": ParagraphStyle(
            "heading1", fontName=_FONT_BOLD, fontSize=14, leading=18,
            spaceBefore=14, spaceAfter=6, keepWithNext=1,
            textColor=colors.black),
        "heading2": ParagraphStyle(
            "heading2", fontName=_FONT_BOLD, fontSize=12, leading=16,
            spaceBefore=12, spaceAfter=5, keepWithNext=1,
            textColor=colors.black),
        "heading3": ParagraphStyle(
            "heading3", fontName=_FONT_BOLD, fontSize=10.5, leading=14,
            spaceBefore=10, spaceAfter=4, keepWithNext=1,
            textColor=colors.black),
        "body": ParagraphStyle(
            "body", fontName=_FONT_REGULAR, fontSize=9.5, leading=13.5,
            spaceAfter=5, textColor=colors.black),
        "list_item": ParagraphStyle(
            "list_item", fontName=_FONT_REGULAR, fontSize=9.5, leading=13.5,
            spaceAfter=2, leftIndent=14, bulletIndent=4,
            textColor=colors.black),
        "card_label": ParagraphStyle(
            "card_label", fontName=_FONT_REGULAR, fontSize=9.5, leading=13.5,
            spaceBefore=6, spaceAfter=2, backColor=_CARD_BACKGROUND,
            borderColor=_CARD_BORDER, borderWidth=0.8, borderPadding=4,
            leftIndent=2, textColor=colors.black),
        "card_body": ParagraphStyle(
            "card_body", fontName=_FONT_REGULAR, fontSize=9.5, leading=13.5,
            spaceAfter=2, backColor=_CARD_BACKGROUND,
            borderColor=_CARD_BORDER, borderWidth=0.8, borderPadding=4,
            leftIndent=2, textColor=colors.black),
        "card_meta": ParagraphStyle(
            "card_meta", fontName=_FONT_REGULAR, fontSize=8.5, leading=12,
            spaceAfter=2, spaceBefore=2, backColor=_CARD_BACKGROUND,
            borderColor=_CARD_BORDER, borderWidth=0.8, borderPadding=4,
            leftIndent=2, textColor=_MUTED_TEXT),
        "caption": ParagraphStyle(
            "caption", fontName=_FONT_REGULAR, fontSize=8, leading=11,
            spaceBefore=4, spaceAfter=8, textColor=_MUTED_TEXT),
        "table_header": ParagraphStyle(
            "table_header", fontName=_FONT_BOLD, fontSize=8.5, leading=11.5,
            textColor=colors.black),
        "table_cell": ParagraphStyle(
            "table_cell", fontName=_FONT_REGULAR, fontSize=8.5, leading=11.5,
            textColor=colors.black),
        "mono_cell": ParagraphStyle(
            "mono_cell", fontName=_FONT_MONO, fontSize=7.5, leading=10,
            textColor=colors.black),
        "mono_header": ParagraphStyle(
            "mono_header", fontName=_FONT_MONO_BOLD, fontSize=7.5, leading=10,
            textColor=colors.black),
        "appendix_label": ParagraphStyle(
            "appendix_label", fontName=_FONT_BOLD, fontSize=9.5, leading=13,
            spaceBefore=10, spaceAfter=3, keepWithNext=1,
            textColor=colors.black),
    }


# --------------------------------------------------------------------------- #
# Rich bodies, lists and cards
# --------------------------------------------------------------------------- #


def _body_flowables(body, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    """Render an annotation body (paragraphs and nested lists)."""
    flowables: list[Flowable] = []
    for child in body:
        if isinstance(child, RichTextParagraph):
            flowables.append(Paragraph(_runs_markup(child.content),
                                       styles["card_body"]))
        elif isinstance(child, RichTextList):
            flowables.extend(_list_flowables(
                child.content, ordered=child.type == "ordered_list",
                styles=styles, depth=1))
        else:  # pragma: no cover - the typed union is closed
            raise _refuse(
                "The frozen plan contains an annotation body the PDF "
                "renderer does not support", "body", "unsupported_body_child")
    return flowables


def _list_flowables(items: tuple[RichTextListItem, ...], *, ordered: bool,
                    styles: dict[str, ParagraphStyle], depth: int) -> list[Flowable]:
    """Render list items recursively (the canonical nested-list grammar).

    A nested list flows under its parent item, indented one step further;
    numbering restarts per list exactly like the Markdown renderer's.
    """
    flowables: list[Flowable] = []
    for index, item in enumerate(items, start=1):
        marker = f"{index}." if ordered else "•"
        inline: list[str] = []
        nested: list[Flowable] = []
        for child in item.content:
            if isinstance(child, RichTextParagraph):
                inline.append(_runs_markup(child.content))
            elif isinstance(child, RichTextList):
                nested.extend(_list_flowables(
                    child.content, ordered=child.type == "ordered_list",
                    styles=styles, depth=depth + 1))
            else:  # pragma: no cover - the typed union is closed
                raise _refuse(
                    "The frozen plan contains a list child the PDF renderer "
                    "does not support", "list_item", "unsupported_list_child")
        style = ParagraphStyle(
            f"list-{depth}", parent=styles["list_item"],
            leftIndent=14 * depth, bulletIndent=14 * (depth - 1) + 4)
        flowables.append(Paragraph(
            " ".join(inline).rstrip(), style, bulletText=marker))
        flowables.extend(nested)
    return flowables


def _context_lines(context) -> list[str]:
    """The pinned-context provenance lines of an insight card (mirrors the
    Markdown renderer's ``_context_lines`` semantics, without backticks)."""
    if isinstance(context, ModelContext):
        return [f"model run {context.model_run_id}"]
    selection = context.selection
    return [
        f"chart definition version {context.chart_definition_version_id}",
        f"dataset version {context.dataset_version_id}",
        f"window {selection.start} to {selection.end} ({selection.frequency})",
        f"resolved at {context.resolved_at}",
        f"context hash {context.context_hash}",
    ]


# --------------------------------------------------------------------------- #
# Block rendering (exhaustive over the export contract)
# --------------------------------------------------------------------------- #


class _FigureAssets:
    """The verified assets of one chart block."""

    def __init__(self, chart):
        self.svg = chart.svg
        self.csv = chart.csv


def _embed_drawing(svg: str, path: str) -> Drawing:
    """Parse one boundary-verified chart SVG into a scaled ReportLab drawing.

    The SVG's font-family declarations are rewritten to the registered
    export family (a deterministic, content-neutral transform of the same
    declaration the NI-057 renderer emits), then the drawing is scaled to
    the printable width and the figure-height cap — aspect ratio preserved,
    never cropped. A parse failure or a degenerate drawing is a typed
    refusal, never a blank box.
    """
    _require_svg_text_coverage(svg, path)
    mapped = re.sub(r"font-family\s*:\s*[^;}\"]+", f"font-family:{_SVG_FONT_FAMILY}", svg)
    mapped = re.sub(r"""font-family\s*=\s*"[^"]*""", f'font-family="{_SVG_FONT_FAMILY}"',
                    mapped)
    try:
        drawing = svg2rlg(io.StringIO(mapped))
    except Exception as error:  # noqa: BLE001 - typed refusal, never a partial PDF
        raise _refuse(
            f"The chart asset at {path} could not be embedded as a vector "
            f"drawing ({error!r})", path, "chart_embed_failed") from error
    if drawing is None or drawing.width <= 0 or drawing.height <= 0:
        raise _refuse(
            f"The chart asset at {path} is empty or degenerate and cannot be "
            "embedded", path, "chart_embed_failed")
    scale = min(_FRAME_WIDTH / drawing.width, _MAX_FIGURE_HEIGHT / drawing.height, 1.0)
    drawing.scale(scale, scale)
    drawing.width *= scale
    drawing.height *= scale
    return drawing


_TEXT_TAGS = ("}text", "}tspan")


def _svg_text_nodes(svg: str) -> str:
    """All rendered text content of one chart SVG (for glyph coverage)."""
    texts: list[str] = []
    root = ElementTree.fromstring(svg)
    for element in root.iter():
        tag = element.tag
        if isinstance(tag, str) and (tag.endswith("text") or tag.endswith("tspan")):
            texts.extend(element.itertext())
    return "".join(texts)


def _require_svg_text_coverage(svg: str, path: str) -> None:
    try:
        text = _svg_text_nodes(svg)
    except ElementTree.ParseError as error:
        raise _refuse(
            f"The chart asset at {path} is not well-formed XML and cannot be "
            "embedded", path, "chart_embed_failed") from error
    _require_glyphs(text, path)


def _figure_flowables(block: ExportChartBlock, assets: _FigureAssets,
                      number: int, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    drawing = _embed_drawing(assets.svg, f"charts.{block.block_id}.svg")
    caption = Paragraph(
        f"<b>Figure {number}.</b> Frozen chart view of block "
        f"{block.block_id} — chart definition version "
        f"{block.chart_definition_version_id}, dataset version "
        f"{block.observed_dataset_version_id}, resolved {block.view.resolved_at}. "
        f"Exact values: chart-data appendix, table {number}.",
        styles["caption"])
    return [KeepTogether([drawing, caption])]


def _cell_text(cell) -> str:
    """One authored cell verbatim (mirrors the Markdown renderer)."""
    if cell is None:
        return ""
    if cell is True:
        return "true"
    if cell is False:
        return "false"
    return str(cell)


def _column_widths(header_lengths: list[int], body_max_lengths: list[int],
                   count: int) -> list[float]:
    """Content-weighted column widths over the printable width.

    Cells are wrapping paragraphs, so every column stays readable and no
    cell is ever clipped; narrow tables get proportional widths, and past
    ten columns the width is distributed evenly (each column then wraps its
    values line-by-line — exact but taller).
    """
    if count > 10:
        even = _FRAME_WIDTH / count
        return [even] * count
    weights = [max(min(header, 40), min(body, 40), 6) + 4
               for header, body in zip(header_lengths, body_max_lengths)]
    total = sum(weights)
    widths = [_FRAME_WIDTH * weight / total for weight in weights]
    # Normalize to the exact frame width (float rounding guard).
    correction = (_FRAME_WIDTH - sum(widths)) / count
    return [width + correction for width in widths]


def _data_table_flowables(block: ExportDataTableBlock,
                          styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    header_lengths = [len(column.label) + (len(column.unit or "") + 2)
                      for column in block.columns]
    body_max: list[int] = []
    rows = None
    if block.rows is not None:
        rows = [[Paragraph(escape_text(_cell_text(cell)), styles["table_cell"])
                 for cell in row] for row in block.rows]
        for row in block.rows:
            for index, cell in enumerate(row):
                length = len(_cell_text(cell))
                if index < len(body_max):
                    body_max[index] = max(body_max[index], length)
                else:
                    body_max.append(length)
    header = [Paragraph(escape_text(column.label)
                        + (f" ({escape_text(column.unit)})" if column.unit else ""),
                        styles["table_header"])
              for column in block.columns]
    count = len(block.columns)
    body_max += [0] * (count - len(body_max))
    widths = _column_widths(header_lengths, body_max, count)
    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _TABLE_HEADER_BACKGROUND),
        ("GRID", (0, 0), (-1, -1), 0.4, _GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    flowables: list[Flowable] = []
    if rows is None:
        dataset = block.dataset
        assert dataset is not None  # the export contract keeps exactly one payload
        pin = Paragraph(
            f"Projected from approved dataset {escape_text(dataset.dataset_key)} "
            f"version {dataset.version} (content {dataset.content_sha256}). "
            "The projection resolves through this immutable dataset version, "
            "never a latest pointer.", styles["card_meta"])
        flowables.append(KeepTogether([Table([header], colWidths=widths,
                                              repeatRows=1, style=table_style),
                                       pin]))
    else:
        flowables.append(Table([header, *rows], colWidths=widths,
                               repeatRows=1, style=table_style))
    flowables.append(Spacer(1, 6))
    return flowables


def _exact_value_table(csv_text: str, path: str,
                       styles: dict[str, ParagraphStyle]) -> Table:
    """The chart's CSV asset as an exact-value table (verbatim strings).

    The normalized long-format CSV of the NI-057 renderer is parsed with the
    standard RFC-4180 reader and every field is rendered verbatim — exact
    decimal strings, bound kinds, quality reasons; missing values stay
    empty. Numbers are never reformatted.
    """
    rows = list(csv_module.reader(io.StringIO(csv_text)))
    if not rows:
        raise _refuse(f"The chart CSV asset at {path} is empty",
                      path, "chart_embed_failed")
    count = len(rows[0])
    for row in rows[1:]:
        if len(row) != count:
            raise _refuse(
                f"The chart CSV asset at {path} has a ragged row; the "
                "exact-value table refuses instead of guessing",
                path, "chart_embed_failed")
    for text in (cell for row in rows for cell in row):
        _require_glyphs(text, path, mono=True)
    header = [Paragraph(escape_text(cell), styles["mono_header"])
              for cell in rows[0]]
    body = [[Paragraph(escape_text(cell), styles["mono_cell"]) for cell in row]
            for row in rows[1:]]
    widths = _column_widths([len(cell) for cell in rows[0]],
                            [max([len(row[index]) for row in rows[1:]], default=0)
                             for index in range(count)],
                            count)
    return Table([header, *body], colWidths=widths, repeatRows=1, style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _TABLE_HEADER_BACKGROUND),
        ("GRID", (0, 0), (-1, -1), 0.4, _GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))


def _model_result_flowables(block, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    """Render a ``modelResult`` block (NI-055) duck-typed.

    The branch is written against the recorded ``ExportModelResultBlock``
    shape (block: model_run_id, dataset_version_id, spec_id, spec_version,
    interpretation, summary; summary: run_id, model_id, model_version,
    gate_verdict, sample_start, sample_end_exclusive, nobs,
    coefficient_rtol, coefficient_atol, manifest_url, coefficients,
    diagnostics). Coefficients and diagnostics are rendered verbatim —
    exact decimal strings are never reformatted.
    """
    summary = block.summary
    flowables: list[Flowable] = [
        Paragraph(
            f"<b>Model result</b> — run {escape_text(str(summary.run_id))} "
            f"(model {escape_text(str(summary.model_id))} "
            f"v{escape_text(str(summary.model_version))}), gate verdict "
            f"{escape_text(str(summary.gate_verdict))}",
            styles["card_label"]),
        Paragraph(
            f"Specification {escape_text(str(block.spec_id))} version "
            f"{escape_text(str(block.spec_version))}; dataset version "
            f"{escape_text(str(block.dataset_version_id))}; sample "
            f"{escape_text(str(summary.sample_start))} to "
            f"{escape_text(str(summary.sample_end_exclusive))} (nobs "
            f"{escape_text(str(summary.nobs))}).",
            styles["card_meta"]),
    ]
    flowables.extend(_body_flowables(block.interpretation, styles))
    flowables.append(Paragraph(
        f"Coefficient verification tolerance: rtol "
        f"{escape_text(str(summary.coefficient_rtol))}, atol "
        f"{escape_text(str(summary.coefficient_atol))}.",
        styles["card_meta"]))
    coefficients = getattr(summary, "coefficients", None)
    if coefficients:
        header = [Paragraph(escape_text(name), styles["mono_header"]) for name in
                  ("name", "estimate", "std_error", "t_stat", "p_value",
                   "ci95_low", "ci95_high")]
        rows = []
        max_lengths = [len(name) for name in
                       ("name", "estimate", "std_error", "t_stat", "p_value",
                        "ci95_low", "ci95_high")]
        for coefficient in coefficients:
            values = [str(getattr(coefficient, field))
                      for field in ("name", "estimate", "std_error", "t_stat",
                                    "p_value", "ci95_low", "ci95_high")]
            for index, value in enumerate(values):
                _require_glyphs(value, f"modelResult.{summary.run_id}", mono=True)
                max_lengths[index] = max(max_lengths[index], len(value))
            rows.append([Paragraph(escape_text(value), styles["mono_cell"])
                         for value in values])
        flowables.append(Paragraph("Coefficients (exact values):",
                                   styles["card_body"]))
        flowables.append(Table([header, *rows],
                               colWidths=_column_widths(
                                   [len(name) for name in
                                    ("name", "estimate", "std_error", "t_stat",
                                     "p_value", "ci95_low", "ci95_high")],
                                   max_lengths, 7),
                               repeatRows=1, style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _TABLE_HEADER_BACKGROUND),
            ("GRID", (0, 0), (-1, -1), 0.4, _GRID_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])))
    manifest_url = getattr(summary, "manifest_url", None)
    if manifest_url:
        flowables.append(Paragraph(
            f"Manifest: {escape_text(str(manifest_url))}",
            styles["card_meta"]))
    diagnostics = getattr(summary, "diagnostics", None)
    if diagnostics is not None:
        if isinstance(diagnostics, dict):
            lines = "; ".join(
                f"{key}: {escape_text(str(diagnostics[key]))}"
                for key in sorted(diagnostics))
        else:
            lines = escape_text(str(diagnostics))
        flowables.append(Paragraph(f"Diagnostics: {lines}",
                                   styles["card_meta"]))
    return flowables


def _render_block(block: ExportBlock, *, chart_number: int,
                  assets_by_id: dict[UUID, _FigureAssets],
                  styles: dict[str, ParagraphStyle],
                  ) -> tuple[list[Flowable], int]:
    """Render one plan block; returns the flowables and the chart counter.

    The ``modelResult`` branch (NI-055) runs first, duck-typed: on a tree
    without NI-055 the plan grammar cannot produce such a block, so the
    branch is unreachable there and the typed union below stays exhaustive.
    """
    if getattr(block, "block_type", None) == "modelResult":
        return _card_flowables(
            _model_result_flowables(block, styles), styles), chart_number
    if isinstance(block, ExportParagraphBlock):
        return [Paragraph(_runs_markup(block.runs), styles["body"])], chart_number
    if isinstance(block, ExportHeadingBlock):
        style = styles[f"heading{min(block.level, 3)}"]
        return [Paragraph(_runs_markup(block.runs), style)], chart_number
    if isinstance(block, ExportListBlock):
        return _list_flowables(block.items,
                               ordered=block.block_type == "ordered_list",
                               styles=styles, depth=1), chart_number
    if isinstance(block, ExportChartBlock):
        chart_number += 1
        assets = assets_by_id[block.block_id]
        return (_figure_flowables(block, assets, chart_number, styles),
                chart_number)
    if isinstance(block, ExportDataTableBlock):
        return _data_table_flowables(block, styles), chart_number
    if isinstance(block, ExportInsightBlock):
        flowables = [
            Paragraph(
                f"<b>Insight ({escape_text(str(block.insight_type))}, "
                f"{escape_text(block.classification)})</b> — authored "
                f"{block.authored_at}",
                styles["card_label"]),
        ]
        flowables.extend(_body_flowables(block.body, styles))
        flowables.append(Paragraph(
            "Pinned context: " + "; ".join(escape_text(line)
                                           for line in _context_lines(block.context))
            + ".", styles["card_meta"]))
        if block.hypothesis_id is not None:
            flowables.append(Paragraph(
                f"Related hypothesis: {block.hypothesis_id}.",
                styles["card_meta"]))
        return _card_flowables(flowables, styles), chart_number
    if isinstance(block, ExportHypothesisBlock):
        flowables = [
            Paragraph(
                f"<b>Hypothesis ({escape_text(block.assessment)})</b> — "
                f"authored {block.authored_at}",
                styles["card_label"]),
            Paragraph(escape_text(block.statement), styles["card_body"]),
        ]
        return _card_flowables(flowables, styles), chart_number
    if isinstance(block, ExportEvidenceBlock):
        if block.target_kind == "insight":
            target = f"insight {block.target_id}"
        elif block.target_kind == "chart_block":
            target = f"chart block {block.target_id}"
        elif block.target_kind == "model_run":
            target = f"published model run {block.target_id}"
        else:
            target = f"public citation artifact {block.target_id}"
        flowables = [Paragraph(
            f"<b>Evidence ({escape_text(block.classification)})</b> → "
            f"{escape_text(target)} — {escape_text(block.explanation)}",
            styles["card_label"])]
        return _card_flowables(flowables, styles), chart_number
    if isinstance(block, ExportRiskBlock):
        flowables = [
            Paragraph(f"<b>Risk: {escape_text(block.title)}</b>",
                      styles["card_label"]),
        ]
        flowables.extend(_body_flowables(block.body, styles))
        if block.related_hypothesis_id is not None:
            flowables.append(Paragraph(
                f"Related hypothesis: {block.related_hypothesis_id}.",
                styles["card_meta"]))
        return _card_flowables(flowables, styles), chart_number
    if isinstance(block, ExportDividerBlock):
        table = Table([[""]], colWidths=[_FRAME_WIDTH], rowHeights=[1],
                      style=TableStyle([
                          ("LINEBELOW", (0, 0), (-1, -1), 0.6, _GRID_COLOR),
                          ("TOPPADDING", (0, 0), (-1, -1), 0),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                      ]))
        return [Spacer(1, 4), table, Spacer(1, 8)], chart_number
    raise _refuse(
        "The frozen plan contains a block the PDF renderer does not support",
        f"blocks.{getattr(block, 'block_id', '?')}", "unsupported_block_type")


def _card_flowables(flowables: list[Flowable],
                    styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    """Close one annotation card (the trailing border box of the group)."""
    flowables.append(Paragraph("", ParagraphStyle(
        "card_end", parent=styles["card_body"], fontSize=2, leading=2,
        spaceAfter=0)))
    return flowables


# --------------------------------------------------------------------------- #
# Front matter, registries, appendix and provenance
# --------------------------------------------------------------------------- #


def _front_matter(plan: ExportIr, plan_sha256: str,
                  styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    meta = plan.document
    author = escape_text(meta.author.display_name) if meta.author.display_name \
        else str(meta.author.owner_id)
    return [
        Paragraph(escape_text(meta.title), styles["title"]),
        Paragraph(
            f"Exported revision {meta.revision} of document "
            f"{meta.document_id} (version {meta.version_id}, content "
            f"{meta.content_sha256}, schema version {meta.schema_version}) "
            f"authored by {author}, created {meta.created_at}.",
            styles["attribution"]),
        Paragraph(
            "This PDF is the frozen export of exactly this revision; later "
            "edits, renames or newer dataset publications do not change it. "
            "The Markdown ZIP bundle of the same revision carries the same "
            "evidence with a manifest.json pinning every file hash.",
            styles["attribution"]),
        Paragraph(
            f"Plan identity: export IR version {plan.ir_version}, plan "
            f"SHA-256 {plan_sha256}. PDF layout version {PDF_FORMAT_VERSION}.",
            styles["attribution"]),
        Spacer(1, 8),
    ]


def _registries_flowables(plan: ExportIr,
                          styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph("Sources", styles["heading1"]),
    ]
    if plan.sources:
        flowables.extend(
            Paragraph(f"{escape_text(source.source_id)} — "
                      f"{escape_text(source.name)}",
                      ParagraphStyle("source_item", parent=styles["list_item"]),
                      bulletText="•")
            for source in plan.sources)
    else:
        flowables.append(Paragraph(
            "No data sources are referenced by this revision.",
            styles["body"]))
    flowables.append(Paragraph("Model runs", styles["heading1"]))
    if plan.model_runs:
        flowables.extend(
            Paragraph(f"{run.run_id} — specification "
                      f"{escape_text(run.spec_id)} version {run.spec_version}",
                      ParagraphStyle("run_item", parent=styles["list_item"]),
                      bulletText="•")
            for run in plan.model_runs)
    else:
        flowables.append(Paragraph(
            "No published model runs are referenced by this revision.",
            styles["body"]))
    flowables.append(Paragraph("Citations", styles["heading1"]))
    if plan.citations:
        flowables.extend(
            Paragraph(f"Public citation artifact {citation.artifact_id}",
                      ParagraphStyle("citation_item",
                                     parent=styles["list_item"]),
                      bulletText="•")
            for citation in plan.citations)
    else:
        flowables.append(Paragraph(
            "No public citation artifacts are referenced by this revision.",
            styles["body"]))
    flowables.append(Paragraph("Limitations", styles["heading1"]))
    flowables.extend(
        Paragraph(escape_text(item), ParagraphStyle("limitation_item",
                                                    parent=styles["list_item"]),
                  bulletText="•")
        for item in limitations_of(plan))
    return flowables


def _chart_data_appendix(plan: ExportIr, assets_by_id: dict[UUID, _FigureAssets],
                         styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    """The exact-value appendix: one verbatim table per chart, in figure order."""
    flowables: list[Flowable] = []
    number = 0
    for block in plan.blocks:
        if not isinstance(block, ExportChartBlock):
            continue
        number += 1
        path = f"charts.{block.block_id}.csv"
        table = _exact_value_table(assets_by_id[block.block_id].csv, path, styles)
        flowables.append(Paragraph(
            f"<b>Figure {number} data (exact values)</b> — block "
            f"{block.block_id}", styles["appendix_label"]))
        flowables.append(table)
        flowables.append(Spacer(1, 8))
    return flowables


def _provenance_flowables(plan: ExportIr, plan_sha256: str,
                          assets: ChartRenderResult | None,
                          styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    """The rendering provenance record (what the ZIP manifest pins)."""
    flowables = [
        Paragraph("Rendering provenance", styles["heading1"]),
        Paragraph(
            f"Export IR version {plan.ir_version}; plan SHA-256 "
            f"{plan_sha256}; document content {plan.document.content_sha256}.",
            styles["body"]),
    ]
    if assets is not None:
        rows = [
            ("renderer id", assets.renderer.id),
            ("echarts version", assets.renderer.echarts_version),
            ("node version", assets.renderer.node_version),
            ("request SHA-256", assets.input_sha256),
            ("renderer script SHA-256", assets.script_sha256),
        ]
        flowables.append(Table(
            [[Paragraph(escape_text(label), styles["mono_header"]),
              Paragraph(escape_text(value), styles["mono_cell"])]
             for label, value in rows],
            colWidths=[_FRAME_WIDTH * 0.3, _FRAME_WIDTH * 0.7],
            style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, _GRID_COLOR),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ])))
        for chart in assets.charts:
            _require_glyphs(str(chart.chart_id), "renderer.chart_id")
    else:
        flowables.append(Paragraph(
            "This revision carries no chart blocks; no chart renderer ran.",
            styles["body"]))
    flowables.append(Paragraph(
        "No live data, screenshot or network access happened during this "
        "export: every figure is the static SVG asset rendered from the "
        "frozen chart view, and every value comes from the plan pinned "
        "above.", styles["body"]))
    return flowables


# --------------------------------------------------------------------------- #
# The renderer
# --------------------------------------------------------------------------- #


def _footer(canvas: Canvas, _doc) -> None:
    canvas.saveState()
    canvas.setFont(_FONT_REGULAR, 7.5)
    canvas.setFillColor(_MUTED_TEXT)
    canvas.drawCentredString(
        _PAGE_WIDTH / 2, _BOTTOM_MARGIN / 2 - 6,
        f"NEAR Intelligence frozen export — page {canvas.getPageNumber()}")
    canvas.restoreState()


def render_pdf(plan: ExportIr, assets: ChartRenderResult | None) -> bytes:
    """Render the frozen plan into the deterministic PDF report.

    ``assets`` is the NI-057 boundary-verified render of the plan's chart
    blocks (``None`` exactly when the plan carries no chart). The output is
    a pure function of the plan and the assets: byte-identical inputs give
    byte-identical PDF bytes.
    """
    if plan.ir_version != _BUNDLE_IR_VERSION:
        raise PdfRenderError(
            f"The export plan uses IR version {plan.ir_version}; this "
            f"renderer renders version {_BUNDLE_IR_VERSION} only",
            [("ir_version", "unsupported_ir_version")])
    _ensure_fonts()

    chart_blocks = [block for block in plan.blocks
                    if isinstance(block, ExportChartBlock)]
    if assets is None and chart_blocks:
        raise _refuse("The plan carries chart blocks but no verified chart "
                      "render", "charts", "missing_chart_render")
    if assets is not None:
        rendered_ids = [chart.chart_id for chart in assets.charts]
        expected_ids = [block.block_id for block in chart_blocks]
        if rendered_ids != expected_ids:
            raise _refuse(
                "The chart render does not cover the plan's chart blocks "
                "exactly", "charts", "chart_set_mismatch")
    assets_by_id = ({chart.chart_id: _FigureAssets(chart)
                     for chart in assets.charts} if assets is not None else {})

    styles = _styles()
    plan_bytes = export_ir_canonical_bytes(plan)
    plan_sha256 = hashlib.sha256(plan_bytes).hexdigest()
    # The attribution strings render on every page's parent flow; check the
    # fixed header text and the document meta once up front.
    _require_glyphs(plan.document.title, "document.title")
    _require_glyphs(str(plan.document.author.display_name or
                        plan.document.author.owner_id), "document.author")

    story: list[Flowable] = []
    story.extend(_front_matter(plan, plan_sha256, styles))
    chart_number = 0
    for block in plan.blocks:
        rendered, chart_number = _render_block(
            block, chart_number=chart_number,
            assets_by_id=assets_by_id, styles=styles)
        story.extend(rendered)
        story.append(Spacer(1, 4))
    story.extend(_registries_flowables(plan, styles))
    appendix = _chart_data_appendix(plan, assets_by_id, styles)
    if appendix:
        story.append(Paragraph("Chart data (exact values)", styles["heading1"]))
        story.extend(appendix)
    story.extend(_provenance_flowables(plan, plan_sha256, assets, styles))

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=_TOP_MARGIN, bottomMargin=_BOTTOM_MARGIN,
        invariant=1, title=plan.document.title,
        author=(plan.document.author.display_name
                or str(plan.document.author.owner_id)),
        subject=(f"Frozen export of revision {plan.document.revision} "
                 f"(content {plan.document.content_sha256})"),
        creator=f"near-api export renderer (NI-059), layout v{PDF_FORMAT_VERSION}")
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
