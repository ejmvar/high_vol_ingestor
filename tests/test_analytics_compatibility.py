import pytest

from analytics_contract import EXPECTED_SUMMARY, FIXTURE_ROWS
from analytics_contract.chdb_adapter import ChDBAnalyticsAdapter, available as chdb_available
from analytics_contract.duckdb_adapter import DuckDBAnalyticsAdapter, available as duckdb_available
from analytics_contract.reference import ReferenceAnalyticsAdapter


def test_reference_fixture_has_stable_expected_summary() -> None:
    assert ReferenceAnalyticsAdapter().summarize(FIXTURE_ROWS) == EXPECTED_SUMMARY


@pytest.mark.parametrize(
    ("adapter", "available"),
    ((DuckDBAnalyticsAdapter, duckdb_available()), (ChDBAnalyticsAdapter, chdb_available())),
)
def test_available_engine_matches_reference(adapter, available: bool) -> None:
    if not available:
        pytest.skip(f"{adapter.name} optional dependency is unavailable")

    assert adapter().summarize(FIXTURE_ROWS) == EXPECTED_SUMMARY
