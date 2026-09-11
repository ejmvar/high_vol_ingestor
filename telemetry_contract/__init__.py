"""Validation primitives for the provider-neutral telemetry envelope."""

from .validator import (
    ContractError,
    StatefulTelemetryValidator,
    ValidationResult,
    validate_envelope,
)
from .generator import GeneratedChunk, VibrationGeneratorConfig, generate_vibration_chunk
from .stream import generate_vibration_chunks
from .ingestion import DurablePublisher, IngestionEndpoint, IngestionReceipt
from .kafka_publisher import KafkaDurablePublisher, KafkaPublisherConfig

__all__ = [
    "ContractError",
    "StatefulTelemetryValidator",
    "ValidationResult",
    "GeneratedChunk",
    "VibrationGeneratorConfig",
    "generate_vibration_chunk",
    "generate_vibration_chunks",
    "DurablePublisher",
    "IngestionEndpoint",
    "IngestionReceipt",
    "KafkaDurablePublisher",
    "KafkaPublisherConfig",
    "validate_envelope",
]
