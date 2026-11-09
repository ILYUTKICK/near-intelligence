"""NI-041/042/043 real gateway/JWT/DB insertion, edits and frozen reads."""
import copy
import csv
import datetime as dt
import io
import json
from unittest.mock import patch
from uuid import uuid4

import test_saved_charts_http as gateway_fixture
import test_delivery_apis as data_fixture
from near_api.datasets import delivery
from near_api.schemas.chart_blocks import DocumentChartViewResponse


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
        # NI-042 resolves the stored immutable UUID through the private fixed
        # gateway route. No request defaults to latest during reopen.
        query = {"chart_definition_version_id": payload["chart_definition_version_id"],
                 "start": payload["selection"]["start"],
                 "end": payload["selection"]["end"],
                 "dataset_version": payload["dataset_version_id"],
                 "filters": json.dumps(payload["selection"]["filters"])}
        chart_path = path + "/chart-view"
        pinned_response = client.get(chart_path, params=query)
        self.assertEqual(pinned_response.status_code, 200, pinned_response.text)
        self.assertEqual(pinned_response.headers["cache-control"], "no-store")
        pinned = DocumentChartViewResponse.model_validate(pinned_response.json())
        self.assertEqual(str(pinned.definition.id), payload["chart_definition_version_id"])
        self.assertEqual(str(pinned.dataset.id), payload["dataset_version_id"])
        self.assertEqual(pinned.context_hash, context["context_hash"])
        self.assertIsNotNone(pinned.latest_approved_dataset_version_id)
        self.assertNotEqual(pinned.latest_approved_dataset_version_id, pinned.dataset.id)
        exact_values = [point.value for series in pinned.series for point in series.points
                        if point.value is not None]
        self.assertEqual(exact_values, ["12.123456789012345678901234"])

        revision_two_id = opened["current_version_id"]
        historical = f"{path}/versions/{revision_two_id}/chart-blocks/{block['attrs']['block_id']}"
        frozen_view = client.get(historical + "/view")
        self.assertEqual(frozen_view.status_code, 200, frozen_view.text)
        self.assertEqual(frozen_view.json()["context_hash"], context["context_hash"])
        self.assertEqual(frozen_view.json()["dataset"]["id"], payload["dataset_version_id"])
        frozen_csv = client.get(historical + "/csv")
        self.assertEqual(frozen_csv.status_code, 200, frozen_csv.text)
        self.assertEqual(frozen_csv.headers["cache-control"], "no-store")
        self.assertTrue(frozen_csv.headers["content-disposition"].startswith("attachment;"))
        rows = list(csv.DictReader(io.StringIO(frozen_csv.text)))
        self.assertEqual([row["value"] for row in rows], exact_values)
        self.assertEqual(client.get(historical + "/view", params={"dataset_version": "latest"}).status_code, 422)

        # Range + filter change is inspected first, then one explicit saved
        # document edit. A source was published after the old inspection, but
        # this request retains v1 until Refresh explicitly sends latest.
        changed_query = {**query, "end": "2026-01-03", "filters": "{}"}
        changed_response = client.get(chart_path, params=changed_query)
        self.assertEqual(changed_response.status_code, 200, changed_response.text)
        inspected = changed_response.json()
        changed_content = copy.deepcopy(again["content"])
        attrs = changed_content["content"][0]["attrs"]
        attrs["selection"] = inspected["selection"]
        attrs["observed_dataset_version_id"] = inspected["dataset"]["id"]
        published_after_preview = data_fixture.DeliveryDatabaseTests.stage_fixture(
            self, f"ni043-http.{uuid4().hex[:12]}",
            [data_fixture.observation(data_fixture.METRIC_VOLUME, dt.date(2026, 1, 1),
                                      value="1234", dimensions={"source": "SRC-LLAMA"})],
            [data_fixture.METRIC_VOLUME], window=("2026-01-01", "2026-01-02"))
        headers.update({"If-Match": '"3"', "Idempotency-Key": str(uuid4())})
        edit_body = {"schema_version": 1, "content": changed_content, "observed_contexts": [{
            "chart_definition_version_id": inspected["definition"]["id"],
            "dataset_version_id": inspected["dataset"]["id"], "selection": inspected["selection"],
            "context_hash": inspected["context_hash"], "resolved_at": inspected["resolved_at"],
            "renderer_version": inspected["definition"]["renderer_version"],
            "metric_definition_versions": inspected["definition"]["metric_definition_ids"],
        }]}
        edited = client.post(path + "/versions", json=edit_body, headers=headers)
        self.assertEqual(edited.status_code, 201, edited.text)
        self.assertEqual(client.post(path + "/versions", json=edit_body,
                                     headers=headers).json(), edited.json())
        reopened = client.get(path).json()
        self.assertEqual(reopened["revision"], 4)
        self.assertEqual(reopened["content"]["content"][0]["attrs"]["selection"],
                         inspected["selection"])
        saved_context = reopened["resolved_contexts"][block["attrs"]["block_id"]]
        self.assertEqual(saved_context["context_hash"], inspected["context_hash"])
        self.assertEqual(saved_context["dataset_version_id"], payload["dataset_version_id"])
        old = client.get(path + "/versions/" + revision_two_id).json()
        self.assertEqual(old["resolved_contexts"][block["attrs"]["block_id"]], context)
        self.assertEqual(client.get(historical + "/csv").content, frozen_csv.content)
        self.assertEqual(client.get(historical + "/view").json(), frozen_view.json())
        self.assertEqual(client.get(chart_path, params=changed_query).json()["latest_approved_dataset_version_id"],
                         str(published_after_preview.dataset_version_id))
        self.assertEqual(client.get(f"/workspace/research/{document['id']}/versions?version={revision_two_id}").status_code, 200)

        # Preview latest is read-only. Only adopting its returned UUID into
        # the canonical node and saving makes a new pin.
        fresh_response = client.get(chart_path,
                                    params={**changed_query, "dataset_version": "latest"})
        self.assertEqual(fresh_response.status_code, 200, fresh_response.text)
        fresh = fresh_response.json()
        self.assertNotEqual(fresh["dataset"]["id"], payload["dataset_version_id"])
        self.assertEqual(client.get(path).json()["revision"], 4)
        refreshed_content = copy.deepcopy(reopened["content"])
        refreshed_attrs = refreshed_content["content"][0]["attrs"]
        refreshed_attrs["observed_dataset_version_id"] = fresh["dataset"]["id"]
        refreshed_attrs["selection"] = fresh["selection"]
        headers.update({"If-Match": '"4"', "Idempotency-Key": str(uuid4())})
        refreshed = client.post(path + "/versions",
            json={"schema_version": 1, "content": refreshed_content,
                  "observed_contexts": []}, headers=headers)
        self.assertEqual(refreshed.status_code, 201, refreshed.text)
        current = client.get(path).json()
        refreshed_context = current["resolved_contexts"][block["attrs"]["block_id"]]
        self.assertEqual(refreshed_context["context_hash"], fresh["context_hash"])
        self.assertEqual(refreshed_context["dataset_version_id"], fresh["dataset"]["id"])
        stale = client.post(path + "/versions", json=edit_body,
                            headers={**headers, "Idempotency-Key": str(uuid4())})
        self.assertEqual(stale.status_code, 409, stale.text)

        # A localized chart-source/delivery outage cannot disable prose saves.
        # This failure affects the real API route while document validation
        # retains already-verified immutable attrs, without a latest query.
        with patch.object(delivery, "build_chart_view",
                          side_effect=delivery.DeliveryDataNotReady("Synthetic chart delivery outage")):
            outage = client.get(chart_path, params=changed_query)
            self.assertEqual(outage.status_code, 503, outage.text)
            self.assertEqual(outage.headers["cache-control"], "no-store")
            outage_content = copy.deepcopy(current["content"])
            outage_content["content"].append({
                "type": "paragraph", "attrs": {"block_id": str(uuid4())},
                "content": [{"type": "text", "text": "Synthetic prose during source outage"}]})
            headers.update({"If-Match": '"5"', "Idempotency-Key": str(uuid4())})
            prose = client.post(path + "/versions", json={"schema_version": 1,
                                "content": outage_content, "observed_contexts": []}, headers=headers)
            self.assertEqual(prose.status_code, 201, prose.text)
        final = client.get(path).json()
        self.assertEqual(final["revision"], 6)
        self.assertEqual(final["resolved_contexts"][block["attrs"]["block_id"]], refreshed_context)
        self.assertEqual(client.get(path + "/versions/" + revision_two_id).json()["resolved_contexts"][block["attrs"]["block_id"]], context)
        self.assertEqual(client.get("/workspace/research/" + document["id"]).status_code, 200)

        # NI-047 uses the same verified gateway and exact saved chart context.
        insights = path + "/insights"
        note_id = str(uuid4())
        headers.update({"If-Match": '"6"', "Idempotency-Key": str(uuid4())})
        note = {"block_id": note_id, "after_block_id": block["attrs"]["block_id"],
                "type": "observation", "classification": "uncertain", "context": refreshed_context,
                "body": [{"type": "paragraph", "content": [{"type": "text", "text": "Synthetic gateway insight"}]}]}
        written = client.post(insights, json=note, headers=headers)
        self.assertEqual(written.status_code, 201, written.text)
        acknowledged = written.json()
        saved_note = acknowledged["value"]
        self.assertEqual(saved_note["context"]["context_hash"], refreshed_context["context_hash"])
        self.assertEqual(saved_note["context"]["dataset_version_id"], refreshed_context["dataset_version_id"])
        self.assertEqual(acknowledged["version"]["content"]["content"][1]["attrs"]["block_id"], note_id)
        self.assertEqual(client.get(insights).json(), [saved_note])
        self.assertEqual(client.get(insights, params={"version_id": revision_two_id}).json(), [])
        note_path = f"{insights}/{saved_note['id']}"
        headers.update({"If-Match": '"7"', "Idempotency-Key": str(uuid4())})
        amended = client.patch(note_path, json={"classification": "contradicting"}, headers=headers)
        self.assertEqual(amended.status_code, 200, amended.text)
        self.assertEqual(amended.json()["value"]["context"], saved_note["context"])
        self.assertEqual(amended.json()["value"]["classification"], "contradicting")

        client.cookies.set("ni_session", session_cookie("bob"))
        self.assertEqual(client.get(path).status_code, 404)
        self.assertEqual(client.post(path + "/chart-blocks", json=payload, headers=headers).status_code, 404)
        self.assertEqual(client.get(chart_path, params=query).status_code, 404)
        self.assertEqual(client.get(historical + "/view").status_code, 404)
        self.assertEqual(client.get(historical + "/csv").status_code, 404)
        self.assertEqual(client.get(insights).status_code, 404)
        self.assertEqual(client.patch(note_path, json={"classification": "supporting"}, headers=headers).status_code, 404)
        denied_save = client.post(path + "/versions", json=edit_body, headers=headers)
        self.assertEqual(denied_save.status_code, 404, denied_save.text)
        print("NI-041/042/043/047 gateway E2E: insert/retry, observed save after publication, "
              "identical old view/CSV, pinned insight create/edit/history, explicit refresh, "
              "chart outage + prose save, Bob denied", flush=True)
