"""Run the canonical fixture against available analytics adapters."""

from __future__ import annotations

import sys

from .chdb_adapter import ChDBAnalyticsAdapter, available as chdb_available
from .duckdb_adapter import DuckDBAnalyticsAdapter, available as duckdb_available
from .fixture import EXPECTED_SUMMARY, FIXTURE_ROWS
from .reference import ReferenceAnalyticsAdapter


def main() -> int:
    expected = ReferenceAnalyticsAdapter().summarize(FIXTURE_ROWS)
    if expected != EXPECTED_SUMMARY:
        print("FAIL reference fixture expectation mismatch")
        return 1
    print("PASS reference")

    unavailable = 0
    for adapter_type, is_available in (
        (DuckDBAnalyticsAdapter, duckdb_available()),
        (ChDBAnalyticsAdapter, chdb_available()),
    ):
        name = adapter_type.name
        if not is_available:
            print(f"UNAVAILABLE {name}: optional dependency is not installed")
            unavailable += 1
            continue
        if adapter_type().summarize(FIXTURE_ROWS) != expected:
            print(f"FAIL {name}: result parity mismatch")
            return 1
        print(f"PASS {name}")
    return 2 if unavailable else 0


if __name__ == "__main__":
    sys.exit(main())
