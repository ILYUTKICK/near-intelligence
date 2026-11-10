"""NI-062 untrusted-content audit: hostile text, links, SVG, ZIP and names.

Offline (no database, no network). Proves the export and editor content
boundaries stay inert when a hostile author plants XSS/markdown-structure
payloads, unsafe link targets, path-traversal asset names or executable
content in a download path:

- ``exports.markdown`` renders user prose inert (structure characters
  escaped, newlines flattened, link destinations percent-encoded);
- the canonical editor schema rejects script/HTML/unknown nodes, event
  handler marks and non-http(s)/credential-bearing link targets BEFORE
  storage;
- the NI-057 boundary refuses unsafe SVG output (script/foreignObject/event
  handlers/remote references) and non-UUID asset names;
- bundle ZIP entry names are flat server-derived names, and reading a
  hostile ZIP back refuses traversal/absolute names.
"""

import io
import re
import unittest
import zipfile
from uuid import uuid4

from near_api.documents.schema import (
    DocumentSchemaError,
    parse_document,
)
from near_api.exports.bundle import (
    BundleError,
    BundleFile,
    extract_bundle,
    zip_bundle,
)
from near_api.exports.charts import (
    ChartRendererError,
    _assert_static_svg,
    safe_chart_asset_name,
)
from near_api.exports.markdown import _escape_link, escape_text, render_markdown
from near_api.schemas.export import (
    ExportAuthor,
    ExportDataTableBlock,
    ExportDataTableColumn,
    ExportDividerBlock,
    ExportDocumentMeta,
    ExportEvidenceBlock,
    ExportHypothesisBlock,
    ExportIr,
    ExportParagraphBlock,
)

from test_documents import evidence_attrs, hypothesis_attrs, text_node

TS = "2026-11-06T12:00:00Z"
SHA256 = "a" * 64
HOSTILE_TEXT = ("<script>alert('xss')</script>\n# injected heading\n"
                "[link](javascript:alert(1)) | fake table | *em* `code`")


def top_paragraph(text: str, marks: list | None = None) -> dict:
    """A top-level paragraph block (canonical blocks carry attrs.block_id)."""
    return {"type": "paragraph", "attrs": {"block_id": str(uuid4())},
            "content": [text_node(text, marks)]}


def hostile_plan() -> ExportIr:
    """A frozen plan whose every authored string is a hostile payload."""
    uid = str(uuid4())
    return ExportIr(
        ir_version=1,
        document=ExportDocumentMeta(
            document_id=uuid4(), version_id=uuid4(), revision=1, schema_version=1,
            content_sha256=SHA256, title="<script>alert('title')</script># heading",
            author=ExportAuthor(owner_id=uuid4(), display_name="<b>Alice</b>"),
            created_at=TS),
        blocks=(
            ExportParagraphBlock(block_type="paragraph", block_id=uuid4(), runs=(
                {"type": "text", "text": HOSTILE_TEXT,
                 "marks": [{"type": "link", "attrs": {"href": "https://example.test/safe"}}]},
                {"type": "text", "text": "![img](data:text/html,<script>alert(1)</script>) <iframe>"},
            )),
            ExportDataTableBlock(
                block_type="dataTable",
                block_id=uuid4(),
                columns=(ExportDataTableColumn(
                    key="fees", label="| Fees | <script> |", type="string", unit="USD"),
                    ExportDataTableColumn(key="note", label="Note", type="string"),
                    ExportDataTableColumn(key="bound", label="Bound", type="string")),
                rows=(("123456789.123456789012345678901234",
                       "| 1 | <script>alert(1)</script> |", "≥0.5"),)),
            ExportHypothesisBlock(
                block_type="hypothesis",
                block_id=uuid4(), hypothesis_id=uuid4(),
                statement=HOSTILE_TEXT, assessment="untested",
                authored_at=TS, modified_at=TS),
            ExportEvidenceBlock(
                block_type="evidence",
                block_id=uuid4(), evidence_id=uuid4(), hypothesis_id=uuid4(),
                classification="contradicting", target_kind="citation",
                target_id=uuid4(), target_block_id=None,
                explanation="> quoted\n`1); DROP TABLE users;--"),
            ExportDividerBlock(block_type="divider", block_id=uuid4()),
        ),
        sources=(), model_runs=(), citations=(),
    )


