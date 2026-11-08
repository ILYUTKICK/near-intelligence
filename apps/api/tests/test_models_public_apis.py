"""NI-054 tests: the operator publish flow, migration 0010, the RLS matrix and
the public model APIs.

Offline classes run everywhere (request validation answered before any
database access); DB classes need scripts/run-db-tests.py. A skip is never
integration evidence. All bundles are the synthetic NI-054 fixtures built from
the committed preregistered configs — no real archive, no provider, no network;
publication happens through the real operator CLI against the disposable
cluster.
"""

import json
import os
import shutil
import unittest
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from near_api.auth.principal import get_runtime_engine
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.main import app
from near_api.research.publication import load_bundle, verify_bundle
from near_api.research.publish_store import PublishConflictError, publish_run
from test_models_publication import (MANIFEST_KEYS, bundle_dir, canonical_artifact_hash,
                                     derive_run_id, valid_bundle)

REPO_ROOT = Path(__file__).resolve().parents[3]


class ModelRouteValidationTests(unittest.TestCase):
    """HTTP validation answered before any database access (no cluster)."""

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_runtime_engine] = lambda: None
        cls.client = TestClient(app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_runtime_engine, None)

    def test_validation_gates(self):
        cases = (
            ("/api/model-runs", {"model_id": "UPPER_CASE"}, 422),
            ("/api/model-runs", {"cursor": "%%%"}, 422),
            ("/api/model-runs", {"limit": "101"}, 422),
            ("/api/model-runs/definitely-not-a-uuid", {}, 422),
            ("/api/model-runs/also-not-a-uuid/manifest", {}, 422),
            ("/api/model-definitions/Not-A-Spec", {}, 422),
            ("/api/model-definitions/gross_fee_activity_v1", {"version": "0"}, 422),
        )
        for path, params, expected in cases:
            with self.subTest(path=path, params=params):
                response = self.client.get(path, params=params or None)
                self.assertEqual(response.status_code, expected)

    def test_every_model_route_is_read_only_get(self):
        for route in app.routes:
            if getattr(route, "path", "").startswith(("/api/model-runs",
                                                      "/api/model-definitions")):
                self.assertEqual(route.methods, {"GET"},
                                 f"{route.path} must be a read-only GET")


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ModelMigrationRoundTripTests(unittest.TestCase):
    """Migration 0010 round trip, RLS flags and metadata drift check."""

    @classmethod
    def setUpClass(cls):
        cls.repo = REPO_ROOT
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"],
                                  poolclass=NullPool, hide_parameters=True)
        command.upgrade(cls.config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.admin.dispose()

    def test_round_trip_and_metadata(self):
        command.downgrade(self.config, "0009_idempotency_records")
        with self.admin.connect() as connection:
            self.assertIsNone(connection.scalar(
                text("SELECT to_regclass('app.model_runs')")))
        command.upgrade(self.config, "head")
        command.check(self.config)
        with self.admin.connect() as connection:
            row = connection.execute(text("""
                SELECT relrowsecurity, relforcerowsecurity,
                       pg_get_userbyid(relowner) AS owner
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app' AND relname = 'model_runs'
            """)).mappings().one()
            self.assertTrue(row["relrowsecurity"])
            self.assertTrue(row["relforcerowsecurity"])
            grants = connection.execute(text("""
                SELECT privilege_type FROM information_schema.role_table_grants
                WHERE table_schema = 'app' AND table_name = 'model_runs'
                      AND grantee = 'near_app'
            """)).scalars().all()
            self.assertEqual(sorted(grants), ["SELECT"])


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ModelPublicationDatabaseTests(unittest.TestCase):
    """Publish flow, RLS matrix and the public model APIs."""

    @classmethod
    def setUpClass(cls):
        cls.repo = REPO_ROOT
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"],
                                            pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"],
                                     poolclass=NullPool, hide_parameters=True)
        cls.public = create_engine(os.environ["NI_TEST_PUBLIC_URL"],
                                   poolclass=NullPool, hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"],
                                  poolclass=NullPool, hide_parameters=True)
        command.upgrade(cls.config, "head")
        cls.directory = Path(os.environ["NI_TEST_TMP_DIR"]) / "ni054-bundle"
        cls.directory.mkdir(parents=True, exist_ok=True)
        cls.bundle_path = bundle_dir(cls.directory, valid_bundle())
        cls._publish_cli()
        cls.run_id = derive_run_id(
            {key: canonical_artifact_hash(json.loads(
                (cls.bundle_path / f"{key}.json").read_text("utf-8")))
             for key in MANIFEST_KEYS})
        app.dependency_overrides[get_runtime_engine] = lambda: cls.runtime
        cls.client = TestClient(app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_runtime_engine, None)
        cls.runtime.dispose()
        cls.operator.dispose()
        cls.public.dispose()
        cls.admin.dispose()
        shutil.rmtree(cls.directory, ignore_errors=True)

    @classmethod
    def _publish_cli(cls):
        import subprocess
        import sys
        completed = subprocess.run(
            [sys.executable, "-m", "near_api.research", "publish",
             "--bundle", str(cls.bundle_path),
             "--database-url", os.environ["NI_TEST_OPERATOR_URL"]],
            cwd=cls.repo, env={**os.environ,
                               "PYTHONPATH": str(cls.repo / "apps/api/src")},
            capture_output=True, text=True, timeout=300)
        cls.publish_output = completed.stdout + completed.stderr
        cls.publish_returncode = completed.returncode

    # -- publish flow -------------------------------------------------------- #

    def test_01_cli_publish_wrote_exactly_one_published_row(self):
        self.assertEqual(self.publish_returncode, 0, self.publish_output)
        self.assertIn('"published": true', self.publish_output)
        with self.operator.connect() as connection:
            rows = connection.execute(text("""
                SELECT run_id, spec_id, gate_verdict, status, nobs,
                       sample_start, sample_end_exclusive
                FROM app.model_runs
            """)).mappings().all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_id"], self.run_id)
        self.assertEqual(rows[0]["spec_id"], "gross_fee_activity_v1")
        self.assertEqual(rows[0]["gate_verdict"], "READY_WITH_LIMITS")
        self.assertEqual(rows[0]["status"], "published")
        self.assertEqual(rows[0]["nobs"], 60)

    def test_02_republish_identical_bundle_is_idempotent(self):
        result = publish_run(os.environ["NI_TEST_OPERATOR_URL"],
                             load_bundle(self.bundle_path), self.run_id)
        self.assertTrue(result.already_published)
        with self.operator.connect() as connection:
            count = connection.scalar(text("SELECT count(*) FROM app.model_runs"))
        self.assertEqual(count, 1)

    def test_03_same_content_different_approval_is_a_conflict(self):
        bundle = load_bundle(self.bundle_path)
        bundle["publication_approval"] = {
            **bundle["publication_approval"], "notes": "re-review with different notes"}
        with self.assertRaises(PublishConflictError):
            publish_run(os.environ["NI_TEST_OPERATOR_URL"], bundle, self.run_id)

    def test_04_gate_refuses_broken_bundles_before_any_write(self):
        bundle = load_bundle(self.bundle_path)
        bundle["fit_manifest"]["estimation"]["r_squared"] = 0.0
        self.assertFalse(verify_bundle(bundle).passed)
        with self.operator.connect() as connection:
            count = connection.scalar(text("SELECT count(*) FROM app.model_runs"))
        self.assertEqual(count, 1, "a refused bundle must never reach the database")

    # -- RLS matrix ---------------------------------------------------------- #

    def test_10_near_app_reads_published_and_cannot_write(self):
        # Each refusal runs in its own transaction: a failed statement aborts
        # its transaction, and the next statement there would report the
        # aborted-state error (25P02) instead of the real permission code.
        with user_transaction(self.runtime, None) as connection:
            row = connection.execute(text("""
                SELECT spec_id, status FROM app.model_runs WHERE run_id = :run_id
            """), {"run_id": str(self.run_id)}).mappings().first()
            self.assertIsNotNone(row, "near_app must read published runs")
            self.assertEqual(row["status"], "published")
        with user_transaction(self.runtime, None) as connection:
            with self.assertRaises(SQLAlchemyError) as raised:
                connection.execute(text("""
                    INSERT INTO app.model_runs (run_id, spec_id, spec_version,
                          gate_verdict, status, manifests, artifacts,
                          publication_approval, code_commit, dependency_lock_sha256,
                          coefficient_rtol, coefficient_atol, sample_start,
                          sample_end_exclusive, nobs, published_by)
                    VALUES (gen_random_uuid(), 'x', 1, 'READY', 'published', '{}',
                            '{}', '{}', 'a', 'b', '1', '1', '2026-01-01',
                            '2026-01-02', 1, 'attacker')
                """))
            self.assertEqual(raised.exception.orig.sqlstate, "42501")
        with user_transaction(self.runtime, None) as connection:
            with self.assertRaises(SQLAlchemyError) as raised_update:
                connection.execute(text("UPDATE app.model_runs SET nobs = 1"))
            self.assertEqual(raised_update.exception.orig.sqlstate, "42501")
        with user_transaction(self.runtime, None) as connection:
            with self.assertRaises(SQLAlchemyError) as raised_delete:
                connection.execute(text("DELETE FROM app.model_runs"))
            self.assertEqual(raised_delete.exception.orig.sqlstate, "42501")

    def test_11_near_operator_cannot_mutate_published_rows(self):
        with self.operator.begin() as connection:
            with self.assertRaises(SQLAlchemyError) as raised_update:
                connection.execute(text("UPDATE app.model_runs SET nobs = 1"))
            self.assertEqual(raised_update.exception.orig.sqlstate, "42501")
        with self.operator.begin() as connection:
            with self.assertRaises(SQLAlchemyError) as raised_delete:
                connection.execute(text("DELETE FROM app.model_runs"))
            self.assertEqual(raised_delete.exception.orig.sqlstate, "42501")

    def test_12_near_public_is_locked_out_by_force_rls(self):
        with self.assertRaises(SQLAlchemyError) as raised:
            with self.public.connect() as connection:
                connection.execute(text("SELECT count(*) FROM app.model_runs"))
        self.assertIsInstance(raised.exception, ProgrammingError)
        self.assertEqual(raised.exception.orig.sqlstate, "42501")

    # -- public model APIs --------------------------------------------------- #

    def test_20_catalog_lists_the_published_run_only(self):
        response = self.client.get("/api/model-runs")
        self.assertEqual(response.status_code, 200)
        document = response.json()
        self.assertEqual(len(document["items"]), 1)
        summary = document["items"][0]
        self.assertEqual(summary["run_id"], str(self.run_id))
        self.assertEqual(summary["model_id"], "gross_fee_activity_v1")
        self.assertEqual(summary["gate_verdict"], "READY_WITH_LIMITS")
        self.assertEqual(summary["sample"]["nobs"], 60)
        self.assertEqual(summary["tolerances"]["coefficient_rtol"], "0.00000001")
        self.assertIn("published_at", summary)
        self.assertIn("manifest_url", summary)
        # A rejected/unpublished specification has no run row to leak.
        filtered = self.client.get("/api/model-runs",
                                   params={"model_id": "true_revenue_daily_v1"})
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["items"], [])

    def test_21_unknown_run_is_a_generic_404_without_existence_leak(self):
        response = self.client.get(f"/api/model-runs/{uuid4()}")
        self.assertEqual(response.status_code, 404)
        error = response.json()["error"]
        self.assertEqual(error["code"], "NOT_FOUND")
        self.assertFalse(error["retryable"])
        manifest = self.client.get(f"/api/model-runs/{uuid4()}/manifest")
        self.assertEqual(manifest.status_code, 404)
        self.assertEqual(manifest.json()["error"]["code"], "NOT_FOUND")

    def test_22_run_detail_serves_recorded_results(self):
        response = self.client.get(f"/api/model-runs/{self.run_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"],
                         "public, max-age=31536000, immutable")
        detail = response.json()
        self.assertEqual(detail["specification"]["spec_id"], "gross_fee_activity_v1")
        names = [coefficient["name"] for coefficient in detail["coefficients"]]
        self.assertEqual(names, ["const", "dlog_provider_intents_volume_usd"])
        for coefficient in detail["coefficients"]:
            self.assertTrue(coefficient["std_error"] > 0)
            self.assertLessEqual(coefficient["ci95_low"], coefficient["ci95_high"])
        self.assertEqual(detail["estimation"]["method"], "OLS")
        self.assertIn("stationarity", detail["diagnostics"])
        self.assertIn("residual_diagnostics", detail["diagnostics"])
        self.assertIn("sensitivity", detail["diagnostics"])
        self.assertEqual(detail["interpretation"]["template_id"],
                         "bounded_association_v1")
        self.assertEqual(detail["limitations"]["prohibited_labels"],
                         ["protocol_revenue", "token_valuation", "causal_effect"])
        self.assertIn("Mechanical construction warning",
                      detail["limitations"]["spec_limitation_notes"][0])
        self.assertEqual(detail["approval"]["decision"], "approve")
        self.assertIn("reviewer", detail["approval"])
        # The detailed response carries no wall-clock fit field: published_at is
        # the DB authoring time, the manifests stay deterministic.

    def test_23_manifest_bundle_round_trips_through_the_offline_verifier(self):
        response = self.client.get(f"/api/model-runs/{self.run_id}/manifest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"],
                         "public, max-age=31536000, immutable")
        self.assertEqual(response.headers["ETag"], f'"{self.run_id}"')
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
        served = self.directory / "served-manifest.json"
        served.write_text(json.dumps(response.json(), sort_keys=True), encoding="utf-8")
        bundle = load_bundle(served)
        self.assertEqual(bundle["run_id"], self.run_id)
        report = verify_bundle(bundle)
        failures = [check.detail for check in report.checks if not check.passed]
        self.assertEqual(failures, [], "the served bundle must verify offline")

    def test_24_definitions_come_from_published_runs(self):
        response = self.client.get("/api/model-definitions")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        definition = items[0]
        self.assertEqual(definition["model_id"], "gross_fee_activity_v1")
        self.assertEqual(definition["version"], 1)
        self.assertIn("gross_provider_fees", definition["question"])
        self.assertEqual(definition["required_metric_ids"],
                         ["provider_gross_fees_usd", "provider_intents_volume_usd"])
        self.assertIn("min_complete_daily_observations", definition["readiness_rules"])
        self.assertIn("Mechanical construction warning",
                      definition["limitations"]["spec_limitation_notes"][0])
        single = self.client.get("/api/model-definitions/gross_fee_activity_v1")
        self.assertEqual(single.status_code, 200)
        self.assertEqual(single.json()["id"], definition["id"])
        # A gate-evaluated-but-unpublished specification has no public definition.
        missing = self.client.get("/api/model-definitions/true_revenue_daily_v1")
        self.assertEqual(missing.status_code, 404)
        unknown = self.client.get("/api/model-definitions/no_such_model_v9")
        self.assertEqual(unknown.status_code, 404)

    def test_25_readiness_serves_the_recorded_gate_verdicts(self):
        admitted = self.client.get(
            "/api/model-definitions/gross_fee_activity_v1/readiness")
        self.assertEqual(admitted.status_code, 200)
        verdict = admitted.json()
        self.assertTrue(verdict["ready"])
        self.assertEqual(verdict["verdict"], "READY_WITH_LIMITS")
        self.assertEqual(verdict["overall_verdict"], "PROXY_ONLY_READY_WITH_LIMITS")
        self.assertEqual(verdict["selected_specification"], "gross_fee_activity_v1")
        self.assertEqual(verdict["recorded_in_run_id"], str(self.run_id))
        self.assertTrue(any(reason["severity"] == "limit"
                            for reason in verdict["reasons"]))
        # The same published report honestly records the not-ready verdicts.
        not_ready = self.client.get(
            "/api/model-definitions/true_revenue_daily_v1/readiness")
        self.assertEqual(not_ready.status_code, 200)
        self.assertFalse(not_ready.json()["ready"])
        self.assertEqual(not_ready.json()["verdict"], "NOT_READY")
        self.assertTrue(not_ready.json()["reasons"],
                        "a NOT_READY verdict records its rejecting reasons")
        # A specification no published report ever evaluated is the same 404.
        unknown = self.client.get("/api/model-definitions/no_such_model_v9/readiness")
        self.assertEqual(unknown.status_code, 404)

    def test_26_published_jsonb_survives_the_round_trip_byte_stably(self):
        # The manifest bundle served from jsonb must hash identically to the
        # approved local artifacts (the approval binding depends on it).
        response = self.client.get(f"/api/model-runs/{self.run_id}/manifest")
        document = response.json()
        artifacts = document["artifact_sha256"]
        for key in MANIFEST_KEYS:
            self.assertEqual(canonical_artifact_hash(document["manifests"][key]),
                             artifacts[key],
                             f"{key} changed bytes across the jsonb round trip")


if __name__ == "__main__":
    unittest.main()
