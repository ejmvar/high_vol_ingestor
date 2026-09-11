"""Consecutive deterministic telemetry chunk production."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta

from .generator import GeneratedChunk, VibrationGeneratorConfig, generate_vibration_chunk


def generate_vibration_chunks(
    config: VibrationGeneratorConfig = VibrationGeneratorConfig(),
    *,
    count: int,
    event_start: datetime,
) -> Iterator[GeneratedChunk]:
    """Yield a bounded sequence of contiguous, ordered vibration chunks."""
    if count < 0:
        raise ValueError("count must be non-negative")
    if event_start.tzinfo is None:
        raise ValueError("event_start must include a timezone")

    chunk_duration = timedelta(seconds=config.duration_seconds)
    for offset in range(count):
        chunk_config = replace(config, producer_sequence=config.producer_sequence + offset)
        yield generate_vibration_chunk(
            chunk_config,
            event_start=event_start + offset * chunk_duration,
        )
