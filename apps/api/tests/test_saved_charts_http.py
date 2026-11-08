"""NI-035 HTTP E2E: real gateway cookies/CSRF/JWT, API and PostgreSQL.

Only the provider JWKS transport is replaced by an ephemeral synthetic key;
JWT signature/issuer/audience verification, principal bootstrap and RLS run.
Use run-db-tests.py --saved-charts-http after pnpm build. No external auth service.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import ec
import httpx
import jwt
import uvicorn

from near_api.auth import principal
from near_api.auth.jwks import JWKSCache
from near_api.auth.verification import TokenVerifier
from near_api.charts.registry import chart_by_chart_id
from near_api.main import app
import test_delivery_apis as fixtures


def port():
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use run-db-tests.py --saved-charts-http")
class SavedChartsHTTPE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.DeliveryDatabaseTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixtures.DeliveryDatabaseTests.tearDownClass.__func__(cls)

    def setUp(self):
        fixtures.DeliveryDatabaseTests.setUp(self)

    def test_cookie_gateway_save_reopen_and_two_users(self):
        web = self.repo / "apps/web"
        self.assertTrue((web / ".next/BUILD_ID").exists(), "Build the frozen web app first")
        api_url, web_url = f"http://127.0.0.1:{port()}", f"http://127.0.0.1:{port()}"
        secret = secrets.token_urlsafe(32)
        issuer = "https://synthetic.supabase.co/auth/v1"
        environment = {**os.environ, "APP_ENV": "test", "APP_ORIGIN": web_url,
            "API_INTERNAL_URL": api_url, "NEXT_TELEMETRY_DISABLED": "1",
            "NEXT_PUBLIC_SUPABASE_URL": "https://synthetic.supabase.co",
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_synthetic_0123456789",
            "SUPABASE_JWT_ISSUER": issuer, "SUPABASE_JWKS_URL": issuer + "/.well-known/jwks.json",
            "SUPABASE_JWT_AUDIENCE": "authenticated", "SUPABASE_JWT_ALGORITHM": "ES256",
            "AUTH_ALLOWED_REDIRECT_ORIGINS": web_url, "AUTH_COOKIE_SIGNING_SECRET": secret,
            "CSRF_SIGNING_SECRET": secrets.token_urlsafe(32)}
        key = ec.generate_private_key(ec.SECP256R1())
        public = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
        public.update(kid="ni035-synthetic", alg="ES256", use="sig")
        from types import SimpleNamespace
        settings = SimpleNamespace(SUPABASE_JWT_ISSUER=issuer,
                                   SUPABASE_JWT_AUDIENCE="authenticated", SUPABASE_JWT_ALGORITHM="ES256")
        verifier = TokenVerifier(settings, JWKSCache(environment["SUPABASE_JWKS_URL"],
                                                    fetcher=lambda _: {"keys": [public]}))
        self.enterContext(patch.object(principal, "_get_verifier", return_value=verifier))
        self.enterContext(patch.object(principal, "_get_engine", return_value=self.runtime))
        users = {name: uuid4() for name in ("alice", "bob")}
        def session_cookie(name):
            token = jwt.encode({"sub": str(users[name]), "iss": issuer, "aud": "authenticated",
                                "exp": int(time.time()) + 600}, key, algorithm="ES256",
                               headers={"kid": "ni035-synthetic"})
            payload = {"accessToken": token, "refreshToken": "synthetic-not-used",
                       "expiresAt": int(time.time() * 1000) + 600_000}
            body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
            signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
            return f"{body}.{signature}"
        dataset = fixtures.DeliveryDatabaseTests.stage_fixture(
            self, f"ni035-http.{uuid4().hex[:12]}",
            [fixtures.observation(fixtures.METRIC_VOLUME, dt.date(2026, 1, 1), value="12.123456789012345678901234",
                                  dimensions={"source": "SRC-LLAMA"})], [fixtures.METRIC_VOLUME],
            window=("2026-01-01", "2026-01-02"))
        if os.environ.get("NI_BROWSER_HANDOFF") == "1":
            from fastapi.responses import RedirectResponse
            @app.get("/__ni035_synthetic_session/{name}", include_in_schema=False)
            def browser_session(name: str):
                response = RedirectResponse(web_url + "/charts/intents-volume?version=1&start=2026-01-01&end=2026-01-02&filters=%7B%22source%22%3A%22SRC-LLAMA%22%7D")
                response.set_cookie("ni_session", session_cookie(name), httponly=True, samesite="lax")
                return response
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=int(api_url.rsplit(":", 1)[1]), log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        def stop_api():
            server.should_exit = True; thread.join(timeout=10)
        self.addCleanup(stop_api)
        deadline = time.monotonic() + 20
        while not server.started and time.monotonic() < deadline: time.sleep(0.05)
        self.assertTrue(server.started)
        log = self.enterContext((self.directory / "web.log").open("wb"))
        process = subprocess.Popen([shutil.which("node"), str(web / "node_modules/next/dist/bin/next"),
                                    "start", "--hostname", "127.0.0.1", "--port", web_url.rsplit(":", 1)[1]],
                                   cwd=web, env=environment, stdout=log, stderr=subprocess.STDOUT)
        def stop_web():
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        self.addCleanup(stop_web)
        client = self.enterContext(httpx.Client(base_url=web_url, timeout=20, trust_env=False))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if client.get("/health").status_code == 200: break
            except httpx.HTTPError: pass
            time.sleep(0.1)
        self.assertIsNone(process.poll())
        client.cookies.set("ni_session", session_cookie("alice"))
        token = client.get("/api/auth/csrf").json()["token"]
        headers = {"Origin": web_url, "x-csrf-token": token, "Idempotency-Key": str(uuid4())}
        body = {"chart_definition_version_id": str(chart_by_chart_id("intents-volume").id),
                "dataset_version_id": str(dataset.dataset_version_id), "mode": "live", "label": "Synthetic HTTP E2E",
                "selection": {"start": "2026-01-01", "end": "2026-01-02", "frequency": "day", "filters": {"source": "SRC-LLAMA"}}}
        response = client.post("/api/saved-charts", json=body, headers=headers)
        self.assertEqual(response.status_code, 201, response.text)
        saved = response.json()
        retry = client.post("/api/saved-charts", json=body, headers=headers)
        self.assertEqual(retry.json(), saved)
        path = "/api/saved-charts/" + saved["id"]
        self.assertEqual(client.get(path).json()["saved_chart"]["selection"], body["selection"])
        self.assertEqual(client.get("/workspace/saved-charts/" + saved["id"]).status_code, 200)
        self.assertEqual(client.get(path).headers["cache-control"], "no-store")
        client.cookies.set("ni_session", session_cookie("bob"))
        self.assertEqual(client.get("/api/saved-charts").json()["items"], [])
        self.assertEqual(client.get(path).status_code, 404)
        self.assertEqual(client.patch(path, json={"label": "Stolen"}, headers=headers).status_code, 404)
        self.assertEqual(client.delete(path, headers=headers).status_code, 404)
        if os.environ.get("NI_BROWSER_HANDOFF") == "1":
            info = self.repo / ".local/ni035-browser.json"
            marker = self.repo / ".local/ni035-browser.done"
            marker.unlink(missing_ok=True)
            info.write_text(json.dumps({"web": web_url, "alice": api_url + "/__ni035_synthetic_session/alice",
                                        "bob": api_url + "/__ni035_synthetic_session/bob", "saved_id": saved["id"]}))
            deadline = time.monotonic() + 240
            while not marker.exists() and time.monotonic() < deadline: time.sleep(0.2)
            self.assertTrue(marker.exists(), "Browser handoff did not complete")
        print("NI-035 real HTTP E2E: cookie/CSRF/ES256 JWT/bootstrap/RLS, save/retry/reopen, Bob denial passed", flush=True)
