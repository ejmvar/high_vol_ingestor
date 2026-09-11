"""Structural and stateful validation for telemetry chunk envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
import re
from collections.abc import Mapping
from typing import Any


_SIGNALS = {"voltage", "current", "active_power", "vibration", "audio", "ultrasonic"}
_CODECS = {"none", "gzip", "zstd", "flac"}
_FORMATS = {"pcm_s16le", "float32", "scalar_f64"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED = {
    "schema_name", "schema_version", "event_id", "motor_id", "signal_type",
    "event_start", "event_end", "sample_rate_hz", "channel_count", "sample_count",
    "producer_id", "producer_sequence", "payload_byte_length", "checksum", "codec",
    "format", "idempotency_key",
}
_OPTIONAL = {"source", "quality"}


class ContractError(ValueError):
    """A contract or state-machine violation with a stable reason code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ValidationResult:
    status: str
    envelope: Mapping[str, Any]


def _require_string(envelope: Mapping[str, Any], name: str) -> str:
    value = envelope.get(name)
    if not isinstance(value, str) or not value:
        raise ContractError("invalid_field", f"{name} must be a non-empty string")
    return value


def _parse_timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ContractError("invalid_field", f"{name} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("invalid_field", f"{name} must be an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ContractError("invalid_field", f"{name} must include a timezone")
    return parsed


def validate_envelope(raw: Mapping[str, Any], payload: bytes | None = None) -> Mapping[str, Any]:
    """Validate one envelope and optionally verify its exact payload bytes."""
    if not isinstance(raw, Mapping):
        raise ContractError("invalid_record", "envelope must be an object")
    unknown = set(raw) - _REQUIRED - _OPTIONAL
    missing = _REQUIRED - set(raw)
    if missing:
        raise ContractError("missing_field", f"missing fields: {sorted(missing)}")
    if unknown:
        raise ContractError("unknown_field", f"unknown fields: {sorted(unknown)}")
    if raw["schema_name"] != "nvt.telemetry.chunk" or raw["schema_version"] != "1.0":
        raise ContractError("unsupported_schema", "unsupported telemetry schema")

    for name in ("event_id", "motor_id", "producer_id", "idempotency_key"):
        _require_string(raw, name)
    if raw["signal_type"] not in _SIGNALS:
        raise ContractError("invalid_field", "unsupported signal_type")
    if raw["codec"] not in _CODECS or raw["format"] not in _FORMATS:
        raise ContractError("invalid_field", "unsupported codec or format")

    start = _parse_timestamp(raw["event_start"], "event_start")
    end = _parse_timestamp(raw["event_end"], "event_end")
    if end <= start:
        raise ContractError("invalid_interval", "event_end must be later than event_start")

    for name in ("channel_count", "sample_count", "producer_sequence", "payload_byte_length"):
        value = raw[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < (0 if name == "producer_sequence" else 1):
            raise ContractError("invalid_field", f"{name} must be a valid non-negative or positive integer")
    rate = raw["sample_rate_hz"]
    if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not math.isfinite(rate) or rate <= 0:
        raise ContractError("invalid_field", "sample_rate_hz must be a positive finite number")

    checksum = raw["checksum"]
    if not isinstance(checksum, Mapping) or checksum.get("algorithm") != "sha256" or not isinstance(checksum.get("value"), str) or not _SHA256.fullmatch(checksum["value"]):
        raise ContractError("invalid_checksum", "checksum must contain a lowercase SHA-256 digest")
    if payload is not None:
        if len(payload) != raw["payload_byte_length"]:
            raise ContractError("payload_length_mismatch", "payload length does not match envelope")
        if hashlib.sha256(payload).hexdigest() != checksum["value"]:
            raise ContractError("checksum_mismatch", "payload checksum does not match envelope")
    return raw


class StatefulTelemetryValidator:
    """Apply idempotency and per-producer ordering rules to accepted envelopes."""

    def __init__(self) -> None:
        self._accepted: dict[str, tuple[str, int]] = {}
        self._last_sequence: dict[tuple[str, str], int] = {}

    def accept(self, raw: Mapping[str, Any], payload: bytes | None = None) -> ValidationResult:
        result = self.inspect(raw, payload)
        if result.status == "accepted":
            self.commit(result.envelope)
        return result

    def inspect(self, raw: Mapping[str, Any], payload: bytes | None = None) -> ValidationResult:
        """Validate and classify a record without changing validator state."""
        envelope = validate_envelope(raw, payload)
        identity = str(envelope["idempotency_key"])
        fingerprint = (str(envelope["checksum"]["value"]), int(envelope["payload_byte_length"]))
        existing = self._accepted.get(identity)
        if existing is not None:
            if existing != fingerprint:
                raise ContractError("conflicting_duplicate", "idempotency key has different payload metadata")
            return ValidationResult("duplicate", envelope)

        order_key = (str(envelope["producer_id"]), str(envelope["motor_id"]))
        sequence = int(envelope["producer_sequence"])
        previous = self._last_sequence.get(order_key)
        if previous is not None and sequence <= previous:
            raise ContractError("out_of_order", "producer sequence must increase")
        return ValidationResult("accepted", envelope)

    def commit(self, envelope: Mapping[str, Any]) -> None:
        """Record a previously inspected accepted envelope."""
        identity = str(envelope["idempotency_key"])
        fingerprint = (str(envelope["checksum"]["value"]), int(envelope["payload_byte_length"]))
        order_key = (str(envelope["producer_id"]), str(envelope["motor_id"]))
        sequence = int(envelope["producer_sequence"])
        self._accepted[identity] = fingerprint
        self._last_sequence[order_key] = sequence
