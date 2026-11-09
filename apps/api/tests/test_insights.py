"""NI-046 insight/evidence contract tests (offline; no database, no HTTP I/O).

Schema matrix per the task card: every insight type/classification/assessment/
target kind validates, unsupported values are rejected, contexts require the
selected range/filters/dataset pins, stable ids are opaque validated UUIDs,
author timestamps are server-side (client timestamps and owner fields are
rejected on every input contract), and the rich text bodies reuse the canonical
editor grammar bounds/sanitization. The canonical JSON round-trip proves the
contracts neither drift from nor rewrite the authoritative editor schema.

All identities and content are synthetic test fixtures, never research data.
"""

import copy
import unittest
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError

from near_api.documents.schema import (
    MAX_BODY_PLAIN_CHARS,
    MAX_STATEMENT_CHARS,
    SCHEMA_VERSION,
    parse_document,
)
from near_api.insights.schemas import (
    Evidence,
    EvidenceInput,
    Hypothesis,
    HypothesisInput,
    Insight,
    InsightInput,
    ModelContext,
    ResolvedContext,
    RiskInput,
)
from near_api.main import app
from near_api.schemas.document_evidence import EvidenceCreateRequest, EvidencePatchRequest

TS = "2026-11-06T12:00:00Z"
OFFSET_TS = "2026-11-06T15:00:00+03:00"  # same instant, +03:00 spelling
SELECTION = {"start": "2025-01-01", "end": "2025-02-01", "frequency": "day", "filters": {}}
SHA256 = "a" * 64

INSIGHT_TYPES = ("observation", "hypothesis", "risk", "conclusion")
CLASSIFICATIONS = ("supporting", "contradicting", "uncertain")
ASSESSMENTS = ("untested", "supported", "mixed", "weakened", "insufficient_data")
TARGET_KINDS = ("insight", "chart_block", "model_run", "citation")


def chart_context() -> dict:
    return {"chart_definition_version_id": str(uuid4()),
            "dataset_version_id": str(uuid4()),
            "selection": dict(SELECTION),
            "context_hash": SHA256,
            "renderer_version": "echarts-1",
            "metric_definition_versions": [],
            "resolved_at": TS}


def model_context() -> dict:
    return {"model_run_id": str(uuid4()), "dataset_version_id": str(uuid4()),
            "specification_version": "gross-fee-activity-v1", "context_hash": SHA256}


def text_node(text: str, marks: list | None = None) -> dict:
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def paragraph_node(text: str, marks: list | None = None) -> dict:
    return {"type": "paragraph", "content": [text_node(text, marks)]}


def body_node() -> list:
    return [paragraph_node("Fee share concentrated in two weeks of the window")]


def insight_payload(**changes) -> dict:
    payload = {"block_id": str(uuid4()), "type": "observation",
               "classification": "supporting", "body": body_node(),
               "context": chart_context(), "hypothesis_id": None}
    payload.update(changes)
    return payload


def evidence_payload(**changes) -> dict:
    payload = {"block_id": str(uuid4()), "hypothesis_id": str(uuid4()),
               "classification": "contradicting", "target_kind": "insight",
               "target_id": str(uuid4()),
               "explanation": "Fee share moved against the claim"}
    payload.update(changes)
    return payload


