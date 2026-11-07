"""NI-022 owner-scoped home aggregation tests.

Use scripts/run-db-tests.py for the cluster-dependent cases; direct discovery
skips them without its explicit isolated-cluster environment. A skip is never
successful integration evidence. The offline cases cover the HTTP failure
matrix (401 without/with an invalid session), the standardized 404 mapping
and the response contract shape including the honest pending sections.

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

from near_api.auth import principal as principal_module
from near_api.auth.principal import Principal, bootstrap_principal
from near_api.auth.verification import TokenInvalid, VerifiedToken
from near_api.contracts import install_contracts
from near_api.db.security import ResourceNotFound, principal_transaction
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.main import app
from near_api.repositories import documents as documents_repo
from near_api.schemas.common import ErrorResponse
from near_api.schemas.home import DocumentSummary, HomeResponse, PendingHomeSection
from near_api.workspace.aggregation import HomeOverview, home_overview

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

    def test_01_home_is_documented_in_openapi_with_required_pending_sections(self):
        schema = self.client.get("/openapi.json").json()
        # The contract grows with implemented routes: NI-025 added /api/me,
        # NI-036 added the document revision routes and NI-032 added the
        # public metrics/chart/dataset/source delivery routes.
        self.assertEqual(set(schema["paths"]), {"/health", "/api/home", "/api/me",
                                                "/api/documents",
                                                "/api/documents/{document_id}",
                                                "/api/documents/{document_id}/versions",
                                                "/api/metrics",
                                                "/api/metrics/{metric_id}",
                                                "/api/metrics/{metric_id}/series",
                                                "/api/charts", "/api/charts/{chart_id}",
                                                "/api/charts/{chart_id}/view",
                                                "/api/data-sources",
                                                "/api/data-sources/{source_id}",
                                                "/api/datasets/{version_id}",
                                                "/api/datasets/{version_id}/manifest"})
        self.assertEqual(schema["paths"]["/api/home"]["get"]["operationId"], "getWorkspaceHome")
        response_schema = schema["components"]["schemas"]["HomeResponse"]
        # Every documented field is always present: empty arrays stay explicit
        # instead of turning into optional fields later (NI-024 consumption).
        self.assertEqual(set(response_schema["required"]), HOME_FIELDS)
        for section in ("recent_charts", "recent_insights", "indicators"):
            self.assertEqual(response_schema["properties"][section]["maxItems"], 0,
                             "pending sections must forbid items until their owning task lands")
        self.assertEqual(response_schema["properties"]["recent_documents"]["maxItems"], 5)
        for name in ("DocumentSummary", "DocumentProgress", "PendingHomeSection", "HomeCounts"):
            self.assertIn(name, schema["components"]["schemas"])

    def test_02_response_contract_rejects_fabricated_or_wrong_data(self):
        with self.assertRaises(ValidationError):
            # A pending section can never carry a placeholder item.
            HomeResponse(recent_documents=(), recent_charts=(PendingHomeSection(),),
                         recent_insights=(), indicators=(), counts={"documents": 0})
        with self.assertRaises(ValidationError):
            # The recent list is capped by the schema at 5.
            HomeResponse(recent_documents=tuple(summary() for _ in range(6)),
                         recent_charts=(), recent_insights=(), indicators=(),
                         counts={"documents": 6})
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
        self.assertEqual(payload["indicators"], [])

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
        self.assertEqual(payload["indicators"], [])
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
        self.assertLessEqual(alice_statements, 6)


if __name__ == "__main__":
    unittest.main()
