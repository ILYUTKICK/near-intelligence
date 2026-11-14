#!/usr/bin/env python3
"""NI-090 local-only production environment and resolved-topology checks.

Python standard library only. Never source the env file or print resolved
Compose configuration: it contains role credentials. No provider is contacted.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit

DIRECTORY = Path(__file__).resolve().parent
REPOSITORY = DIRECTORY.parents[1]
ORIGIN = "https://near-intelligence.me"
ARTIFACT_ROOT = "/var/lib/near-intelligence/artifacts"
CADDY_IMAGE = "caddy:2.11.9-alpine@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0"
POSTGRES_IMAGE = "postgres:18.6-bookworm@sha256:f1ea2a1a4fb7b68d4836be1fdcb8a6466a89b072158bf9d97663600538c294c5"
DB_SECRETS = (
    "DB_BOOTSTRAP_PASSWORD", "DB_RUNTIME_PASSWORD",
    "DB_MIGRATION_PASSWORD", "DB_OPERATOR_PASSWORD",
)
SERVER_SECRETS = ("AUTH_COOKIE_SIGNING_SECRET", "CSRF_SIGNING_SECRET")
JWT_NAMES = (
    "SUPABASE_JWT_ISSUER", "SUPABASE_JWKS_URL",
    "SUPABASE_JWT_AUDIENCE", "SUPABASE_JWT_ALGORITHM",
)
DISABLED_COLLECTION = {
    "INGESTION_ENABLED": "false",
    "INGESTION_SOURCE_ALLOWLIST": "",
    "BIGQUERY_MAX_BYTES_BILLED": "0",
    "PROVIDER_REQUESTS_PER_MINUTE": "0",
    "PROVIDER_MAX_DAILY_REQUESTS": "0",
}
KEYS = frozenset((
    "RELEASE_TAG", "CADDY_IMAGE", "APP_ENV", "APP_ORIGIN", "API_INTERNAL_URL",
    *DB_SECRETS, "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
    *JWT_NAMES, "AUTH_ALLOWED_REDIRECT_ORIGINS", *SERVER_SECRETS,
    "ARTIFACT_ROOT", "LOG_LEVEL", *DISABLED_COLLECTION,
))
RELEASE_PATTERN = re.compile(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12,64}\Z")


class ValidationError(ValueError):
    """Safe diagnostic: variable/contract names only, never their values."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def parse_env(text: str) -> dict[str, str]:
    """A deliberately small dotenv subset, with no expansion or shell syntax."""
    values: dict[str, str] = {}
    require(len(text.encode("utf-8")) <= 65536, "Environment file is too large.")
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([^\s\x00-\x20\x7f]*)", line)
        require(match is not None, f"Environment line {number} must be plain KEY=value.")
        assert match is not None
        key, value = match.groups()
        require(key in KEYS, f"Environment line {number} has an unsupported variable.")
        require(key not in values, f"{key} is duplicated.")
        require(not any(char in value for char in "'$`\"\\#"),
                f"{key} must not contain quoting, interpolation or shell syntax.")
        values[key] = value
    require(set(values) == KEYS, "Environment variables are missing; use the VPS template.")
    return values


def validate_release_tag(value: str) -> None:
    require(bool(RELEASE_PATTERN.fullmatch(value)),
            "RELEASE_TAG must be UTC timestamp-source SHA256, with 12..64 lowercase hash characters.")
    try:
        datetime.strptime(value.split("-", 1)[0], "%Y%m%dT%H%M%SZ")
    except ValueError:
        raise ValidationError("RELEASE_TAG has an invalid UTC timestamp.") from None


def validate_publishable_key(value: str) -> None:
    require(len(value) >= 20 and "service_role" not in value.lower()
            and not value.lower().startswith("sb_secret_"),
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY must be browser-safe.")
    if re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]{20,}", value):
        return
    # Older Supabase anon JWTs are accepted only after inspecting the role;
    # this does not authenticate the token or replace provider verification.
    try:
        pieces = value.split(".")
        require(len(pieces) == 3, "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY has an unsupported format.")
        payload = json.loads(base64.urlsafe_b64decode(pieces[1] + "=" * (-len(pieces[1]) % 4)))
        require(isinstance(payload, dict) and payload.get("role") == "anon",
                "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY must have the anon role.")
    except (ValueError, UnicodeError, TypeError):
        raise ValidationError("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY is not a browser-safe key.") from None


