"""Cross-router helpers.

`assert_exists` collapses the ~8 copies of the "does this primary key exist?"
pattern that were previously duplicated across the route handlers.

A module-level `logger` is also exported so handlers can emit structured
log messages instead of silently swallowing exceptions.
"""

from __future__ import annotations

import logging
from typing import Any

from contextlib import contextmanager
from typing import Generator, Literal

from fastapi import HTTPException
from sqlalchemy import Column, select
from sqlalchemy.engine import Connection, Engine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("foodgraph")


def assert_exists(
    conn: Connection,
    pk_column: Column[Any],
    pk_value: Any,
    *,
    label: str,
) -> None:
    """Raise HTTP 404 if no row has `pk_column == pk_value`.

    Args:
        conn: An open SQLAlchemy connection.
        pk_column: The column to filter on (typically a primary key).
        pk_value: The value to match.
        label: Human-readable resource name used in the 404 detail, e.g. "User".
    """
    found = conn.execute(select(pk_column).where(pk_column == pk_value)).first()
    if not found:
        raise HTTPException(status_code=404, detail=f"{label} not found.")


IsolationLevel = Literal[
    "READ UNCOMMITTED",
    "READ COMMITTED",
    "REPEATABLE READ",
    "SERIALIZABLE",
]


@contextmanager
def transactional(
    engine: Engine,
    *,
    isolation_level: IsolationLevel | None = None,
) -> Generator[Connection, None, None]:
    """Open a read/write transaction, optionally pinning an isolation level.

    Postgres defaults to READ COMMITTED. Endpoints that need a stable snapshot
    across multiple queries (shopping list, consume) pass REPEATABLE READ or
    SERIALIZABLE explicitly.
    """
    with engine.connect() as conn:
        if isolation_level is not None:
            conn = conn.execution_options(isolation_level=isolation_level)
        with conn.begin():
            yield conn
