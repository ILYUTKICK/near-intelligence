"""NI-030 bounded authorized live smoke: exactly ONE real finalized-header request.

Operator authorization: OQ-03 RESOLVED 2026-11-06 (participant A, ILYUTKICK,
docs/OPEN_QUESTIONS.md) — public NEAR mainnet RPC ``https://rpc.mainnet.near.org``,
1 request/minute, <=1440/day, budget 0, header-only responses with the
implemented byte caps, public on-chain header data. This file is deliberately
NOT part of the run-db-tests.py CI discovery list (the same pattern as the
NI-029 real-archive suite): it runs only when BOTH environment gates are set —

    NI_ISOLATED_PG_TEST=1   (a disposable loopback cluster context is live)
    NI_LIVE_SMOKE=1         (the operator explicitly asks for the live request)

With any other invocation the whole class skips without any network I/O. The
test performs exactly one ``run_once`` (one provider request) through the same
guarded adapter the CLI uses, asserts the sanitized schema/freshness invariants
and records the fresh block height/hash/time for the NI-030 verification
evidence.
"""

import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.datasets.service import create_dataset_operator_engine
from near_api.ingestion.providers.finalized_header import (
    DATASET_KEY,
    SOURCE_ID,
    FinalizedHeaderRefresh,
)

LIVE = (os.environ.get("NI_ISOLATED_PG_TEST") == "1"
        and os.environ.get("NI_LIVE_SMOKE") == "1")


@unittest.skipUnless(LIVE, "Bounded live smoke: set NI_ISOLATED_PG_TEST=1 and "
                           "NI_LIVE_SMOKE=1 with an operator-authorized run")
class FinalizedHeaderLiveSmoke(unittest.TestCase):
    """One real approved refresh against the OQ-03-approved public endpoint."""

    def test_01_one_real_refresh_publishes_fresh_finalized_header(self):
        repo = Path(__file__).resolve().parents[3]
        config = Config(str(repo / "apps/api/alembic.ini"))
        operator = create_dataset_operator_engine(os.environ["NI_TEST_OPERATOR_URL"])
        command.upgrade(config, "head")
        with operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.sources(id, name, docs_url, base_url, access_status,
                                        license_status)
                VALUES ('SRC-NEAR-RPC', 'NEAR public RPC',
                        'https://docs.near.org/api/rpc/providers',
                        'https://rpc.mainnet.near.org', 'approved', 'verified')
                ON CONFLICT (id) DO UPDATE SET access_status = 'approved',
                    base_url = EXCLUDED.base_url
            """))
            from near_api.metrics import register_definitions
            register_definitions(connection)
        with tempfile.TemporaryDirectory(prefix="ni030-live-") as directory:
            root = Path(directory)
            refresh = FinalizedHeaderRefresh(operator, root / "storage",
                                             Path(os.environ["NI_TEST_TMP_DIR"]))
            started_at = dt.datetime.now(dt.timezone.utc)
            report = refresh.run_once()  # the single authorized real request
            finished_at = dt.datetime.now(dt.timezone.utc)
        operator.dispose()

        self.assertEqual(report["status"], "published", report)
        self.assertEqual(report["source_id"], SOURCE_ID)
        self.assertEqual(report["dataset_key"], DATASET_KEY)
        height, block_hash = report["height"], report["block_hash"]
        self.assertIsInstance(height, int)
        self.assertGreater(height, 200_000_000)  # mainnet finalized head magnitude
        self.assertRegex(block_hash, r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
        header_time = dt.datetime.fromisoformat(report["block_timestamp_utc"])
        self.assertIsNotNone(header_time.tzinfo)
        lag = finished_at - header_time
        self.assertLess(lag.total_seconds(), 3600,
                        "the finalized header must be fresh (well under the 60 min "
                        "staleness target)")
        # The published dataset version is the active pointer for the key.
        admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool)
        try:
            with admin.connect() as connection:
                active = connection.execute(text("""
                    SELECT v.version, v.status FROM app.active_datasets a
                    JOIN app.dataset_versions v ON v.id = a.dataset_version_id
                    WHERE a.dataset_key = :key
                """), {"key": DATASET_KEY}).mappings().one()
                point = connection.execute(text(
                    "SELECT last_height, last_block_hash, last_failure_kind "
                    "FROM app.ingestion_checkpoints WHERE source_id = :id"),
                    {"id": SOURCE_ID}).mappings().one()
        finally:
            admin.dispose()
        self.assertEqual(active["status"], "approved")
        self.assertEqual(point["last_height"], height)
        self.assertEqual(point["last_block_hash"], block_hash)
        self.assertIsNone(point["last_failure_kind"])
        # Recorded evidence (visible in -v output).
        print(f"\nNI-030 live smoke evidence: request {started_at.isoformat()} -> "
              f"{finished_at.isoformat()} | final block height={height} "
              f"hash={block_hash} header_time={report['block_timestamp_utc']} "
              f"lag_seconds={lag.total_seconds():.3f} "
              f"dataset_version={report['dataset_version_id']} "
              f"content_sha256={report['content_sha256']}", flush=True)


if __name__ == "__main__":
    unittest.main()