def validate_values(values: dict[str, str]) -> None:
    require(set(values) == KEYS, "Environment variable names do not match the VPS template.")
    for key, value in values.items():
        require(not re.search(r"REPLACE|PLACEHOLDER|CHANGEME|YOUR[_-]", value, re.I),
                f"{key} still contains a placeholder.")
    validate_release_tag(values["RELEASE_TAG"])
    require(values["CADDY_IMAGE"] == CADDY_IMAGE, "CADDY_IMAGE does not match the verified digest pin.")
    require(values["APP_ENV"] == "production", "APP_ENV must be production.")
    require(values["APP_ORIGIN"] == ORIGIN, "APP_ORIGIN must match the final HTTPS origin exactly.")
    require(values["AUTH_ALLOWED_REDIRECT_ORIGINS"] == ORIGIN,
            "AUTH_ALLOWED_REDIRECT_ORIGINS must match the final HTTPS origin exactly.")
    require(values["API_INTERNAL_URL"] == "http://api:8000", "API_INTERNAL_URL must use the private API service.")
    require(values["ARTIFACT_ROOT"] == ARTIFACT_ROOT, "ARTIFACT_ROOT must match the durable volume mount.")
    require(values["LOG_LEVEL"] in {"INFO", "WARNING", "ERROR"}, "LOG_LEVEL must be INFO, WARNING or ERROR.")
    for key in DB_SECRETS:
        require(bool(re.fullmatch(r"[a-f0-9]{64}", values[key])),
                f"{key} must be 32 bytes encoded as 64 lowercase hex characters for safe DSNs.")
    for key in SERVER_SECRETS:
        require(bool(re.fullmatch(r"[A-Za-z0-9_-]{43,}", values[key])),
                f"{key} must be a distinct URL-safe random secret of at least 43 characters.")
    secret_values = [values[key] for key in (*DB_SECRETS, *SERVER_SECRETS)]
    require(len(set(secret_values)) == len(secret_values), "Database and server secrets must all be distinct.")
    for key, expected in DISABLED_COLLECTION.items():
        require(values[key] == expected, f"{key} must remain disabled in this preparation.")
    base = values["NEXT_PUBLIC_SUPABASE_URL"]
    try:
        parsed = urlsplit(base)
        require(parsed.scheme == "https" and parsed.hostname is not None
                and "." in parsed.hostname and parsed.username is None
                and parsed.password is None and parsed.port is None
                and parsed.path == "" and not parsed.query and not parsed.fragment,
                "NEXT_PUBLIC_SUPABASE_URL must be the HTTPS provider origin without a trailing slash.")
    except ValueError:
        raise ValidationError("NEXT_PUBLIC_SUPABASE_URL is invalid.") from None
    require(values["SUPABASE_JWT_ISSUER"] == base + "/auth/v1", "SUPABASE_JWT_ISSUER must match the configured provider.")
    require(values["SUPABASE_JWKS_URL"] == base + "/auth/v1/.well-known/jwks.json",
            "SUPABASE_JWKS_URL must match the configured provider.")
    require(values["SUPABASE_JWT_AUDIENCE"] == "authenticated", "SUPABASE_JWT_AUDIENCE must be authenticated.")
    require(values["SUPABASE_JWT_ALGORITHM"] in {"ES256", "RS256", "EdDSA"},
            "SUPABASE_JWT_ALGORITHM must be asymmetric.")
    validate_publishable_key(values["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"])


