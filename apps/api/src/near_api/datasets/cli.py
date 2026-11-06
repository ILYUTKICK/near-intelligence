"""Operator CLI for dataset staging, validation, publication and history.

Implemented verbs (operator-only; no browser may call these — DATA_PIPELINE.md):

- ``python -m near_api.datasets stage --manifest PATH --storage-root DIR --database-url URL``
  Parse the prepared manifest, persist input artifacts, stage observations and
  run validation in ONE transaction: the committed status is ``validated`` or
  ``rejected``; a contract/verification failure leaves zero rows.
- ``python -m near_api.datasets stage-from-import --batch MANIFEST_SHA256 --binding PATH
  --storage-root DIR --database-url URL`` — same, with observation records read
  from the files of an already verified NI-027 import batch (offline).
- ``python -m near_api.datasets validate --id UUID --database-url URL`` — re-run
  the validation gate; failure marks the version ``rejected`` and never
  touches the active pointer.
- ``python -m near_api.datasets publish --id UUID --database-url URL`` — approve
  a validated version and switch the active pointer in one transaction
  (advisory lock; previous pointer retained on any failure).
- ``python -m near_api.datasets show (--id UUID | --key KEY) --database-url URL``
  — query the active version, full history (all hashes) and observations.

Exit codes: 0 success, 3 validation/verification/publish refusal, 4 contract
error, 5 database error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from near_api.datasets.from_import import stage_from_import
from near_api.datasets.manifest import ManifestFormatError
from near_api.datasets.service import (
    MAX_QUERY_PAGE,
    DatasetContractError,
    DatasetLookupError,
    DatasetVerificationError,
    PublishRefused,
    _assert_operator,
    active_version,
    create_dataset_operator_engine,
    get_version,
    list_inputs,
    list_observations,
    publish,
    stage,
    validate,
    version_history,
)
from near_api.ingestion.archive import OperatorDatabaseError

EXIT_OK = 0
EXIT_VERIFICATION = 3
EXIT_CONTRACT = 4
EXIT_DATABASE = 5

_BATCH_SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def _batch_sha(value: str) -> str:
    if not _BATCH_SHA_PATTERN.match(value):
        raise argparse.ArgumentTypeError("batch must be a lowercase SHA-256 hex string")
    return value


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a UUID") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m near_api.datasets", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_parser = subparsers.add_parser("stage", help="stage and validate a prepared manifest")
    stage_parser.add_argument("--manifest", type=Path, required=True)
    stage_parser.add_argument("--storage-root", type=Path, required=True)
    stage_parser.add_argument("--database-url", required=True)

    import_parser = subparsers.add_parser(
        "stage-from-import",
        help="stage and validate from a verified NI-027 archive import batch")
    import_parser.add_argument("--batch", type=_batch_sha, required=True,
                               help="manifest SHA-256 of the verified import batch")
    import_parser.add_argument("--binding", type=Path, required=True)
    import_parser.add_argument("--storage-root", type=Path, required=True)
    import_parser.add_argument("--database-url", required=True)

    validate_parser = subparsers.add_parser("validate", help="re-run the validation gate")
    validate_parser.add_argument("--id", type=_uuid, required=True)
    validate_parser.add_argument("--database-url", required=True)

    publish_parser = subparsers.add_parser(
        "publish", help="approve a validated version and switch the active pointer")
    publish_parser.add_argument("--id", type=_uuid, required=True)
    publish_parser.add_argument("--database-url", required=True)

    show_parser = subparsers.add_parser("show", help="query active/history/observations")
    show_group = show_parser.add_mutually_exclusive_group(required=True)
    show_group.add_argument("--id", type=_uuid)
    show_group.add_argument("--key")
    show_parser.add_argument("--observations", type=int, default=50,
                             help=f"observation page size (1..{MAX_QUERY_PAGE})")
    show_parser.add_argument("--database-url", required=True)
    return parser


def _show(engine, args) -> dict:
    with engine.connect() as connection:
        _assert_operator(connection)
        if args.id is not None:
            version = get_version(connection, args.id)
            if version is None:
                raise DatasetLookupError(f"Dataset version {args.id} does not exist")
            page = list_observations(connection, args.id, limit=args.observations)
            return {"version": version, "inputs": list_inputs(connection, args.id),
                    "observations": page}
        history = version_history(connection, args.key)
        if not history:
            raise DatasetLookupError(f"Dataset key {args.key!r} has no versions")
        return {"active": active_version(connection, args.key), "history": history}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = create_dataset_operator_engine(args.database_url)
    try:
        if args.command == "stage":
            result = stage(engine, args.manifest, args.storage_root)
            _print({"staged": True, "deduplicated": result.deduplicated,
                    "dataset_version_id": str(result.dataset_version_id),
                    "dataset_key": result.dataset_key, "version": result.version,
                    "content_sha256": result.content_sha256, "status": result.status,
                    "observations": result.observation_count, "inputs": result.input_count,
                    "validation": result.validation})
            return EXIT_OK if result.status == "validated" else EXIT_VERIFICATION
        if args.command == "stage-from-import":
            result = stage_from_import(engine, args.batch, args.binding, args.storage_root)
            _print({"staged": True, "deduplicated": result.deduplicated,
                    "dataset_version_id": str(result.dataset_version_id),
                    "dataset_key": result.dataset_key, "version": result.version,
                    "content_sha256": result.content_sha256, "status": result.status,
                    "observations": result.observation_count, "inputs": result.input_count,
                    "validation": result.validation})
            return EXIT_OK if result.status == "validated" else EXIT_VERIFICATION
        if args.command == "validate":
            _print(validate(engine, args.id))
            return EXIT_OK
        if args.command == "publish":
            _print(publish(engine, args.id))
            return EXIT_OK
        if args.command == "show":
            _print(_show(engine, args))
            return EXIT_OK
        raise DatasetContractError(f"Unknown command {args.command!r}")
    except (DatasetContractError, ManifestFormatError) as error:
        print(f"contract error: {error}", file=sys.stderr)
        return EXIT_CONTRACT
    except (DatasetVerificationError, DatasetLookupError, PublishRefused) as error:
        print(f"verification error: {error}", file=sys.stderr)
        return EXIT_VERIFICATION
    except OperatorDatabaseError as error:
        print(f"operator database error: {error}", file=sys.stderr)
        return EXIT_DATABASE
    except SQLAlchemyError as error:
        print(f"database error: {error}", file=sys.stderr)
        return EXIT_DATABASE
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
