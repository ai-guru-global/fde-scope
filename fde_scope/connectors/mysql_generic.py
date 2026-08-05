"""MySQL connector — a real, working implementation against any MySQL 8+ server.

This is the canonical example of a "framework-agnostic FDE connector":
you point it at a DSN, and ``discover_schema`` / ``extract_sample`` /
``stream`` all work the same way they do for the CSV fallback. The
connector is registered under the ``mysql`` slug and is selected when
the FDE opts in to the ``[mysql]`` extra (``pip install fde-scope[mysql]``).

DSN format
----------
The ``source`` argument accepts a URL of the form::

    mysql://user:password@host:3306/database

or, equivalently, a keyword-argument ``dsn=...`` that the connector
parses the same way. The connector never logs the password.

Why this matters
----------------
The vast majority of customer-data environments an FDE walks into still
have a relational store at the bottom of the stack — even if the modern
surface is REST or a SaaS UI. A working MySQL connector means the
connect step of the SOP can complete on day 1, even before any bespoke
SaaS integration has been written.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import unquote, urlparse

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

# Heuristic: column names that suggest personally identifiable information.
# Mirrors the CSV connector's table so the corpus engine treats them uniformly.
_PII_NAME_HINTS = {
    "name",
    "customer_name",
    "username",
    "full_name",
    "first_name",
    "last_name",
    "email",
    "email_address",
    "phone",
    "mobile",
    "address",
    "id_card",
    "ssn",
    "passport",
}

# MySQL type -> normalized type used in :class:`SchemaField.inferred_type`.
_MYSQL_TYPE_MAP: dict[str, str] = {
    "tinyint": "int",
    "smallint": "int",
    "mediumint": "int",
    "int": "int",
    "integer": "int",
    "bigint": "int",
    "float": "float",
    "double": "float",
    "decimal": "float",
    "numeric": "float",
    "bool": "bool",
    "boolean": "bool",
    "datetime": "datetime",
    "timestamp": "datetime",
    "date": "datetime",
    "time": "datetime",
    "json": "json",
}


def _parse_dsn(dsn: str) -> dict[str, Any]:
    """Parse a ``mysql://user:pw@host:port/db`` URL into a connection-params dict.

    Falls back to treating the input as a plain ``host[:port]/database`` for
    convenience on a local dev box.
    """
    parsed = urlparse(dsn)
    if parsed.scheme not in ("mysql", "mysql+connector"):
        # Tolerate bare "host:3306/db" or "host/db" inputs.
        m = re.match(r"^(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<database>[^?]+)$", dsn)
        if m:
            return {
                "host": m.group("host"),
                "port": int(m.group("port") or 3306),
                "database": m.group("database"),
                "user": None,
                "password": None,
            }
        raise ValueError(
            f"MySQL DSN must start with mysql:// (got {dsn!r}). "
            f"Example: mysql://user:password@host:3306/database"
        )
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "database": parsed.path.lstrip("/") or None,
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
    }


def _map_mysql_type(raw: str) -> str:
    """Map a MySQL column type to the corpus engine's coarse taxonomy."""
    head = re.split(r"[\s(,]", raw, maxsplit=1)[0].lower()
    return _MYSQL_TYPE_MAP.get(head, "string")


def _looks_like_pii(column_name: str) -> bool:
    return any(h in column_name.lower() for h in _PII_NAME_HINTS)


