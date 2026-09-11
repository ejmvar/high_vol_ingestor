"""Transport-neutral ingestion boundary for validated telemetry chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from collections.abc import Mapping

from .validator import StatefulTelemetryValidator, ValidationResult


class DurablePublisher(Protocol):
    """Port implemented by a queue adapter such as Redpanda/Kafka."""

    def publish(self, envelope: Mapping[str, object], payload: bytes) -> str:
        """Publish and return an adapter-defined acceptance offset."""


@dataclass(frozen=True)
class IngestionReceipt:
    status: str
    idempotency_key: str
    queue_offset: str | None


class IngestionEndpoint:
    """Validate records before durable publication and state commitment."""

    def __init__(self, publisher: DurablePublisher) -> None:
        self._publisher = publisher
        self._validator = StatefulTelemetryValidator()

    def ingest(self, envelope: Mapping[str, object], payload: bytes) -> IngestionReceipt:
        result: ValidationResult = self._validator.inspect(envelope, payload)
        identity = str(result.envelope["idempotency_key"])
        if result.status == "duplicate":
            return IngestionReceipt("duplicate", identity, None)

        offset = self._publisher.publish(result.envelope, payload)
        self._validator.commit(result.envelope)
        return IngestionReceipt("accepted", identity, offset)
