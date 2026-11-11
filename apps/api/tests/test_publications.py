"""NI-045 template and public-research duplication tests.

Use scripts/run-db-tests.py for the cluster-dependent cases; direct discovery
skips them without its explicit isolated-cluster environment. A skip is never
successful integration evidence.

Offline cases cover the pure ID-remap graph oracle (complete rewrite of
block/insight/hypothesis/evidence identities, rewritten in-document links,
verbatim public pins, prepended attribution, untouched input) and the
template shape (eight headings only, unique ids, canonical-parse clean).

Database cases cover: the template save/reopen round trip through the
document service, the fail-closed publication seed gate, the public release
read route, the duplicate happy path (fresh ids, rewritten links, rebuilt
and re-verified chart contexts, retained attribution, fresh server-authored
annotation timestamps), public-source isolation after private edits,
Idempotency-Key replay returning the SAME document, generic 404s for
unknown/unpublished releases, explicit 422s for unavailable pins (never a
latest substitution) and the Alice/Bob ownership matrix on the duplicate
route.

All identities, slugs, titles and contents are synthetic test fixtures,
never research data.
"""

import copy
import os
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from pydantic import ValidationError

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.auth import principal as principal_module
from near_api.auth.principal import Principal, get_runtime_engine
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.documents.schema import (
    DocumentSchemaError,
    ReferenceInvalid,
    empty_document,
    parse_document,
)
from near_api.documents.templates import (
    INVESTMENT_V1_HEADINGS,
    TEMPLATE_HEADING_LEVEL,
    template_document,
)
from near_api.main import app
from near_api.publications.duplicate import (
    ATTRIBUTION_TEXT,
    remap_publication_content,
)
from near_api.publications.seed import (
    PublicationSeedConflict,
    PublicationSeedError,
    seed_publication,
)
from near_api.schemas.common import ErrorResponse
import test_chart_blocks as chart_fixtures
import test_documents as document_fixtures

SHA256 = "a" * 64


def text_paragraph(text: str) -> dict:
    return {"type": "paragraph", "attrs": {"block_id": str(uuid4())},
            "content": [{"type": "text", "text": text}]}


def publication_document(*, chart_definition_version_id: str | None = None,
                         dataset_version_id: str | None = None,
                         insight_context: dict | None = None,
                         citation_target: str | None = None) -> dict:
    """A synthetic release covering the full reference graph: liveChart,
    insight (linked to a hypothesis, pinned context), hypothesis, evidence
    with every in-document target kind plus a public citation target, and a
    risk linked to the hypothesis."""
    chart = document_fixtures.block(
        "liveChart", chart_definition_version_id=chart_definition_version_id or str(uuid4()),
        mode="live", selection=copy.deepcopy(document_fixtures.SELECTION),
        observed_dataset_version_id=dataset_version_id or str(uuid4()))
    hypothesis = document_fixtures.hypothesis_attrs()
    hypothesis_id = hypothesis["attrs"]["hypothesis_id"]
    insight = document_fixtures.insight_attrs(
        hypothesis_id=hypothesis_id, context=insight_context or document_fixtures.resolved_context())
    insight_id = insight["attrs"]["insight_id"]
    content = [
        text_paragraph("Public release intro (synthetic fixture)"),
        chart,
        hypothesis,
        insight,
        document_fixtures.evidence_attrs(hypothesis_id, "insight", insight_id),
        document_fixtures.evidence_attrs(hypothesis_id, "chart_block", chart["attrs"]["block_id"]),
        document_fixtures.risk_attrs(hypothesis_id),
    ]
    if citation_target is not None:
        content.append(document_fixtures.evidence_attrs(hypothesis_id, "citation", citation_target))
    return {"schema_version": 1, "type": "doc", "content": content}


