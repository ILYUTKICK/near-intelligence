"""NI-022 owner-scoped home aggregation tests.

Use scripts/run-db-tests.py for the cluster-dependent cases; direct discovery
skips them without its explicit isolated-cluster environment. A skip is never
successful integration evidence. The offline cases cover the HTTP failure
matrix (401 without/with an invalid session), the standardized 404 mapping
and the bounded response contracts.

All identities, titles and document contents are synthetic test fixtures,
never research data.
"""

import hashlib
import json
import os
import unittest
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import make_url

from near_api.auth import principal as principal_module
from near_api.auth.principal import Principal, bootstrap_principal
from near_api.auth.verification import TokenInvalid, VerifiedToken
from near_api.contracts import install_contracts
from near_api.db.security import ResourceNotFound, principal_transaction
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.main import app
from near_api.repositories import documents as documents_repo
from near_api.schemas.common import ErrorResponse
from near_api.schemas.home import DocumentSummary, HomeResponse, HomeIndicator
from near_api.workspace.aggregation import HomeOverview, home_overview
from near_api.documents import service as document_service
import test_documents as document_fixtures
import test_chart_blocks as chart_fixtures
import test_delivery_apis as delivery_fixtures
from near_api.charts import saved
from near_api.charts.registry import chart_by_chart_id
from near_api.schemas.saved_charts import SavedChartCreateRequest
from near_api.datasets import delivery

DOCUMENT_CONTENT = {"type": "doc", "content": [{"type": "paragraph"}]}
HOME_FIELDS = {"recent_documents", "recent_charts", "recent_insights", "indicators", "counts"}