class InsightContractMatrixTests(unittest.TestCase):
    """Types, classifications, assessments, target kinds and context shapes."""

    def test_01_normative_value_sets(self):
        # The four insight types, three classifications, five authored
        # assessment states and four target kinds are normative
        # (EDITOR_SPECIFICATION + API_SPECIFICATION); the contract Literals
        # must enumerate exactly these values.
        from typing import get_args
        from near_api.insights.schemas import (
            EvidenceClassification, EvidenceTargetKind, HypothesisAssessment,
            InsightType,
        )
        self.assertEqual(get_args(InsightType), INSIGHT_TYPES)
        self.assertEqual(get_args(EvidenceClassification), CLASSIFICATIONS)
        self.assertEqual(get_args(HypothesisAssessment), ASSESSMENTS)
        self.assertEqual(get_args(EvidenceTargetKind), TARGET_KINDS)

    def test_02_every_insight_type_and_classification_validates(self):
        for insight_type in INSIGHT_TYPES:
            for classification in CLASSIFICATIONS:
                with self.subTest(type=insight_type, classification=classification):
                    parsed = InsightInput.model_validate(insight_payload(
                        type=insight_type, classification=classification))
                    self.assertEqual(parsed.type, insight_type)
                    self.assertEqual(parsed.classification, classification)
                    self.assertIsNone(parsed.hypothesis_id)

    def test_03_unsupported_types_classifications_and_unknown_fields_rejected(self):
        for changes in ({"type": "causal"}, {"type": "note"}, {"type": 1},
                        {"classification": "neutral"}, {"classification": "causal"},
                        {"unexpected": "field"}, {"insight_id": str(uuid4())},
                        {"id": str(uuid4())}, {"authored_at": TS},
                        {"modified_at": TS}, {"created_at": TS},
                        {"updated_at": TS}, {"owner_id": str(uuid4())},
                        {"user_id": str(uuid4())}, {"document_id": str(uuid4())}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    InsightInput.model_validate(insight_payload(**changes))

    def test_04_hypothesis_assessment_matrix_and_statement_bounds(self):
        for assessment in ASSESSMENTS:
            with self.subTest(assessment=assessment):
                parsed = HypothesisInput.model_validate({
                    "block_id": str(uuid4()),
                    "statement": "Adoption drives fee revenue within the window",
                    "assessment": assessment})
                self.assertEqual(parsed.assessment, assessment)
        for changes in ({"assessment": "confirmed"}, {"assessment": "supported_by_model"},
                        {"assessment": None}, {"statement": ""},
                        {"statement": "   "}, {"statement": "x" * (MAX_STATEMENT_CHARS + 1)},
                        {"statement": 12}, {"block_id": "not-a-uuid"},
                        {"authored_at": TS}, {"owner_id": str(uuid4())}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    HypothesisInput.model_validate({
                        "block_id": str(uuid4()), "statement": "Statement",
                        "assessment": "untested", **changes})

    def test_05_evidence_target_kind_matrix_and_bounds(self):
        for target_kind in TARGET_KINDS:
            with self.subTest(target_kind=target_kind):
                parsed = EvidenceInput.model_validate(evidence_payload(target_kind=target_kind))
                self.assertEqual(parsed.target_kind, target_kind)
        for changes in ({"target_kind": "document"}, {"target_kind": "metric"},
                        {"target_kind": None}, {"classification": "neutral"},
                        {"target_id": "12345"}, {"hypothesis_id": None},
                        {"explanation": ""}, {"explanation": "  "},
                        {"explanation": "x" * 2001}, {"authored_at": TS},
                        {"owner_id": str(uuid4())}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    EvidenceInput.model_validate(evidence_payload(**changes))

    def test_06_resolved_context_carries_range_filters_dataset_and_stable_ids(self):
        base = chart_context()
        context = ResolvedContext.model_validate(base)
        dumped = context.model_dump(mode="json")
        self.assertEqual(dumped["selection"]["start"], SELECTION["start"])
        self.assertEqual(dumped["selection"]["end"], SELECTION["end"])
        self.assertEqual(dumped["selection"]["filters"], {})
        self.assertEqual(UUID(dumped["dataset_version_id"]).version, 4)
        self.assertEqual(dumped["context_hash"], SHA256)
        # Offset timestamp spellings and uppercase UUIDs normalize to the one
        # canonical form (UTC instant, lowercase id): the same record respelled
        # serializes identically.
        respelled = {**base,
                     "chart_definition_version_id": base["chart_definition_version_id"].upper(),
                     "dataset_version_id": base["dataset_version_id"].upper(),
                     "resolved_at": OFFSET_TS}
        self.assertEqual(ResolvedContext.model_validate(respelled).model_dump_json(),
                         context.model_dump_json())
        self.assertEqual(context.resolved_at.isoformat(), "2026-11-06T12:00:00+00:00")

    def test_07_context_required_fields_and_bounds_are_enforced(self):
        base = chart_context()
        missing_cases = ["chart_definition_version_id", "dataset_version_id",
                         "selection", "context_hash", "renderer_version",
                         "metric_definition_versions", "resolved_at"]
        for field in missing_cases:
            broken = {key: value for key, value in base.items() if key != field}
            with self.subTest(missing=field), self.assertRaises(ValidationError):
                ResolvedContext.model_validate(broken)
        for changes in ({"context_hash": SHA256.upper()}, {"context_hash": "z" * 64},
                        {"renderer_version": ""}, {"metric_definition_versions": ["x"]},
                        {"metric_definition_versions": [str(uuid4())] * 101},
                        {"resolved_at": "2026-11-06T12:00:00"},  # naive timestamp
                        {"resolved_at": 0}, {"dataset_version_id": None},
                        {"unverified_extra": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ResolvedContext.model_validate({**base, **changes})
        for selection in ({"start": "2025-02-01", "end": "2025-01-01", "frequency": "day",
                           "filters": {}},
                          {"start": "2025-01-01", "end": "2026-01-03", "frequency": "day",
                           "filters": {}},  # 367 days > the Selection bound
                          {"start": "2025-01-01", "end": "2025-02-01", "frequency": "week",
                           "filters": {}},
                          {"start": "2025-01-01", "end": "2025-02-01", "frequency": "day",
                           "filters": {"country": "x"}}):
            with self.subTest(selection=selection), self.assertRaises(ValidationError):
                ResolvedContext.model_validate({**base, "selection": selection})

    def test_08_model_context_and_union_discrimination(self):
        parsed = ModelContext.model_validate(model_context())
        self.assertEqual(parsed.specification_version, "gross-fee-activity-v1")
        insight = InsightInput.model_validate(insight_payload(context=model_context()))
        self.assertIsInstance(insight.context, ModelContext)
        chart = InsightInput.model_validate(insight_payload(context=chart_context()))
        self.assertIsInstance(chart.context, ResolvedContext)
        for broken in ({**model_context(), "chart_definition_version_id": str(uuid4())},
                       {key: value for key, value in model_context().items()
                        if key != "model_run_id"},
                       {key: value for key, value in model_context().items()
                        if key != "context_hash"},
                       {"resolved_at": TS},  # neither shape
                       [chart_context()]):
            with self.subTest(broken=str(broken)[:40]), self.assertRaises(ValidationError):
                InsightInput.model_validate(insight_payload(context=broken))


class ServerAuthorshipTests(unittest.TestCase):
    """Timestamps and ownership: server-side only, clients never supply them."""

    def test_01_client_timestamps_are_rejected_on_every_input(self):
        for model, payload in ((InsightInput, insight_payload()),
                               (HypothesisInput, {"block_id": str(uuid4()),
                                                  "statement": "S", "assessment": "untested"}),
                               (EvidenceInput, evidence_payload()),
                               (RiskInput, {"block_id": str(uuid4()), "title": "Risk",
                                            "body": body_node()})):
            for field in ("authored_at", "modified_at", "created_at", "updated_at",
                          "owner_id", "user_id"):
                with self.subTest(model=model.__name__, field=field):
                    with self.assertRaises(ValidationError):
                        model.model_validate({**payload, field: TS})

    def test_02_response_timestamps_are_required_server_fields(self):
        core = {"block_id": str(uuid4()), "type": "conclusion",
                "classification": "uncertain", "body": body_node(),
                "context": chart_context(), "id": str(uuid4()),
                "document_id": str(uuid4())}
        with self.assertRaises(ValidationError):
            Insight.model_validate(core)
        parsed = Insight.model_validate({**core, "authored_at": OFFSET_TS,
                                         "modified_at": TS})
        dumped = parsed.model_dump(mode="json")
        self.assertEqual(dumped["authored_at"], "2026-11-06T12:00:00Z")
        self.assertEqual(dumped["modified_at"], TS)
        # Naive timestamps stay rejected on responses too.
        with self.assertRaises(ValidationError):
            Insight.model_validate({**core, "authored_at": "2026-11-06T12:00:00",
                                    "modified_at": TS})
        for model, payload in ((Hypothesis, {"id": str(uuid4()), "document_id": str(uuid4()),
                                             "block_id": str(uuid4()), "statement": "S",
                                             "assessment": "mixed"}),
                               (Evidence, {**evidence_payload(), "id": str(uuid4()),
                                           "document_id": str(uuid4())})):
            with self.subTest(model=model.__name__), self.assertRaises(ValidationError):
                model.model_validate(payload)  # authored_at/modified_at missing
            # Offset spellings normalize to UTC on responses as well.
            validated = model.model_validate({**payload, "authored_at": OFFSET_TS,
                                              "modified_at": TS})
            self.assertEqual(validated.authored_at.utcoffset().total_seconds(), 0)
            self.assertEqual(validated.modified_at.utcoffset().total_seconds(), 0)

    def test_03_stable_ids_are_validated_not_derived(self):
        # Identity is a persisted opaque UUID, not a content hash: the same
        # payload with different block ids yields distinct identities, and the
        # exact supplied UUID round-trips unchanged (uppercase normalizes).
        upper = str(uuid4()).upper()
        one = InsightInput.model_validate(insight_payload(block_id=upper))
        self.assertEqual(str(one.block_id), upper.lower())
        two = InsightInput.model_validate(insight_payload(block_id=str(uuid4())))
        self.assertNotEqual(one.block_id, two.block_id)
        self.assertEqual(InsightInput.model_validate(
            insight_payload(block_id=str(one.block_id))).block_id, one.block_id)
        with self.assertRaises(ValidationError):
            InsightInput.model_validate(insight_payload(block_id="block-17"))


class RichTextBoundsTests(unittest.TestCase):
    """Bounded/sanitized annotation bodies via the canonical grammar reuse."""

    def test_01_valid_marks_and_nesting(self):
        rich = [{"type": "paragraph", "content": [
                    text_node("bold ", marks=[{"type": "bold"}]),
                    text_node("italic ", marks=[{"type": "italic"}]),
                    text_node("linked", marks=[{"type": "link",
                                                "attrs": {"href": "https://example.com/a"}}])]},
                {"type": "bullet_list", "content": [
                    {"type": "list_item", "content": [
                        paragraph_node("first"),
                        {"type": "ordered_list", "content": [
                            {"type": "list_item", "content": [
                                paragraph_node("nested"),
                                {"type": "bullet_list", "content": [
                                    {"type": "list_item", "content": [
                                        paragraph_node("deepest")]}]}]}]}]}]}]
        parsed = InsightInput.model_validate(insight_payload(body=rich))
        self.assertEqual(len(parsed.body), 2)
        risk = RiskInput.model_validate({"block_id": str(uuid4()), "title": "R",
                                         "body": rich, "related_hypothesis_id": None})
        self.assertEqual(len(risk.body), 2)

    def test_02_sanitization_matrix_rejects_unsupported_content(self):
        cases = {
            "empty_body": [],
            "not_a_list": "plain text",
            "html_block": [{"type": "html_block", "html": "<script>x</script>"}],
            "iframe_node": [{"type": "iframe", "attrs": {"src": "https://evil.example"}}],
            "code_node": [{"type": "code_block", "content": [text_node("x")]}],
            "unsupported_rich_node": [{"type": "image", "attrs": {"src": "x"}}],
            "unknown_mark": [{"type": "paragraph", "content": [
                text_node("x", marks=[{"type": "underline"}])]}],
            "duplicate_mark": [{"type": "paragraph", "content": [
                text_node("x", marks=[{"type": "bold"}, {"type": "bold"}])]}],
            "too_many_marks": [{"type": "paragraph", "content": [
                text_node("x", marks=[{"type": "bold"}, {"type": "italic"},
                                      {"type": "link", "attrs": {"href": "https://e.com"}},
                                      {"type": "underline"}])]}],
            "javascript_link": [{"type": "paragraph", "content": [
                text_node("x", marks=[{"type": "link", "attrs": {"href": "javascript:alert(1)"}}])]}],
            "credentials_in_link": [{"type": "paragraph", "content": [
                text_node("x", marks=[{"type": "link",
                                       "attrs": {"href": "https://user:pw@example.com"}}])]}],
            "empty_paragraph_text": [{"type": "paragraph", "content": [
                text_node("")]}],
            "nesting_depth_4": [{"type": "bullet_list", "content": [
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
                                            paragraph_node("4")]}]}]}]}]}]}]}]}],
            "list_without_paragraph_first": [{"type": "bullet_list", "content": [
                {"type": "list_item", "content": [
                    {"type": "ordered_list", "content": [
                        {"type": "list_item", "content": [paragraph_node("x")]}]}]}]}],
            "empty_list": [{"type": "bullet_list", "content": []}],
            "body_too_long": [{"type": "paragraph", "content": [
                text_node("y" * (MAX_BODY_PLAIN_CHARS + 1))]}],
        }
        for name, body in cases.items():
            with self.subTest(case=name), self.assertRaises(ValidationError):
                InsightInput.model_validate(insight_payload(body=body))
        # The risk contract reuses exactly the same whitelist.
        with self.assertRaises(ValidationError):
            RiskInput.model_validate({"block_id": str(uuid4()), "title": "R",
                                      "body": [{"type": "html_block",
                                                "html": "<b>x</b>"}]})

    def test_03_risk_title_and_optional_hypothesis_link(self):
        with self.assertRaises(ValidationError):
            RiskInput.model_validate({"block_id": str(uuid4()), "title": "  ",
                                      "body": body_node()})
        with self.assertRaises(ValidationError):
            RiskInput.model_validate({"block_id": str(uuid4()), "title": "x" * 201,
                                      "body": body_node()})
        parsed = RiskInput.model_validate({"block_id": str(uuid4()), "title": "Concentration",
                                           "body": body_node(),
                                           "related_hypothesis_id": str(uuid4())})
        self.assertIsNotNone(parsed.related_hypothesis_id)


