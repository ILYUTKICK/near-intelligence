"""NI-012: real Next HTTP -> FastAPI HTTP -> disposable PostgreSQL.

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
from near_api.metrics.registry import definition_by_metric_id, register_definitions
from test_delivery_apis import SOURCE_IDS, manifest_document, observation

START, END = "2026-08-06", "2026-11-04"
METRICS = ("observed_near_purchases", "treasury_payouts_near", "provider_gross_fees_usd")


class LandingHTML(HTMLParser):
    """Visible article text only: React's script payloads are not UI evidence."""

    def __init__(self, html: str):
        super().__init__()
        self.articles: dict[str, list[str]] = {}
        self.current: str | None = None
        self.hidden = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag == "article" and not self.hidden:
            self.current = dict(attrs).get("aria-labelledby")
            if self.current:
                self.articles[self.current] = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden -= 1
        if tag == "article":
            self.current = None

    def handle_data(self, data):
        if self.current and not self.hidden:
            self.articles[self.current].append(data)

    def metric(self, metric_id: str) -> str:
        return " ".join("".join(self.articles[f"{metric_id}-metric-heading"]).split())


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
        metric_ids = [definition_by_metric_id(name).id for name in METRICS]
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

    def test_live_delivery_render_and_outage(self):
        """No approved data -> real publication -> rendered values -> API outage."""
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

        empty = self.http.get(web_url)
        self.assertEqual(empty.status_code, 200)
        parsed = LandingHTML(empty.text)
        for name in METRICS:
            self.assertIn("not zero", parsed.metric(name))
            self.assertNotIn("Latest approved observation", parsed.metric(name))

        document, original_hashes = self.prepared_manifest()
        manifest = self.directory / "prepared.json"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        result = stage(self.operator, manifest, self.directory / "storage")
        self.assertEqual(result.status, "validated", result.validation)
        publish(self.operator, result.dataset_version_id)
        expected = {}
        for name in METRICS:
            response = self.http.get(api_url + f"/api/metrics/{name}/series", params={
                "definition_version": 1, "start": START, "end": END,
                "dataset_version": "latest", "frequency": "day"})
            self.assertEqual(response.status_code, 200)
            expected[name] = response.json()
            self.assertEqual(expected[name]["dataset"]["id"], str(result.dataset_version_id))

        rendered = self.http.get(web_url)
        self.assertEqual(rendered.status_code, 200)
        parsed = LandingHTML(rendered.text)
        observations_shown = 0
        for name, series in expected.items():
            card = parsed.metric(name)
            valued = [p for p in series["points"] if p["value"] is not None]
            if valued:
                observations_shown += 1
                self.assertIn(valued[-1]["value"], card)
                self.assertIn(series["metric"]["unit"], card)
                self.assertIn("Data as of:", card)
                self.assertIn(series["dataset"]["dataset_key"], card)
                self.assertIn("approved", card)
                self.assertIn("end exclusive", card)
            else:
                # Multiple provider variants remain unavailable; never pick
                # one or sum the variants to manufacture a headline number.
                self.assertIn("not zero", card)
                self.assertNotIn("Latest approved observation", card)
                point_reasons = {reason for point in series["points"]
                                 for reason in point["quality"]["reasons"]}
                self.assertTrue(point_reasons, "Unavailable data must explain why")
                self.assertTrue(any(reason in card for reason in point_reasons),
                                "Point-level reasons must survive the API-to-HTML boundary")
            self.assertNotIn("Live", card)
        self.assertGreaterEqual(observations_shown, 2)
        self.assertIn('href="/methodology#definitions"', rendered.text)
        self.assertIn('href="/methodology#collection"', rendered.text)

        self.stop_process(api)
        outage = self.http.get(web_url)
        self.assertEqual(outage.status_code, 200)
        parsed = LandingHTML(outage.text)
        for name in METRICS:
            self.assertIn("not zero", parsed.metric(name))
            self.assertNotIn("Latest approved observation", parsed.metric(name))
        for path, digest in original_hashes.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest,
                             "Saved research inputs must remain byte-identical")
        label = "saved archive (read-only)" if original_hashes else "synthetic regression fixture"
        print(f"NI-012 integration: {label}; {observations_shown}/3 observed metric cards; "
              "publication/render/outage passed; source bytes unchanged", flush=True)
