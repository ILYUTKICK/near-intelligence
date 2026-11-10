"""NI-062 session/JWT boundary audit at the HTTP layer (offline).

Runs the REAL NI-018 verification chain (synthetic local ES256 key, injected
JWKS fetcher — no provider, no network) against a live private route, and
proves the fail-closed matrix produces ONE generic 401 envelope with no
reason detail and no cacheability:

- missing/empty/malformed/garbage bearer values;
- expired token, future nbf, wrong issuer, wrong audience;
- HS256 and alg=none (rejected before any key lookup), signature tampering;
- every rejection identical in body shape (no oracle for enumerating valid
  subjects) and ``Cache-Control: no-store`` on every 401.

The success path (verified subject -> principal bootstrap -> owned data) is
covered on the disposable cluster by test_security_http_ownership.py.
"""

import time
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid1, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from near_api.auth import principal as principal_module
from near_api.auth.jwks import JWKSCache
from near_api.auth.verification import TokenVerifier
from near_api.auth_settings import AuthSettings
from near_api.main import app

ISSUER = "https://provider.synthetic.test/auth/v1"
JWKS_URL = "https://provider.synthetic.test/auth/v1/.well-known/jwks.json"
AUDIENCE = "authenticated"
SUBJECT = str(uuid4())
KID = "synthetic-key"


def settings(algorithm="ES256") -> AuthSettings:
    return AuthSettings(
        SUPABASE_JWT_ISSUER=ISSUER,
        SUPABASE_JWKS_URL=JWKS_URL,
        SUPABASE_JWT_AUDIENCE=AUDIENCE,
        SUPABASE_JWT_ALGORITHM=algorithm,
        AUTH_ALLOWED_REDIRECT_ORIGINS="http://localhost:3000",
        AUTH_COOKIE_SIGNING_SECRET="a" * 40,
        CSRF_SIGNING_SECRET="b" * 40,
    )


class SessionBoundaryTests(unittest.TestCase):
    """The generic 401 envelope is identical for every rejection reason."""

    @classmethod
    def setUpClass(cls):
        cls.private_key = ec.generate_private_key(ec.SECP256R1())
        jwk = jwt.algorithms.ECAlgorithm.to_jwk(cls.private_key.public_key(), as_dict=True)
        jwk.update({"kid": KID, "use": "sig"})
        fetcher_calls = []
        cls.fetch_count = 0

        def fetcher(url):
            fetcher_calls.append(url)
            cls.fetch_count += 1
            return {"keys": [jwk]}

        cls.fetcher_urls = fetcher_calls
        verifier = TokenVerifier(settings(), JWKSCache(JWKS_URL, fetcher=fetcher))
        cls.patcher = patch.object(principal_module, "_get_verifier",
                                   return_value=verifier)
        cls.patcher.start()
        # The runtime engine dependency is evaluated alongside identity; on
        # every case below verification fails first, so a sentinel stub is
        # never used. No database is configured in this offline suite.
        cls.engine_patcher = patch.object(principal_module, "_get_engine",
                                          return_value=object())
        cls.engine_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()
        cls.engine_patcher.stop()

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=True)

    def token(self, *, claims=None, headers=None, algorithm="ES256") -> str:
        now = int(time.time())
        payload = {"iss": ISSUER, "aud": AUDIENCE, "sub": SUBJECT,
                   "iat": now, "nbf": now - 1, "exp": now + 600}
        payload.update(claims or {})
        extra = dict(headers or {})
        extra.setdefault("kid", KID)
        return jwt.encode(payload, self.private_key, algorithm=algorithm,
                          headers=extra)

    def rejection(self, token: str | None):
        headers = {} if token is None else {"Authorization": f"Bearer {token}"}
        response = self.client.get("/api/me", headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        body = response.json()
        self.assertEqual(body["error"]["code"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(body["error"]["message"], "Authentication is required")
        self.assertNotIn("details", body["error"])
        return body["error"]

    @staticmethod
    def comparable(error: dict) -> dict:
        """The envelope minus the per-request id (identity, not semantics)."""
        return {key: value for key, value in error.items() if key != "request_id"}

    def test_missing_and_empty_and_garbage_bearers_fail_identically(self):
        baseline = self.rejection(None)
        for header in ("", "Bearer", "Bearer ", "Basic dXNlcjpwYXNz",
                       "not-a-jwt", "Bearer .", "Bearer a.b.c"):
            response = self.client.get("/api/me",
                                       headers={"Authorization": header} if header else {})
            self.assertEqual(response.status_code, 401, header)
            self.assertEqual(self.comparable(response.json()["error"]),
                             self.comparable(baseline))

    def test_expired_future_nbf_and_claim_mismatches_fail_identically(self):
        now = int(time.time())
        # The offline baseline is a rejection (an expired token); a VALID
        # token reaches the database and is covered by the cluster suites.
        baseline = self.rejection(self.token(claims={"exp": now - 10}))
        for claims in ({"exp": now - 10}, {"nbf": now + 3600},
                       {"iss": "https://evil.test/auth/v1"},
                       {"aud": "other-audience"},
                       {"sub": "not-a-uuid"}, {"sub": str(uuid4()).upper()},
                       {"sub": str(uuid1())}):
            self.assertEqual(self.comparable(self.rejection(self.token(claims=claims))),
                             self.comparable(baseline))

    def test_algorithm_confusion_and_tampering_fail_identically(self):
        now = int(time.time())
        payload = {"iss": ISSUER, "aud": AUDIENCE, "sub": SUBJECT,
                   "iat": now, "nbf": now - 1, "exp": now - 10}
        baseline = self.rejection(self.token(claims={"exp": now - 10}))
        # alg=none and HS256 never reach the JWKS cache (header check first).
        none_token = jwt.encode(payload, key=None, algorithm="none",
                                headers={"kid": KID})
        hs_token = jwt.encode(payload, key="symmetric-secret", algorithm="HS256",
                              headers={"kid": KID})
        for hostile in (none_token, hs_token):
            self.assertEqual(self.comparable(self.rejection(hostile)),
                             self.comparable(baseline))
        # A tampered signature of an otherwise valid ES256 token.
        good = self.token()
        tampered = good[:-6] + ("A" * 6)
        self.assertNotEqual(tampered, good)
        self.assertEqual(self.comparable(self.rejection(tampered)),
                         self.comparable(baseline))
        # Unknown kid: exactly one forced refresh, then fail closed.
        before = self.fetch_count
        unknown = self.token(headers={"kid": "stale-key"})
        self.assertEqual(self.comparable(self.rejection(unknown)),
                         self.comparable(baseline))
        self.assertEqual(self.fetch_count, before + 1)
        self.assertEqual(self.fetcher_urls[before], JWKS_URL)

    def test_rejections_carry_no_reason_detail_or_identity(self):
        error = self.rejection(self.token(claims={"exp": int(time.time()) - 10}))
        self.assertNotIn(str(SUBJECT), json_of(error))
        self.assertTrue(set(error.keys()) <=
                        {"code", "message", "request_id", "details", "retryable"})


def json_of(body) -> str:
    import json
    return json.dumps(body)


if __name__ == "__main__":
    unittest.main()
