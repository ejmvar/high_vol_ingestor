from datetime import datetime, timezone

import pytest

from telemetry_contract import VibrationGeneratorConfig, generate_vibration_chunks


START = datetime(2026, 9, 10, 19, 0, tzinfo=timezone.utc)


def test_stream_emits_contiguous_increasing_chunks() -> None:
    config = VibrationGeneratorConfig(sample_rate_hz=100, duration_seconds=1.0, seed=42)

    chunks = list(generate_vibration_chunks(config, count=3, event_start=START))

    assert [chunk.envelope["producer_sequence"] for chunk in chunks] == [0, 1, 2]
    assert [chunk.envelope["event_start"] for chunk in chunks] == [
        "2026-09-10T19:00:00.000000Z",
        "2026-09-10T19:00:01.000000Z",
        "2026-09-10T19:00:02.000000Z",
    ]
    assert all(
        left.envelope["event_end"] == right.envelope["event_start"]
        for left, right in zip(chunks, chunks[1:])
    )


def test_stream_honors_initial_sequence() -> None:
    config = VibrationGeneratorConfig(sample_rate_hz=100, producer_sequence=10)

    chunks = list(generate_vibration_chunks(config, count=2, event_start=START))

    assert [chunk.envelope["producer_sequence"] for chunk in chunks] == [10, 11]


def test_stream_is_reproducible() -> None:
    config = VibrationGeneratorConfig(sample_rate_hz=100, seed=7)

    first = list(generate_vibration_chunks(config, count=3, event_start=START))
    second = list(generate_vibration_chunks(config, count=3, event_start=START))

    assert first == second


@pytest.mark.parametrize("count", [-1])
def test_stream_rejects_negative_count(count: int) -> None:
    with pytest.raises(ValueError, match="count"):
        list(generate_vibration_chunks(count=count, event_start=START))
