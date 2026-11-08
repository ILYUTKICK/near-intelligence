"""NI-024 production gateway/API/isolated PostgreSQL persistence verification.

Only synthetic auth transport and visibly labeled data fixtures are used.
The inherited harness verifies ES256/JWKS, cookie/Origin/CSRF, principal and RLS.
NI_BROWSER_HANDOFF=1 keeps this disposable stack for native-browser review.
"""
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import text

from near_api.datasets import delivery
import test_documents as documents_fixture
import test_saved_charts_http as gateway_fixture


class WorkspaceHomeHTTPE2E(gateway_fixture.SavedChartsHTTPE2E):
    def after_gateway_checks(self, client, session_cookie, body):
        client.cookies.set("ni_session", session_cookie("alice"))
        first = client.get("/api/home")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.headers["cache-control"], "no-store")
        self.assertEqual(first.json()["recent_documents"], [])
        self.assertEqual(first.json()["counts"], {"documents": 0})
        self.assertEqual(len(first.json()["recent_charts"]), 1)
        token = client.get("/api/auth/csrf").json()["token"]
        headers = {"Origin": str(client.base_url).rstrip("/"), "x-csrf-token": token,
                   "Idempotency-Key": str(uuid4())}
        created = client.post("/api/documents", json={"title": "Synthetic Home persistence E2E"}, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        document = created.json()
        self.http_document_id = document["id"]
        path = "/api/documents/" + document["id"]
        content = documents_fixture.full_document()
        headers.update({"If-Match": '"1"', "Idempotency-Key": str(uuid4())})
        saved = client.post(path + "/versions", json={"schema_version": 1, "content": content,
                                                       "observed_contexts": []}, headers=headers)
        self.assertEqual(saved.status_code, 201, saved.text)
        home = client.get("/api/home").json()
        self.assertEqual(home["recent_documents"][0]["id"], document["id"])
        self.assertEqual(home["recent_documents"][0]["revision"], 2)
        self.assertEqual(home["recent_documents"][0]["progress"], {"headings": 1, "charts": 0, "insights": 1})
        self.assertEqual(len(home["recent_insights"]), 1)
        self.assertEqual(client.get(path).json()["content"], documents_fixture.parse_document(content).canonical)
        workspace = client.get("/workspace")
        self.assertEqual(workspace.status_code, 200)
        self.assertIn("no-store", workspace.headers["cache-control"])
        self.assertEqual(client.get("/workspace/research/" + document["id"]).status_code, 200)

        original = delivery.load_chart_definition
        def source_outage(connection, chart_id, version):
            if chart_id == "gross-fees":
                connection.execute(text("SELECT 1 / 0"))  # actual isolated SQL failure
            return original(connection, chart_id, version)
        with patch.object(delivery, "load_chart_definition", side_effect=source_outage):
            failed = client.get("/api/home")
        self.assertEqual(failed.status_code, 200, failed.text)
        self.assertEqual(failed.json()["recent_documents"], home["recent_documents"])
        self.assertEqual(failed.json()["indicators"][1]["status"], "unavailable")
        self.assertEqual(failed.json()["indicators"][0]["status"], "available")

        client.cookies.set("ni_session", session_cookie("bob"))
        bob = client.get("/api/home")
        self.assertEqual(bob.status_code, 200, bob.text)
        for section in ("recent_documents", "recent_charts", "recent_insights"):
            self.assertEqual(bob.json()[section], [])
        self.assertEqual(bob.json()["counts"], {"documents": 0})
        self.assertEqual(client.get(path).status_code, 404)
        self.assertNotIn(document["id"], bob.text)
        print("NI-024 HTTP: first-use empty, create/save/current resume, exact owner lists, source outage and Bob isolation passed", flush=True)
