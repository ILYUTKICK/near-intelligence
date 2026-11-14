"""NI-090 adversarial configuration tests; no Docker daemon or network needed."""

from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("vps_env", Path(__file__).resolve().parents[1] / "env.py")
assert SPEC is not None and SPEC.loader is not None
env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(env)
TAG = "20261114T120000Z-0123456789abcdef"


def valid_values() -> dict[str, str]:
    values = env.parse_env((env.DIRECTORY / ".env.example").read_text())
    values["RELEASE_TAG"] = TAG
    for index, key in enumerate(env.DB_SECRETS):
        values[key] = str(index + 1) * 64
    values["AUTH_COOKIE_SIGNING_SECRET"] = "cookie_" + "a" * 60
    values["CSRF_SIGNING_SECRET"] = "csrf_" + "b" * 60
    values["NEXT_PUBLIC_SUPABASE_URL"] = "https://ni090-test.supabase.co"
    values["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_" + "a" * 32
    values["SUPABASE_JWT_ISSUER"] = "https://ni090-test.supabase.co/auth/v1"
    values["SUPABASE_JWKS_URL"] = "https://ni090-test.supabase.co/auth/v1/.well-known/jwks.json"
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    path.chmod(0o600)


def topology(values: dict[str, str]) -> dict:
    """Normalized fixture for negative trust-boundary mutations, not a YAML parser."""
    services = {}
    environments = env.service_environments(values)
    for name in ("db", "api", "web", "proxy", "migrate", "worker"):
        services[name] = {
            "environment": environments[name],
            "image": env.POSTGRES_IMAGE if name == "db" else env.CADDY_IMAGE if name == "proxy"
            else "near-intelligence-" + ("web" if name == "web" else "api") + ":" + TAG,
            "networks": {key: None for key in (["edge"] if name == "proxy" else ["edge", "backend"] if name == "web" else ["backend"])},
            "restart": "no" if name in {"migrate", "worker"} else "unless-stopped",
            "profiles": [name] if name in {"migrate", "worker"} else [],
            "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
            "volumes": [],
        }
        if name in {"api", "web", "migrate", "worker"}:
            services[name]["build"] = {"context": str(env.REPOSITORY), "dockerfile": "Dockerfile.web" if name == "web" else "Dockerfile.api"}
            services[name]["pull_policy"] = "never"
    services["api"]["command"] = env.API_COMMAND[:]
    services["migrate"]["command"] = env.MIGRATE_COMMAND[:]
    services["worker"]["command"] = env.WORKER_COMMAND[:]
    services["proxy"]["ports"] = [{"target": port, "published": str(port), "protocol": "tcp"} for port in (80, 443)]
    services["db"]["volumes"] = [
        {"type": "volume", "source": "near_db_data", "target": "/var/lib/postgresql"},
        {"type": "bind", "source": str(env.REPOSITORY / "scripts/db/010-roles.sql"), "target": "/docker-entrypoint-initdb.d/010-roles.sql", "read_only": True},
    ]
    services["api"]["volumes"] = [{"type": "volume", "source": "near_artifacts", "target": env.ARTIFACT_ROOT, "read_only": True}]
    services["worker"]["volumes"] = [{"type": "volume", "source": "near_artifacts", "target": env.ARTIFACT_ROOT}]
    services["proxy"]["volumes"] = [
        {"type": "bind", "source": str(env.DIRECTORY / "Caddyfile"), "target": "/etc/caddy/Caddyfile", "read_only": True},
        {"type": "volume", "source": "caddy_data", "target": "/data"},
        {"type": "volume", "source": "caddy_config", "target": "/config"},
    ]
    return {"services": services, "networks": {key: {"driver": "bridge"} for key in ("edge", "backend")},
            "volumes": {key: {} for key in ("near_db_data", "near_artifacts", "caddy_data", "caddy_config")}}


class EnvironmentTests(unittest.TestCase):
    def test_complete_configuration_accepted(self):
        env.validate_values(valid_values())

    def test_initialization_creates_distinct_secrets_with_exact_permissions_and_no_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.vps"
            env.init_env(path, TAG)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            body = path.read_bytes()
            values = env.parse_env(body.decode())
            self.assertEqual(values["RELEASE_TAG"], TAG)
            self.assertEqual(len({values[key] for key in (*env.DB_SECRETS, *env.SERVER_SECRETS)}), 6)
            for key in env.DB_SECRETS:
                self.assertRegex(values[key], r"^[a-f0-9]{64}$")
            self.assertIn("REPLACE_PROJECT", values["NEXT_PUBLIC_SUPABASE_URL"])
            self.assertIn("REPLACE_PUBLIC_KEY", values["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"])
            with self.assertRaises(env.ValidationError):
                env.init_env(path, TAG)
            self.assertEqual(path.read_bytes(), body)
            with self.assertRaisesRegex(env.ValidationError, "placeholder"):
                env.validate_env_file(path)

    def test_init_refuses_nonignored_path_or_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "secrets"
            target.write_text("original")
            link = Path(directory) / ".env.vps"
            link.symlink_to(target)
            for path in (target, link):
                with self.subTest(path=path.name), self.assertRaises(env.ValidationError):
                    env.init_env(path, TAG)
            self.assertEqual(target.read_text(), "original")

    def test_file_permissions_and_symlinks_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.vps"
            write_env(path, valid_values())
            self.assertEqual(env.validate_env_file(path), valid_values())
            path.chmod(0o644)
            with self.assertRaisesRegex(env.ValidationError, "permissions"):
                env.validate_env_file(path)
            path.chmod(0o600)
            link = Path(directory) / ".env.vps.link"
            link.symlink_to(path)
            with self.assertRaisesRegex(env.ValidationError, "symlink"):
                env.validate_env_file(link)

    def test_shell_syntax_unknown_keys_and_duplicates_rejected(self):
        body = "".join(f"{key}={value}\n" for key, value in valid_values().items())
        for append in ("APP_ENV=production\n", "UNEXPECTED_SECRET=secret\n", "APP_ENV=$(id)\n", "export APP_ENV=production\n"):
            with self.subTest(append=append), self.assertRaises(env.ValidationError):
                env.parse_env(body + append)
        for value in ("'quoted'", "a$HOME", "`id`", '"quoted"', "white space", "new\\line", "inline#comment"):
            with self.subTest(value=value), self.assertRaises(env.ValidationError):
                env.parse_env(body.replace("LOG_LEVEL=INFO", "LOG_LEVEL=" + value))

    def test_placeholder_and_origin_failures(self):
        cases = {
            "APP_ENV": "development", "APP_ORIGIN": "http://near-intelligence.me",
            "AUTH_ALLOWED_REDIRECT_ORIGINS": env.ORIGIN + "/",
            "SUPABASE_JWT_ISSUER": "https://other.supabase.co/auth/v1",
            "SUPABASE_JWKS_URL": "https://other.supabase.co/auth/v1/.well-known/jwks.json",
            "SUPABASE_JWT_ALGORITHM": "HS256", "SUPABASE_JWT_AUDIENCE": "other",
            "API_INTERNAL_URL": "http://localhost:8000", "ARTIFACT_ROOT": "/tmp/artifacts",
            "LOG_LEVEL": "DEBUG", "NEXT_PUBLIC_SUPABASE_URL": "https://REPLACE_PROJECT.supabase.co",
            "CADDY_IMAGE": "caddy:latest", "RELEASE_TAG": "local",
        }
        for key, value in cases.items():
            values = valid_values()
            values[key] = value
            with self.subTest(key=key), self.assertRaises(env.ValidationError):
                env.validate_values(values)

    def test_invalid_timestamp_and_secret_duplicates_rejected(self):
        for tag in ("20261314T120000Z-0123456789ab", "20261114T250000Z-0123456789ab"):
            with self.subTest(tag=tag), self.assertRaises(env.ValidationError):
                env.validate_release_tag(tag)
        values = valid_values()
        values["DB_RUNTIME_PASSWORD"] = values["DB_BOOTSTRAP_PASSWORD"]
        with self.assertRaisesRegex(env.ValidationError, "distinct"):
            env.validate_values(values)
        values = valid_values()
        values["CSRF_SIGNING_SECRET"] = values["DB_BOOTSTRAP_PASSWORD"]
        with self.assertRaisesRegex(env.ValidationError, "distinct"):
            env.validate_values(values)
        values = valid_values()
        values["DB_RUNTIME_PASSWORD"] = "password@with:unsafe/chars" * 3
        with self.assertRaises(env.ValidationError):
            env.validate_values(values)

    def test_collection_and_budgets_must_stay_disabled(self):
        for key in env.DISABLED_COLLECTION:
            values = valid_values()
            values[key] = "near-rpc" if key.endswith("ALLOWLIST") else "1"
            with self.subTest(key=key), self.assertRaises(env.ValidationError):
                env.validate_values(values)

    def test_browser_key_rejects_secret_prefix_and_encoded_service_role(self):
        def jwt(role):
            payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
            return "eyJhbGciOiJIUzI1NiJ9." + payload + ".signature"
        env.validate_publishable_key(jwt("anon"))
        for key in (jwt("service_role"), jwt("authenticated"), "sb_secret_" + "a" * 64,
                    "service_role_" + "a" * 64, "arbitrary_" + "a" * 32):
            with self.subTest(format=key[:8]), self.assertRaises(env.ValidationError):
                env.validate_publishable_key(key)

    def test_cli_redacts_values_on_failure(self):
        values = valid_values()
        secret = values["DB_BOOTSTRAP_PASSWORD"]
        values["APP_ORIGIN"] = "https://" + secret + ".invalid"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.vps"
            write_env(path, values)
            output, error = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                status = env.main(["validate", "--env-file", str(path)])
            self.assertEqual(status, 2)
            self.assertNotIn(secret, output.getvalue() + error.getvalue())
            self.assertIn("APP_ORIGIN", error.getvalue())

    def test_shell_values_cannot_override_explicit_env_file(self):
        values = valid_values()
        with patch.dict(os.environ, {"APP_ORIGIN": "https://wrong.invalid", "DB_RUNTIME_PASSWORD": "secret",
                                     "COMPOSE_FILE": "override.yml", "COMPOSE_PROFILES": "refresh"}):
            isolated = env.compose_environment(values)
        for key in (*values, "COMPOSE_FILE", "COMPOSE_PROFILES"):
            self.assertNotIn(key, isolated)
        self.assertEqual(isolated["COMPOSE_DISABLE_ENV_FILE"], "true")


class TopologyTests(unittest.TestCase):
    def setUp(self):
        self.values = valid_values()
        self.config = topology(self.values)

    def refused(self, config):
        with self.assertRaises(env.ValidationError):
            env.validate_compose(config, self.values)

    def test_reviewed_contract_accepted(self):
        env.validate_compose(self.config, self.values)

    def test_every_service_environment_is_an_exact_allowlist(self):
        for service in ("web", "api", "worker", "migrate", "proxy"):
            for variable in env.DB_SECRETS:
                config = copy.deepcopy(self.config)
                config["services"][service]["environment"][variable] = self.values[variable]
                with self.subTest(service=service, variable=variable):
                    self.refused(config)
        config = copy.deepcopy(self.config)
        config["services"]["web"]["environment"]["DATABASE_URL"] = self.config["services"]["api"]["environment"]["DATABASE_URL"]
        self.refused(config)
        config = copy.deepcopy(self.config)
        config["services"]["api"]["environment"]["OPERATOR_DATABASE_URL"] = self.config["services"]["worker"]["environment"]["OPERATOR_DATABASE_URL"]
        self.refused(config)

    def test_whole_environment_injection_and_public_internal_ports_rejected(self):
        for name in self.config["services"]:
            config = copy.deepcopy(self.config)
            config["services"][name]["env_file"] = [".env.vps"]
            with self.subTest(service=name, failure="env_file"):
                self.refused(config)
            if name != "proxy":
                config = copy.deepcopy(self.config)
                config["services"][name]["ports"] = [{"target": 5432, "published": "5432"}]
                with self.subTest(service=name, failure="port"):
                    self.refused(config)
        config = copy.deepcopy(self.config)
        config["services"]["proxy"]["ports"].append({"target": 2019, "published": "2019"})
        self.refused(config)

    def test_proxy_cannot_join_database_network_and_artifacts_are_durable(self):
        config = copy.deepcopy(self.config)
        config["services"]["proxy"]["networks"]["backend"] = None
        self.refused(config)
        for service in ("db", "api", "worker", "proxy"):
            config = copy.deepcopy(self.config)
            config["services"][service]["volumes"] = []
            with self.subTest(service=service):
                self.refused(config)

    def test_no_refresh_unbounded_worker_or_automatic_migration(self):
        config = copy.deepcopy(self.config)
        config["services"]["refresh"] = copy.deepcopy(config["services"]["worker"])
        self.refused(config)
        for service in ("worker", "migrate"):
            config = copy.deepcopy(self.config)
            config["services"][service]["profiles"] = []
            with self.subTest(service=service):
                self.refused(config)
        config = copy.deepcopy(self.config)
        config["services"]["worker"]["command"][2] = env.WORKER_COMMAND[2].replace("--max-jobs 10", "--max-jobs 0")
        self.refused(config)
        config = copy.deepcopy(self.config)
        config["services"]["api"]["command"] = env.MIGRATE_COMMAND
        self.refused(config)

    def test_image_build_and_restart_drift_refused(self):
        for name in ("api", "web", "worker", "migrate"):
            config = copy.deepcopy(self.config)
            config["services"][name]["image"] = "near-intelligence-api:local"
            with self.subTest(service=name, failure="image"):
                self.refused(config)
            config = copy.deepcopy(self.config)
            config["services"][name]["build"]["args"] = {"SECRET": "do-not-bake"}
            with self.subTest(service=name, failure="build"):
                self.refused(config)
        config = copy.deepcopy(self.config)
        config["services"]["worker"]["restart"] = "always"
        self.refused(config)

    def test_static_source_has_no_whole_env_file_and_only_web_reverse_proxy(self):
        compose = (env.DIRECTORY / "compose.yaml").read_text()
        self.assertNotIn("env_file:", compose)
        caddy = (env.DIRECTORY / "Caddyfile").read_text()
        active_lines = [line.strip() for line in caddy.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(active_lines[0], "near-intelligence.me {")
        self.assertEqual([line for line in active_lines if line.startswith("reverse_proxy")], ["reverse_proxy web:3000"])
        self.assertFalse(any("cache" in line for line in active_lines))

    def test_render_failure_never_echoes_docker_secrets(self):
        secret = self.values["DB_BOOTSTRAP_PASSWORD"]
        failure = type("Result", (), {"returncode": 1, "stdout": secret, "stderr": secret})()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.vps"
            write_env(path, self.values)
            output, error = io.StringIO(), io.StringIO()
            with patch.object(env.subprocess, "run", return_value=failure), redirect_stdout(output), redirect_stderr(error):
                status = env.main(["check-compose", "--env-file", str(path)])
            self.assertEqual(status, 2)
            self.assertNotIn(secret, output.getvalue() + error.getvalue())


if __name__ == "__main__":
    unittest.main()