class MarkdownInertnessTests(unittest.TestCase):
    """The export renderer cannot be turned into structure by authored text."""

    def test_structure_characters_are_escaped_and_flattened(self):
        escaped = escape_text(HOSTILE_TEXT)
        for fragment in ("<script>", "| fake table |",
                         "*em*", "`code`", "[link]"):
            self.assertNotIn(fragment, escaped)
        self.assertNotIn("\n", escaped)
        # Heading/table/link/emphasis structure is escaped in place (the
        # authored text is preserved verbatim, only inert).
        self.assertIn("\\# injected", escaped)
        self.assertIn("\\[link\\]", escaped)
        # The javascript: URL survives only as escaped literal TEXT: the
        # brackets that would make it a clickable Markdown link are escaped,
        # so it can never become a link structure in any CommonMark renderer.
        self.assertNotIn("[link](", escaped)

    def test_html_and_ampersand_are_entity_escaped(self):
        escaped = escape_text("<b>bold</b> & <img src=x onerror=alert(1)>")
        self.assertNotIn("<b>", escaped)
        self.assertNotIn("<img", escaped)
        self.assertIn("&lt;b&gt;", escaped)
        self.assertIn("&amp;", escaped)

    def test_link_destination_is_percent_encoded_and_control_stripped(self):
        encoded = _escape_link("https://example.test/a(b)<c>%41\nx")
        self.assertEqual(encoded, "https://example.test/a%28b%29%3Cc%3E%2541x")
        self.assertNotIn("\n", encoded)

    def test_hostile_plan_renders_inert_markdown(self):
        rendered = render_markdown(hostile_plan(), {})
        lowered = rendered.lower()
        for fragment in ("<script", "onerror=", "<iframe"):
            self.assertNotIn(fragment, lowered)
        # No authored structure injection: the renderer's own headings are
        # the only line-start hashes, and the authored heading payload exists
        # only escaped inline ("\\# injected"), never at a line start.
        self.assertNotIn("\n# injected", rendered)
        self.assertNotIn("\n| fake table |", rendered)
        self.assertNotIn("\n[link]", rendered)
        # Every REAL (unescaped) Markdown link destination is allowlisted:
        # authored javascript:/data: payloads survive only as escaped text
        # whose brackets can never re-form a link.
        destinations = re.findall(r"(?<!\\)\]\(([^)\n]*)\)", rendered)
        self.assertEqual(destinations, ["https://example.test/safe"])
        self.assertIn("\\#", rendered)
        self.assertIn("\\|", rendered)
        # The authored text itself is preserved verbatim in inert form (never
        # dropped): the payload characters survive only escaped.
        self.assertIn("alert(", rendered)


class EditorSchemaHostileContentTests(unittest.TestCase):
    """Unknown nodes, HTML hosts, handlers and unsafe links fail pre-storage."""

    def _rejects(self, node: dict) -> None:
        with self.assertRaises(DocumentSchemaError):
            parse_document({"schema_version": 1, "type": "doc", "content": [node]})

    def test_script_iframe_and_html_nodes_are_unknown_types(self):
        for node_type, attrs in (
                ("script", {}),
                ("iframe", {"src": "https://evil.test"}),
                ("html", {"html": "<marquee>"}),
                ("embed", {"src": "data:text/html,<script>"}),
        ):
            self._rejects({"type": node_type, "attrs": attrs})

    def test_javascript_data_vbscript_and_credential_links_are_rejected(self):
        # Plain http(s) is allowed by spec (AUTHENTICATION_SECURITY "Allow
        # only http/https citation links"); schemes outside it, protocol
        # relative targets and credential-bearing URLs are refused.
        for href in ("javascript:alert(1)", "data:text/html,<script>alert(1)</script>",
                     "vbscript:msgbox", "https://user:pass@evil.test/x",
                     "//protocol-relative.test/x", "file:///etc/passwd"):
            self._rejects(top_paragraph("text", marks=[
                {"type": "link", "attrs": {"href": href}}]))

    def test_https_links_and_literal_angle_brackets_are_accepted(self):
        node = top_paragraph("<b>escaped as literal text</b>", marks=[
            {"type": "link", "attrs": {"href": "https://example.test/ok"}}])
        parsed = parse_document({"schema_version": 1, "type": "doc", "content": [node]})
        self.assertTrue(parsed.content_sha256)
        self.assertIn("<b>", parsed.canonical["content"][0]["content"][0]["text"])

    def test_event_handler_attributes_are_unknown_and_rejected(self):
        node = top_paragraph("text")
        node["content"][0]["marks"] = [{"type": "bold", "attrs": {"onclick": "alert(1)"}}]
        self._rejects(node)

    def test_hostile_card_payloads_validate_but_export_inert(self):
        # Authored card text is free-form (validated for size only); the
        # security boundary is the inert export renderer above, so a hostile
        # statement/body must parse and then render inert.
        hypothesis = hypothesis_attrs(statement=HOSTILE_TEXT)
        parsed = parse_document({"schema_version": 1, "type": "doc",
                                 "content": [hypothesis]})
        self.assertEqual(len(parsed.hypotheses), 1)
        evidence = evidence_attrs(hypothesis["attrs"]["hypothesis_id"],
                                  "insight", str(uuid4()), explanation=HOSTILE_TEXT)
        self._rejects(evidence)  # target must exist in the same revision