class CanonicalRoundTripTests(unittest.TestCase):
    """Contracts never rewrite the authoritative canonical editor JSON."""

    @staticmethod
    def _document() -> dict:
        hypothesis_id = str(uuid4())
        insight_id = str(uuid4())
        return {"schema_version": SCHEMA_VERSION, "type": "doc", "content": [
            {"type": "hypothesis", "attrs": {
                "block_id": str(uuid4()), "hypothesis_id": hypothesis_id,
                "statement": "Adoption drives fee revenue", "assessment": "untested",
                "authored_at": TS, "modified_at": TS}},
            {"type": "insight", "attrs": {
                "block_id": str(uuid4()), "insight_id": insight_id,
                "type": "observation", "classification": "supporting",
                "body": [paragraph_node("Observation body"),
                         {"type": "bullet_list", "content": [
                             {"type": "list_item", "content": [paragraph_node("detail")]}]}],
                "context": chart_context(),
                "authored_at": OFFSET_TS, "modified_at": TS,
                "hypothesis_id": hypothesis_id}},
            {"type": "evidence", "attrs": {
                "block_id": str(uuid4()), "evidence_id": str(uuid4()),
                "hypothesis_id": hypothesis_id, "classification": "contradicting",
                "target_kind": "insight", "target_id": insight_id,
                "explanation": "Fee share moved against the claim"}},
            {"type": "risk", "attrs": {
                "block_id": str(uuid4()), "title": "Concentration risk",
                "body": body_node(), "related_hypothesis_id": hypothesis_id}},
        ]}

    def test_01_contract_validation_preserves_canonical_content_sha256(self):
        document = self._document()
        canonical = parse_document(document)
        insight_attrs = canonical.canonical["content"][1]["attrs"]
        # Input contract: the annotation fields of the canonical node minus the
        # server-authored timestamps revalidate, and reassembling a document
        # from the contract-dumped fields keeps the byte-identical canonical
        # hash — the contract neither rewrites nor drifts from the schema.
        round_tripped = InsightInput.model_validate({
            "block_id": insight_attrs["block_id"], "type": insight_attrs["type"],
            "classification": insight_attrs["classification"],
            "body": insight_attrs["body"], "context": insight_attrs["context"],
            "hypothesis_id": insight_attrs["hypothesis_id"]}).model_dump(mode="json")
        rebuilt = copy.deepcopy(document)
        rebuilt["content"][1]["attrs"].update({
            "block_id": round_tripped["block_id"], "type": round_tripped["type"],
            "classification": round_tripped["classification"],
            "body": round_tripped["body"], "context": round_tripped["context"],
            "hypothesis_id": round_tripped["hypothesis_id"]})
        self.assertEqual(parse_document(rebuilt).content_sha256, canonical.content_sha256)

    def test_02_response_models_map_canonical_nodes_plus_server_metadata(self):
        canonical = parse_document(self._document())
        document_id = str(uuid4())
        insight_attrs = canonical.canonical["content"][1]["attrs"]
        # The canonical node's `insight_id` maps onto the response `id`; every
        # other node attribute maps 1:1 (timestamps server-authored values).
        insight = Insight.model_validate({
            "id": insight_attrs["insight_id"], "document_id": document_id,
            "block_id": insight_attrs["block_id"], "type": insight_attrs["type"],
            "classification": insight_attrs["classification"],
            "body": insight_attrs["body"], "context": insight_attrs["context"],
            "authored_at": insight_attrs["authored_at"],
            "modified_at": insight_attrs["modified_at"],
            "hypothesis_id": insight_attrs["hypothesis_id"]})
        self.assertEqual(insight.model_dump(mode="json")["id"],
                         insight_attrs["insight_id"])
        self.assertEqual(insight.hypothesis_id,
                         UUID(insight_attrs["hypothesis_id"]))
        hypothesis_attrs = canonical.canonical["content"][0]["attrs"]
        hypothesis = Hypothesis.model_validate({
            "id": hypothesis_attrs["hypothesis_id"], "document_id": document_id,
            "block_id": hypothesis_attrs["block_id"],
            "statement": hypothesis_attrs["statement"],
            "assessment": hypothesis_attrs["assessment"],
            "authored_at": hypothesis_attrs["authored_at"],
            "modified_at": hypothesis_attrs["modified_at"]})
        self.assertEqual(hypothesis.statement, hypothesis_attrs["statement"])
        evidence_attrs = canonical.canonical["content"][2]["attrs"]
        evidence = Evidence.model_validate({
            "id": evidence_attrs["evidence_id"], "document_id": document_id,
            "block_id": evidence_attrs["block_id"],
            "hypothesis_id": evidence_attrs["hypothesis_id"],
            "classification": evidence_attrs["classification"],
            "target_kind": evidence_attrs["target_kind"],
            "target_id": evidence_attrs["target_id"],
            "explanation": evidence_attrs["explanation"],
            "authored_at": TS, "modified_at": TS})  # server-authored response metadata
        self.assertEqual(str(evidence.target_id), evidence_attrs["target_id"])
        risk_attrs = canonical.canonical["content"][3]["attrs"]
        risk = RiskInput.model_validate(risk_attrs)
        self.assertEqual(risk.title, risk_attrs["title"])
        self.assertEqual(risk.related_hypothesis_id,
                         UUID(risk_attrs["related_hypothesis_id"]))

    def test_03_timestamp_canonicalization_matches_editor_schema(self):
        # The editor schema canonicalizes authored_at to "...Z"; the response
        # contracts normalize the same instant to UTC.
        canonical = parse_document(self._document())
        insight_attrs = canonical.canonical["content"][1]["attrs"]
        self.assertEqual(insight_attrs["authored_at"], TS)  # OFFSET_TS canonicalized
        insight = Insight.model_validate({
            "id": insight_attrs["insight_id"], "document_id": str(uuid4()),
            "block_id": insight_attrs["block_id"], "type": insight_attrs["type"],
            "classification": insight_attrs["classification"],
            "body": insight_attrs["body"], "context": insight_attrs["context"],
            "authored_at": insight_attrs["authored_at"],
            "modified_at": insight_attrs["modified_at"],
            "hypothesis_id": insight_attrs["hypothesis_id"]})
        self.assertEqual(insight.model_dump(mode="json")["authored_at"], TS)


