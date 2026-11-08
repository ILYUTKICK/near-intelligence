"""NI-041 true gateway/JWT/DB insertion, pinned evidence and reopen/save E2E."""
import copy
import datetime as dt
from uuid import uuid4

import test_saved_charts_http as gateway_fixture
import test_delivery_apis as data_fixture
from near_api.datasets import delivery


class ChartInsertionHTTPE2E(gateway_fixture.SavedChartsHTTPE2E):
    def after_gateway_checks(self, client, session_cookie, body):
        client.cookies.set("ni_session", session_cookie("alice"))
        token = client.get("/api/auth/csrf").json()["token"]
        headers = {"Origin": str(client.base_url).rstrip("/"), "x-csrf-token": token,
                   "Idempotency-Key": str(uuid4())}
        created = client.post("/api/documents", json={"title": "Synthetic chart research E2E"}, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        document = created.json()
        self.http_document_id = document["id"]
        # A newer source arrives after inspection but BEFORE insertion.
        data_fixture.DeliveryDatabaseTests.stage_fixture(
            self, f"ni041-http.{uuid4().hex[:12]}",
            [data_fixture.observation(data_fixture.METRIC_VOLUME, dt.date(2026, 1, 1),
                                      value="999", dimensions={"source": "SRC-LLAMA"})],
            [data_fixture.METRIC_VOLUME], window=("2026-01-01", "2026-01-02"))
        delivery.reset_delivery_caches()
        payload = {key: body[key] for key in ("chart_definition_version_id", "dataset_version_id", "selection", "mode")}
        headers.update({"If-Match": '"1"', "Idempotency-Key": str(uuid4())})
        path = "/api/documents/" + document["id"]
        inserted = client.post(path + "/chart-blocks", json=payload, headers=headers)
        self.assertEqual(inserted.status_code, 201, inserted.text)
        headers["If-Match"] = '"2"'
        replay = client.post(path + "/chart-blocks", json=payload, headers=headers)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json(), inserted.json())
        opened = client.get(path).json()
        self.assertEqual(opened["revision"], 2)
        self.assertEqual(len(opened["content"]["content"]), 1)
        block = opened["content"]["content"][0]
        self.assertEqual(block["attrs"]["selection"], payload["selection"])
        self.assertEqual(block["attrs"]["observed_dataset_version_id"], payload["dataset_version_id"])
        context = opened["resolved_contexts"][block["attrs"]["block_id"]]
        self.assertEqual(context["dataset_version_id"], payload["dataset_version_id"])
        content = copy.deepcopy(opened["content"])
        content["content"].append({"type": "paragraph", "attrs": {"block_id": str(uuid4())},
                                   "content": [{"type": "text", "text": "Synthetic note after chart insertion"}]})
        headers["Idempotency-Key"] = str(uuid4())
        saved = client.post(path + "/versions", json={"schema_version": 1, "content": content,
                                                      "observed_contexts": []}, headers=headers)
        self.assertEqual(saved.status_code, 201, saved.text)
        again = client.get(path).json()
        self.assertEqual(again["resolved_contexts"][block["attrs"]["block_id"]], context)
        self.assertEqual(again["revision"], 3)
        self.assertEqual(client.get("/workspace/research/" + document["id"]).status_code, 200)
        client.cookies.set("ni_session", session_cookie("bob"))
        self.assertEqual(client.get(path).status_code, 404)
        self.assertEqual(client.post(path + "/chart-blocks", json=payload, headers=headers).status_code, 404)
        print("NI-041 gateway E2E: one insertion/retry, inspected pin survives newer source + prose save; Bob denied", flush=True)
