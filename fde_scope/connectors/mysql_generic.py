"""Generic MySQL connector — SQL skeleton.

STATUS: skeleton. The real implementation will use
``mysql-connector-python`` (an optional extra) and a configurable SQL query /
table name. The contract surface is in place.

Roadmap hook: accepts ``query`` or ``table`` in options; defaults to a full
``SELECT * FROM {table}`` if only a table is given.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema


@register
class MySQLConnector(DataConnector):
    """Connect to a generic MySQL database.

    ``source`` is a libpq-style or plain host string; full connection params
    (user/password/port/database) arrive via ``options``.
    """

    type = "mysql"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.host = source
        self.user = options.get("user", "")
        self.password = options.get("password", "")
        self.database = options.get("database", "")
        self.table = options.get("table")
        self.query = options.get("query")

    def _ensure_driver(self) -> None:
        try:
            import mysql.connector  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "MySQLConnector needs the optional 'mysql' extra: "
                "pip install 'fde-scope[mysql]'"
            ) from exc

    def discover_schema(self) -> Schema:
        # TODO: `SELECT * FROM {table} LIMIT 1` → describe columns.
        self._ensure_driver()
        return Schema(source=f"mysql://{self.host}/{self.database}", fields=[])

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        # TODO: `... LIMIT {n}`
        self._ensure_driver()
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        # TODO: server-side cursor, fetchmany(batch_size).
        self._ensure_driver()
        return
        yield  # pragma: no cover
