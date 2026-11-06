"""NI-018 JWT verification matrix. Synthetic local keys only; no network I/O.

Every external fetch is an injected recording fetcher, so no committed test
contacts a real provider. The real-JWKS path is a manual operator smoke and is
deliberately not a CI step.
"""

import json
import time
from datetime import UTC, datetime, timedelta
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID, uuid1, uuid4, uuid5

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from near_api.auth import principal
from near_api.auth.jwks import JWKSCache, JWKSUnavailable, MAX_JWKS_KEYS, UnknownKeyID
from near_api.auth.principal import Principal, UserDisabled, get_principal
from near_api.auth.verification import TokenInvalid, TokenVerifier, VerifiedToken
from near_api.auth_settings import AuthSettings
from near_api.contracts import install_contracts
from near_api.schemas.common import ErrorResponse

ISSUER = "https://provider.synthetic.test/auth/v1"
JWKS_URL = "https://provider.synthetic.test/auth/v1/.well-known/jwks.json"
AUDIENCE = "authenticated"
SUBJECT = str(uuid4())


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


def es_keypair():
    private = ec.generate_private_key(ec.SECP256R1())
    return private, jwt.algorithms.ECAlgorithm.to_jwk(private.public_key(), as_dict=True)


def rsa_keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)


class RecordingFetcher:
    """Injected JWKS fetcher; records every requested URL."""

    def __init__(self, document):
        self.document = document
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if isinstance(self.document, Exception):
            raise self.document
        return self.document

    @property
    def fetch_count(self):
        return len(self.urls)


class Clock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value


def signed_jwk(kid, jwk):
    entry = dict(jwk)
    entry.update({"kid": kid, "use": "sig"})
    return entry


def base_claims(**changes):
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": SUBJECT,
        "iat": now,
        "nbf": now - 1,
        "exp": now + 600,
    }
    payload.update(changes)
    return payload


def make_token(private, *, kid="synthetic-key", algorithm="ES256", claims=None, headers=None):
    payload = base_claims()
    payload.update(claims or {})
    extra_headers = dict(headers or {})
    if kid is not None:
        extra_headers.setdefault("kid", kid)
    return jwt.encode(payload, private, algorithm=algorithm, headers=extra_headers)


def reheader(token, **changes):
    """Return the token with modified header fields and unchanged signature."""
    header, payload, signature = token.split(".")
    decoded = json.loads(jwt.utils.base64url_decode(header.encode()))
    decoded.update(changes)
    encoded = jwt.utils.base64url_encode(json.dumps(decoded, separators=(",", ":")).encode())
    return b".".join([encoded, payload.encode(), signature.encode()]).decode()


