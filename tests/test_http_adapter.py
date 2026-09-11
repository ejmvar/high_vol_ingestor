import base64
import json
from http.client import HTTPConnection
from threading import Thread

from telemetry_contract import IngestionEndpoint, VibrationGeneratorConfig, generate_vibration_chunk
from ingestor_http import create_http_server


class Publisher:
    def __init__(self) -> None:
        self.records = []

    def publish(self, envelope, payload):
        self.records.append((envelope, payload))
        return "topic-0-7"


def request(server, body: dict, path: str = "/v1/telemetry/chunks", method: str = "POST"):
    connection = HTTPConnection(*server.server_address)
    request_body = json.dumps(body) if method == "POST" else None
    headers = {"Content-Type": "application/json"} if request_body is not None else {}
    connection.request(method, path, request_body, headers)
    response = connection.getresponse()
    result = response.status, json.loads(response.read())
    connection.close()
    return result


def body_for_chunk(chunk):
    return {"envelope": chunk.envelope, "payload_base64": base64.b64encode(chunk.payload).decode("ascii")}


def test_http_adapter_maps_accepted_and_duplicate_receipts() -> None:
    publisher = Publisher()
    server = create_http_server(IngestionEndpoint(publisher), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        chunk = generate_vibration_chunk(VibrationGeneratorConfig(sample_rate_hz=100))
        assert request(server, body_for_chunk(chunk))[0] == 202
        assert request(server, body_for_chunk(chunk)) == (200, {
            "idempotency_key": chunk.envelope["idempotency_key"],
            "queue_offset": None,
            "status": "duplicate",
        })
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert len(publisher.records) == 1


def test_http_adapter_rejects_invalid_payload_before_publisher() -> None:
    publisher = Publisher()
    server = create_http_server(IngestionEndpoint(publisher), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        chunk = generate_vibration_chunk(VibrationGeneratorConfig(sample_rate_hz=100))
        body = body_for_chunk(chunk)
        body["payload_base64"] = "not-base64"
        status, result = request(server, body)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert status == 400
    assert result["error"]["code"] == "invalid_request"
    assert publisher.records == []


def test_http_adapter_returns_not_found_for_other_paths() -> None:
    server = create_http_server(IngestionEndpoint(Publisher()), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, result = request(server, {}, "/unknown", method="GET")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert status == 404
    assert result == {"error": {"code": "not_found"}}


def test_http_adapter_exposes_non_secret_readiness() -> None:
    server = create_http_server(IngestionEndpoint(Publisher()), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, result = request(server, {}, "/health", method="GET")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert status == 200
    assert result == {"status": "ready"}
