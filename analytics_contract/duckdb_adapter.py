"""Optional DuckDB adapter; importable only when DuckDB is installed."""

from __future__ import annotations

from collections.abc import Sequence

from .fixture import Observation, Summary


class DuckDBAnalyticsAdapter:
    name = "duckdb"

    def summarize(self, rows: Sequence[Observation]) -> tuple[Summary, ...]:
        import duckdb

        connection = duckdb.connect(":memory:")
        try:
            connection.execute(
                "CREATE TABLE observations (observed_at VARCHAR, signal_type VARCHAR, value DOUBLE, quality VARCHAR)"
            )
            connection.executemany(
                "INSERT INTO observations VALUES (?, ?, ?, ?)",
                [(row.observed_at, row.signal_type, row.value, row.quality) for row in rows],
            )
            result = connection.execute(
                "SELECT signal_type, COUNT(*), MIN(value), MAX(value), AVG(value) "
                "FROM observations GROUP BY signal_type ORDER BY signal_type"
            ).fetchall()
            return tuple(Summary(str(signal), int(count), float(minimum), float(maximum), float(average))
                         for signal, count, minimum, maximum, average in result)
        finally:
            connection.close()


def available() -> bool:
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return False
    return True
