from types import SimpleNamespace

from telemetry_contract import KafkaDurablePublisher, KafkaPublisherConfig, generate_vibration_chunk


class Future:
    def __init__(self, metadata):
        self.metadata = metadata
        self.timeout = None

    def get(self, timeout):
        self.timeout = timeout
        return self.metadata


class Producer:
    def __init__(self):
        self.calls = []
        self.future = Future(SimpleNamespace(topic="nvt.telemetry.raw.v1", partition=2, offset=19))

    def send(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.future

    def flush(self):
        self.flushed = True

    def close(self):
        self.closed = True


def test_kafka_publisher_waits_for_ack_and_returns_offset() -> None:
    producer = Producer()
    publisher = KafkaDurablePublisher(
        KafkaPublisherConfig(acknowledgement_timeout_seconds=4.0), producer=producer
    )
    chunk = generate_vibration_chunk()

    offset = publisher.publish(chunk.envelope, chunk.payload)

    assert offset == "nvt.telemetry.raw.v1:2:19"
    assert producer.calls[0][0] == ("nvt.telemetry.raw.v1",)
    assert producer.calls[0][1]["key"] == chunk.envelope["idempotency_key"].encode()
    assert producer.calls[0][1]["value"] == chunk.payload
    assert producer.future.timeout == 4.0
    headers = dict(producer.calls[0][1]["headers"])
    assert headers["schema-name"] == b"nvt.telemetry.chunk"
    assert b'"idempotency_key"' in headers["nvt-envelope"]


def test_kafka_publisher_exposes_explicit_lifecycle() -> None:
    producer = Producer()
    publisher = KafkaDurablePublisher(producer=producer)

    publisher.flush()
    publisher.close()

    assert producer.flushed is True
    assert producer.closed is True
