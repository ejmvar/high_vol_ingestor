from datetime import datetime, timezone

from telemetry_contract import (
    VibrationGeneratorConfig,
    generate_vibration_chunk,
    validate_envelope,
)


START = datetime(2026, 9, 10, 19, 0, tzinfo=timezone.utc)


def test_generator_is_reproducible_for_same_config_and_start() -> None:
    config = VibrationGeneratorConfig(sample_rate_hz=100, seed=42)

    first = generate_vibration_chunk(config, event_start=START)
    second = generate_vibration_chunk(config, event_start=START)

    assert first.payload == second.payload
    assert first.envelope == second.envelope


def test_generated_chunk_matches_its_envelope() -> None:
    chunk = generate_vibration_chunk(
        VibrationGeneratorConfig(sample_rate_hz=100, duration_seconds=2.0),
        event_start=START,
    )

    assert len(chunk.payload) == 100 * 2 * 2
    assert chunk.envelope["sample_count"] == 200
    assert chunk.envelope["payload_byte_length"] == len(chunk.payload)
    validate_envelope(chunk.envelope, chunk.payload)


def test_seed_changes_payload_and_checksum() -> None:
    base = VibrationGeneratorConfig(sample_rate_hz=100, seed=1)
    changed = VibrationGeneratorConfig(sample_rate_hz=100, seed=2)

    first = generate_vibration_chunk(base, event_start=START)
    second = generate_vibration_chunk(changed, event_start=START)

    assert first.payload != second.payload
    assert first.envelope["checksum"] != second.envelope["checksum"]


def test_event_end_is_derived_from_sample_count_and_rate() -> None:
    chunk = generate_vibration_chunk(
        VibrationGeneratorConfig(sample_rate_hz=100, duration_seconds=1.5),
        event_start=START,
    )

    assert chunk.envelope["event_start"] == "2026-09-10T19:00:00.000000Z"
    assert chunk.envelope["event_end"] == "2026-09-10T19:00:01.500000Z"


def test_generator_marks_clipped_samples_in_quality_metadata() -> None:
    chunk = generate_vibration_chunk(
        VibrationGeneratorConfig(sample_rate_hz=100, amplitude=1.0, noise_amplitude=0.5),
        event_start=START,
    )

    assert chunk.envelope["quality"]["clipped"] is True  # type: ignore[index]