def validate_env_file(path: Path) -> dict[str, str]:
    try:
        metadata = path.lstat()
        require(stat.S_ISREG(metadata.st_mode), "Environment path must be a regular file, not a symlink.")
        require(stat.S_IMODE(metadata.st_mode) == 0o600, "Environment file permissions must be 0600.")
        values = parse_env(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        raise ValidationError("Cannot read the environment file.") from None
    validate_values(values)
    return values


def init_env(path: Path, release_tag: str, caddy_image: str | None = None) -> None:
    """Exclusive creation only; restarting this command never rotates secrets."""
    validate_release_tag(release_tag)
    require(caddy_image is None or caddy_image == CADDY_IMAGE, "CADDY_IMAGE must match the verified digest pin.")
    require(path.name.startswith(".env.vps"), "Use an ignored .env.vps filename at an explicit path.")
    values = parse_env((DIRECTORY / ".env.example").read_text(encoding="utf-8"))
    values["RELEASE_TAG"] = release_tag
    values["CADDY_IMAGE"] = caddy_image or CADDY_IMAGE
    for key in DB_SECRETS:
        values[key] = secrets.token_hex(32)
    for key in SERVER_SECRETS:
        values[key] = secrets.token_urlsafe(48)
    template = (DIRECTORY / ".env.example").read_text(encoding="utf-8")
    body = "\n".join(
        (line.split("=", 1)[0] + "=" + values[line.split("=", 1)[0]])
        if line and not line.startswith("#") and "=" in line else line
        for line in template.splitlines()
    ) + "\n"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError:
        raise ValidationError("Cannot create environment file; it must not already exist and its directory must exist.") from None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            # fchmod makes the exact permission independent of the caller umask.
            os.fchmod(output.fileno(), 0o600)
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    except OSError:
        path.unlink(missing_ok=True)
        raise ValidationError("Cannot write environment file.") from None


def compose_environment(values: dict[str, str]) -> dict[str, str]:
    """Use explicit env-file values rather than stale interactive-shell overrides."""
    environment = dict(os.environ)
    for key in (*values, "COMPOSE_FILE", "COMPOSE_PROFILES", "COMPOSE_ENV_FILES",
                "COMPOSE_PROJECT_NAME", "COMPOSE_PATH_SEPARATOR"):
        environment.pop(key, None)
    # No implicit repository .env lookup; --env-file supplies the only values.
    environment["COMPOSE_DISABLE_ENV_FILE"] = "true"
    return environment


def service_environments(values: dict[str, str]) -> dict[str, dict[str, str]]:
    runtime = "postgresql+psycopg://near_app:" + values["DB_RUNTIME_PASSWORD"] + "@db:5432/near_intelligence"
    operator = "postgresql+psycopg://near_operator:" + values["DB_OPERATOR_PASSWORD"] + "@db:5432/near_intelligence"
    common = {"APP_ENV": "production", "APP_ORIGIN": ORIGIN, "API_INTERNAL_URL": "http://api:8000"}
    jwt = {key: values[key] for key in JWT_NAMES}
    return {
        "db": {"POSTGRES_DB": "near_intelligence", "POSTGRES_USER": "near_bootstrap",
               "POSTGRES_PASSWORD": values["DB_BOOTSTRAP_PASSWORD"],
               **{key: values[key] for key in DB_SECRETS}},
        "migrate": {"MIGRATION_DATABASE_URL": "postgresql+psycopg://near_migrator:" + values["DB_MIGRATION_PASSWORD"] + "@db:5432/near_intelligence"},
        "api": {**common, **jwt, **DISABLED_COLLECTION, "DATABASE_URL": runtime,
                "ARTIFACT_ROOT": ARTIFACT_ROOT, "LOG_LEVEL": values["LOG_LEVEL"]},
        "web": {**common, **jwt, **{key: values[key] for key in (
            "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
            "AUTH_ALLOWED_REDIRECT_ORIGINS", *SERVER_SECRETS)}},
        "worker": {**DISABLED_COLLECTION, "DATABASE_URL": runtime,
                   "OPERATOR_DATABASE_URL": operator, "ARTIFACT_ROOT": ARTIFACT_ROOT,
                   "LOG_LEVEL": values["LOG_LEVEL"]},
        "proxy": {},
    }


WORKER_COMMAND = ["/bin/sh", "-ec", 'exec .venv/bin/python -m near_api.exports.worker --database-url "${DATABASE_URL}" --operator-database-url "${OPERATOR_DATABASE_URL}" --worker-id vps-worker --max-jobs 10 --lease-seconds 300 --timeout 60']
API_COMMAND = [".venv/bin/python", "-m", "uvicorn", "near_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
MIGRATE_COMMAND = [".venv/bin/python", "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"]


def validate_compose(config: dict[str, Any], values: dict[str, str]) -> None:
    """Inspect normalized `docker compose config --format json` in memory."""
    validate_values(values)
    services = config.get("services", {})
    require(set(services) == {"db", "api", "web", "proxy", "migrate", "worker"},
            "Compose service set differs from the reviewed VPS topology.")
    expected_environment = service_environments(values)
    networks = {"db": {"backend"}, "api": {"backend"}, "web": {"edge", "backend"},
                "proxy": {"edge"}, "migrate": {"backend"}, "worker": {"backend"}}
    require(set(config.get("networks", {})) == {"edge", "backend"}, "Compose networks differ from the private topology.")
    for network in config["networks"].values():
        require(network.get("driver") == "bridge" and not network.get("external"),
                "Compose networks must be dedicated bridges.")
    require(set(config.get("volumes", {})) == {"near_db_data", "near_artifacts", "caddy_data", "caddy_config"},
            "Compose durable volume set differs from the reviewed topology.")
    for volume in config["volumes"].values():
        require(not volume.get("external") and not volume.get("driver_opts"),
                "Compose volumes must use the project-local storage contract.")
    expected_images = {
        "db": POSTGRES_IMAGE, "proxy": CADDY_IMAGE,
        "web": "near-intelligence-web:" + values["RELEASE_TAG"],
        **{key: "near-intelligence-api:" + values["RELEASE_TAG"] for key in ("api", "migrate", "worker")},
    }
    expected_volumes = {
        "db": {("volume", "near_db_data", "/var/lib/postgresql", False),
               ("bind", str(REPOSITORY / "scripts/db/010-roles.sql"), "/docker-entrypoint-initdb.d/010-roles.sql", True)},
        "api": {("volume", "near_artifacts", ARTIFACT_ROOT, True)},
        "worker": {("volume", "near_artifacts", ARTIFACT_ROOT, False)},
        "proxy": {("bind", str(DIRECTORY / "Caddyfile"), "/etc/caddy/Caddyfile", True),
                  ("volume", "caddy_data", "/data", False), ("volume", "caddy_config", "/config", False)},
        "web": set(), "migrate": set(),
    }
    expected_commands = {"api": API_COMMAND, "migrate": MIGRATE_COMMAND, "worker": WORKER_COMMAND}
    for name, service in services.items():
        require(service.get("environment", {}) == expected_environment[name],
                f"{name}: service environment differs from its explicit allowlist.")
        require(not service.get("env_file"), f"{name}: whole env_file injection is forbidden.")
        require(service.get("image") == expected_images[name], f"{name}: image reference differs from the reviewed pin/tag.")
        require(set(service.get("networks", {})) == networks[name], f"{name}: network isolation differs from the reviewed topology.")
        require(not service.get("privileged") and not service.get("network_mode")
                and not service.get("cap_add") and not service.get("pid")
                and not service.get("devices"), f"{name}: unexpected elevated container access.")
        require(service.get("restart") == ("no" if name in {"worker", "migrate"} else "unless-stopped"),
                f"{name}: restart policy differs from the reviewed lifecycle.")
        require(service.get("profiles", []) == ([name] if name in {"worker", "migrate"} else []),
                f"{name}: startup profile differs from the reviewed lifecycle.")
        require(service.get("logging") == {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
                f"{name}: bounded logging policy is required.")
        volume_set = {(item.get("type"), item.get("source"), item.get("target"), bool(item.get("read_only")))
                      for item in service.get("volumes", [])}
        require(volume_set == expected_volumes[name], f"{name}: durable mount contract differs from the reviewed topology.")
        if name in expected_commands:
            command = service.get("command", [])
            normalized = [part.replace("$$", "$") for part in command]
            require(normalized == expected_commands[name], f"{name}: command differs from the explicit reviewed action.")
        else:
            require(not service.get("command"), f"{name}: unexpected command override.")
        if name == "proxy":
            ports = service.get("ports", [])
            require(len(ports) == 2 and {(p.get("target"), str(p.get("published")), p.get("protocol", "tcp")) for p in ports}
                    == {(80, "80", "tcp"), (443, "443", "tcp")}, "proxy: only host 80/443 TCP may be published.")
        else:
            require(not service.get("ports"), f"{name}: host-published ports are forbidden.")
        if name in {"api", "web", "worker", "migrate"}:
            expected_dockerfile = "Dockerfile.web" if name == "web" else "Dockerfile.api"
            require(service.get("pull_policy") == "never", f"{name}: audited local image is required.")
            require(service.get("build") == {"context": str(REPOSITORY), "dockerfile": expected_dockerfile},
                    f"{name}: build must use the current frozen-lock source without build arguments.")


def check_compose(path: Path, compose_file: Path | None = None,
                  project_name: str = "near-intelligence-vps") -> None:
    values = validate_env_file(path)
    command = ["docker", "compose", "--project-name", project_name, "--env-file", str(path.absolute()),
               "-f", str((compose_file or DIRECTORY / "compose.yaml").absolute()),
               "--profile", "migrate", "--profile", "worker", "config", "--format", "json"]
    try:
        result = subprocess.run(command, env=compose_environment(values), capture_output=True, text=True, check=False, timeout=60)
        require(result.returncode == 0, "Docker Compose could not render the selected configuration; no values were printed.")
        config = json.loads(result.stdout)
        require(isinstance(config, dict), "Docker Compose returned an unexpected configuration format.")
        validate_compose(config, values)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        raise ValidationError("Cannot inspect Docker Compose configuration; no values were printed.") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    initialize = commands.add_parser("init", help="create an ignored 0600 env file; never overwrite")
    initialize.add_argument("--env-file", type=Path, required=True)
    initialize.add_argument("--release-tag", required=True)
    initialize.add_argument("--caddy-image", default=None)
    for action in ("validate", "check-compose"):
        command = commands.add_parser(action)
        command.add_argument("--env-file", type=Path, required=True)
        if action == "check-compose":
            command.add_argument("--compose-file", type=Path)
            command.add_argument("--project-name", default="near-intelligence-vps")
    args = parser.parse_args(argv)
    try:
        if args.action == "init":
            init_env(args.env_file, args.release_tag, args.caddy_image)
            print("Created 0600 environment file. Fill Supabase placeholders, then run validate. No credentials printed.")
        elif args.action == "validate":
            validate_env_file(args.env_file)
            print("Environment checks passed. Provider account and remote readiness were not tested.")
        else:
            check_compose(args.env_file, args.compose_file, args.project_name)
            print("Resolved Compose isolation checks passed. No containers or provider requests started.")
    except ValidationError as error:
        print(f"VPS configuration refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