class RemapGraphTests(unittest.TestCase):
    """Pure ID-remap oracle: complete rewrite, links consistent, pins kept."""

    def test_01_every_identity_is_reallocated_and_links_rewritten(self):
        document = publication_document()
        parsed = parse_document(document)
        old_blocks = {str(item.block_id) for item in parsed.blocks}
        old_insights = {str(item.insight_id) for item in parsed.insights}
        old_hypotheses = {str(item.hypothesis_id) for item in parsed.hypotheses}
        old_evidence = {str(item.evidence_id) for item in parsed.evidence}
        old_chart_target = document["content"][1]["attrs"]["block_id"]

        remapped, mapping = remap_publication_content(
            copy.deepcopy(document), attribution_text="Source attribution.")

        # Old identities are gone, new identities are complete and disjoint.
        new_blocks = {node["attrs"]["block_id"] for node in remapped["content"]}
        self.assertFalse(new_blocks & old_blocks)
        self.assertEqual(len(new_blocks), len(old_blocks) + 1)  # + attribution
        for old, new in mapping.block_ids.items():
            self.assertIn(old, old_blocks)
            self.assertNotIn(new, old_blocks)
        new_insights = {node["attrs"]["insight_id"] for node in remapped["content"]
                        if node["type"] == "insight"}
        self.assertFalse(new_insights & old_insights)
        self.assertEqual(new_insights, set(mapping.insight_ids.values()))
        new_hypotheses = {node["attrs"]["hypothesis_id"] for node in remapped["content"]
                          if node["type"] == "hypothesis"}
        self.assertFalse(new_hypotheses & old_hypotheses)
        new_evidence = {node["attrs"]["evidence_id"] for node in remapped["content"]
                        if node["type"] == "evidence"}
        self.assertFalse(new_evidence & old_evidence)

        # The rewritten graph parses (same-document links all resolve).
        reparsed = parse_document(remapped)
        self.assertEqual(len(reparsed.insights), len(parsed.insights))
        self.assertEqual(len(reparsed.evidence), len(parsed.evidence))
        self.assertEqual(len(reparsed.hypotheses), len(parsed.hypotheses))
        self.assertEqual(len(reparsed.risks), len(parsed.risks))
        self.assertEqual(len(reparsed.live_charts), len(parsed.live_charts))

        # Every in-document link points at the REMAPPED ids only.
        new_hypothesis_ids = {str(item.hypothesis_id) for item in reparsed.hypotheses}
        for item in reparsed.evidence:
            self.assertIn(str(item.hypothesis_id), new_hypothesis_ids)
            self.assertNotIn(str(item.hypothesis_id), old_hypotheses)
            if item.target_kind == "insight":
                self.assertIn(str(item.target_id),
                              {str(i.insight_id) for i in reparsed.insights})
            elif item.target_kind == "chart_block":
                self.assertIn(str(item.target_id),
                              {str(c.block_id) for c in reparsed.live_charts})
        for item in reparsed.insights:
            self.assertIn(str(item.hypothesis_id), new_hypothesis_ids)
        for risk in reparsed.risks:
            self.assertIn(str(risk.related_hypothesis_id), new_hypothesis_ids)
        # The chart block identity changed too (evidence -> chart_block followed).
        self.assertNotIn(old_chart_target, new_blocks)
        self.assertIn(str(reparsed.live_charts[0].block_id), new_blocks)

    def test_02_public_pins_and_contexts_are_carried_verbatim(self):
        context = document_fixtures.resolved_context()
        selection = copy.deepcopy(document_fixtures.SELECTION)
        dataset_id, chart_id, citation = str(uuid4()), str(uuid4()), str(uuid4())
        document = publication_document(chart_definition_version_id=chart_id,
                                        dataset_version_id=dataset_id,
                                        insight_context=context,
                                        citation_target=citation)
        remapped, _mapping = remap_publication_content(copy.deepcopy(document))
        chart_attrs = remapped["content"][1]["attrs"]
        self.assertEqual(chart_attrs["chart_definition_version_id"], chart_id)
        self.assertEqual(chart_attrs["observed_dataset_version_id"], dataset_id)
        self.assertEqual(chart_attrs["selection"], selection)
        self.assertEqual(chart_attrs["mode"], "live")
        insight_attrs = remapped["content"][3]["attrs"]
        self.assertEqual(insight_attrs["context"], context)
        citation_evidence = remapped["content"][7]["attrs"]
        self.assertEqual(citation_evidence["target_kind"], "citation")
        self.assertEqual(citation_evidence["target_id"], citation)

    def test_03_attribution_paragraph_is_prepended_and_input_untouched(self):
        document = publication_document()
        before = copy.deepcopy(document)
        remapped, _mapping = remap_publication_content(
            copy.deepcopy(document), attribution_text="Duplicated from release v1.")
        self.assertEqual(document, before)
        first = remapped["content"][0]
        self.assertEqual(first["type"], "paragraph")
        self.assertEqual(first["content"][0]["text"], "Duplicated from release v1.")
        self.assertNotEqual(remapped["content"][1]["attrs"]["block_id"],
                            before["content"][0]["attrs"]["block_id"])
        # Without attribution text the block order and node count stay stable.
        plain, _mapping = remap_publication_content(copy.deepcopy(document))
        self.assertEqual([node["type"] for node in plain["content"]],
                         [node["type"] for node in document["content"]])
        self.assertEqual(len(plain["content"]), len(document["content"]))

    def test_04_dangling_reference_is_a_typed_failure_never_partial_rewrite(self):
        document = publication_document()
        hypothesis_id = document["content"][2]["attrs"]["hypothesis_id"]
        # Evidence pointing at a hypothesis id that is absent from the maps.
        broken = copy.deepcopy(document)
        broken["content"][4]["attrs"]["hypothesis_id"] = str(uuid4())
        with self.assertRaises(ReferenceInvalid):
            remap_publication_content(copy.deepcopy(broken))
        # An evidence targeting an insight that is not in the document.
        broken_target = copy.deepcopy(document)
        broken_target["content"][4]["attrs"]["target_id"] = str(uuid4())
        with self.assertRaises(ReferenceInvalid):
            remap_publication_content(copy.deepcopy(broken_target))
        # The original fixture is untouched by both failures.
        self.assertEqual(document["content"][2]["attrs"]["hypothesis_id"], hypothesis_id)

    def test_05_remap_is_nondeterministic_per_call(self):
        document = publication_document()
        first, _a = remap_publication_content(copy.deepcopy(document))
        second, _b = remap_publication_content(copy.deepcopy(document))
        first_ids = {node["attrs"]["block_id"] for node in first["content"]}
        second_ids = {node["attrs"]["block_id"] for node in second["content"]}
        self.assertFalse(first_ids & second_ids)


