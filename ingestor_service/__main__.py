"""Start the local HTTP-to-Kafka ingestor service."""

from __future__ import annotations

import os

from ingestor_http import create_http_server
from telemetry_contract import IngestionEndpoint, KafkaDurablePublisher, KafkaPublisherConfig


def main() -> None:
    bootstrap_servers = tuple(
        item.strip()
        for item in os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092").split(",")
        if item.strip()
    )
    publisher = KafkaDurablePublisher(KafkaPublisherConfig(
        bootstrap_servers=bootstrap_servers,
        topic=os.environ.get("KAFKA_TOPIC", "nvt.telemetry.raw.v1"),
    ))
    server = create_http_server(
        IngestionEndpoint(publisher),
        host=os.environ.get("INGESTOR_HOST", "0.0.0.0"),
        port=int(os.environ.get("INGESTOR_PORT", "8080")),
        max_in_flight=int(os.environ.get("INGESTOR_MAX_IN_FLIGHT", "128")),
    )
    try:
        server.serve_forever()
    finally:
        publisher.flush()
        publisher.close()
        server.server_close()


if __name__ == "__main__":
    main()
