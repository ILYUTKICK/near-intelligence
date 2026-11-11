"""NI-063 e2e harness: boot the real product stack on a disposable loopback cluster.

This script is HARNESS code (never imported by the application). It composes the
already-verified production scenario patterns from scripts/run-db-tests.py and
apps/api/tests/test_saved_charts_http.py:

- a disposable loopback PostgreSQL 18 cluster (initdb/pg_ctl/createdb/roles,
  generated passwords kept inside the temp directory, removed afterwards);
- the real FastAPI gateway on uvicorn with the synthetic ES256 verifier (only
  the provider JWKS transport is synthetic — signature, issuer, audience,
  principal bootstrap and RLS execute normally);
- the real production Next.js server (`next start` of the prebuilt bundle);
- the real NI-058 export worker processing queued jobs in a loop;
- visibly synthetic datasets staged through the real NI-028 pipeline
  (stage -> validate -> approve -> publish) and the registered chart catalog.

NI-064 additions (same harness, same rules): a second 366-day synthetic
dataset and one 200-block document with 20 liveChart references owned by the
synthetic alice, created through the real principal bootstrap and the real
document service, so the desktop performance spec measures the PRD budgets
(200 blocks / 20 chart refs / 366 daily points) on persisted real-stack data.

Harness-only extras, clearly prefixed `/_ni063_` and never part of the product:

- `GET /_ni063/session/{name}?next=...` — the synthetic-session handoff used by
  NI-035/NI-042/NI-050 for browser evidence: sets the real signed session cookie
  for a synthetic user and redirects to an internal path. No real Supabase
  account is created or contacted.
- `POST /_ni063/outage` — toggles the source-outage mode at the delivery
  boundary: `delivery.resolve_latest_version` raises `DeliveryDataNotReady`,
  the same failure mode as the NI-042 chart-delivery outage. Pinned
  reconstruction (NI-043) and the export path (NI-056) do not consult the
  latest pointer, so saved evidence keeps working while the live source is
  explicit about being unavailable.
- `GET /_ni063/inspect/document/{id}` — read-only DB inspection for the
  Playwright assertions: the current `app.document_versions` row (version id,
  revision, content hash, resolved contexts) and the pinned dataset version
  identity. Read-only SELECT; returns no credentials or paths.

Run under the frozen API environment after `pnpm build`:
  uv run --project apps/api python apps/web/e2e/harness/stack.py \
      --pg-bin <postgresql-18-bin> --handoff <path-to-json>
It blocks until SIGTERM/SIGINT, then stops every process and deletes the
disposable cluster. Everything stays on loopback; no provider, collector or
network beyond localhost is touched.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from uuid import UUID, uuid4

REPO = Path(__file__).resolve().parents[4]  # apps/web/e2e/harness/stack.py
sys.path.insert(0, str(REPO / "apps" / "api" / "src"))
sys.path.insert(0, str(REPO / "apps" / "api" / "tests"))

import jwt  # noqa: E402
import uvicorn  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.responses import JSONResponse, RedirectResponse  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import URL  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from near_api.auth import principal  # noqa: E402
from near_api.auth.jwks import JWKSCache  # noqa: E402
from near_api.auth.principal import bootstrap_principal  # noqa: E402
from near_api.auth.verification import TokenVerifier, VerifiedToken  # noqa: E402
from near_api.charts.registry import chart_by_chart_id  # noqa: E402
from near_api.datasets import delivery  # noqa: E402
from near_api.datasets.service import publish, stage  # noqa: E402
from near_api.documents import service as document_service  # noqa: E402
from near_api.main import app  # noqa: E402
from near_api.metrics.registry import definition_by_metric_id  # noqa: E402

import test_chart_blocks as chart_fixtures  # noqa: E402


WINDOW_START = dt.date(2026, 1, 1)
WINDOW_DAYS = 14
DATASET_DAYS = WINDOW_DAYS  # coverage end is the last day with an observation
EXACT_PIN_VALUE = "12.123456789012345678901234"

# NI-064 performance fixture (all visibly synthetic, never published research):
# a 366-day dataset so the PRD budget measurement resolves 366 daily points,
# and one 200-block document with 20 liveChart references so the PRD document
# budget (200 blocks / 20 mounted chart references) is measured on real data.
PERF_WINDOW_START = dt.date(2026, 1, 1)
PERF_DATASET_DAYS = 366
PERF_CHART_REFS = 20
PERF_BLOCKS = 200


def log(message: str) -> None:
    print(f"[ni063-stack] {message}", flush=True)


def free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


def synthetic_observations() -> tuple[list[dict], dict[str, str]]:
    """Fourteen distinct days so every range preset stays inside coverage."""
    volume = definition_by_metric_id("provider_intents_volume_usd").id
    values = [EXACT_PIN_VALUE, "100.5", "200.25", "321.125", "88.0625", "140.75",
              "95.5", "300.1", "410.03125", "270.625", "185.875", "240.4375",
              "160.375", "205.8125"]
    observations = []
    for index in range(DATASET_DAYS):
        day = WINDOW_START + dt.timedelta(days=index)
        observations.append({
            "metric_definition_id": str(volume),
            "period_start": dt.datetime.combine(day, dt.time.min,
                                                tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period_end": (dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc)
                           + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dimensions": {"source": "SRC-LLAMA"},
            "value": values[index],
            "quality_status": "verified",
            "bound_kind": "exact",
            "source_record_ref": None,
            "quality": {},
        })
    return observations, dict(zip(
        [(WINDOW_START + dt.timedelta(days=index)).isoformat() for index in range(DATASET_DAYS)],
        values))


def perf_observations() -> tuple[list[dict], str]:
    """366 distinct daily rows so a max-range view resolves 366 real points."""
    volume = definition_by_metric_id("provider_intents_volume_usd").id
    observations = []
    for index in range(PERF_DATASET_DAYS):
        day = PERF_WINDOW_START + dt.timedelta(days=index)
        observations.append({
            "metric_definition_id": str(volume),
            "period_start": dt.datetime.combine(day, dt.time.min,
                                                tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period_end": (dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc)
                           + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dimensions": {"source": "SRC-LLAMA"},
            "value": f"{100 + (index % 50)}.{(index * 7) % 100:02d}",
            "quality_status": "verified",
            "bound_kind": "exact",
            "source_record_ref": None,
            "quality": {},
        })
    return observations, (PERF_WINDOW_START + dt.timedelta(days=PERF_DATASET_DAYS - 1)).isoformat()


def perf_day_values() -> dict[str, str]:
    """The perf dataset's day -> stored decimal-string map (for assertions)."""
    return {
        (PERF_WINDOW_START + dt.timedelta(days=index)).isoformat():
            f"{100 + (index % 50)}.{(index * 7) % 100:02d}"
        for index in range(PERF_DATASET_DAYS)
    }


