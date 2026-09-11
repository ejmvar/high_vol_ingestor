"""Small standard-library HTTP adapter around the ingestion application port."""

from __future__ import annotations

import base64
import binascii
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from typing import Any

from telemetry_contract import ContractError, IngestionEndpoint


MAX_REQUEST_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_IN_FLIGHT = 128


def create_http_server(
    endpoint: IngestionEndpoint,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    max_in_flight: int = DEFAULT_MAX_IN_FLIGHT,
) -> ThreadingHTTPServer:
    """Create an unstarted server; the caller owns its lifecycle."""
    if max_in_flight < 1:
        raise ValueError("max_in_flight must be positive")

    class Handler(IngestionRequestHandler):
        ingestion_endpoint = endpoint
        request_slots = BoundedSemaphore(max_in_flight)

    return ThreadingHTTPServer((host, port), Handler)


class IngestionRequestHandler(BaseHTTPRequestHandler):
    """Translate HTTP requests into the provider-neutral ingestion DTO."""

    ingestion_endpoint: IngestionEndpoint
    request_slots: BoundedSemaphore

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._respond(HTTPStatus.NOT_FOUND, {"error": {"code": "not_found"}})
            return
        self._respond(HTTPStatus.OK, {"status": "ready"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/telemetry/chunks":
            self._respond(HTTPStatus.NOT_FOUND, {"error": {"code": "not_found"}})
            return
        if not self.request_slots.acquire(blocking=False):
            self._respond(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": {"code": "backpressure", "message": "ingestor capacity is full"}},
                retry_after="1",
            )
            return
        try:
            try:
                request = self._read_json()
                envelope = request["envelope"]
                payload = base64.b64decode(request["payload_base64"], validate=True)
                receipt = self.ingestion_endpoint.ingest(envelope, payload)
            except (ContractError, KeyError, TypeError, ValueError, binascii.Error) as error:
                code = error.code if isinstance(error, ContractError) else "invalid_request"
                self._respond(HTTPStatus.BAD_REQUEST, {"error": {"code": code, "message": str(error)}})
                return
            except Exception:
                self._respond(HTTPStatus.SERVICE_UNAVAILABLE, {"error": {"code": "publisher_unavailable"}})
                return

            status = HTTPStatus.OK if receipt.status == "duplicate" else HTTPStatus.ACCEPTED
            self._respond(status, {
                "status": receipt.status,
                "idempotency_key": receipt.idempotency_key,
                "queue_offset": receipt.queue_offset,
            })
        finally:
            self.request_slots.release()

    def log_message(self, format: str, *args: Any) -> None:
        """Avoid writing payloads or request data to default stderr logs."""
        return None

    def _read_json(self) -> dict[str, Any]:
        content_length = self.headers.get("Content-Length")
        if content_length is None or not content_length.isdigit():
            raise ValueError("Content-Length is required")
        size = int(content_length)
        if size > MAX_REQUEST_BYTES:
            raise ValueError("request body is too large")
        raw = self.rfile.read(size)
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise ValueError("request body must be an object")
        if not isinstance(document.get("envelope"), dict) or not isinstance(document.get("payload_base64"), str):
            raise ValueError("request requires envelope and payload_base64")
        return document

    def _respond(
        self,
        status: HTTPStatus,
        document: dict[str, Any],
        *,
        retry_after: str | None = None,
    ) -> None:
        body = json.dumps(document, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if retry_after is not None:
            self.send_header("Retry-After", retry_after)
        self.end_headers()
        self.wfile.write(body)
