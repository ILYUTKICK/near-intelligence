"""Create, test and stop a disposable loopback PostgreSQL cluster; no user DB used.

Run with the frozen API environment and --pg-bin pointing to PostgreSQL 18 bin.
No Docker daemon, provider, auth account or historical research archive is needed.
"""

import argparse
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile

from sqlalchemy.engine import URL


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chart-insertion-http", action="store_true")
    parser.add_argument("--workspace-home-http", action="store_true",
                        help="run Home aggregation and production gateway persistence checks")
    parser.add_argument("--saved-charts-http", action="store_true",
                        help="run saved-chart DB and production gateway HTTP checks only")
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--suite", choices=("all", "landing", "insights", "exports", "publications", "history"),
                        default="all",
                        help="run all database suites, landing HTTP integration, focused "
                             "insight, export, or publication checks")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    local = (repo / ".local").resolve()
    local.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="ni003-pg-", dir=local)).resolve()
    if directory.parent != local or not directory.name.startswith("ni003-pg-"):
        raise RuntimeError("Unsafe temporary-cluster path")
    executable_suffix = ".exe" if os.name == "nt" else ""
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
        port = candidate.getsockname()[1]
    environment.update(PGHOST="127.0.0.1", PGPORT=str(port), PGUSER="ni_test_admin")
    data = directory / "data"
    started, stopped = False, False

    def run_pg(name, *arguments):
        binary = args.pg_bin / (name + executable_suffix)
        if not binary.is_file():
            raise RuntimeError(f"PostgreSQL binary is unavailable: {name}")
        # Background postgres children may inherit a pipe even after pg_ctl exits.
        # A file avoids waiting forever for EOF from that inherited handle.
        output = directory / f"{name}-command.log"
        with output.open("wb") as log:
            result = subprocess.run([str(binary), *map(str, arguments)], env=environment,
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        message = output.read_text(encoding="utf-8", errors="replace")
        if result.returncode:
            for key in ("PGPASSWORD", "DB_RUNTIME_PASSWORD", "DB_MIGRATION_PASSWORD",
                        "DB_OPERATOR_PASSWORD", "DB_PUBLIC_PASSWORD"):
                message = message.replace(environment[key], "[redacted]")
            raise RuntimeError(f"{name} failed: {message}")
        return message

    def url(user, password):
        return URL.create("postgresql+psycopg", username=user, password=password,
                          host="127.0.0.1", port=port, database="near_intelligence_test").render_as_string(
                              hide_password=False)

    try:
        version = run_pg("postgres", "--version").strip()
        if " 18." not in version:
            raise RuntimeError("The verified integration target is PostgreSQL major 18")
        print(f"Testing {version} in a disposable loopback cluster", flush=True)
        run_pg("initdb", "-D", data, "-U", "ni_test_admin", "--pwfile", password_file,
               "--auth-host=scram-sha-256", "--auth-local=trust", "--encoding=UTF8", "--no-locale")
        password_file.unlink()
        # A partially successful start must also be stopped before any cleanup.
        started = True
        run_pg("pg_ctl", "-D", data, "-l", directory / "server.log", "-w", "-t", "20", "-o",
               f"-h 127.0.0.1 -p {port}", "start")
        run_pg("createdb", "near_intelligence_test")
        run_pg("psql", "--no-psqlrc", "-d", "near_intelligence_test", "-f", repo / "scripts/db/010-roles.sql")
        environment.update(
            NI_ISOLATED_PG_TEST="1", PYTHONPATH=str(repo / "apps/api/src"),
            NI_TEST_TMP_DIR=str(directory),
            NI_TEST_ADMIN_URL=url("ni_test_admin", environment["PGPASSWORD"]),
            NI_TEST_RUNTIME_URL=url("near_app", environment["DB_RUNTIME_PASSWORD"]),
            NI_TEST_OPERATOR_URL=url("near_operator", environment["DB_OPERATOR_PASSWORD"]),
            NI_TEST_PUBLIC_URL=url("near_public", environment["DB_PUBLIC_PASSWORD"]),
            MIGRATION_DATABASE_URL=url("near_migrator", environment["DB_MIGRATION_PASSWORD"]),
        )
        test_log = directory / "test-results.log"
        # NI-003 identity/RLS, NI-018 bootstrap, NI-019 ownership/RLS,
        # NI-022 home aggregation, NI-027 archive import, NI-028 dataset
        # staging/publication, NI-029 metric computations, NI-030 refresh
        # adapter, NI-031 chart registry, NI-032 public delivery APIs,
        # NI-051 model readiness gate (offline research code, no database
        # use), the NI-052 deterministic estimator (also offline research
        # code), the NI-053 diagnostics battery (same), the NI-054
        # publication gate + public model APIs (publish flow, migration 0010,
        # RLS matrix), the NI-036 document revision suites, the NI-041
        # chart-block insertion suites, the NI-055 model-result block
        # insertion suites, the NI-056 frozen export representation suite,
        # the NI-058 export job lifecycle suite, the NI-045 template and
        # publication suites, the NI-060 share suite, the NI-061 integration
        # invariant suite (independent oracles across DB/API/editor
        # boundaries) and the NI-062 security audit suites (HTTP ownership
        # matrix, direct RLS and share capability probes).
        patterns = ["test_database.py", "test_auth_bootstrap.py", "test_ownership_rls.py",
                    "test_home_aggregation.py", "test_archive_import.py",
                    "test_dataset_staging.py", "test_metrics.py",
                    "test_refresh_adapter.py", "test_chart_registry.py",
                    "test_delivery_apis.py", "test_saved_charts.py", "test_snapshots.py",
                    "test_profile.py", "test_documents.py", "test_chart_blocks.py",
                    "test_model_blocks.py", "test_document_insights.py", "test_publications.py",
                    "test_integrity.py",
                    "test_models_readiness.py",
                    "test_models_fit.py", "test_models_diagnostics.py",
                    "test_models_publication.py", "test_models_public_apis.py",
                    "test_exports_ir.py", "test_exports_jobs.py",
                    "test_shares.py",
                    "test_invariants_db_chain.py",
                    "test_security_http_ownership.py", "test_security_rls_probes.py",
                    "test_security_shares.py"]
        if args.suite == "landing":
            patterns = ["test_landing_integration.py"]
        if args.suite == "insights":
            patterns = ["test_home_aggregation.py", "test_documents.py", "test_insights.py", "test_document_insights.py"]
        if args.suite == "exports":
            patterns = ["test_exports_ir.py", "test_exports_jobs.py"]
        if args.suite == "publications":
            patterns = ["test_publications.py"]
        if args.suite == "history":
            patterns = ["test_chart_registry.py", "test_delivery_apis.py", "test_research_history.py"]
        # NI-030 bounded authorized live smoke: only when the operator
        # explicitly sets NI_LIVE_SMOKE=1 in the invoking environment (the same
        # gate the smoke file itself requires) does one real finalized-header
        # request run inside this disposable cluster, after the standard suites.
        if args.suite == "all" and os.environ.get("NI_LIVE_SMOKE") == "1":
            environment["NI_LIVE_SMOKE"] = "1"
            patterns.append("test_refresh_live_smoke.py")
        if args.saved_charts_http:
            patterns = ["test_saved_charts.py", "test_snapshots.py", "test_saved_charts_http.py"]
        if args.chart_insertion_http:
            patterns = ["test_chart_blocks.py", "test_chart_insertion_http.py"]
        if args.workspace_home_http:
            patterns = ["test_home_aggregation.py", "test_workspace_home_http.py"]
        returncode = 0
        with test_log.open("wb") as log:
            for pattern in patterns:
                result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "apps/api/tests",
                                         "-p", pattern, "-v"], cwd=repo, env=environment,
                                        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        timeout=300 if os.environ.get("NI_BROWSER_HANDOFF") == "1" else 120,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if result.returncode and not returncode:
                    returncode = result.returncode
        report = test_log.read_text(encoding="utf-8", errors="replace")
        for key in ("PGPASSWORD", "DB_RUNTIME_PASSWORD", "DB_MIGRATION_PASSWORD",
                    "DB_OPERATOR_PASSWORD", "DB_PUBLIC_PASSWORD"):
            report = report.replace(environment[key], "[redacted]")
        print(report, flush=True)
        if not report or "skipped=" in report:
            raise RuntimeError("Integration tests must execute; no-output/skip is not a pass")
        return returncode
    finally:
        if started:
            try:
                run_pg("pg_ctl", "-D", data, "-m", "fast", "-w", "-t", "20", "stop")
                stopped = True
            except Exception:
                print(f"Cluster stop needs attention; retained isolated files at {directory}", file=sys.stderr)
                raise
        if (not started or stopped) and directory.parent == local and directory.name.startswith("ni003-pg-"):
            shutil.rmtree(directory)


if __name__ == "__main__":
    sys.exit(main())