def perf_document_content(chart_definition_id: UUID, dataset_id: UUID) -> dict:
    """200 top-level blocks: 180 prose blocks + 20 liveChart references.

    Every chart block pins the same approved synthetic dataset and a 7-day
    selection inside its coverage, exactly the canonical attrs the NI-041
    insertion produces; the save resolves and freezes all 20 contexts the
    same way any owner save does. Text is explicitly labeled synthetic.
    Section and paragraph numbering use SEPARATE counters so the specs can
    address stable markers ("section 1", "paragraph 1"..."paragraph 160").
    """
    selection = {"start": "2026-01-01", "end": "2026-01-08",
                 "frequency": "day", "filters": {}}
    content: list[dict] = []
    section_index = 0
    paragraph_index = 0
    for block_index in range(PERF_BLOCKS):
        if block_index % 10 == 5:
            content.append({"type": "liveChart", "attrs": {
                "block_id": str(uuid4()), "mode": "live", "selection": selection,
                "chart_definition_version_id": str(chart_definition_id),
                "observed_dataset_version_id": str(dataset_id),
            }})
        elif block_index % 10 == 0:
            section_index += 1
            content.append({
                "type": "heading", "attrs": {"block_id": str(uuid4()), "level": 2},
                "content": [{"type": "text",
                             "text": f"NI-064 performance fixture section {section_index} (synthetic)"}]})
        else:
            paragraph_index += 1
            content.append({
                "type": "paragraph", "attrs": {"block_id": str(uuid4())},
                "content": [{"type": "text",
                             "text": f"NI-064 performance fixture paragraph {paragraph_index}: "
                                     "synthetic desktop-QA body text used to measure editor "
                                     "load, autosave and lazy chart mounting. It carries no "
                                     "research claim. (synthetic)"}]})
    assert len(content) == PERF_BLOCKS
    assert paragraph_index == 160 and section_index == 20
    return {"schema_version": 1, "type": "doc", "content": content}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True,
                        help="path of the JSON handoff file written for the Playwright harness")
    parser.add_argument("--keep", action="store_true",
                        help="keep the disposable cluster directory for debugging")
    args = parser.parse_args()

    web_dir = REPO / "apps" / "web"
    if not (web_dir / ".next" / "BUILD_ID").exists():
        raise RuntimeError("apps/web/.next/BUILD_ID missing — run `pnpm --filter web build` first")
    node_bin = shutil.which("node")
    if node_bin is None:
        raise RuntimeError("node must be on PATH (the export worker renderer needs it)")

    local = (REPO / ".local").resolve()
    local.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="ni063-e2e-", dir=local)).resolve()
    if directory.parent != local or not directory.name.startswith("ni063-e2e-"):
        raise RuntimeError("Unsafe temporary-cluster path")

    # ---- disposable PostgreSQL (scripts/run-db-tests.py pattern) ---------- #
    environment = os.environ.copy()
    environment["PGPASSWORD"] = secrets.token_urlsafe(32)
    environment["DB_BOOTSTRAP_PASSWORD"] = environment["PGPASSWORD"]
    for key in ("DB_RUNTIME_PASSWORD", "DB_MIGRATION_PASSWORD", "DB_OPERATOR_PASSWORD",
                "DB_PUBLIC_PASSWORD"):
        environment[key] = secrets.token_urlsafe(32)
    password_file = directory / "bootstrap-password"
    password_file.write_text(environment["PGPASSWORD"], encoding="utf-8")
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        pg_port = candidate.getsockname()[1]
    environment.update(PGHOST="127.0.0.1", PGPORT=str(pg_port), PGUSER="ni_test_admin")
    data = directory / "data"
    started = False

    def run_pg(name: str, *arguments: Any):
        binary = args.pg_bin / name
        if not binary.is_file():
            raise RuntimeError(f"PostgreSQL binary is unavailable: {binary}")
        output = directory / f"{name}-command.log"
        with output.open("wb") as log_file:
            result = subprocess.run([str(binary), *map(str, arguments)], env=environment,
                                    stdin=subprocess.DEVNULL, stdout=log_file,
                                    stderr=subprocess.STDOUT, timeout=60)
        message = output.read_text(encoding="utf-8", errors="replace")
        if result.returncode:
            for key in ("PGPASSWORD", "DB_RUNTIME_PASSWORD", "DB_MIGRATION_PASSWORD",
                        "DB_OPERATOR_PASSWORD", "DB_PUBLIC_PASSWORD"):
                message = message.replace(environment[key], "[redacted]")
            raise RuntimeError(f"{name} failed: {message}")
        return message

    def url(user: str, password: str) -> str:
        return URL.create("postgresql+psycopg", username=user, password=password,
                          host="127.0.0.1", port=pg_port,
                          database="near_intelligence").render_as_string(hide_password=False)

    try:
        version = run_pg("postgres", "--version").strip()
        if " 18." not in version:
            raise RuntimeError("The verified integration target is PostgreSQL major 18")
        log(f"disposable {version} on 127.0.0.1:{pg_port}")
        run_pg("initdb", "-D", data, "-U", "ni_test_admin", "--pwfile", password_file,
               "--auth-host=scram-sha-256", "--auth-local=trust", "--encoding=UTF8",
               "--no-locale")
        password_file.unlink()
        started = True
        run_pg("pg_ctl", "-D", data, "-l", directory / "server.log", "-w", "-t", "20",
               "-o", f"-h 127.0.0.1 -p {pg_port}", "start")
        run_pg("createdb", "near_intelligence")
        run_pg("psql", "--no-psqlrc", "-d", "near_intelligence", "-f",
               REPO / "scripts" / "db" / "010-roles.sql")

        environment.update(
            NI_ISOLATED_PG_TEST="1",
            NI_TEST_TMP_DIR=str(directory),
            NI_TEST_ADMIN_URL=url("ni_test_admin", environment["PGPASSWORD"]),
            NI_TEST_RUNTIME_URL=url("near_app", environment["DB_RUNTIME_PASSWORD"]),
            NI_TEST_OPERATOR_URL=url("near_operator", environment["DB_OPERATOR_PASSWORD"]),
            NI_TEST_PUBLIC_URL=url("near_public", environment["DB_PUBLIC_PASSWORD"]),
            MIGRATION_DATABASE_URL=url("near_migrator", environment["DB_MIGRATION_PASSWORD"]),
        )
        # Alembic/uvicorn run in this very process, so the credentials must be
        # visible through os.environ as well (run-db-tests.py sets them for
        # child unittest processes instead).
        os.environ.update({key: environment[key] for key in (
            "NI_ISOLATED_PG_TEST", "NI_TEST_TMP_DIR", "NI_TEST_ADMIN_URL",
            "NI_TEST_RUNTIME_URL", "NI_TEST_OPERATOR_URL", "NI_TEST_PUBLIC_URL",
            "MIGRATION_DATABASE_URL")})

        runtime = None
        operator = None
        admin = None
        server = None
        web_process = None
        web_log = None
        worker_stop = threading.Event()
        try:
            from near_api.db.session import create_runtime_engine
            runtime = create_runtime_engine(environment["NI_TEST_RUNTIME_URL"], pool_size=2)
            operator = create_engine(environment["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
            admin = create_engine(environment["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
            config = Config(str(REPO / "apps" / "api" / "alembic.ini"))
            command.upgrade(config, "head")
            chart_fixtures.register_test_chart_catalog(operator)
            log("migrations applied, synthetic chart catalog registered")

            # ---- NI-064 performance dataset first: the NI-063 journey ---- #
            # ---- dataset is published LAST and stays the "latest" one ---- #
            perf_observations_list, perf_last_day = perf_observations()
            volume_metric = definition_by_metric_id("provider_intents_volume_usd").id
            perf_manifest = {
                "schema_version": 1,
                "dataset_key": f"ni064-perf.{uuid4().hex[:12]}",
                "frequency": "daily",
                "window": {"start": PERF_WINDOW_START.isoformat(),
                           "end_exclusive": (PERF_WINDOW_START
                                             + dt.timedelta(days=PERF_DATASET_DAYS)).isoformat()},
                "pipeline_version": "ni064-perf",
                "code_commit": None, "config_hash": None, "dependency_lock_hash": None,
                "source_as_of": None, "retrieved_at": None,
                "quality": {"notes": "synthetic NI-064 performance fixture — visibly "
                                     "labeled, never published research"},
                "member_metrics": [str(volume_metric)],
                "inputs": [],
                "observations": perf_observations_list,
            }
            fixture_dir = directory / "fixtures"
            fixture_dir.mkdir()
            perf_dir = fixture_dir / "perf"
            perf_dir.mkdir()
            perf_manifest_path = perf_dir / "dataset.json"
            perf_manifest_path.write_text(json.dumps(perf_manifest, indent=2, sort_keys=True)
                                          + "\n", encoding="utf-8")
            storage_root = directory / "storage"
            perf_result = stage(operator, perf_manifest_path, storage_root)
            if perf_result.status != "validated":
                raise RuntimeError(f"perf dataset did not validate: {perf_result.validation}")
            publish(operator, perf_result.dataset_version_id)
            log(f"NI-064 perf dataset published: version {perf_result.dataset_version_id} "
                f"({PERF_DATASET_DAYS} daily rows)")

            # ---- synthetic approved dataset (real NI-028 pipeline) -------- #
            observations, day_values = synthetic_observations()
            manifest = {
                "schema_version": 1,
                "dataset_key": f"ni063-e2e.{uuid4().hex[:12]}",
                "frequency": "daily",
                "window": {"start": WINDOW_START.isoformat(),
                           "end_exclusive": (WINDOW_START + dt.timedelta(days=WINDOW_DAYS)).isoformat()},
                "pipeline_version": "ni063-e2e",
                "code_commit": None, "config_hash": None, "dependency_lock_hash": None,
                "source_as_of": None, "retrieved_at": None,
                "quality": {"notes": "synthetic NI-063 e2e fixture — visibly labeled, never published research"},
                "member_metrics": [str(volume_metric)],
                "inputs": [],
                "observations": observations,
            }
            manifest_path = fixture_dir / "dataset.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                     encoding="utf-8")
            result = stage(operator, manifest_path, storage_root)
            if result.status != "validated":
                raise RuntimeError(f"synthetic dataset did not validate: {result.validation}")
            publish(operator, result.dataset_version_id)
            delivery.reset_delivery_caches()
            log(f"synthetic dataset published: version {result.dataset_version_id} "
                "(latest approved for its metric)")

            # ---- synthetic ES256 verifier (production gateway pattern) ---- #
            secret = secrets.token_urlsafe(32)
            csrf_secret = secrets.token_urlsafe(32)
            api_port, web_port = free_port(), free_port()
            api_url = f"http://127.0.0.1:{api_port}"
            web_url = f"http://127.0.0.1:{web_port}"
            issuer = "https://synthetic.supabase.co/auth/v1"
            next_environment = {**environment,
                                "APP_ENV": "test", "APP_ORIGIN": web_url,
                                "API_INTERNAL_URL": api_url,
                                "NEXT_TELEMETRY_DISABLED": "1",
                                "NEXT_PUBLIC_SUPABASE_URL": "https://synthetic.supabase.co",
                                "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_synthetic_0123456789",
                                "SUPABASE_JWT_ISSUER": issuer,
                                "SUPABASE_JWKS_URL": issuer + "/.well-known/jwks.json",
                                "SUPABASE_JWT_AUDIENCE": "authenticated",
                                "SUPABASE_JWT_ALGORITHM": "ES256",
                                "AUTH_ALLOWED_REDIRECT_ORIGINS": web_url,
                                "AUTH_COOKIE_SIGNING_SECRET": secret,
                                "CSRF_SIGNING_SECRET": csrf_secret}

            key = ec.generate_private_key(ec.SECP256R1())
            public_jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
            public_jwk.update(kid="ni063-synthetic", alg="ES256", use="sig")
            from types import SimpleNamespace
            settings = SimpleNamespace(SUPABASE_JWT_ISSUER=issuer,
                                       SUPABASE_JWT_AUDIENCE="authenticated",
                                       SUPABASE_JWT_ALGORITHM="ES256")
            verifier = TokenVerifier(settings, JWKSCache(
                next_environment["SUPABASE_JWKS_URL"],
                fetcher=lambda _url: {"keys": [public_jwk]}))
            # The same two process seams the production HTTP suites patch;
            # restored nowhere because this process ends with the harness.
            principal._get_verifier = lambda: verifier  # noqa: SLF001
            principal._get_engine = lambda: runtime  # noqa: SLF001

            users = {name: uuid4() for name in ("alice", "bob")}

            # ---- NI-064 performance document (real service + identity) ---- #
            perf_alice = bootstrap_principal(runtime, VerifiedToken(
                subject=users["alice"], expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=2),
                issued_at=dt.datetime.now(dt.UTC)))
            perf_definition_id = chart_by_chart_id("intents-volume").id
            perf_document = document_service.create_document(
                runtime, perf_alice,
                title="NI-064 performance fixture (synthetic 200 blocks / 20 charts)")
            document_service.save_revision(
                runtime, perf_alice, perf_document.document.id, expected_revision=1,
                document_payload=perf_document_content(perf_definition_id,
                                                       perf_result.dataset_version_id),
                observed_contexts=[])
            log(f"NI-064 perf fixture ready: dataset {perf_result.dataset_version_id}, "
                f"document {perf_document.document.id} "
                f"({PERF_BLOCKS} blocks / {PERF_CHART_REFS} chart refs)")

            def session_cookie(name: str, lifetime_seconds: int = 3600) -> str:
                token = jwt.encode({"sub": str(users[name]), "iss": issuer,
                                    "aud": "authenticated",
                                    "exp": int(time.time()) + lifetime_seconds},
                                   key, algorithm="ES256",
                                   headers={"kid": "ni063-synthetic"})
                payload = {"accessToken": token, "refreshToken": "synthetic-not-used",
                           "expiresAt": int(time.time() * 1000) + lifetime_seconds * 1000}
                body = base64.urlsafe_b64encode(
                    json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
                signature = base64.urlsafe_b64encode(
                    hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
                ).rstrip(b"=").decode()
                return f"{body}.{signature}"

            # ---- harness-only routes -------------------------------------- #
            def internal_next(value: str | None) -> str:
                if value and value.startswith("/") and not value.startswith("//") \
                        and "\\" not in value and len(value) <= 4096:
                    return value
                return "/data/intents/intents-volume"

            @app.get("/_ni063/session/{name}", include_in_schema=False)
            def harness_session(name: str, next: str | None = None):  # noqa: A002
                if name not in users:
                    return JSONResponse({"error": "unknown harness user"}, status_code=404)
                # A relative Location would resolve against THIS api origin;
                # the browser must land on the web origin with the session set.
                response = RedirectResponse(web_url + internal_next(next))
                response.set_cookie("ni_session", session_cookie(name),
                                    httponly=True, samesite="lax")
                return response

            outage_state = {"enabled": False}
            original_resolve_latest = delivery.resolve_latest_version

            def outaged_resolve_latest(connection, required_ids, *args, **kwargs):
                if outage_state["enabled"]:
                    raise delivery.DeliveryDataNotReady(
                        "Synthetic NI-063 source outage: the latest approved dataset "
                        "pointer is unavailable (no values are invented)")
                return original_resolve_latest(connection, required_ids, *args, **kwargs)

            delivery.resolve_latest_version = outaged_resolve_latest

            @app.post("/_ni063/outage", include_in_schema=False)
            def harness_outage(body: dict):
                outage_state["enabled"] = bool(body.get("enabled"))
                delivery.reset_delivery_caches()
                return {"enabled": outage_state["enabled"]}

            @app.get("/_ni063/inspect/document/{document_id}", include_in_schema=False)
            def harness_inspect_document(document_id: str):
                UUID(document_id)
                with admin.connect() as connection:
                    row = connection.execute(text("""
                        SELECT id, document_id, revision, schema_version, content_sha256,
                               resolved_contexts, created_at
                        FROM app.document_versions
                        WHERE document_id = :document_id
                        ORDER BY revision DESC LIMIT 1
                    """), {"document_id": document_id}).mappings().first()
                if row is None:
                    return JSONResponse({"error": "no version row"}, status_code=404)
                return {key: (value.isoformat() if isinstance(value, dt.datetime) else value)
                        for key, value in row.items()}

            @app.get("/_ni063/inspect/dataset/{dataset_version_id}", include_in_schema=False)
            def harness_inspect_dataset(dataset_version_id: str):
                UUID(dataset_version_id)
                with admin.connect() as connection:
                    row = connection.execute(text("""
                        SELECT id, dataset_key, status, content_sha256, window_start, window_end
                        FROM app.dataset_versions WHERE id = :id
                    """), {"id": dataset_version_id}).mappings().first()
                if row is None:
                    return JSONResponse({"error": "no dataset row"}, status_code=404)
                return dict(row)

            # ---- API server (real app, synthetic provider transport) ------ #
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port,
                                                   log_level="warning"))
            api_thread = threading.Thread(target=server.run, daemon=True)
            api_thread.start()
            deadline = time.monotonic() + 30
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("the FastAPI gateway did not start")
            log(f"FastAPI gateway on {api_url}")

            # ---- production Next.js server -------------------------------- #
            web_log = (directory / "web.log").open("wb")
            web_process = subprocess.Popen(
                [node_bin, str(web_dir / "node_modules/next/dist/bin/next"),
                 "start", "--hostname", "127.0.0.1", "--port", str(web_port)],
                cwd=web_dir, env=next_environment, stdout=web_log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL)
            import httpx
            client = httpx.Client(base_url=web_url, timeout=10, trust_env=False)
            deadline = time.monotonic() + 60
            healthy = False
            while time.monotonic() < deadline:
                try:
                    if client.get("/health").status_code == 200:
                        healthy = True
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
            if not healthy or web_process.poll() is not None:
                web_log.flush()
                raise RuntimeError("the production Next.js server did not become healthy; "
                                   f"see {directory / 'web.log'}")
            client.close()
            log(f"production Next.js on {web_url}")

            # ---- export worker loop (real NI-058 operator CLI) ------------ #
            def worker_loop() -> None:
                while not worker_stop.is_set():
                    completed = subprocess.run(
                        [sys.executable, "-m", "near_api.exports.worker", "--worker-id",
                         "ni063-e2e-worker", "--database-url",
                         environment["NI_TEST_RUNTIME_URL"], "--operator-database-url",
                         environment["NI_TEST_OPERATOR_URL"]],
                        cwd=REPO, env=environment, stdin=subprocess.DEVNULL,
                        capture_output=True, timeout=120)
                    if completed.returncode != 0:
                        log("export worker exited with an error: "
                            + completed.stderr.decode("utf-8", "replace")[-500:])
                    worker_stop.wait(1.0)

            worker_thread = threading.Thread(target=worker_loop, daemon=True)
            worker_thread.start()
            log("export worker loop running (real near_api.exports.worker CLI)")

            # ---- handoff --------------------------------------------------- #
            args.handoff.parent.mkdir(parents=True, exist_ok=True)
            args.handoff.write_text(json.dumps({
                "web_url": web_url,
                "api_url": api_url,
                "dataset_version_id": str(result.dataset_version_id),
                "dataset_key": manifest["dataset_key"],
                "window": {"start": WINDOW_START.isoformat(),
                           "end": (WINDOW_START + dt.timedelta(days=DATASET_DAYS - 1)).isoformat()},
                "day_values": day_values,
                "pin_value": EXACT_PIN_VALUE,
                "session_alice": f"{api_url}/_ni063/session/alice",
                "session_bob": f"{api_url}/_ni063/session/bob",
                "outage": f"{api_url}/_ni063/outage",
                "inspect_document": f"{api_url}/_ni063/inspect/document",
                "inspect_dataset": f"{api_url}/_ni063/inspect/dataset",
                "perf_dataset_version_id": str(perf_result.dataset_version_id),
                "perf_dataset_key": perf_manifest["dataset_key"],
                "perf_day_values": perf_day_values(),
                "perf_window": {"start": PERF_WINDOW_START.isoformat(),
                                "end": perf_last_day,
                                "end_exclusive": (PERF_WINDOW_START
                                                  + dt.timedelta(days=PERF_DATASET_DAYS)).isoformat()},
                "perf_document_id": str(perf_document.document.id),
                "cluster_dir": str(directory),
            }, indent=2) + "\n", encoding="utf-8")
            log(f"handoff written to {args.handoff}")

            stop_event = threading.Event()

            def handle_signal(signum, _frame):
                log(f"received signal {signum}; stopping the stack")
                stop_event.set()

            signal.signal(signal.SIGTERM, handle_signal)
            signal.signal(signal.SIGINT, handle_signal)
            while not stop_event.is_set():
                if web_process.poll() is not None:
                    log("the Next.js server exited unexpectedly")
                    raise RuntimeError("web server died")
                time.sleep(0.5)
            return 0
        finally:
            worker_stop.set()
            if server is not None:
                server.should_exit = True
            if web_process is not None and web_process.poll() is None:
                web_process.terminate()
                try:
                    web_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    web_process.kill()
                    web_process.wait(timeout=10)
            if web_log is not None:
                web_log.close()
            if runtime is not None:
                runtime.dispose()
            if operator is not None:
                operator.dispose()
            if admin is not None:
                admin.dispose()
    finally:
        if started:
            try:
                run_pg("pg_ctl", "-D", data, "-m", "fast", "-w", "-t", "20", "stop")
                log("disposable PostgreSQL stopped")
                if not args.keep:
                    shutil.rmtree(directory, ignore_errors=True)
                else:
                    log(f"cluster directory retained for debugging: {directory}")
            except Exception:
                print(f"Cluster stop needs attention; retained isolated files at {directory}",
                      file=sys.stderr)
                raise


if __name__ == "__main__":
    sys.exit(main())