def sha256_of(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def summary(**changes) -> dict:
    now = datetime.now(UTC)
    return {"id": str(uuid4()), "title": "Synthetic", "revision": 1, "schema_version": 1,
            "current_version_id": None, "created_at": now.isoformat(),
            "updated_at": now.isoformat(), "progress": {"headings": 0, "charts": 0, "insights": 0},
            **changes}


class StubVerifier:
    """Stubbed token verifier so no provider or JWKS is ever contacted."""

    def __init__(self, result):
        self.result = result
        self.tokens = []

    def verify(self, token):
        self.tokens.append(token)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def verified(subject) -> VerifiedToken:
    return VerifiedToken(subject=subject, expires_at=datetime.now(UTC) + timedelta(minutes=5),
                         issued_at=datetime.now(UTC))


class HomeContractTests(unittest.TestCase):
    """Offline contract and HTTP failure behavior; no database required."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_01_home_is_documented_in_openapi_with_bounded_typed_sections(self):
        schema = self.client.get("/openapi.json").json()
        # The contract grows with implemented routes: NI-025 added /api/me,
        # NI-036 added the document revision routes, NI-037 added the version
        # detail route, NI-032 added the public
        # metrics/chart/dataset/source delivery routes, NI-054 added the
        # public model definition/readiness/run routes and NI-041 added the
        # chart-block insertion route.
        self.assertEqual(set(schema["paths"]), {"/health", "/api/home", "/api/me",
                "/api/saved-charts", "/api/saved-charts/{instance_id}",
                                                "/api/documents",
                                                "/api/documents/{document_id}",
                                                "/api/documents/{document_id}/versions",
                                                "/api/documents/{document_id}/versions/{version_id}",
                                                "/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/view",
                                                "/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/csv",
                                                "/api/documents/{document_id}/chart-blocks",
                                                "/api/documents/{document_id}/chart-view",
                                                "/api/documents/{document_id}/insights",
                                                "/api/documents/{document_id}/insights/{insight_id}",
                                                "/api/documents/{document_id}/hypotheses",
                                                "/api/documents/{document_id}/hypotheses/{hypothesis_id}",
                                                "/api/documents/{document_id}/evidence",
                                                "/api/documents/{document_id}/evidence/{evidence_id}",
                                                "/api/documents/{document_id}/evidence-targets",
                                                "/api/metrics",
                                                "/api/metrics/{metric_id}",
                                                "/api/metrics/{metric_id}/series",
                                                "/api/charts", "/api/charts/{chart_id}",
                                                "/api/charts/{chart_id}/view",
                                                "/api/data-sources",
                                                "/api/data-sources/{source_id}",
                                                "/api/datasets/{version_id}",
                                                "/api/datasets/{version_id}/manifest",
                                                "/api/model-definitions",
                                                "/api/model-definitions/{model_id}",
                                                "/api/model-definitions/{model_id}/readiness",
                                                "/api/model-runs",
                                                "/api/model-runs/{run_id}",
                                                "/api/model-runs/{run_id}/manifest",
                                                "/api/documents/{document_id}/exports",
                                                "/api/documents/{document_id}/exports/{job_id}",
                                                "/api/documents/{document_id}/exports/{job_id}/download",
                                                "/api/documents/{document_id}/shares",
                                                "/api/documents/{document_id}/shares/preview",
                                                "/api/documents/{document_id}/shares/{share_id}",
                                                "/api/shares/{token}",
                                                "/api/shares/{token}/charts/{block_id}/view",
                                                "/api/shares/{token}/charts/{block_id}/csv"})
        self.assertEqual(schema["paths"]["/api/home"]["get"]["operationId"], "getWorkspaceHome")
        response_schema = schema["components"]["schemas"]["HomeResponse"]
        # Every documented field is always present: empty arrays stay explicit
        # instead of turning into optional fields later (NI-024 consumption).
        self.assertEqual(set(response_schema["required"]), HOME_FIELDS)
        for section, cap in (("recent_charts", 5), ("recent_insights", 5), ("indicators", 3)):
            self.assertEqual(response_schema["properties"][section]["maxItems"], cap)
        self.assertEqual(response_schema["properties"]["recent_documents"]["maxItems"], 5)
        for name in ("DocumentSummary", "DocumentProgress", "HomeInsightSummary", "HomeIndicator", "HomeCounts"):
            self.assertIn(name, schema["components"]["schemas"])

    def test_02_response_contract_rejects_fabricated_or_wrong_data(self):
        with self.assertRaises(ValidationError):
            # A placeholder cannot validate as a persisted saved chart.
            HomeResponse(recent_documents=(), recent_charts=({"status": "pending"},),
                         recent_insights=(), indicators=(), counts={"documents": 0})
        with self.assertRaises(ValidationError):
            # The recent list is capped by the schema at 5.
            HomeResponse(recent_documents=tuple(summary() for _ in range(6)),
                         recent_charts=(), recent_insights=(), indicators=(),
                         counts={"documents": 6})
        with self.assertRaises(ValidationError):
            HomeIndicator(chart_id="gross-fees", title="Synthetic", chart_version=1,
                          status="available", series=None, reason=None)
        with self.assertRaises(ValidationError):
            HomeIndicator(chart_id="gross-fees", title="Synthetic", chart_version=None,
                          status="unavailable", series=None, reason=None)
        with self.assertRaises(ValidationError):
            DocumentSummary.model_validate(summary(revision=0))
        with self.assertRaises(ValidationError):
            DocumentSummary.model_validate(summary(title=""))
        with self.assertRaises(ValidationError):
            DocumentSummary.model_validate({**summary(), "owner_id": str(uuid4())})
        with self.assertRaises(ValidationError):
            DocumentSummary.model_validate(
                {**summary(), "progress": {"headings": -1, "charts": 0, "insights": 0}})

    def test_03_overview_serializes_honest_empty_sections(self):
        overview = HomeOverview(recent_documents=(), documents_total=0)
        response = overview.to_home_response()
        payload = response.model_dump(mode="json")
        self.assertEqual(set(payload), HOME_FIELDS)
        self.assertEqual(payload["recent_documents"], [])
        self.assertEqual(payload["recent_charts"], [])
        self.assertEqual(payload["recent_insights"], [])
        self.assertEqual(payload["indicators"], [])
        self.assertEqual(payload["counts"], {"documents": 0})
        self.assertEqual(HomeResponse.model_validate_json(response.model_dump_json()), response)

    def test_04_missing_or_malformed_authorization_is_401(self):
        # The real get_principal dependency rejects before any provider,
        # settings or database access happens.
        for header in (None, "", "Bearer", "Bearer   ", "Basic c3ludGg6c2VjcmV0", "Token abc"):
            with self.subTest(header=header):
                headers = {} if header is None else {"Authorization": header}
                response = self.client.get("/api/home", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
                error = ErrorResponse.model_validate(response.json())
                self.assertEqual(error.error.code, "AUTHENTICATION_REQUIRED")
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(str(error.error.request_id), response.headers["X-Request-ID"])

    def test_05_invalid_session_is_one_generic_401_without_detail_leak(self):
        verifier = StubVerifier(TokenInvalid("synthetic-private-verification-reason"))
        with patch.object(principal_module, "_get_verifier", return_value=verifier):
            response = self.client.get("/api/home",
                                       headers={"Authorization": "Bearer aaa.bbb.ccc"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        ErrorResponse.model_validate(response.json())
        self.assertNotIn("synthetic-private", response.text)
        self.assertNotIn("reason", response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(verifier.tokens, ["aaa.bbb.ccc"])

    def test_06_resource_not_found_maps_to_one_generic_404(self):
        application = FastAPI()
        install_contracts(application)

        @application.get("/__synthetic__/missing")
        def synthetic_missing():
            raise ResourceNotFound("synthetic-private-not-found-reason")

        with TestClient(application, raise_server_exceptions=False) as client:
            response = client.get("/__synthetic__/missing")
        self.assertEqual(response.status_code, 404)
        error = ErrorResponse.model_validate(response.json())
        self.assertEqual(error.error.code, "NOT_FOUND")
        self.assertNotIn("synthetic-private", response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class HomeAggregationTests(unittest.TestCase):
    """Two-user home aggregation matrix on the disposable PostgreSQL cluster."""

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

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.operator.dispose()
        cls.admin.dispose()

    def setUp(self):
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))
        self.alice_id, self.bob_id = uuid4(), uuid4()
        for subject, name in ((self.alice_id, "Synthetic Alice"), (self.bob_id, "Synthetic Bob")):
            with user_transaction(self.engine, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"), {"id": subject})
                connection.execute(text("""INSERT INTO app.user_profiles(user_id, display_name)
                                          VALUES (:id, :name)"""), {"id": subject, "name": name})
        self.client = TestClient(app, raise_server_exceptions=False)

    def principal(self, subject) -> Principal:
        return Principal(id=subject, display_name="Synthetic", display_timezone="UTC")

    def alice(self) -> Principal:
        return self.principal(self.alice_id)

    def bob(self) -> Principal:
        return self.principal(self.bob_id)

    def create_documents(self, principal: Principal, titles, *, versions: int = 1):
        """Create owned documents, newest last; returns (document_id, version_id) pairs."""
        created = []
        with principal_transaction(self.engine, principal) as connection:
            for title in titles:
                document_id = documents_repo.create_document(connection, principal,
                                                             title=title, schema_version=1)
                version_ids = [documents_repo.create_version(
                    connection, principal, document_id, content=DOCUMENT_CONTENT,
                    content_sha256=sha256_of(DOCUMENT_CONTENT)) for _ in range(versions)]
                created.append((document_id, version_ids[-1] if version_ids else None))
        return created

    def stagger_updated_at(self, oldest_first):
        """Force distinct updated_at values so the sort order is deterministic."""
        base = datetime.now(UTC).replace(microsecond=0)
        with self.admin.begin() as connection:
            for position, document_id in enumerate(oldest_first):
                connection.execute(text(
                    "UPDATE app.documents SET updated_at = :ts WHERE id = :id"),
                    {"ts": base + timedelta(seconds=position), "id": document_id})

    def as_session(self, subject):
        """Route calls run the real get_principal with a stubbed verifier only."""
        verifier = StubVerifier(verified(subject))
        context = ExitStack()
        context.enter_context(patch.object(principal_module, "_get_verifier",
                                           return_value=verifier))
        context.enter_context(patch.object(principal_module, "_get_engine",
                                           return_value=self.engine))
        return context

    def test_01_home_is_scoped_and_capped_for_two_users(self):
        alice, bob = self.alice(), self.bob()
        alice_documents = self.create_documents(
            alice, [f"alice-doc-{number:02d}" for number in range(25)])
        bob_documents = self.create_documents(bob, [f"bob-doc-{number}" for number in range(2)])
        # Created oldest-first, so alice-doc-24 is the newest document.
        self.stagger_updated_at([document_id for document_id, _ in alice_documents])
        with principal_transaction(self.engine, alice) as connection:
            overview = home_overview(connection, alice)
            self.assertEqual(overview.documents_total, 25)
            self.assertEqual(len(overview.recent_documents), 5)
            self.assertEqual([item.title for item in overview.recent_documents],
                             [f"alice-doc-{number:02d}" for number in range(24, 19, -1)])
            self.assertTrue(all(item.id not in {identifier for identifier, _ in bob_documents}
                                for item in overview.recent_documents))
        with principal_transaction(self.engine, bob) as connection:
            overview = home_overview(connection, bob)
            self.assertEqual(overview.documents_total, 2)
            self.assertEqual({item.title for item in overview.recent_documents},
                             {"bob-doc-0", "bob-doc-1"})
            self.assertTrue(all(item.id not in {identifier for identifier, _ in alice_documents}
                                for item in overview.recent_documents))
        # HTTP level through the real dependency chain (stubbed verifier only).
        with self.as_session(self.alice_id):
            response = self.client.get("/api/home", headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        payload = response.json()
        self.assertEqual(set(payload), HOME_FIELDS)
        self.assertEqual(payload["counts"], {"documents": 25})
        self.assertEqual(len(payload["recent_documents"]), 5)
        self.assertEqual([item["title"] for item in payload["recent_documents"]],
                         [f"alice-doc-{number:02d}" for number in range(24, 19, -1)])
        newest = payload["recent_documents"][0]
        self.assertEqual(set(newest), {"id", "title", "revision", "schema_version",
                                       "current_version_id", "created_at", "updated_at",
                                       "progress"})
        self.assertEqual(newest["id"], str(alice_documents[-1][0]))
        # The summary carries the document's current revision, not a stale one.
        self.assertEqual(newest["revision"], 2)
        self.assertEqual(newest["current_version_id"], str(alice_documents[-1][1]))
        self.assertEqual(newest["progress"], {"headings": 0, "charts": 0, "insights": 0})
        HomeResponse.model_validate(payload)
        with self.as_session(self.bob_id):
            response = self.client.get("/api/home", headers={"Authorization": "Bearer t.bob"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"], {"documents": 2})
        self.assertTrue(all("alice-doc" not in item["title"]
                            for item in payload["recent_documents"]))
        self.assertEqual(payload["recent_charts"], [])
        self.assertEqual(payload["recent_insights"], [])
        self.assertEqual(len(payload["indicators"]), 3)
        self.assertTrue(all(item["status"] == "unavailable" for item in payload["indicators"]))

    def test_02_deleted_document_leaves_recent_without_error(self):
        alice = self.alice()
        documents = self.create_documents(alice, ["doomed-latest", "kept-2", "kept-1"])
        self.stagger_updated_at([documents[2][0], documents[1][0], documents[0][0]])
        with principal_transaction(self.engine, alice) as connection:
            documents_repo.delete_document(connection, alice, documents[0][0])
        with principal_transaction(self.engine, alice) as connection:
            overview = home_overview(connection, alice)
            self.assertEqual(overview.documents_total, 2)
            self.assertEqual([item.title for item in overview.recent_documents],
                             ["kept-2", "kept-1"])
        with self.as_session(self.alice_id):
            response = self.client.get("/api/home", headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"], {"documents": 2})
        self.assertEqual([item["title"] for item in payload["recent_documents"]],
                         ["kept-2", "kept-1"])
        self.assertNotIn(str(documents[0][0]), response.text)

    def test_03_fresh_user_gets_a_valid_empty_home(self):
        with self.as_session(self.alice_id):
            response = self.client.get("/api/home", headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        payload = response.json()
        self.assertEqual(set(payload), HOME_FIELDS)
        self.assertEqual(payload["recent_documents"], [])
        self.assertEqual(payload["recent_charts"], [])
        self.assertEqual(payload["recent_insights"], [])
        self.assertEqual(len(payload["indicators"]), 3)
        self.assertTrue(all(item["status"] == "unavailable" for item in payload["indicators"]))
        self.assertEqual(payload["counts"], {"documents": 0})
        HomeResponse.model_validate(payload)

    def test_04_disabled_account_is_403_fail_closed_and_recovers(self):
        bootstrap_principal(self.engine, verified(self.alice_id))
        with self.operator.begin() as connection:
            connection.execute(text("UPDATE app.users SET disabled_at = now() WHERE id = :id"),
                               {"id": self.alice_id})
        with self.as_session(self.alice_id):
            response = self.client.get("/api/home", headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(response.status_code, 403)
        error = ErrorResponse.model_validate(response.json())
        self.assertEqual(error.error.code, "FORBIDDEN")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        # State-dependent: restoring the account restores the (empty) home.
        with self.operator.begin() as connection:
            connection.execute(text("UPDATE app.users SET disabled_at = NULL WHERE id = :id"),
                               {"id": self.alice_id})
        with self.as_session(self.alice_id):
            response = self.client.get("/api/home", headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"], {"documents": 0})

    def test_05_query_count_is_bounded_and_independent_of_row_count(self):
        alice, bob = self.alice(), self.bob()
        self.create_documents(alice, [f"alice-doc-{number:02d}" for number in range(25)])
        self.create_documents(bob, ["bob-only-doc"])
        statements = []

        def count_statement(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", count_statement)
        try:
            with principal_transaction(self.engine, alice) as connection:
                home_overview(connection, alice)
            alice_statements = len(statements)
            statements.clear()
            with principal_transaction(self.engine, bob) as connection:
                home_overview(connection, bob)
            bob_statements = len(statements)
        finally:
            event.remove(self.engine, "before_cursor_execute", count_statement)
        # Identical statement count for 25 rows and 1 row proves there is no
        # per-row follow-up query (no N+1); the absolute bound stays small.
        self.assertEqual(alice_statements, bob_statements)
        self.assertLessEqual(alice_statements, 20)
        # 6 private queries + identity setup + <=3 savepoint/catalog attempts.


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class HomeContextDatabaseTests(unittest.TestCase):
    """Actual canonical saves, saved instances and approved indicator data."""

    @classmethod
    def setUpClass(cls):
        # Delivery's catalog fixture inserts/updates shared scientific rows.
        # Give this class a copy of the existing isolated database so neither
        # those writes nor approved immutable datasets can leak to later suites.
        # The original DB is never changed; this also preserves preexisting data.
        original = make_url(os.environ["NI_TEST_ADMIN_URL"])
        database_name = f"ni024_home_{uuid4().hex}"
        cls.bootstrap = create_engine(original.set(database="postgres"), poolclass=NullPool,
                                      hide_parameters=True, isolation_level="AUTOCOMMIT")
        quote = cls.bootstrap.dialect.identifier_preparer.quote
        database_sql = quote(database_name)
        with cls.bootstrap.connect() as connection:
            connection.execute(text(f"CREATE DATABASE {database_sql} OWNER near_migrator "
                                    f"TEMPLATE {quote(original.database)}"))
            connection.execute(text(f"REVOKE ALL ON DATABASE {database_sql} FROM PUBLIC"))
            connection.execute(text(f"GRANT CONNECT ON DATABASE {database_sql} "
                                    "TO near_app, near_operator, near_migrator, near_public"))
            for role in ("near_app", "near_operator"):
                connection.execute(text(f"ALTER ROLE {role} IN DATABASE {database_sql} "
                                        "SET search_path = pg_catalog, app"))
            connection.execute(text(f"ALTER ROLE near_public IN DATABASE {database_sql} "
                                    "SET search_path = pg_catalog"))

        def drop_class_database():
            try:
                with cls.bootstrap.connect() as connection:
                    connection.execute(text(f"DROP DATABASE {database_sql} WITH (FORCE)"))
            finally:
                cls.bootstrap.dispose()

        cls.addClassCleanup(drop_class_database)
        environment = {}
        for key in ("NI_TEST_ADMIN_URL", "NI_TEST_RUNTIME_URL", "NI_TEST_OPERATOR_URL",
                    "NI_TEST_PUBLIC_URL", "MIGRATION_DATABASE_URL"):
            environment[key] = make_url(os.environ[key]).set(database=database_name).render_as_string(
                hide_password=False)
        cls.environment = patch.dict(os.environ, environment)
        cls.environment.start()
        cls.addClassCleanup(cls.environment.stop)
        delivery_fixtures.DeliveryDatabaseTests.setUpClass.__func__(cls)
        cls.addClassCleanup(delivery_fixtures.DeliveryDatabaseTests.tearDownClass.__func__, cls)
        cls.addClassCleanup(delivery.reset_delivery_caches)
        cls.engine = cls.runtime

    def setUp(self):
        delivery_fixtures.DeliveryDatabaseTests.setUp(self)
        self.alice = Principal(uuid4(), "Synthetic Alice", "UTC")
        self.bob = Principal(uuid4(), "Synthetic Bob", "UTC")
        with self.admin.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))
            for actor in (self.alice, self.bob):
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"), {"id": actor.id})

    def overview(self, actor):
        with principal_transaction(self.runtime, actor) as connection:
            return home_overview(connection, actor).to_home_response()

    def test_current_canonical_notes_and_progress_exclude_history_and_other_owner(self):
        day = datetime(2026, 1, 1).date()
        dataset = delivery_fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni024.notes.{uuid4().hex[:12]}",
            [delivery_fixtures.observation(delivery_fixtures.METRIC_VOLUME, day, value="12.5")],
            [delivery_fixtures.METRIC_VOLUME], window=("2026-01-01", "2026-01-02"))
        context = chart_fixtures.volume_context(self.operator, dataset.dataset_version_id)
        document = document_service.create_document(self.runtime, self.alice, title="Synthetic Alice current")
        old_note = document_fixtures.insight_attrs(context=context)
        heading = document_fixtures.block("heading", level=1)
        heading["content"] = [{"type": "text", "text": "Synthetic heading"}]
        document_service.save_revision(self.runtime, self.alice, document.document.id,
            expected_revision=1, document_payload={"type": "doc", "schema_version": 1,
                                                 "content": [heading, old_note]})
        # Same immutable note ID across revisions must appear exactly once;
        # the removed old heading must not inflate workflow completion.
        notes = [old_note] + [document_fixtures.insight_attrs(context=context) for _ in range(6)]
        document_service.save_revision(self.runtime, self.alice, document.document.id,
            expected_revision=2, document_payload={"type": "doc", "schema_version": 1, "content": notes})
        bob_doc = document_service.create_document(self.runtime, self.bob, title="Synthetic Bob private")
        document_service.save_revision(self.runtime, self.bob, bob_doc.document.id,
            expected_revision=1, document_payload={"type": "doc", "schema_version": 1,
                                                 "content": [heading, document_fixtures.insight_attrs(context=context)]})
        home = self.overview(self.alice)
        self.assertEqual(home.counts.documents, 1)
        self.assertEqual(home.recent_documents[0].progress.model_dump(),
                         {"headings": 0, "charts": 0, "insights": 7})
        self.assertEqual(len(home.recent_insights), 5)
        self.assertTrue(all(item.document_id == document.document.id for item in home.recent_insights))
        self.assertEqual(len({item.insight_id for item in home.recent_insights}), 5)
        self.assertTrue(all(item.excerpt == "Observation body" for item in home.recent_insights))
        bob_home = self.overview(self.bob)
        self.assertEqual(bob_home.recent_documents[0].progress.headings, 1)
        self.assertEqual(len(bob_home.recent_insights), 1)
        with principal_transaction(self.runtime, self.alice) as connection:
            documents_repo.delete_document(connection, self.alice, document.document.id)
        self.assertEqual(self.overview(self.alice).recent_insights, ())

    def test_owned_saved_chart_cap_exact_indicator_and_isolated_sql_source_failure(self):
        day = datetime(2026, 1, 1).date()
        exact = "123456789.123456789012345678901234"
        dataset = delivery_fixtures.DeliveryDatabaseTests.stage_fixture(self, f"ni024.{uuid4().hex[:16]}",
            [delivery_fixtures.observation(delivery_fixtures.METRIC_VOLUME, day, value=exact),
             delivery_fixtures.observation(delivery_fixtures.METRIC_FEES, day, value="1.5")],
            [delivery_fixtures.METRIC_VOLUME, delivery_fixtures.METRIC_FEES],
            window=("2026-01-01", "2026-01-02"))
        body = SavedChartCreateRequest.model_validate({
            "chart_definition_version_id": str(chart_by_chart_id("intents-volume").id),
            "label": "Synthetic saved context", "mode": "live",
            "dataset_version_id": str(dataset.dataset_version_id),
            "selection": {"start": "2026-01-01", "end": "2026-01-02", "frequency": "day", "filters": {}}})
        saved_ids = []
        with principal_transaction(self.runtime, self.alice) as connection:
            for _ in range(7):
                saved_ids.append(saved.create(connection, self.alice.id, body).id)
        with principal_transaction(self.runtime, self.bob) as connection:
            bob_saved = saved.create(connection, self.bob.id, body)
        document = document_service.create_document(self.runtime, self.alice, title="Synthetic persists through outage")
        home = self.overview(self.alice)
        self.assertEqual(len(home.recent_charts), 5)
        self.assertTrue(all(item.id in saved_ids for item in home.recent_charts))
        self.assertNotIn(bob_saved.id, {item.id for item in home.recent_charts})
        self.assertEqual(home.indicators[0].series.points[0].value, exact)
        self.assertEqual(home.indicators[0].series.dataset.id, dataset.dataset_version_id)
        self.assertEqual(home.indicators[0].chart_version, 1)
        self.assertEqual(home.indicators[0].series.selection.start.isoformat(), "2026-01-01")
        self.assertEqual(home.indicators[0].series.selection.end.isoformat(), "2026-01-02")
        original = delivery.load_chart_definition

        def fail_one_source(connection, chart_id, version):
            if chart_id == "intents-volume":
                connection.execute(text("SELECT * FROM app.synthetic_missing_source_table"))
            return original(connection, chart_id, version)

        with patch.object(delivery, "load_chart_definition", side_effect=fail_one_source):
            failed = self.overview(self.alice)
        self.assertEqual(failed.recent_documents[0].id, document.document.id)
        self.assertEqual(len(failed.recent_charts), 5)
        self.assertEqual(failed.indicators[0].status, "unavailable")
        self.assertIsNone(failed.indicators[0].series)
        self.assertNotIn("synthetic_missing_source_table", failed.model_dump_json())
        self.assertEqual(failed.indicators[1].status, "available")
        self.assertEqual(failed.indicators[1].series.points[0].value, "1.5")
        self.assertEqual(len(self.overview(self.bob).recent_charts), 1)
        # Cold canonical delivery has a fixed bound too: more private rows do
        # not multiply queries or trigger one lookup per recent item.
        statements = []

        def count_statement(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(self.runtime, "before_cursor_execute", count_statement)
        try:
            counts = []
            for actor in (self.alice, self.bob):
                delivery.reset_delivery_caches()
                statements.clear()
                self.overview(actor)
                counts.append(len(statements))
        finally:
            event.remove(self.runtime, "before_cursor_execute", count_statement)
        self.assertEqual(counts[0], counts[1])
        self.assertLessEqual(counts[0], 64)


if __name__ == "__main__":
    unittest.main()
