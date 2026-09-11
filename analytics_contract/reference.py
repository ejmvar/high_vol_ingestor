"""Dependency-free reference implementation for parity expectations."""

from collections import defaultdict
from collections.abc import Sequence

from .fixture import Observation, Summary


class ReferenceAnalyticsAdapter:
    name = "reference"

    def summarize(self, rows: Sequence[Observation]) -> tuple[Summary, ...]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            grouped[row.signal_type].append(row.value)
        return tuple(
            Summary(signal, len(values), min(values), max(values), sum(values) / len(values))
            for signal, values in sorted(grouped.items())
        )