class SvgStaticSafetyTests(unittest.TestCase):
    """The NI-057 boundary re-scans renderer output; hostile SVG fails typed."""

    def test_hostile_svg_vectors_are_refused(self):
        hostile = (
            "<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
            "<svg xmlns='http://www.w3.org/2000/svg'><foreignObject><body/></foreignObject></svg>",
            "<svg xmlns='http://www.w3.org/2000/svg'><image href='https://evil.test/x'/></svg>",
            "<svg xmlns='http://www.w3.org/2000/svg'><a href='javascript:alert(1)'><rect/></a></svg>",
            "<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'><rect/></svg>",
            "<svg xmlns='http://www.w3.org/2000/svg'><rect fill='url(https://evil.test)'/></svg>",
            "<svg xmlns='http://www.w3.org/2000/svg'><rect fill='data:text/html,<script/>'/></svg>",
        )
        for svg in hostile:
            with self.assertRaises(ChartRendererError):
                _assert_static_svg(svg, "assets/chart-x.svg")

    def test_namespace_identifier_is_not_a_remote_reference(self):
        safe = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'>"
                "<rect width='10' height='10'/></svg>")
        _assert_static_svg(safe, "assets/chart-x.svg")  # must not raise


class AssetNameAndZipSafetyTests(unittest.TestCase):
    """Export filenames are server-derived; hostile archives fail closed."""

    def test_asset_names_are_uuid_derived_and_extensions_bounded(self):
        name = safe_chart_asset_name("0f0e0d0c-0b0a-4999-8999-000000000009", "svg")
        self.assertEqual(name, "chart-0f0e0d0c-0b0a-4999-8999-000000000009.svg")
        for bad_id in ("../../etc/passwd", "chart.svg",
                       "0F0E0D0C-0B0A-4999-8999-000000000009",
                       "{0f0e0d0c-0b0a-4999-8999-000000000009}", "", "x" * 40):
            with self.assertRaises(ChartRendererError):
                safe_chart_asset_name(bad_id, "svg")
        for bad_ext in ("SVG", "svg/", ".", "s.v.g", "toolongextension", ""):
            with self.assertRaises(ChartRendererError):
                safe_chart_asset_name("0f0e0d0c-0b0a-4999-8999-000000000009", bad_ext)

    def test_bundle_asset_names_are_only_server_derived_svg_csv(self):
        # The real call site chooses the extension, never user input: a plan's
        # chart blocks produce exactly one .svg and one .csv asset each.
        from collections import namedtuple

        from near_api.exports.bundle import chart_asset_files

        fake_block = namedtuple("Block", ["block_id"])(
            uuid4())  # the helper reads only block_id
        files = chart_asset_files((fake_block,))
        suffix = f"chart-{fake_block.block_id}"
        self.assertEqual(
            (files[fake_block.block_id].svg_name, files[fake_block.block_id].csv_name),
            (f"assets/{suffix}.svg", f"assets/{suffix}.csv"))

    def test_bundle_zip_entries_are_flat_server_names(self):
        files = [BundleFile("research.md", b"ok"),
                 BundleFile("assets/chart-0f0e0d0c-0b0a-4999-8999-000000000009.svg", b"<svg/>"),
                 BundleFile("manifest.json", b"{}")]
        extracted = extract_bundle(zip_bundle(files))
        self.assertEqual(set(extracted), {entry.path for entry in files})
        self.assertTrue(all(not name.startswith("/") and ".." not in name
                            and "\\" not in name for name in extracted))

    def test_hostile_zip_entry_names_are_refused(self):
        for hostile in ("../escape.md", "/absolute.md", "assets\\win.md",
                        "assets/../../outside.md", "..\\..\\windows.md"):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(hostile, "payload")
            with self.assertRaises(BundleError):
                extract_bundle(buffer.getvalue())


class ExactValuesSurviveUntrustedNeighborsTests(unittest.TestCase):
    """Inertness never corrupts exact monetary strings beside hostile cells."""

    def test_exact_decimal_string_and_bounds_survive_hostile_table(self):
        rendered = render_markdown(hostile_plan(), {})
        # Exact monetary strings survive verbatim (never reformatted) while
        # hostile neighbor cells render escaped, and bounds stay bounds.
        self.assertIn("123456789.123456789012345678901234", rendered)
        self.assertIn("≥0.5", rendered)
        self.assertNotIn("| 1 | <script>", rendered)


if __name__ == "__main__":
    unittest.main()