@register
class MySQLConnector(DataConnector):
    """Connect to a MySQL 8+ server and surface its tables as a corpus."""

    connector_type = "mysql"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        # `source` is the DSN; per-call overrides may be passed via options.
        params = _parse_dsn(source)
        params.update(
            {k: v for k, v in options.items() if k in {"host", "port", "database", "user", "password"}}
        )
        self._conn_params: dict[str, Any] = params
        # Optional: scope the connector to a specific table (or a LIKE pattern).
        self._table_filter: str | None = options.get("table")
        # Cap rows when streaming so a misconfigured run can't pull billions.
        self._row_cap: int | None = options.get("row_cap")

    # -- driver lazy import -----------------------------------------------------
    def _ensure_driver(self) -> None:
        try:
            import mysql.connector  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "MySQLConnector needs the optional 'mysql' extra "
                "(mysql-connector-python): pip install 'fde-scope[mysql]'"
            ) from exc

    def _connect(self):  # pragma: no cover — thin wrapper for the test seam
        import mysql.connector

        return mysql.connector.connect(**self._conn_params)

    # -- internals --------------------------------------------------------------
    def _list_tables(self, conn) -> list[str]:
        """``SHOW TABLES`` is a one-shot; we open a dedicated dict-mode cursor
        so the parser can use ``row.values()`` uniformly. The caller may pass
        a tuple-mode cursor for the rest of its work; that's fine."""
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SHOW TABLES")
            rows = cursor.fetchall()
        finally:
            # ``mysql.connector`` cursors are disposable; the fake doesn't care.
            close = getattr(cursor, "close", None)
            if callable(close):
                close()
        all_tables = [next(iter(r.values())) for r in rows]
        if self._table_filter is None:
            return all_tables
        # Translate SQL LIKE wildcards so users can pass e.g. "ticket_%".
        pattern = re.compile(self._table_filter.replace("%", ".*").replace("_", "."))
        return [t for t in all_tables if pattern.fullmatch(t)]

    def _describe_table(self, cursor, table: str) -> list[SchemaField]:
        # Backtick-quote the table name to be safe against reserved words / hyphens.
        cursor.execute(f"DESCRIBE `{table}`")
        fields: list[SchemaField] = []
        for row in cursor.fetchall():
            col = row["Field"]
            raw_type = row["Type"]
            nullable = (row.get("Null") or "").upper() == "YES"
            fields.append(
                SchemaField(
                    name=col,
                    inferred_type=_map_mysql_type(raw_type),
                    nullable=nullable,
                    sample_values=[],
                    pii_candidate=_looks_like_pii(col),
                )
            )
        return fields

    def _count_rows(self, cursor, table: str) -> int | None:
        try:
            cursor.execute(f"SELECT COUNT(*) AS n FROM `{table}`")
            return int(cursor.fetchone()["n"])
        except Exception:
            return None

    def _row_to_dict(self, cursor_description: list, row: tuple) -> dict[str, Any]:
        # mysql-connector-python returns rows as tuples; description gives
        # the column names in order.
        return {cursor_description[i][0]: row[i] for i in range(len(row))}

    # -- the three-step contract -----------------------------------------------
    def discover_schema(self) -> Schema:
        """List all tables (filtered) with their columns, types, and counts."""
        self._ensure_driver()
        conn = self._connect()
        try:
            cursor = conn.cursor(dictionary=True)
            tables = self._list_tables(conn)
            if not tables:
                return Schema(source=self.source, fields=[], row_count=0, detected_categories=[])

            all_fields: list[SchemaField] = []
            detected_categories: list[str] = []
            total_rows = 0
            for table in tables:
                all_fields.extend(self._describe_table(cursor, table))
                # Tag every table in `detected_categories` so the FDE can pick
                # a subset to forge a corpus from via `fde-scope corpus`.
                if table not in detected_categories:
                    detected_categories.append(table)
                n = self._count_rows(cursor, table)
                if n is not None:
                    total_rows += n
            return Schema(
                source=self.source,
                fields=all_fields,
                row_count=total_rows or None,
                detected_categories=detected_categories,
            )
        finally:
            conn.close()

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        """Pull at most ``n`` rows per table for eyeball inspection."""
        self._ensure_driver()
        conn = self._connect()
        try:
            cursor = conn.cursor()
            tables = self._list_tables(conn)
            out: list[dict[str, Any]] = []
            for table in tables:
                cursor.execute(f"SELECT * FROM `{table}` LIMIT %s", (n,))
                desc = cursor.description or []
                for row in cursor.fetchall():
                    out.append(self._row_to_dict(desc, row))
                    if len(out) >= n * max(len(tables), 1):
                        break
            return out
        finally:
            conn.close()

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        """Stream every row of every (filtered) table in batches.

        Honors ``self._row_cap`` if set, so a misbehaving ``SELECT * FROM
        multi_billion_row_table`` can't OOM the FDE's laptop.
        """
        self._ensure_driver()
        conn = self._connect()
        try:
            tables = self._list_tables(conn)
            emitted = 0
            for table in tables:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM `{table}`")
                desc = cursor.description or []
                while True:
                    chunk = cursor.fetchmany(batch_size)
                    if not chunk:
                        break
                    rows = [self._row_to_dict(desc, r) for r in chunk]
                    if self._row_cap is not None:
                        remaining = self._row_cap - emitted
                        if remaining <= 0:
                            return
                        if len(rows) > remaining:
                            rows = rows[:remaining]
                    emitted += len(rows)
                    yield Batch(rows, source=f"{self.source}#{table}")
        finally:
            conn.close()
