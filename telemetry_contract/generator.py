"""Deterministic vibration payload generation for local contract tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import math
import random
import struct


@dataclass(frozen=True)
class VibrationGeneratorConfig:
    motor_id: str = "MOTOR-c2ad"
    producer_id: str = "generator-vibration-01"
    sample_rate_hz: int = 25_600
    duration_seconds: float = 1.0
    frequency_hz: float = 120.0
    amplitude: float = 0.35
    noise_amplitude: float = 0.01
    seed: int = 1
    producer_sequence: int = 0


@dataclass(frozen=True)
class GeneratedChunk:
    envelope: dict[str, object]
    payload: bytes


def _timestamp(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def generate_vibration_chunk(
    config: VibrationGeneratorConfig = VibrationGeneratorConfig(),
    *,
    event_start: datetime | None = None,
) -> GeneratedChunk:
    """Generate one reproducible mono PCM s16le vibration chunk."""
    if config.sample_rate_hz <= 0 or config.duration_seconds <= 0:
        raise ValueError("sample rate and duration must be positive")
    if config.amplitude < 0 or config.noise_amplitude < 0:
        raise ValueError("amplitude values must be non-negative")
    if config.producer_sequence < 0:
        raise ValueError("producer sequence must be non-negative")

    start = event_start or datetime.now(timezone.utc)
    if start.tzinfo is None:
        raise ValueError("event_start must include a timezone")
    sample_count = round(config.sample_rate_hz * config.duration_seconds)
    if sample_count < 1:
        raise ValueError("duration is shorter than one sample")
    duration = sample_count / config.sample_rate_hz
    end = start + timedelta(seconds=duration)
    rng = random.Random(config.seed)
    payload = bytearray()
    clipped = False
    for index in range(sample_count):
        phase = 2.0 * math.pi * config.frequency_hz * index / config.sample_rate_hz
        value = config.amplitude * math.sin(phase)
        value += rng.uniform(-config.noise_amplitude, config.noise_amplitude)
        if not -1.0 <= value <= 1.0:
            clipped = True
        value = max(-1.0, min(1.0, value))
        payload.extend(struct.pack("<h", round(value * 32767)))
    payload_bytes = bytes(payload)
    start_text = _timestamp(start)
    end_text = _timestamp(end)
    identity = f"{config.motor_id}/vibration/{start_text}/{config.producer_sequence}"
    digest = hashlib.sha256(payload_bytes).hexdigest()
    envelope: dict[str, object] = {
        "schema_name": "nvt.telemetry.chunk",
        "schema_version": "1.0",
        "event_id": f"{config.producer_id}:{config.producer_sequence}",
        "motor_id": config.motor_id,
        "signal_type": "vibration",
        "event_start": start_text,
        "event_end": end_text,
        "sample_rate_hz": config.sample_rate_hz,
        "channel_count": 1,
        "sample_count": sample_count,
        "producer_id": config.producer_id,
        "producer_sequence": config.producer_sequence,
        "payload_byte_length": len(payload_bytes),
        "checksum": {"algorithm": "sha256", "value": digest},
        "codec": "none",
        "format": "pcm_s16le",
        "idempotency_key": identity,
        "source": {"kind": "deterministic-generator", "version": "0.1.0"},
        "quality": {"clock_synchronized": start.tzinfo is not None, "clipped": clipped, "missing_samples": 0},
    }
    return GeneratedChunk(envelope=envelope, payload=payload_bytes)
