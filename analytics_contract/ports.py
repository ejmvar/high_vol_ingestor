"""Application-facing analytics port."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .fixture import Observation, Summary


class AnalyticsAdapter(Protocol):
    """Minimal query surface shared by embedded and server adapters."""

    name: str

    def summarize(self, rows: Sequence[Observation]) -> tuple[Summary, ...]:
        """Return deterministic summaries for the supplied observations."""