class JWKSCacheTests(TestCase):
    def setUp(self):
        self.private, self.jwk = es_keypair()
        self.fetcher = RecordingFetcher({"keys": [signed_jwk("synthetic-key", self.jwk)]})
        self.clock = Clock()
        self.cache = JWKSCache(JWKS_URL, ttl_seconds=600.0, fetcher=self.fetcher, clock=self.clock)

    def test_known_key_is_cached_within_ttl(self):
        first = self.cache.get_key("synthetic-key")
        second = self.cache.get_key("synthetic-key")
        self.assertIs(first, second)
        self.assertEqual(self.fetcher.fetch_count, 1)

    def test_expired_entry_forces_refresh(self):
        self.cache.get_key("synthetic-key")
        self.clock.value += 601.0
        self.cache.get_key("synthetic-key")
        self.assertEqual(self.fetcher.fetch_count, 2)

    def test_unknown_kid_refreshes_exactly_once_per_attempt(self):
        with self.assertRaises(UnknownKeyID):
            self.cache.get_key("rotated-key")
        self.assertEqual(self.fetcher.fetch_count, 1)
        self.assertEqual(self.fetcher.urls, [JWKS_URL])
        with self.assertRaises(UnknownKeyID):
            self.cache.get_key("rotated-key")
        self.assertEqual(self.fetcher.fetch_count, 2)
        # A known key still resolves from cache without any extra fetch.
        self.cache.get_key("synthetic-key")
        self.assertEqual(self.fetcher.fetch_count, 2)

    def test_unusable_documents_fail_closed(self):
        cases = {
            "empty": {"keys": []},
            "missing_keys": {},
            "keys_not_list": {"keys": "synthetic"},
            "entry_not_object": {"keys": ["synthetic"]},
            "entry_without_kid": {"keys": [dict(self.jwk)]},
            "symmetric_key_type": {"keys": [{"kid": "k", "kty": "oct", "k": "AAA"}]},
            "not_a_signing_key": {"keys": [signed_jwk("k", self.jwk) | {"use": "enc"}]},
            "duplicate_kid": {"keys": [signed_jwk("k", self.jwk), signed_jwk("k", self.jwk)]},
            "too_many_keys": {"keys": [signed_jwk(f"k{i}", self.jwk)
                                       for i in range(MAX_JWKS_KEYS + 1)]},
        }
        for name, broken in cases.items():
            with self.subTest(document=name):
                fetcher = RecordingFetcher(broken)
                cache = JWKSCache(JWKS_URL, fetcher=fetcher, clock=self.clock)
                with self.assertRaises(JWKSUnavailable):
                    cache.get_key("synthetic-key")
                self.assertEqual(fetcher.fetch_count, 1)
        with self.subTest(document="not_an_object"):
            fetcher = RecordingFetcher(["keys"])
            cache = JWKSCache(JWKS_URL, fetcher=fetcher, clock=self.clock)
            with self.assertRaises(JWKSUnavailable):
                cache.get_key("synthetic-key")

    def test_fetch_failures_fail_closed(self):
        for failure in (RuntimeError("connection refused"),
                        JWKSUnavailable("size bound exceeded")):
            with self.subTest(failure=type(failure).__name__):
                fetcher = RecordingFetcher(failure)
                cache = JWKSCache(JWKS_URL, fetcher=fetcher, clock=self.clock)
                with self.assertRaises(JWKSUnavailable):
                    cache.get_key("synthetic-key")

    def test_cache_requires_https_url(self):
        with self.assertRaises(JWKSUnavailable):
            JWKSCache("http://provider.synthetic.test/jwks.json", fetcher=self.fetcher)


