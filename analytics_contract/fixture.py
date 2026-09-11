"""Small canonical dataset used for cross-engine compatibility checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    observed_at: str
    signal_type: str
    value: float
    quality: str


@dataclass(frozen=True)
class Summary:
    signal_type: str
    sample_count: int
    minimum: float
    maximum: float
    average: float


FIXTURE_ROWS = (
    Observation("2026-09-10T19:00:00Z", "vibration", 1.0, "GOOD"),
    Observation("2026-09-10T19:00:01Z", "vibration", 2.0, "GOOD"),
    Observation("2026-09-10T19:00:02Z", "vibration", 3.0, "WARNING"),
    Observation("2026-09-10T19:00:00Z", "temperature", 40.0, "GOOD"),
    Observation("2026-09-10T19:00:01Z", "temperature", 42.0, "GOOD"),
)

EXPECTED_SUMMARY = (
    Summary("temperature", 2, 40.0, 42.0, 41.0),
    Summary("vibration", 3, 1.0, 3.0, 2.0),
)
