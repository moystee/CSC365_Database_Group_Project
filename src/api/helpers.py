"""Cross-router helpers.

`assert_exists` collapses the ~8 copies of the "does this primary key exist?"
pattern that were previously duplicated across the route handlers.

A module-level `logger` is also exported so handlers can emit structured
log messages instead of silently swallowing exceptions.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Column, select
from sqlalchemy.engine import Connection


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
