from datetime import datetime, timezone

import pytest

from telemetry_contract import (
    IngestionEndpoint,
    VibrationGeneratorConfig,
    generate_vibration_chunk,
    generate_vibration_chunks,
)


START = datetime(2026, 9, 10, 19, 0, tzinfo=timezone.utc)


class FakeDurablePublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.records: list[tuple[dict[str, object], bytes]] = []

    def publish(self, envelope: dict[str, object], payload: bytes) -> str:
        if self.fail:
            raise RuntimeError("publisher unavailable")
        self.records.append((envelope, payload))
        return f"memory-{len(self.records) - 1}"


def test_endpoint_publishes_only_after_validation() -> None:
    publisher = FakeDurablePublisher()
    endpoint = IngestionEndpoint(publisher)
    chunk = generate_vibration_chunk(
        VibrationGeneratorConfig(sample_rate_hz=100), event_start=START
    )

    receipt = endpoint.ingest(chunk.envelope, chunk.payload)

    assert receipt.status == "accepted"
    assert receipt.queue_offset == "memory-0"
    assert publisher.records == [(chunk.envelope, chunk.payload)]


def test_duplicate_is_acknowledged_without_republishing() -> None:
    publisher = FakeDurablePublisher()
    endpoint = IngestionEndpoint(publisher)
    chunk = generate_vibration_chunk(event_start=START)

    endpoint.ingest(chunk.envelope, chunk.payload)
    receipt = endpoint.ingest(chunk.envelope, chunk.payload)

    assert receipt.status == "duplicate"
    assert receipt.queue_offset is None
    assert len(publisher.records) == 1


def test_failed_publish_does_not_consume_sequence() -> None:
    publisher = FakeDurablePublisher(fail=True)
    endpoint = IngestionEndpoint(publisher)
    chunks = list(
        generate_vibration_chunks(
            VibrationGeneratorConfig(sample_rate_hz=100), count=2, event_start=START
        )
    )

    with pytest.raises(RuntimeError, match="publisher unavailable"):
        endpoint.ingest(chunks[0].envelope, chunks[0].payload)

    publisher.fail = False
    receipt = endpoint.ingest(chunks[0].envelope, chunks[0].payload)
    assert receipt.status == "accepted"
    assert len(publisher.records) == 1


def test_invalid_record_is_not_published() -> None:
    publisher = FakeDurablePublisher()
    endpoint = IngestionEndpoint(publisher)
    chunk = generate_vibration_chunk(event_start=START)
    chunk.envelope["payload_byte_length"] = 1

    with pytest.raises(ValueError):
        endpoint.ingest(chunk.envelope, chunk.payload)

    assert publisher.records == []
