"""NI-004 contracts: synthetic fixtures, in-process HTTP, no external I/O."""

import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from near_api.contracts import install_contracts
from near_api.main import app
from near_api.schemas.common import DataQuality, ErrorResponse, HealthResponse, Observation, RawAmountString, Selection
from near_api.settings import Settings, SettingsError


class ContractTests(TestCase):
    def setUp(self):
        self.fixture = json.loads((Path(__file__).parent / "fixtures/contracts.json").read_text(encoding="utf-8"))

    def observation(self, index=0, **changes):
        value = {key: value for key, value in self.fixture["observations"][index].items() if key != "name"}
        return {**value, **changes}

    def test_exact_null_and_bound_round_trip(self):
        for index, fixture in enumerate(self.fixture["observations"]):
            with self.subTest(name=fixture["name"]):
                observed = Observation.model_validate_json(json.dumps(self.observation(index)))
                dumped = json.loads(observed.model_dump_json())
                self.assertEqual(dumped["value"], fixture["value"])
                self.assertEqual(dumped["quality"]["bound_kind"], fixture["quality"]["bound_kind"])
                self.assertEqual(dumped["start"], "2026-01-01T00:00:00Z")
        quality = self.observation(2)["quality"]
        for bound in ("exact", "estimate", "lower", "upper"):
            self.assertEqual(DataQuality.model_validate({**quality, "bound_kind": bound}).bound_kind, bound)
        ErrorResponse.model_validate(self.fixture["error"])
        self.assertEqual(TypeAdapter(RawAmountString).validate_python("9" * 78), "9" * 78)

    def test_invalid_decimal_and_null_never_silently_coerce(self):
        for amount in (0, 1.5, True, "NaN", "Infinity", "1e3", "01", "1" * 79,
                       "0." + "1" * 31, None):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                Observation.model_validate(self.observation(value=amount))
        with self.assertRaises(ValidationError):
            Observation.model_validate(self.observation(1, value="0"))
        with self.assertRaises(ValidationError):
            TypeAdapter(RawAmountString).validate_python("-1")

    def test_selection_half_open_limits_and_unknown_fields(self):
        Selection.model_validate(self.fixture["selection"])
        for changes in ({"end": "2024-01-01"}, {"end": "2025-01-02"}, {"start": 0},
                        {"start": "20240101"}, {"frequency": "week"},
                        {"filters": {"unapproved": True}}, {"owner_id": "synthetic"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                Selection.model_validate({**self.fixture["selection"], **changes})

    def test_quality_timestamps_and_nested_fields_fail_closed(self):
        for changes in ({"end": "2026-01-01T00:00:00Z"}, {"start": "2026-01-01T00:00:00"},
                        {"start": 0}, {"extra": "forbidden"}):
            with self.assertRaises(ValidationError):
                Observation.model_validate(self.observation(**changes))
        quality = self.observation()["quality"]
        for changes in ({"coverage": {"observed": 2, "expected": 1}},
                        {"coverage": {"observed": True, "expected": 1}}, {"unknown": 1},
                        {"status": "missing", "bound_kind": None, "reasons": []}):
            with self.assertRaises(ValidationError):
                DataQuality.model_validate({**quality, **changes})

    def test_health_and_openapi_work_without_provider_or_db(self):
        settings = Settings(APP_ENV="test", APP_ORIGIN="http://localhost:3000",
                            API_INTERNAL_URL="http://localhost:8000")
        with TestClient(app) as client, patch("near_api.main.get_settings", return_value=settings):
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(HealthResponse.model_validate(response.json()).service, "api")
            schema = client.get("/openapi.json").json()
            # NI-022 added the first private route; /health stays public.
            # The contract grows with implemented routes: NI-025 added /api/me,
            # NI-036 added the document revision routes, NI-037 added the
            # version detail route, NI-032 added the public
            # metrics/chart/dataset/source delivery routes and NI-054 added
            # the public model definition/readiness/run routes.
            self.assertEqual(set(schema["paths"]), {
                "/health", "/api/home", "/api/me",
                "/api/documents", "/api/documents/{document_id}",
                "/api/documents/{document_id}/versions",
                "/api/documents/{document_id}/versions/{version_id}",
                "/api/metrics", "/api/metrics/{metric_id}",
                "/api/metrics/{metric_id}/series",
                "/api/charts", "/api/charts/{chart_id}", "/api/charts/{chart_id}/view",
                "/api/data-sources", "/api/data-sources/{source_id}",
                "/api/datasets/{version_id}", "/api/datasets/{version_id}/manifest",
                "/api/model-definitions", "/api/model-definitions/{model_id}",
                "/api/model-definitions/{model_id}/readiness",
                "/api/model-runs", "/api/model-runs/{run_id}",
                "/api/model-runs/{run_id}/manifest",
            })
            self.assertIn("DecimalString", schema["components"]["schemas"])
            self.assertFalse(schema["components"]["schemas"]["Selection"]["additionalProperties"])
        with TestClient(app) as client, patch("near_api.main.get_settings", side_effect=SettingsError("Missing APP_ENV")):
            response = client.get("/health")
            self.assertEqual(response.status_code, 503)
            failure = ErrorResponse.model_validate(response.json())
            self.assertIn("APP_ENV", failure.error.message)
            self.assertEqual(str(failure.error.request_id), response.headers["X-Request-ID"])
        self.assertEqual(schema, app.openapi())

    def test_http_failures_redact_input_exception_details_and_headers(self):
        application = FastAPI()
        install_contracts(application)

        @application.post("/__synthetic__/selection")
        def synthetic_selection(selection: Selection):
            return selection

        @application.get("/__synthetic__/fail/{status}")
        def synthetic_failure(status: int):
            if status == 500:
                raise RuntimeError("synthetic-private-exception")
            raise HTTPException(status, "synthetic-private-detail", headers={
                "X-Secret": "synthetic-private-header", "Retry-After": "12",
            })

        with TestClient(application, raise_server_exceptions=False) as client:
            invalid = {**self.fixture["selection"], "synthetic_secret_key": "synthetic-private-body"}
            responses = [client.post("/__synthetic__/selection", json=invalid),
                         client.post("/__synthetic__/selection", content='{"secret":"synthetic-private-json",',
                                     headers={"Content-Type": "application/json"}),
                         client.get("/unknown")]
            self.assertEqual([response.status_code for response in responses], [422, 400, 404])
            responses.extend(client.get(f"/__synthetic__/fail/{status}") for status in (401, 429, 500))
            for response in responses:
                ErrorResponse.model_validate(response.json())
                self.assertNotIn("synthetic-private", response.text)
                self.assertNotIn("synthetic_secret_key", response.text)
                self.assertNotIn("X-Secret", response.headers)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                UUID(response.headers["X-Request-ID"])
            self.assertEqual(responses[-2].headers["Retry-After"], "12")
            self.assertEqual(responses[-3].headers["WWW-Authenticate"], "Bearer")