class TokenVerifierTests(TestCase):
    def setUp(self):
        self.private, self.jwk = es_keypair()
        self.fetcher = RecordingFetcher({"keys": [signed_jwk("synthetic-key", self.jwk)]})
        self.cache = JWKSCache(JWKS_URL, fetcher=self.fetcher, clock=Clock())
        self.verifier = TokenVerifier(settings("ES256"), self.cache)

    def test_valid_es256_token_verifies(self):
        verified = self.verifier.verify(make_token(self.private))
        self.assertIsInstance(verified, VerifiedToken)
        self.assertEqual(verified.subject, UUID(SUBJECT))
        self.assertGreater(verified.expires_at, datetime.now(UTC))
        self.assertIsNotNone(verified.issued_at)

    def test_valid_rs256_token_when_configured(self):
        private, jwk = rsa_keypair()
        fetcher = RecordingFetcher({"keys": [signed_jwk("synthetic-key", jwk)]})
        verifier = TokenVerifier(settings("RS256"), JWKSCache(JWKS_URL, fetcher=fetcher, clock=Clock()))
        self.assertEqual(verifier.verify(make_token(private, algorithm="RS256")).subject, UUID(SUBJECT))

    def test_rejection_matrix(self):
        other_private, _ = es_keypair()
        cases = {
            "forged_signature": make_token(other_private),
            "wrong_issuer": make_token(self.private, claims={"iss": "https://evil.synthetic.test/auth/v1"}),
            "wrong_audience": make_token(self.private, claims={"aud": "service-role"}),
            "audience_list": make_token(self.private, claims={"aud": [AUDIENCE, "other"]}),
            "expired": make_token(self.private, claims={"exp": int(time.time()) - 3600}),
            "future_nbf": make_token(self.private, claims={"nbf": int(time.time()) + 3600}),
            "missing_exp": jwt.encode({k: v for k, v in base_claims().items() if k != "exp"},
                                      self.private, algorithm="ES256", headers={"kid": "synthetic-key"}),
            "missing_sub": jwt.encode({k: v for k, v in base_claims().items() if k != "sub"},
                                      self.private, algorithm="ES256", headers={"kid": "synthetic-key"}),
            "hs256": make_token("synthetic-shared-secret-that-is-definitely-not-a-signing-key", kid="hmac-key", algorithm="HS256"),
            "alg_none": make_token(None, algorithm="none"),
            "unconfigured_asymmetric": reheader(make_token(self.private), alg="RS512"),
            "sub_not_uuid": make_token(self.private, claims={"sub": "admin"}),
            "sub_numeric": make_token(self.private, claims={"sub": 12345}),
            "sub_uuid_v1": make_token(self.private, claims={"sub": str(uuid1())}),
            "sub_uuid_v5": make_token(self.private, claims={"sub": str(uuid5(uuid4(), "synthetic"))}),
            "sub_uppercase": make_token(self.private, claims={"sub": SUBJECT.upper()}),
            "kid_missing": make_token(self.private, kid=None),
            "kid_path_like": make_token(self.private, kid="../evil"),
            "kid_whitespace": make_token(self.private, kid="synthetic key"),
            "garbage": "not-a-jwt",
            "empty_token": "",
            "unsigned_segments": "AAA.BBB.CCC",
        }
        for name, token in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(TokenInvalid):
                    self.verifier.verify(token)

    def test_hs256_and_none_never_touch_jwks(self):
        for algorithm, key in (("HS256", "synthetic-shared-secret-that-is-definitely-not-a-signing-key"), ("none", None)):
            with self.subTest(algorithm=algorithm):
                with self.assertRaises(TokenInvalid):
                    self.verifier.verify(make_token(key, algorithm=algorithm))
                self.assertEqual(self.fetcher.fetch_count, 0)

    def test_unknown_kid_single_retry_then_fail_closed(self):
        token = make_token(self.private, kid="rotated-key")
        with self.assertRaises(TokenInvalid):
            self.verifier.verify(token)
        self.assertEqual(self.fetcher.fetch_count, 1)
        with self.assertRaises(TokenInvalid):
            self.verifier.verify(token)
        self.assertEqual(self.fetcher.fetch_count, 2)

    def test_jku_and_x5u_headers_are_ignored(self):
        evil_urls = ("https://evil.synthetic.test/jwks.json",
                     "https://evil.synthetic.test/x5u.pem")
        for kid in ("rotated-key", "synthetic-key"):
            with self.subTest(kid=kid):
                token = make_token(self.private, kid=kid, headers={
                    "jku": evil_urls[0], "x5u": evil_urls[1]})
                if kid == "rotated-key":
                    with self.assertRaises(TokenInvalid):
                        self.verifier.verify(token)
                else:
                    self.assertEqual(self.verifier.verify(token).subject, UUID(SUBJECT))
                self.assertNotIn(evil_urls[0], self.fetcher.urls)
                self.assertNotIn(evil_urls[1], self.fetcher.urls)
                self.assertTrue(all(url == JWKS_URL for url in self.fetcher.urls))

    def test_jwks_outage_fails_closed(self):
        failing = RecordingFetcher(RuntimeError("provider unreachable"))
        verifier = TokenVerifier(settings("ES256"),
                                 JWKSCache(JWKS_URL, fetcher=failing, clock=Clock()))
        with self.assertRaises(TokenInvalid):
            verifier.verify(make_token(self.private))
        self.assertEqual(failing.fetch_count, 1)


