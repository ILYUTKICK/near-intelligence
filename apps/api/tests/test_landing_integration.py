"""NI-086: editorial Overview resilience plus preserved real metric delivery.

Run through run-db-tests.py --suite landing after the frozen web build.
Default data is explicitly synthetic. NI_LANDING_ARCHIVE_ROOT opts into
read-only saved-input reproduction; no provider or real database is used.
"""

import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import unittest

from alembic import command
from alembic.config import Config
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.datasets.service import publish, stage
from near_api.metrics.emit import DatasetSpec, ManifestInputSpec, build_manifest
from near_api.metrics.loaders import load_metric_inputs
from near_api.metrics.registry import definition_by_metric_id_version, register_definitions
from test_delivery_apis import SOURCE_IDS, manifest_document, observation

START, END = "2026-08-06", "2026-11-04"
METRICS = ("observed_near_purchases", "treasury_payouts_near", "provider_gross_fees_usd")


class LandingHTML(HTMLParser):
    """Visible Overview text/links, excluding React scripts and CSS payloads."""

    def __init__(self, html: str):
        super().__init__()
        self.parts: list[str] = []
        self.links: set[str] = set()
        self.ids: set[str] = set()
        self.hidden = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if not self.hidden:
            attributes = dict(attrs)
            if attributes.get("id"):
                self.ids.add(attributes["id"])
            if tag == "a" and attributes.get("href"):
                self.links.add(attributes["href"])

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    @property
    def visible(self) -> str:
        return " ".join(" ".join(self.parts).split())