class OpenAPIPublicationTests(unittest.TestCase):
    """The contracts are published for the generated TS client (NI-004)."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_01_components_and_annotation_routes_are_published(self):
        schema = self.client.get("/openapi.json").json()
        components = schema["components"]["schemas"]
        for name in ("InsightInput", "Insight", "HypothesisInput", "Hypothesis",
                     "EvidenceInput", "Evidence", "RiskInput", "ResolvedContext",
                     "ModelContext", "RichTextParagraph", "RichTextList",
                     "RichTextListItem", "RichTextRun", "RichTextBoldMark",
                     "RichTextItalicMark", "RichTextLinkMark", "RichTextLinkAttrs"):
            self.assertIn(name, components)
        insight = components["InsightInput"]
        self.assertEqual(insight["properties"]["type"]["enum"], list(INSIGHT_TYPES))
        self.assertEqual(insight["properties"]["classification"]["enum"],
                         list(CLASSIFICATIONS))
        self.assertEqual(components["Hypothesis"]["properties"]["assessment"]["enum"],
                         list(ASSESSMENTS))
        self.assertEqual(components["EvidenceInput"]["properties"]["target_kind"]["enum"],
                         list(TARGET_KINDS))
        # Server-authored fields are required response members, never inputs.
        self.assertIn("authored_at", components["Evidence"]["required"])
        self.assertIn("modified_at", components["Insight"]["required"])
        self.assertNotIn("authored_at", components["InsightInput"]["required"])
        self.assertNotIn("owner_id", components["InsightInput"]["properties"])
        collection = schema["paths"]["/api/documents/{document_id}/insights"]
        item = schema["paths"]["/api/documents/{document_id}/insights/{insight_id}"]
        self.assertEqual({method: route["operationId"] for method, route in collection.items()},
                         {"get": "listDocumentInsights", "post": "createDocumentInsight"})
        self.assertEqual({method: route["operationId"] for method, route in item.items()},
                         {"patch": "updateDocumentInsight", "delete": "deleteDocumentInsight"})
        hypotheses = schema["paths"]["/api/documents/{document_id}/hypotheses"]
        hypothesis = schema["paths"]["/api/documents/{document_id}/hypotheses/{hypothesis_id}"]
        self.assertEqual({method: route["operationId"] for method, route in hypotheses.items()},
                         {"get": "listDocumentHypotheses", "post": "createDocumentHypothesis"})
        self.assertEqual({method: route["operationId"] for method, route in hypothesis.items()},
                         {"patch": "updateDocumentHypothesis", "delete": "deleteDocumentHypothesis"})
        self.assertEqual(set(components["HypothesisPatchRequest"]["properties"]), {"statement", "assessment"})
        self.assertEqual(components["HypothesisDeleteRequest"]["required"], ["remove_evidence_links"])

        evidence = schema["paths"]["/api/documents/{document_id}/evidence"]
        item = schema["paths"]["/api/documents/{document_id}/evidence/{evidence_id}"]
        picker = schema["paths"]["/api/documents/{document_id}/evidence-targets"]["get"]
        self.assertEqual({method: route["operationId"] for method, route in evidence.items()},
                         {"get": "listDocumentEvidence", "post": "createDocumentEvidence"})
        self.assertEqual({method: route["operationId"] for method, route in item.items()},
                         {"patch": "updateDocumentEvidence", "delete": "deleteDocumentEvidence"})
        self.assertNotIn("requestBody", item["delete"])
        self.assertEqual(picker["operationId"], "listDocumentEvidenceTargets")
        self.assertEqual({field["name"]: field["schema"]["enum"]
                          for field in picker["parameters"] if field["name"] == "target_kind"},
                         {"target_kind": ["model_run", "citation"]})
        self.assertEqual(set(components["EvidenceTargetListResponse"]["required"]), {"items", "next_cursor"})

    def test_evidence_mutation_inputs_forbid_trusted_fields_and_null_patches(self):
        create = EvidenceCreateRequest.model_validate(evidence_payload(after_block_id=str(uuid4())))
        self.assertIsInstance(create.after_block_id, UUID)
        patch = EvidencePatchRequest.model_validate({"target_kind": "citation"})
        self.assertEqual(patch.model_dump(exclude_unset=True), {"target_kind": "citation"})
        for field in ("block_id", "evidence_id", "owner_id", "authored_at", "modified_at"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidencePatchRequest.model_validate({field: str(uuid4())})
        for field in ("hypothesis_id", "classification", "target_kind", "target_id", "explanation"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidencePatchRequest.model_validate({field: None})
        with self.assertRaises(ValidationError):
            EvidencePatchRequest.model_validate({})
        for field in ("evidence_id", "owner_id", "authored_at", "modified_at"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidenceCreateRequest.model_validate(evidence_payload(**{field: str(uuid4())}))

    def test_02_openapi_builds_repeatably_without_schema_conflicts(self):
        first = self.client.get("/openapi.json").json()
        second = self.client.get("/openapi.json").json()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
