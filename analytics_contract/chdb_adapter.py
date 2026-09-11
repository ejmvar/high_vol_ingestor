"""Optional chDB adapter; importable only when chDB is installed."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from io import StringIO

from .fixture import Observation, Summary


class ChDBAnalyticsAdapter:
    name = "chdb"

    def summarize(self, rows: Sequence[Observation]) -> tuple[Summary, ...]:
        from chdb import session

        database = session.Session(":memory:")
        try:
            database.query(
                "CREATE TABLE observations (observed_at String, signal_type String, value Float64, quality String) "
                "ENGINE = Memory"
            )
            values = ", ".join(
                f"('{row.observed_at}', '{row.signal_type}', {row.value}, '{row.quality}')"
                for row in rows
            )
            database.query(f"INSERT INTO observations VALUES {values}")
            output = str(database.query(
                "SELECT signal_type, count(), min(value), max(value), avg(value) "
                "FROM observations GROUP BY signal_type ORDER BY signal_type",
                fmt="CSV",
            ))
            parsed = csv.reader(StringIO(output))
            return tuple(
                Summary(row[0], int(row[1]), float(row[2]), float(row[3]), float(row[4]))
                for row in parsed
                if row
            )
        finally:
            database.close()


def available() -> bool:
    try:
        import chdb  # noqa: F401
    except ImportError:
        return False
    return True
