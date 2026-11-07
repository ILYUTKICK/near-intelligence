"""Operator CLI for one bounded scheduled refresh attempt (NI-030).

``python -m near_api.ingestion.refresh --once --database-url URL --storage-root DIR
[--repo-root DIR] [--source SRC-NEAR-RPC]``

There is no daemon and no loop: every invocation performs at most one guarded
refresh attempt (one provider request at most). Scheduling is an explicit
operator opt-in through a host cron/systemd timer calling this same command
(see docs/DEPLOYMENT.md); nothing in the application starts it automatically
and the effective source allowlist starts empty until an operator approves a
row in ``app.sources``. Requires the dedicated unprivileged ``near_operator``
credential, exactly like the NI-027/NI-028 operator verbs.

Exit codes: 0 = published or unchanged (success); 3 = refused before any
network request (budget exhausted, source not approved, scheduler overlap,
stop marker); 4 = failed after the attempt (HTTP 429/auth failure/outage,
schema violation, height regression, publish error) — the last good approved
version is retained and the failure is recorded on the checkpoint; 5 =
database/credential error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from near_api.ingestion.archive import OperatorDatabaseError, create_operator_engine
from near_api.ingestion.providers.finalized_header import (
    SOURCE_ID,
    FinalizedHeaderRefresh,
    RefreshFailed,
    RefreshRefused,
)

EXIT_OK = 0
EXIT_REFUSED = 3
EXIT_FAILED = 4
EXIT_DATABASE = 5


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m near_api.ingestion.refresh",
        description="One bounded scheduled refresh attempt (NI-030); --once only.")
    parser.add_argument("--once", action="store_true", required=True,
                        help="Perform exactly one guarded refresh attempt (no loop).")
    parser.add_argument("--database-url", required=True,
                        help="near_operator psycopg database URL")
    parser.add_argument("--storage-root", type=Path, required=True,
                        help="Content-addressed artifact storage root (NI-028)")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(),
                        help="Repository root for STOP_PUBLIC_COLLECTION marker checks "
                             "(default: current working directory)")
    parser.add_argument("--source", default=SOURCE_ID,
                        help=f"Source identifier (only {SOURCE_ID} is implemented)")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        engine = create_operator_engine(arguments.database_url)
    except OperatorDatabaseError as error:
        _print({"status": "database_error", "reason": str(error)})
        return EXIT_DATABASE
    refresh = FinalizedHeaderRefresh(engine, arguments.storage_root, arguments.repo_root,
                                     source_id=arguments.source)
    try:
        report = refresh.run_once()
    except RefreshRefused as refused:
        _print({"status": "refused", "reason": refused.kind, "source_id": arguments.source,
                "detail": str(refused)})
        return EXIT_REFUSED
    except RefreshFailed as failure:
        _print({"status": "failed", "failure_kind": failure.kind,
                "source_id": arguments.source, "detail": str(failure),
                "last_good": "retained (see app.ingestion_checkpoints / "
                             "app.active_datasets)"})
        # Guard/publish database errors report as database failures (exit 5);
        # everything else consumed the attempt and retains the last good (exit 4).
        return EXIT_DATABASE if failure.kind == "database_error" else EXIT_FAILED
    except (SQLAlchemyError, OperatorDatabaseError) as error:
        _print({"status": "database_error", "reason": type(error).__name__,
                "source_id": arguments.source})
        return EXIT_DATABASE
    finally:
        engine.dispose()
    _print(report)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
