"""Kafka-compatible durable publisher adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KafkaPublisherConfig:
    bootstrap_servers: tuple[str, ...] = ("localhost:19092",)
    topic: str = "nvt.telemetry.raw.v1"
    acknowledgement_timeout_seconds: float = 30.0
    retries: int = 5
    compression_type: str | None = "zstd"


class KafkaDurablePublisher:
    """Adapt the durable publisher port to kafka-python's synchronous future."""

    def __init__(self, config: KafkaPublisherConfig = KafkaPublisherConfig(), *, producer: Any | None = None) -> None:
        if not config.bootstrap_servers or not config.topic:
            raise ValueError("Kafka bootstrap servers and topic are required")
        if config.acknowledgement_timeout_seconds <= 0 or config.retries < 0:
            raise ValueError("Kafka timeout must be positive and retries non-negative")
        self.config = config
        self._producer = producer or self._create_producer(config)

    @staticmethod
    def _create_producer(config: KafkaPublisherConfig) -> Any:
        try:
            from kafka import KafkaProducer
        except ImportError as error:
            raise RuntimeError("install the optional kafka dependency to use KafkaDurablePublisher") from error
        return KafkaProducer(
            bootstrap_servers=list(config.bootstrap_servers),
            acks="all",
            retries=config.retries,
            compression_type=config.compression_type,
        )

    def publish(self, envelope: Mapping[str, object], payload: bytes) -> str:
        """Publish raw bytes and wait for broker acknowledgement before returning."""
        serialized_envelope = json.dumps(dict(envelope), sort_keys=True, separators=(",", ":")).encode("utf-8")
        future = self._producer.send(
            self.config.topic,
            key=str(envelope["idempotency_key"]).encode("utf-8"),
            value=payload,
            headers=[
                ("nvt-envelope", serialized_envelope),
                ("schema-name", str(envelope["schema_name"]).encode("utf-8")),
                ("schema-version", str(envelope["schema_version"]).encode("utf-8")),
            ],
        )
        metadata = future.get(timeout=self.config.acknowledgement_timeout_seconds)
        return f"{metadata.topic}:{metadata.partition}:{metadata.offset}"

    def flush(self) -> None:
        self._producer.flush()

    def close(self) -> None:
        self._producer.close()
