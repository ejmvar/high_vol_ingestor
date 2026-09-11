"""Validation primitives for the provider-neutral telemetry envelope."""

from .validator import (
    ContractError,
    StatefulTelemetryValidator,
    ValidationResult,
    validate_envelope,
)

__all__ = [
    "ContractError",
    "StatefulTelemetryValidator",
    "ValidationResult",
    "validate_envelope",
]