class TemplateShapeTests(unittest.TestCase):
    """The investment-v1 template: eight headings, nothing else (offline)."""

    def test_01_template_has_exactly_the_eight_specified_headings(self):
        document = template_document("investment-v1")
        parsed = parse_document(document)
        self.assertEqual([node["type"] for node in parsed.canonical["content"]],
                         ["heading"] * 8)
        self.assertEqual([node["attrs"]["level"] for node in parsed.canonical["content"]],
                         [TEMPLATE_HEADING_LEVEL] * 8)
        self.assertEqual([node["content"][0]["text"] for node in parsed.canonical["content"]],
                         list(INVESTMENT_V1_HEADINGS))
        # No paragraphs, no numbers, no placeholder claims: headings only.
        self.assertTrue(all(not any(
            key in node["attrs"] for key in ("rows", "dataset_version_id", "context"))
            for node in parsed.canonical["content"]))

    def test_02_each_render_allocates_fresh_unique_block_ids(self):
        first = parse_document(template_document("investment-v1"))
        second = parse_document(template_document("investment-v1"))
        first_ids = {str(block.block_id) for block in first.blocks}
        second_ids = {str(block.block_id) for block in second.blocks}
        self.assertEqual(len(first_ids), 8)
        self.assertFalse(first_ids & second_ids)

    def test_03_unknown_template_is_a_typed_failure(self):
        with self.assertRaises(DocumentSchemaError):
            template_document("unknown-v1")  # type: ignore[arg-type]