def unused_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py --suite landing")
class LandingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[3]
        self.directory = Path(os.environ["NI_TEST_TMP_DIR"]) / "landing"
        self.directory.mkdir()
        self.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"],
                                      poolclass=NullPool, hide_parameters=True)
        self.addCleanup(self.operator.dispose)
        command.upgrade(Config(str(self.repo / "apps/api/alembic.ini")), "head")
        with self.operator.begin() as connection:
            for source_id, name in SOURCE_IDS.items():
                connection.execute(text("""
                    INSERT INTO app.sources(id, name, access_status, license_status)
                    VALUES (:id, :name, 'documented', 'unverified') ON CONFLICT DO NOTHING
                """), {"id": source_id, "name": name})
            register_definitions(connection)
        self.http = httpx.Client(timeout=30, trust_env=False)
        self.addCleanup(self.http.close)

    def start_process(self, name: str, arguments: list[str], environment: dict,
                      cwd: Path, url: str):
        log = (self.directory / f"{name}.log").open("wb")
        self.addCleanup(log.close)
        process = subprocess.Popen(arguments, cwd=cwd, env=environment,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL)
        self.addCleanup(self.stop_process, process)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.fail(f"{name} exited before readiness; inspect its local log")
            try:
                if self.http.get(url).status_code == 200:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        self.fail(f"{name} failed its bounded readiness check")

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    def prepared_manifest(self) -> tuple[dict, dict[Path, str]]:
        archive = os.environ.get("NI_LANDING_ARCHIVE_ROOT")
        if archive:
            root = Path(archive).resolve(strict=True)
            flows = root / "near-longitudinal/data/flows_90d_raw.json"
            daily = root / "near-dollar/analysis/daily.json"
            hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (flows, daily)}
            inputs = load_metric_inputs(
                window_start=dt.date.fromisoformat(START),
                window_end_exclusive=dt.date.fromisoformat(END),
                flows_path=flows, daily_flows_path=daily)
            # Do not invent source/retrieval timestamps from file mtimes.
            document = build_manifest(
                inputs, dataset_key="metrics.flows.daily",
                dataset_spec=DatasetSpec(pipeline_version="ni012-offline-verification"),
                manifest_inputs=(ManifestInputSpec("flows", flows, "raw", "SRC-BQ"),
                                 # The derived daily file contains both
                                 # provider variants, not only SRC-LLAMA.
                                 ManifestInputSpec("daily", daily, "normalized")))
            return document, hashes
        # Stage exactly the definition versions this test queries: the series
        # requests pin definition_version 1, so the payout metric must stage
        # its v1 aggregate id (NI-071 registered a v2 per-recipient version
        # that the latest-pointer shortcut would otherwise bind instead).
        metric_ids = [definition_by_metric_id_version(name, 1).id for name in METRICS]
        records = []
        for metric in metric_ids:
            # Exact precision beyond binary float; isolated regression data.
            for day_index in range(90):
                day = dt.date.fromisoformat(START) + dt.timedelta(days=day_index)
                value = "123456789012345678.123456789012345678901234" if day_index == 89 else None
                records.append(observation(metric, day, value=value))
        document = manifest_document("ni012.synthetic", records, member_metrics=metric_ids,
                                     window=(START, END))
        return document, {}

    def assert_editorial_overview(self, parsed: LandingHTML):
        self.assertIn("Understand NEAR.", parsed.visible)
        self.assertIn("Build your own thesis.", parsed.visible)
        self.assertIn("The research, in focus.", parsed.visible)
        self.assertEqual(parsed.visible.count("A conversion channel."), 1)
        for label in ("Intents activity", "Revenue & fees", "Token economics",
                      "Sources first. Assumptions visible.", "Make the research your own."):
            self.assertIn(label, parsed.visible)
        for path in ("/blog", "/research", "/data", "/data/intents", "/data/revenue",
                     "/data/token-economics", "/methodology", "/workspace"):
            self.assertIn(path, parsed.links)
        self.assertTrue({"evidence", "findings", "mechanism", "release-status"} <= parsed.ids)
        for old_metric in METRICS:
            self.assertNotIn(old_metric, parsed.visible)
        self.assertNotIn("Selected approved metrics", parsed.visible)
        self.assertNotIn("Original research release status", parsed.visible)

    def test_editorial_overview_and_delivery_outage(self):
        """NI-086: stable editorial home; real metric API keeps its own data gates."""
        node = shutil.which("node")
        self.assertIsNotNone(node, "Activate the pinned Node 24 runtime")
        web = self.repo / "apps/web"
        self.assertTrue((web / ".next/BUILD_ID").is_file(), "Build the frozen web app first")
        api_url = f"http://127.0.0.1:{unused_port()}"
        web_url = f"http://127.0.0.1:{unused_port()}"
        environment = {**os.environ, "APP_ENV": "test", "APP_ORIGIN": web_url,
                       "API_INTERNAL_URL": api_url, "DATABASE_URL": os.environ["NI_TEST_RUNTIME_URL"],
                       "NEXT_TELEMETRY_DISABLED": "1"}
        api = self.start_process(
            "api", [sys.executable, "-m", "uvicorn", "near_api.main:app", "--host",
                    "127.0.0.1", "--port", api_url.rsplit(":", 1)[1]], environment,
            self.repo, api_url + "/health")
        self.start_process(
            "web", [node, str(web / "node_modules/next/dist/bin/next"), "start", "--hostname",
                    "127.0.0.1", "--port", web_url.rsplit(":", 1)[1]], environment, web,
            web_url + "/health")
        query = {"definition_version": 1, "start": START, "end": END,
                 "dataset_version": "latest", "frequency": "day"}
        for name in METRICS:
            response = self.http.get(api_url + f"/api/metrics/{name}/series", params=query)
            self.assertEqual(response.status_code, 503, "Unapproved data must stay unavailable")
        empty = self.http.get(web_url)
        self.assertEqual(empty.status_code, 200)
        initial = LandingHTML(empty.text)
        self.assert_editorial_overview(initial)

        document, original_hashes = self.prepared_manifest()
        manifest = self.directory / "prepared.json"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        result = stage(self.operator, manifest, self.directory / "storage")
        self.assertEqual(result.status, "validated", result.validation)
        publish(self.operator, result.dataset_version_id)
        observations_available = 0
        for name in METRICS:
            response = self.http.get(api_url + f"/api/metrics/{name}/series", params=query)
            self.assertEqual(response.status_code, 200)
            series = response.json()
            self.assertEqual(series["dataset"]["id"], str(result.dataset_version_id))
            self.assertEqual(series["metric"]["metric_id"], name)
            self.assertEqual(series["metric"]["version"], 1)
            self.assertEqual(len(series["points"]), 90)
            valued = [point for point in series["points"] if point["value"] is not None]
            if valued:
                observations_available += 1
                self.assertTrue(all(isinstance(point["value"], str) for point in valued))
                if not original_hashes:
                    self.assertEqual(valued[-1]["value"],
                                     "123456789012345678.123456789012345678901234")
            else:
                self.assertTrue(all(point["quality"]["reasons"] for point in series["points"]),
                                "Ambiguous source data must remain null with reasons")
        self.assertGreaterEqual(observations_available, 2)
        rendered = self.http.get(web_url)
        self.assertEqual(rendered.status_code, 200)
        after_publication = LandingHTML(rendered.text)
        self.assert_editorial_overview(after_publication)
        self.assertEqual(initial.visible, after_publication.visible,
                         "Dataset publication must not rewrite the editorial Overview")

        self.stop_process(api)
        with self.assertRaises(httpx.HTTPError):
            self.http.get(api_url + "/health", timeout=1)
        outage = self.http.get(web_url)
        self.assertEqual(outage.status_code, 200)
        after_outage = LandingHTML(outage.text)
        self.assert_editorial_overview(after_outage)
        self.assertEqual(initial.visible, after_outage.visible,
                         "Overview and research entry links must survive an API outage")
        for path, digest in original_hashes.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest,
                             "Saved research inputs must remain byte-identical")
        label = "saved archive (read-only)" if original_hashes else "synthetic regression fixture"
        print(f"NI-086 integration: {label}; {observations_available}/3 metric series available; "
              "editorial Overview stable before/after publication and API outage; "
              "source bytes unchanged", flush=True)
