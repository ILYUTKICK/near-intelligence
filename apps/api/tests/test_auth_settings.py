"""API provider-only configuration at the production web/API boundary."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from near_api.auth_settings import AuthSettingsError, get_auth_settings


PROVIDER_ENV = {
    "SUPABASE_JWT_ISSUER": "https://provider.synthetic.test/auth/v1",
    "SUPABASE_JWKS_URL": "https://provider.synthetic.test/auth/v1/.well-known/jwks.json",
    "SUPABASE_JWT_AUDIENCE": "authenticated",
    "SUPABASE_JWT_ALGORITHM": "ES256",
}


class APIAuthSettingsTests(TestCase):
    def setUp(self):
        # No developer .env or inherited shell variable may hide a missing
        # production variable. The API has no cookie/CSRF/redirect secrets.
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = patch("near_api.auth_settings.find_repo_root", return_value=Path(directory.name))
        root.start()
        self.addCleanup(root.stop)
        environment = patch.dict(os.environ, PROVIDER_ENV, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        get_auth_settings.cache_clear()
        self.addCleanup(get_auth_settings.cache_clear)

    def test_provider_only_environment_loads_without_web_gateway_secrets(self):
        settings = get_auth_settings()
        self.assertEqual(settings.model_dump(), PROVIDER_ENV)
        self.assertEqual(settings.SUPABASE_JWT_ISSUER, PROVIDER_ENV["SUPABASE_JWT_ISSUER"])
        self.assertIs(settings, get_auth_settings())

    def test_each_provider_variable_is_required(self):
        for key in PROVIDER_ENV:
            with self.subTest(variable=key), patch.dict(os.environ, clear=True):
                os.environ.update({name: value for name, value in PROVIDER_ENV.items() if name != key})
                get_auth_settings.cache_clear()
                with self.assertRaises(AuthSettingsError) as error:
                    get_auth_settings()
                self.assertIn(key, str(error.exception))

    def test_provider_urls_require_valid_https(self):
        for key in ("SUPABASE_JWT_ISSUER", "SUPABASE_JWKS_URL"):
            for value in ("http://provider.synthetic.test/auth/v1", "https://", "not-a-url"):
                with self.subTest(variable=key, value=value), patch.dict(os.environ, {key: value}):
                    get_auth_settings.cache_clear()
                    with self.assertRaises(AuthSettingsError):
                        get_auth_settings()

    def test_placeholders_and_empty_audience_fail_closed(self):
        cases = [
            ("SUPABASE_JWT_ISSUER", "https://REPLACE.synthetic.test/auth/v1"),
            ("SUPABASE_JWKS_URL", "https://REPLACE.synthetic.test/jwks.json"),
            ("SUPABASE_JWT_AUDIENCE", "REPLACE_AUDIENCE"),
            ("SUPABASE_JWT_AUDIENCE", "   "),
        ]
        for key, value in cases:
            with self.subTest(variable=key, value=value), patch.dict(os.environ, {key: value}):
                get_auth_settings.cache_clear()
                with self.assertRaises(AuthSettingsError):
                    get_auth_settings()

    def test_only_allowlisted_asymmetric_algorithms_load(self):
        for algorithm in ("HS256", "none", "RS512"):
            with self.subTest(algorithm=algorithm), patch.dict(os.environ, {"SUPABASE_JWT_ALGORITHM": algorithm}):
                get_auth_settings.cache_clear()
                with self.assertRaises(AuthSettingsError):
                    get_auth_settings()
        for algorithm in ("ES256", "RS256", "EdDSA"):
            with self.subTest(algorithm=algorithm), patch.dict(os.environ, {"SUPABASE_JWT_ALGORITHM": algorithm}):
                get_auth_settings.cache_clear()
                self.assertEqual(get_auth_settings().SUPABASE_JWT_ALGORITHM, algorithm)