class PublicationRouteContractTests(unittest.TestCase):
    """Offline HTTP failure behavior; no database required."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_01_duplicate_requires_a_verified_session(self):
        response = self.client.post("/api/publications/some-release/duplicate",
                                    json={"publication_version": 1})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(ErrorResponse.model_validate(response.json()).error.code,
                         "AUTHENTICATION_REQUIRED")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_02_duplicate_request_bounds(self):
        # The version pin is required and positive; the title is bounded.
        from near_api.publications.schemas import PublicationDuplicateRequest
        for payload in ({"publication_version": 0}, {"publication_version": True},
                        {"publication_version": 1, "title": ""},
                        {"publication_version": 1, "title": "x" * 201},
                        {"publication_version": "1"}, {}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    PublicationDuplicateRequest.model_validate(payload)
        ok = PublicationDuplicateRequest.model_validate({"publication_version": 1})
        self.assertIsNone(ok.title)


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class PublicationDatabaseTests(unittest.TestCase):
    """Template/publication guarantees on the disposable PostgreSQL cluster."""

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
        # The public read route resolves the engine through the dependency;
        # override it with the disposable cluster's runtime engine.
        app.dependency_overrides[get_runtime_engine] = lambda: cls.engine
        chart_fixtures.register_test_chart_catalog(cls.operator)
        dataset_id = chart_fixtures.ChartBlockDatabaseFixture.insert_dataset_version(
            cls, f"synthetic.{uuid4().hex[:8]}.publication-notes")
        cls.approved_dataset_id = dataset_id
        cls.chart_context = chart_fixtures.volume_context(cls.operator, dataset_id)
        cls.chart_id = str(chart_fixtures.CHART_ID)
        cls.selection = chart_fixtures.selection()
        # A citation artifact is a public immutable evidence target.
        cls.citation_id = cls._insert_artifact(scope="public")

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_runtime_engine, None)
        cls.engine.dispose()
        cls.operator.dispose()
        cls.admin.dispose()

    @classmethod
    def _insert_artifact(cls, scope: str) -> UUID:
        artifact_id = uuid4()
        with cls.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size,
                       media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/pdf', :scope, NULL, 'unverified')
            """), {"id": artifact_id, "key": f"synthetic/{artifact_id}.pdf",
                   "sha": SHA256, "scope": scope})
        return artifact_id

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

    # -- helpers ------------------------------------------------------------- #

    def as_session(self, subject):
        """HTTP calls run the real dependency chain with a stubbed verifier."""
        verifier = document_fixtures._StubVerifier(document_fixtures._verified(subject))
        context = ExitStack()
        context.enter_context(patch.object(principal_module, "_get_verifier",
                                           return_value=verifier))
        context.enter_context(patch.object(principal_module, "_get_engine",
                                           return_value=self.engine))
        return context

    def seed_release(self, slug: str, *, version: int = 1,
                     title: str = "Synthetic public release",
                     content: dict | None = None,
                     manifest: list | None = None) -> UUID:
        """Seed one synthetic publication through the real operator gate."""
        content = content if content is not None else publication_document(
            chart_definition_version_id=self.chart_id,
            dataset_version_id=str(self.approved_dataset_id),
            insight_context=copy.deepcopy(self.chart_context),
            citation_target=str(self.citation_id))
        manifest = manifest if manifest is not None else [
            {"kind": "citation", "id": str(self.citation_id), "label": "Synthetic citation"}]
        result = seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug,
                                  version=version, title=title, content=content,
                                  evidence_manifest=manifest)
        self.assertFalse(result.already_published)
        return result.id

    def duplicate(self, slug: str, *, version: int = 1, title: str | None = None,
                  subject: Principal | None = None, key: str | None = None,
                  headers_only: bool = False):
        subject = subject or self.alice
        headers = {"Authorization": f"Bearer t.{subject.id}"}
        if title is not None:
            body = {"publication_version": version, "title": title}
        else:
            body = {"publication_version": version}
        if key is not None:
            headers["Idempotency-Key"] = key
        with self.as_session(subject):
            return self.client.post(f"/api/publications/{slug}/duplicate",
                                    json=body, headers=headers)

    def document_row(self, document_id: UUID) -> dict:
        with self.admin.connect() as connection:
            row = connection.execute(text(
                "SELECT id, owner_id, title, revision, source_publication_id "
                "FROM app.documents WHERE id = :id"), {"id": document_id}).mappings().first()
        return dict(row) if row else {}

    def publication_row(self, slug: str, version: int = 1) -> dict:
        with self.admin.connect() as connection:
            row = connection.execute(text(
                "SELECT id, slug, version, title, content, evidence_manifest::text AS manifest, "
                "content_sha256, published_at "
                "FROM app.research_publications WHERE slug = :slug AND version = :version"),
                {"slug": slug, "version": version}).mappings().first()
        return dict(row) if row else {}

    def version_row(self, document_id: UUID, revision: int) -> dict:
        with self.admin.connect() as connection:
            row = connection.execute(text(
                "SELECT id, revision, content, resolved_contexts, content_sha256 "
                "FROM app.document_versions WHERE document_id = :id AND revision = :r"),
                {"id": document_id, "revision": revision}).mappings().one()
        return dict(row)

    def user_document_count(self, owner_id: UUID) -> int:
        with self.admin.connect() as connection:
            return connection.scalar(text(
                "SELECT count(*) FROM app.documents WHERE owner_id = :owner"),
                {"owner": owner_id})

    # -- template lifecycle --------------------------------------------------- #

    def test_01_template_create_save_and_reopen(self):
        with self.as_session(self.alice_id):
            created = self.client.post("/api/documents",
                                       json={"title": "Synthetic templated",
                                             "template_id": "investment-v1"},
                                       headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.headers["ETag"], '"1"')
        document_id = UUID(created.json()["id"])
        content = created.json()["content"]["content"]
        self.assertEqual([node["content"][0]["text"] for node in content],
                         list(INVESTMENT_V1_HEADINGS))
        self.assertEqual([node["attrs"]["level"] for node in content],
                         [TEMPLATE_HEADING_LEVEL] * 8)
        # The revision-1 blocks are real projections of the template content.
        with self.admin.connect() as connection:
            blocks = connection.execute(text(
                "SELECT position, block_type, attrs FROM app.document_blocks "
                "WHERE document_id = :id ORDER BY position"), {"id": document_id}).mappings().all()
        self.assertEqual([row["block_type"] for row in blocks], ["heading"] * 8)
        # Reopen returns the same canonical template content and hash.
        with self.as_session(self.alice_id):
            reopened = self.client.get(f"/api/documents/{document_id}",
                                       headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.json()["content"], created.json()["content"])
        first_version = self.version_row(document_id, 1)
        self.assertEqual(first_version["content"], created.json()["content"])
        # Saving on top of the template advances normally (CAS revision 2).
        body = {"schema_version": 1,
                "content": {"schema_version": 1, "type": "doc", "content":
                            [text_paragraph("Added analysis on top of the template")]}}
        with self.as_session(self.alice_id):
            saved = self.client.post(f"/api/documents/{document_id}/versions", json=body,
                                     headers={"If-Match": '"1"',
                                              "Authorization": "Bearer t.alice"})
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(saved.json()["document"]["revision"], 2)
        # A foreign owner sees nothing (generic 404).
        with self.as_session(self.bob_id):
            foreign = self.client.get(f"/api/documents/{document_id}",
                                      headers={"Authorization": "Bearer t.bob"})
        self.assertEqual(foreign.status_code, 404)

    def test_02_template_create_replays_idempotently(self):
        key = str(uuid4())
        with self.as_session(self.alice_id):
            first = self.client.post("/api/documents",
                                     json={"title": "Synthetic templated",
                                           "template_id": "investment-v1"},
                                     headers={"Authorization": "Bearer t.alice",
                                              "Idempotency-Key": key})
            self.assertEqual(first.status_code, 201)
            retry = self.client.post("/api/documents",
                                     json={"title": "Synthetic templated",
                                           "template_id": "investment-v1"},
                                     headers={"Authorization": "Bearer t.alice",
                                              "Idempotency-Key": key})
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(retry.json(), first.json())
        self.assertEqual(retry.json()["id"], first.json()["id"])
        # template_id is part of the fingerprint: same key, different body -> 409.
        with self.as_session(self.alice_id):
            conflict = self.client.post("/api/documents",
                                        json={"title": "Synthetic templated"},
                                        headers={"Authorization": "Bearer t.alice",
                                                 "Idempotency-Key": key})
        self.assertEqual(conflict.status_code, 409)

    # -- seed gate ------------------------------------------------------------ #

    def test_03_seed_gate_and_reseed_behavior(self):
        slug = f"synthetic-release-{uuid4().hex[:8]}"
        content = publication_document()
        manifest = [{"kind": "citation", "id": str(self.citation_id)}]
        seeded = seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug,
                                  version=1, title="Synthetic release", content=content,
                                  evidence_manifest=manifest)
        row = self.publication_row(slug)
        self.assertEqual(row["id"], seeded.id)
        self.assertEqual(row["content_sha256"], seeded.content_sha256)
        self.assertEqual(row["title"], "Synthetic release")
        # Identical reseed is a no-op with the same id and hash.
        again = seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug,
                                 version=1, title="Synthetic release", content=content,
                                 evidence_manifest=manifest)
        self.assertTrue(again.already_published)
        self.assertEqual(again.id, seeded.id)
        # A different title/content under the same (slug, version) conflicts.
        with self.assertRaises(PublicationSeedConflict):
            seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug,
                             version=1, title="Different title", content=content,
                             evidence_manifest=manifest)
        with self.assertRaises(PublicationSeedConflict):
            seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug,
                             version=1, title="Synthetic release",
                             content=publication_document(), evidence_manifest=manifest)

    def test_04_seed_gate_refuses_noncanonical_and_unavailable_references(self):
        slug = f"synthetic-refused-{uuid4().hex[:8]}"
        # Unknown block type in the projection.
        malformed = {"schema_version": 1, "type": "doc", "content": [
            {"type": "iframe", "attrs": {"block_id": str(uuid4())}}]}
        with self.assertRaises(DocumentSchemaError):
            seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug, version=1,
                             title="Synthetic", content=malformed, evidence_manifest=[])
        # Dangling in-document reference (evidence -> unknown hypothesis).
        dangling = publication_document()
        dangling["content"][4]["attrs"]["hypothesis_id"] = str(uuid4())
        with self.assertRaises(DocumentSchemaError):
            seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug, version=1,
                             title="Synthetic", content=dangling, evidence_manifest=[])
        # Manifest entries must be typed public references.
        with self.assertRaises(PublicationSeedError):
            seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug, version=1,
                             title="Synthetic", content=publication_document(),
                             evidence_manifest=[{"kind": "model_run", "id": str(uuid4())}])
        with self.assertRaises(PublicationSeedError):
            seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug, version=1,
                             title="Synthetic", content=publication_document(),
                             evidence_manifest=[{"kind": "citation", "id": str(uuid4())}])
        with self.assertRaises(PublicationSeedError):
            seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug, version=1,
                             title="Synthetic", content=publication_document(),
                             evidence_manifest=[{"kind": "dataset", "id": str(uuid4())}])
        # Slug grammar is the route grammar.
        with self.assertRaises(PublicationSeedError):
            seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug="Bad Slug",
                             version=1, title="Synthetic",
                             content=empty_document(), evidence_manifest=[])
        # Nothing was created by the refused attempts.
        self.assertEqual(self.publication_row(slug), {})

    # -- public read route ---------------------------------------------------- #

    def test_05_public_read_route_serves_only_published_releases(self):
        slug = f"synthetic-public-{uuid4().hex[:8]}"
        publication_id = self.seed_release(slug, version=1,
                                           title="Synthetic public read")
        response = self.client.get(f"/api/publications/{slug}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], str(publication_id))
        self.assertEqual(body["slug"], slug)
        self.assertEqual(body["version"], 1)
        self.assertEqual(body["title"], "Synthetic public read")
        self.assertEqual(body["content_sha256"], self.publication_row(slug)["content_sha256"])
        self.assertEqual(body["evidence_manifest"],
                         [{"kind": "citation", "id": str(self.citation_id),
                           "label": "Synthetic citation"}])
        self.assertIn("published_at", body)
        self.assertIn("Cache-Control", response.headers)
        # A pinned version is immutable content with its hash ETag.
        pinned = self.client.get(f"/api/publications/{slug}", params={"version": 1})
        self.assertEqual(pinned.status_code, 200)
        self.assertEqual(pinned.headers.get("ETag"),
                         f'"{self.publication_row(slug)["content_sha256"]}"')
        # Unknown slug, unknown version and malformed slug are typed failures.
        missing = self.client.get(f"/api/publications/{uuid4().hex}")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(ErrorResponse.model_validate(missing.json()).error.code,
                         "NOT_FOUND")
        unknown_version = self.client.get(f"/api/publications/{slug}",
                                          params={"version": 99})
        self.assertEqual(unknown_version.status_code, 404)
        malformed = self.client.get("/api/publications/Bad%20Slug")
        self.assertEqual(malformed.status_code, 422)
        # A seeded second version becomes the latest default.
        self.seed_release(slug, version=2, title="Synthetic public read v2")
        latest = self.client.get(f"/api/publications/{slug}")
        self.assertEqual(latest.json()["version"], 2)
        pinned_v1 = self.client.get(f"/api/publications/{slug}", params={"version": 1})
        self.assertEqual(pinned_v1.json()["version"], 1)

    # -- duplicate happy path ------------------------------------------------- #

    def test_06_duplicate_remaps_ids_rebuilds_contexts_and_retains_attribution(self):
        slug = f"synthetic-dup-{uuid4().hex[:8]}"
        self.seed_release(slug, title="Synthetic duplicated release")
        response = self.duplicate(slug, title="Alice private copy")
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        document_id = UUID(body["id"])
        self.assertEqual(body["title"], "Alice private copy")
        self.assertEqual(body["revision"], 2)
        self.assertEqual(body["schema_version"], 1)
        row = self.document_row(document_id)
        self.assertEqual(row["owner_id"], self.alice_id)
        self.assertEqual(row["source_publication_id"],
                         self.publication_row(slug)["id"])

        content = body["content"]["content"]
        # The first block is the retained attribution paragraph naming slug+version.
        self.assertEqual(content[0]["type"], "paragraph")
        attribution_text = content[0]["content"][0]["text"]
        self.assertIn(slug, attribution_text)
        self.assertIn("version 1", attribution_text)
        # No private editorial metadata copied: annotation timestamps are fresh.
        published = parse_document(self.publication_row(slug)["content"])
        duplicated = parse_document(body["content"])
        self.assertEqual(len(duplicated.insights), len(published.insights))
        old_ts = published.insights[0].authored_at
        self.assertNotEqual(duplicated.insights[0].authored_at, old_ts)
        self.assertGreater(duplicated.insights[0].authored_at,
                           published.insights[0].authored_at)

        # Complete identity remap and link consistency.
        release_row = self.publication_row(slug)
        release_block_ids = {node["attrs"]["block_id"] for node in release_row["content"]["content"]}
        copy_block_ids = {node["attrs"]["block_id"] for node in content[1:]}
        self.assertFalse(release_block_ids & copy_block_ids)
        release_insight_ids = {node["attrs"]["insight_id"] for node in release_row["content"]["content"]
                               if node["type"] == "insight"}
        copy_insight_ids = {node["attrs"]["insight_id"] for node in content[1:]
                            if node["type"] == "insight"}
        self.assertFalse(release_insight_ids & copy_insight_ids)

        # Chart contexts rebuilt for the NEW block ids with verified pins.
        contexts = body["resolved_contexts"]
        chart_node = next(node for node in content if node["type"] == "liveChart")
        self.assertIn(chart_node["attrs"]["block_id"], contexts)
        rebuilt = contexts[chart_node["attrs"]["block_id"]]
        self.assertEqual(rebuilt["chart_definition_version_id"], self.chart_id)
        self.assertEqual(rebuilt["dataset_version_id"], str(self.approved_dataset_id))
        # The insight context was re-verified server-side (fresh resolved_at).
        insight_node = next(node for node in content if node["type"] == "insight")
        self.assertEqual(insight_node["attrs"]["context"]["chart_definition_version_id"],
                         self.chart_id)
        self.assertEqual(insight_node["attrs"]["context"]["dataset_version_id"],
                         str(self.approved_dataset_id))

        # Public evidence pins are preserved verbatim (citation target).
        copied_citations = [node for node in content if node["type"] == "evidence"
                            and node["attrs"]["target_kind"] == "citation"]
        self.assertEqual(len(copied_citations), 1)
        self.assertEqual(copied_citations[0]["attrs"]["target_id"], str(self.citation_id))

        # Projections were written for the duplicate owner.
        with self.admin.connect() as connection:
            projections = {
                table: connection.scalar(text(
                    f"SELECT count(*) FROM app.{table} WHERE document_id = :id"),
                    {"id": document_id})
                for table in ("document_versions", "document_blocks", "insights",
                              "hypotheses", "evidence_links")}
        self.assertEqual(projections["document_versions"], 2)
        # + attribution paragraph, + liveChart, + evidence blocks of the release.
        self.assertEqual(projections["document_blocks"],
                         len(published.blocks) + 1)
        self.assertEqual(projections["insights"], len(published.insights))
        self.assertEqual(projections["hypotheses"], len(published.hypotheses))
        self.assertEqual(projections["evidence_links"], len(published.evidence))

        # The copy is invisible to another owner; the release stays public.
        with self.as_session(self.bob_id):
            foreign = self.client.get(f"/api/documents/{document_id}",
                                      headers={"Authorization": "Bearer t.bob"})
        self.assertEqual(foreign.status_code, 404)
        still_public = self.client.get(f"/api/publications/{slug}")
        self.assertEqual(still_public.status_code, 200)

    def test_07_duplicate_title_defaults_to_the_release_title(self):
        slug = f"synthetic-dup-default-{uuid4().hex[:8]}"
        self.seed_release(slug, title="Synthetic default title")
        response = self.duplicate(slug)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["title"], "Synthetic default title")

    # -- source isolation ----------------------------------------------------- #

    def test_08_public_source_unchanged_after_private_edits(self):
        slug = f"synthetic-isolation-{uuid4().hex[:8]}"
        self.seed_release(slug)
        before = self.publication_row(slug)
        duplicated = self.duplicate(slug)
        self.assertEqual(duplicated.status_code, 201)
        document_id = UUID(duplicated.json()["id"])
        # Private edits to the copy: a new revision with different content.
        edited = {"schema_version": 1, "content": {"schema_version": 1, "type": "doc",
                  "content": [text_paragraph("Wholly different private analysis")]}}
        with self.as_session(self.alice_id):
            saved = self.client.post(f"/api/documents/{document_id}/versions", json=edited,
                                     headers={"If-Match": '"2"',
                                              "Authorization": "Bearer t.alice"})
        self.assertEqual(saved.status_code, 201)
        # Even a rename of the copy never touches the release.
        with self.as_session(self.alice_id):
            renamed = self.client.patch(f"/api/documents/{document_id}",
                                        json={"title": "Renamed private copy"},
                                        headers={"If-Match": '"3"',
                                                 "Authorization": "Bearer t.alice"})
        self.assertEqual(renamed.status_code, 200)
        after = self.publication_row(slug)
        self.assertEqual(after["content"], before["content"])
        self.assertEqual(after["content_sha256"], before["content_sha256"])
        self.assertEqual(after["manifest"], before["manifest"])
        self.assertEqual(after["title"], before["title"])
        self.assertEqual(after["published_at"], before["published_at"])
        # The public read still serves the original release content.
        response = self.client.get(f"/api/publications/{slug}")
        self.assertEqual(response.json()["content"], before["content"])

    # -- idempotent retry ------------------------------------------------------ #

    def test_09_idempotent_duplicate_replays_the_same_document(self):
        slug = f"synthetic-idem-{uuid4().hex[:8]}"
        self.seed_release(slug)
        key = str(uuid4())
        first = self.duplicate(slug, title="Synthetic idempotent", key=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.headers["ETag"], '"2"')
        # Lost-response retry: identical owner/route/body replays the original.
        retry = self.duplicate(slug, title="Synthetic idempotent", key=key)
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(retry.json(), first.json())
        self.assertEqual(UUID(retry.json()["id"]), UUID(first.json()["id"]))
        self.assertEqual(retry.headers["ETag"], '"2"')
        self.assertEqual(self.user_document_count(self.alice_id), 1)
        # Same key, different body -> collision, never a second copy.
        conflict = self.duplicate(slug, title="Different body", key=key)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(ErrorResponse.model_validate(conflict.json()).error.code,
                         "IDEMPOTENCY_CONFLICT")
        # A second copy WITHOUT a key is a real second document.
        second = self.duplicate(slug, title="Second copy")
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(second.json()["id"], first.json()["id"])
        self.assertEqual(self.user_document_count(self.alice_id), 2)

    # -- errors and permissions ------------------------------------------------ #

    def test_10_unavailable_releases_are_generic_404s(self):
        slug = f"synthetic-404-{uuid4().hex[:8]}"
        self.seed_release(slug)
        for version, label in ((99, "unknown version"), (0, "invalid version")):
            response = self.duplicate(slug, version=version)
            if label == "unknown version":
                self.assertEqual(response.status_code, 404)
                self.assertEqual(ErrorResponse.model_validate(response.json()).error.code,
                                 "NOT_FOUND")
            else:
                self.assertEqual(response.status_code, 422)
        unknown_slug = self.duplicate(f"synthetic-absent-{uuid4().hex[:8]}")
        self.assertEqual(unknown_slug.status_code, 404)
        self.assertEqual(ErrorResponse.model_validate(unknown_slug.json()).error.code,
                         "NOT_FOUND")
        # No document was created by any failed attempt.
        self.assertEqual(self.user_document_count(self.alice_id), 0)

    def test_11_unapproved_pinned_dataset_fails_explicitly_never_latest(self):
        # The release pins a dataset version that was never approved: the seed
        # gate parses canonical content (pins are not existence-checked there),
        # but the duplicate must fail closed instead of substituting latest.
        slug = f"synthetic-unapproved-{uuid4().hex[:8]}"
        staged_dataset = chart_fixtures.ChartBlockDatabaseFixture.insert_dataset_version(
            self, f"synthetic.{uuid4().hex[:8]}.staged", status="staged")
        content = publication_document(
            chart_definition_version_id=self.chart_id,
            dataset_version_id=str(staged_dataset),
            insight_context=copy.deepcopy(self.chart_context))
        seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug, version=1,
                         title="Synthetic staged pin", content=content,
                         evidence_manifest=[])
        response = self.duplicate(slug)
        self.assertEqual(response.status_code, 422)
        failure = ErrorResponse.model_validate(response.json()).error
        self.assertEqual(failure.code, "REFERENCE_INVALID")
        reasons = {detail.reason for detail in (failure.details or [])}
        self.assertIn("dangling_dataset_reference", reasons)
        # Zero rows: the failed duplicate created nothing.
        self.assertEqual(self.user_document_count(self.alice_id), 0)

    def test_12_unverifiable_insight_context_fails_explicitly(self):
        # The insight context pins an unknown chart definition: re-verification
        # on the duplicate path refuses it (never silently carried forward).
        slug = f"synthetic-ctx-{uuid4().hex[:8]}"
        context = document_fixtures.resolved_context()  # random ids, fake hash
        content = publication_document(
            chart_definition_version_id=self.chart_id,
            dataset_version_id=str(self.approved_dataset_id),
            insight_context=context)
        seed_publication(os.environ["NI_TEST_OPERATOR_URL"], slug=slug, version=1,
                         title="Synthetic bad context", content=content,
                         evidence_manifest=[])
        response = self.duplicate(slug)
        self.assertEqual(response.status_code, 422)
        failure = ErrorResponse.model_validate(response.json()).error
        self.assertEqual(failure.code, "REFERENCE_INVALID")
        self.assertEqual(self.user_document_count(self.alice_id), 0)

    def test_13_duplicate_ownership_matrix_alice_and_bob(self):
        slug = f"synthetic-matrix-{uuid4().hex[:8]}"
        self.seed_release(slug)
        alice_copy = self.duplicate(slug, subject=self.alice)
        bob_copy = self.duplicate(slug, subject=self.bob)
        self.assertEqual(alice_copy.status_code, 201)
        self.assertEqual(bob_copy.status_code, 201)
        alice_id = UUID(alice_copy.json()["id"])
        bob_id = UUID(bob_copy.json()["id"])
        self.assertNotEqual(alice_id, bob_id)
        # Each copy belongs to exactly its requesting owner.
        self.assertEqual(self.document_row(alice_id)["owner_id"], self.alice_id)
        self.assertEqual(self.document_row(bob_id)["owner_id"], self.bob_id)
        # Neither owner sees the other's copy; both read the public release.
        with self.as_session(self.bob_id):
            alice_seen_by_bob = self.client.get(f"/api/documents/{alice_id}",
                                                headers={"Authorization": "Bearer t.bob"})
        self.assertEqual(alice_seen_by_bob.status_code, 404)
        with self.as_session(self.alice_id):
            bob_seen_by_alice = self.client.get(f"/api/documents/{bob_id}",
                                                headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(bob_seen_by_alice.status_code, 404)
        # Idempotency records are owner-scoped: the same key creates Bob's own
        # independent copy instead of replaying Alice's result.
        shared_key = str(uuid4())
        alice_keyed = self.duplicate(slug, subject=self.alice, key=shared_key)
        bob_keyed = self.duplicate(slug, subject=self.bob, key=shared_key)
        self.assertEqual(alice_keyed.status_code, 201)
        self.assertEqual(bob_keyed.status_code, 201)
        self.assertNotEqual(UUID(bob_keyed.json()["id"]), UUID(alice_keyed.json()["id"]))