class StubVerifier:
    def __init__(self, result):
        self.result = result
        self.tokens = []

    def verify(self, token):
        self.tokens.append(token)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def verified(subject=UUID(SUBJECT)):
    return VerifiedToken(subject=subject, expires_at=datetime.now(UTC) + timedelta(minutes=5),
                         issued_at=datetime.now(UTC))


class PrincipalDependencyTests(TestCase):
    def setUp(self):
        self.application = FastAPI()
        install_contracts(self.application)

        @self.application.get("/__synthetic__/me")
        def synthetic_me(current: Principal = Depends(get_principal)):
            return {"id": str(current.id), "display_name": current.display_name,
                    "display_timezone": current.display_timezone}

        @self.application.post("/__synthetic__/me")
        def synthetic_post(payload: dict, current: Principal = Depends(get_principal)):
            return {"id": str(current.id)}

        self.client = TestClient(self.application, raise_server_exceptions=False)
        self.subject = UUID(SUBJECT)
        self.verifier = StubVerifier(verified(self.subject))
        self.engine = object()
        self.bootstraps = []

        def fake_bootstrap(engine, verified_token):
            self.bootstraps.append((engine, verified_token))
            return Principal(id=verified_token.subject, display_name="Synthetic Alice",
                             display_timezone="UTC")

        for item in (patch.object(principal, "_get_verifier", return_value=self.verifier),
                     patch.object(principal, "_get_engine", return_value=self.engine),
                     patch.object(principal, "bootstrap_principal", side_effect=fake_bootstrap)):
            item.start()
            self.addCleanup(item.stop)

    def test_missing_or_malformed_authorization_is_401(self):
        for header in (None, "", "Bearer", "Bearer   ", "Basic c3ludGg6c2VjcmV0", "Token abc"):
            with self.subTest(header=header):
                headers = {} if header is None else {"Authorization": header}
                response = self.client.get("/__synthetic__/me", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
                ErrorResponse.model_validate(response.json())
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(self.bootstraps, [])
                self.assertEqual(self.verifier.tokens, [])

    def test_invalid_token_is_generic_401_without_detail_leak(self):
        self.verifier.result = TokenInvalid("synthetic-private-verification-reason")
        response = self.client.get("/__synthetic__/me", headers={"Authorization": "Bearer aaa.bbb.ccc"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        ErrorResponse.model_validate(response.json())
        self.assertNotIn("synthetic-private-verification-reason", response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.bootstraps, [])

    def test_disabled_user_is_403_fail_closed(self):
        def disabled(engine, verified_token):
            raise UserDisabled("synthetic-disabled")

        with patch.object(principal, "bootstrap_principal", side_effect=disabled):
            response = self.client.get("/__synthetic__/me",
                                       headers={"Authorization": "Bearer aaa.bbb.ccc"})
        self.assertEqual(response.status_code, 403)
        ErrorResponse.model_validate(response.json())
        self.assertNotIn("synthetic-disabled", response.text)

    def test_valid_token_returns_principal_derived_from_verified_subject(self):
        token = "aaa.bbb.ccc"
        response = self.client.get("/__synthetic__/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": SUBJECT, "display_name": "Synthetic Alice",
                                           "display_timezone": "UTC"})
        self.assertEqual(self.verifier.tokens, [token])
        engine, verified_token = self.bootstraps[0]
        self.assertIs(engine, self.engine)
        self.assertEqual(verified_token.subject, self.subject)

    def test_request_body_cannot_override_identity(self):
        other = str(uuid4())
        response = self.client.post("/__synthetic__/me",
                                    headers={"Authorization": "Bearer aaa.bbb.ccc"},
                                    json={"user_id": other, "owner_id": other, "sub": other})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], SUBJECT)
        self.assertEqual(self.bootstraps[0][1].subject, self.subject)


if __name__ == "__main__":
    TestCase.main()
