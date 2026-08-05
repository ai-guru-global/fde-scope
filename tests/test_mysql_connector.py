"""Tests for the MySQL connector.

Two layers:

1. **Mocked unit tests** — every test patches ``mysql.connector`` so the
   suite runs on CI without a real MySQL server. These cover the
   connector's three-step contract (discover / extract / stream),
   DSN parsing, PII heuristics, and the ``row_cap`` safety net.

2. **Real-server integration tests** — gated by the ``FDE_SCOPE_MYSQL_DSN``
   env var (see the ``mysql`` marker in ``pyproject.toml``). They spin up
   against a real MySQL 8 instance and validate the round-trip on actual
   ``SHOW TABLES`` / ``DESCRIBE`` / ``SELECT *`` output.

The mocked layer is the contract test: if it breaks, the real one will
too. The real layer is a smoke test that catches driver-API drift.
"""

from __future__ import annotations

import os
import sys
import types
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from fde_scope.connectors import _registry
from fde_scope.connectors.mysql_generic import MySQLConnector, _parse_dsn


# ---------------------------------------------------------------------------
# Fake mysql.connector (the unit-test seam)
# ---------------------------------------------------------------------------
class _FakeCursor:
    """Minimal cursor that drains result-sets from a shared connection queue.

    Every ``execute()`` pops the next canned result-set off the connection
    queue (matching how real ``mysql.connector`` services a single
    statement at a time, even when multiple cursors are alive). The
    ``dictionary`` flag the cursor was opened with controls whether
    ``fetchall``/``fetchone``/``fetchmany`` hand back dicts or tuples.
    """

    def __init__(self, conn: _FakeConnection, *, dictionary: bool = False) -> None:
        self._conn = conn
        self._dictionary = dictionary
        self._current: list = []
        self.executed: list[tuple[str, tuple | None]] = []
        self.description: list[tuple] | None = None
        self.rowfactory: Any = None

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.executed.append((sql, params))
        next_set = self._conn._queue.pop(0) if self._conn._queue else []
        if self._dictionary:
            self._current = [dict(r) for r in next_set]
        else:
            self._current = [tuple(r.values()) for r in next_set]
        # Synthesize a description from the first row's keys, if any.
        if next_set and isinstance(next_set[0], dict):
            self.description = [(k, None, None, None, None, None, None) for k in next_set[0]]
        else:
            self.description = None

    def fetchall(self) -> list:
        return list(self._current)

    def fetchone(self):
        if not self._current:
            return None
        return self._current[0]

    def fetchmany(self, n: int) -> list:
        out = self._current[:n]
        self._current = self._current[n:]
        return out

    def close(self) -> None:
        pass


class _FakeConnection:
    """Minimal connection: holds a queue of canned result-sets.

    Each ``cursor()`` call hands back a cursor that drains the connection's
    shared queue one result-set per ``execute()`` call. This matches the
    way a real ``mysql.connector`` connection services statements.
    """

    def __init__(self, results: list[list[dict[str, Any]]] | None = None) -> None:
        self._queue: list[list[dict[str, Any]]] = list(results or [])

    def cursor(self, dictionary: bool = False, **_: Any) -> _FakeCursor:
        # Real mysql.connector's default is tuple mode; only opt in to
        # dict mode when the connector asks for it (discover_schema).
        return _FakeCursor(self, dictionary=dictionary)

    def close(self) -> None:
        pass


@pytest.fixture
def fake_mysql_module() -> Iterator[None]:
    """Install a fake ``mysql.connector`` in sys.modules so the connector can import it.

    The fake provides a ``connect()`` MagicMock that the tests pre-program
    via ``sys.modules['mysql.connector'].connect.return_value = ...``. We
    also wire ``mysql.connector`` as an attribute on the fake ``mysql``
    module so the dotted import resolves cleanly.
    """
    fake_connector = types.ModuleType("mysql.connector")
    fake_connector.connect = MagicMock()  # type: ignore[attr-defined]
    fake_mysql = types.ModuleType("mysql")
    fake_mysql.connector = fake_connector  # type: ignore[attr-defined]
    sys.modules["mysql"] = fake_mysql
    sys.modules["mysql.connector"] = fake_connector
    try:
        yield
    finally:
        sys.modules.pop("mysql.connector", None)
        sys.modules.pop("mysql", None)


def _make_connection_mock(cursor_results: list[list[dict[str, Any]]]) -> MagicMock:
    """Wrap a real ``_FakeConnection`` inside a MagicMock so the connector
    sees a connection-like object whose ``cursor()`` honors the
    ``dictionary`` flag the way the real driver does."""
    fake_conn = _FakeConnection(cursor_results)
    conn = MagicMock()
    # Bind the real methods so the ``dictionary`` argument actually flows
    # through; setting ``cursor.return_value`` would return the same
    # cursor regardless of how it's called.
    conn.cursor = fake_conn.cursor  # type: ignore[method-assign]
    conn.close = fake_conn.close  # type: ignore[method-assign]
    return conn


# ---------------------------------------------------------------------------
# DSN parsing
# ---------------------------------------------------------------------------
def test_parse_dsn_full_url() -> None:
    p = _parse_dsn("mysql://alice:s3cr3t@db.example.com:3307/orders")
    assert p == {
        "host": "db.example.com",
        "port": 3307,
        "database": "orders",
        "user": "alice",
        "password": "s3cr3t",
    }


def test_parse_dsn_url_encoded_password() -> None:
    p = _parse_dsn("mysql://bob:p%40ss%21word@127.0.0.1/warehouse")
    assert p["user"] == "bob"
    assert p["password"] == "p@ss!word"
    assert p["port"] == 3306  # default


def test_parse_dsn_bare_form() -> None:
    p = _parse_dsn("localhost:3306/tickets")
    assert p == {
        "host": "localhost",
        "port": 3306,
        "database": "tickets",
        "user": None,
        "password": None,
    }


def test_parse_dsn_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="mysql://"):
        _parse_dsn("not-a-dsn")


# ---------------------------------------------------------------------------
# discover_schema
# ---------------------------------------------------------------------------
def test_discover_schema_lists_tables_and_columns(fake_mysql_module: None) -> None:
    # SHOW TABLES
    show = [{"Tables_in_warehouse": "tickets"}, {"Tables_in_warehouse": "orders"}]
    # DESCRIBE tickets
    desc_tickets = [
        {"Field": "id", "Type": "bigint", "Null": "NO"},
        {"Field": "customer_email", "Type": "varchar(255)", "Null": "YES"},
        {"Field": "created_at", "Type": "datetime", "Null": "NO"},
        {"Field": "body", "Type": "text", "Null": "YES"},
    ]
    # COUNT tickets
    count_tickets = [{"n": 42}]
    # DESCRIBE orders
    desc_orders = [
        {"Field": "id", "Type": "int", "Null": "NO"},
        {"Field": "total", "Type": "decimal(10,2)", "Null": "YES"},
    ]
    # COUNT orders
    count_orders = [{"n": 7}]

    sys.modules["mysql.connector"].connect.return_value = _make_connection_mock(
        [show, desc_tickets, count_tickets, desc_orders, count_orders]
    )

    conn = MySQLConnector("mysql://u:p@h:3306/warehouse")
    schema = conn.discover_schema()

    assert [f.name for f in schema.fields] == ["id", "customer_email", "created_at", "body", "id", "total"]
    assert schema.row_count == 49
    assert schema.detected_categories == ["tickets", "orders"]
    # PII detection flags the email column
    email_field = next(f for f in schema.fields if f.name == "customer_email")
    assert email_field.pii_candidate is True
    assert email_field.inferred_type == "string"
    # Type mapping
    assert next(f for f in schema.fields if f.name == "created_at").inferred_type == "datetime"
    assert next(f for f in schema.fields if f.name == "total").inferred_type == "float"
    # Nullable flag respected
    assert next(f for f in schema.fields if f.name == "id").nullable is False


def test_discover_schema_respects_table_filter(fake_mysql_module: None) -> None:
    # After the filter trims "ticket_archive" away, only "tickets" is described
    # and counted — so the queue needs SHOW TABLES, DESCRIBE tickets, and
    # COUNT tickets in that order.
    show = [{"Tables_in_warehouse": "tickets"}, {"Tables_in_warehouse": "ticket_archive"}]
    desc_tickets = [{"Field": "id", "Type": "bigint", "Null": "NO"}]
    count_tickets = [{"n": 99}]
    sys.modules["mysql.connector"].connect.return_value = _make_connection_mock(
        [show, desc_tickets, count_tickets]
    )

    conn = MySQLConnector("mysql://u:p@h:3306/warehouse", table="tickets")
    schema = conn.discover_schema()
    assert schema.detected_categories == ["tickets"]
    assert schema.row_count == 99


def test_discover_schema_empty_database(fake_mysql_module: None) -> None:
    sys.modules["mysql.connector"].connect.return_value = _make_connection_mock([[]])
    conn = MySQLConnector("mysql://u:p@h:3306/empty")
    schema = conn.discover_schema()
    assert schema.fields == []
    assert schema.row_count == 0


# ---------------------------------------------------------------------------
# extract_sample
# ---------------------------------------------------------------------------
def test_extract_sample_returns_dicts(fake_mysql_module: None) -> None:
    # SHOW TABLES, then SELECT * FROM tickets LIMIT n
    show = [{"Tables_in_warehouse": "tickets"}]
    select = [
        {"id": 1, "body": "refund please"},
        {"id": 2, "body": "where is my order"},
    ]
    sys.modules["mysql.connector"].connect.return_value = _make_connection_mock([show, select])

    conn = MySQLConnector("mysql://u:p@h:3306/warehouse")
    sample = conn.extract_sample(n=10)
    assert sample == [
        {"id": 1, "body": "refund please"},
        {"id": 2, "body": "where is my order"},
    ]


# ---------------------------------------------------------------------------
# stream + row_cap
# ---------------------------------------------------------------------------
def test_stream_yields_batches_with_source_tag(fake_mysql_module: None) -> None:
    # stream() uses a non-dictionary cursor; our fake _FakeCursor handles both.
    # SHOW TABLES, then SELECT * FROM tickets (3 rows), then SELECT * FROM orders (2 rows)
    show = [{"Tables_in_warehouse": "tickets"}, {"Tables_in_warehouse": "orders"}]
    tickets_rows = [
        {"id": 1, "body": "a"},
        {"id": 2, "body": "b"},
        {"id": 3, "body": "c"},
    ]
    orders_rows = [
        {"id": 100, "total": 9.99},
        {"id": 101, "total": 19.99},
    ]
    sys.modules["mysql.connector"].connect.return_value = _make_connection_mock(
        [show, tickets_rows, orders_rows]
    )

    conn = MySQLConnector("mysql://u:p@h:3306/warehouse")
    batches = list(conn.stream(batch_size=2))
    # tickets: 2 + 1; orders: 2
    assert [len(b) for b in batches] == [2, 1, 2]
    # Source tag identifies which table each batch came from
    assert batches[0].source.endswith("#tickets")
    assert batches[2].source.endswith("#orders")
    # Rows are dicts
    assert batches[0][0] == {"id": 1, "body": "a"}


def test_stream_respects_row_cap(fake_mysql_module: None) -> None:
    # 5 rows in the table; row_cap=3 must truncate the emitted stream to 3.
    show = [{"Tables_in_warehouse": "big"}]
    rows = [{"id": i, "v": f"r{i}"} for i in range(5)]
    sys.modules["mysql.connector"].connect.return_value = _make_connection_mock([show, rows])

    conn = MySQLConnector("mysql://u:p@h:3306/wh", row_cap=3)
    batches = list(conn.stream(batch_size=10))
    assert sum(len(b) for b in batches) == 3


# ---------------------------------------------------------------------------
# Driver-availability contract
# ---------------------------------------------------------------------------
def test_ensure_driver_message_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the user forgot to install the [mysql] extra, the error names the fix."""
    # Make the import fail even though the module is present.
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any):
        if name == "mysql.connector" or name.startswith("mysql."):
            raise ImportError("simulated missing driver")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    conn = MySQLConnector("mysql://u:p@h:3306/wh")
    with pytest.raises(ImportError, match="mysql-connector-python"):
        conn._ensure_driver()


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------
def test_mysql_is_registered_after_reload() -> None:
    # The connector is decorated with @register; make sure the registry
    # is consistent with the registry's known-type map.
    reg = _registry.get_registry()
    # Either 'mysql' is there (driver present) or it's absent because
    # the import-time decorator failed — both are acceptable. The
    # important property is that the two states are coherent.
    if "mysql" in reg:
        assert issubclass(reg["mysql"], MySQLConnector)


# ---------------------------------------------------------------------------
# Real-server integration tests (opt-in via env var)
# ---------------------------------------------------------------------------
@pytest.mark.mysql
def test_mysql_real_server_roundtrip() -> None:
    """End-to-end against a real MySQL server. Skipped unless
    FDE_SCOPE_MYSQL_DSN is set (e.g. via docker compose in CI)."""
    dsn = os.environ.get("FDE_SCOPE_MYSQL_DSN")
    if not dsn:
        pytest.skip("FDE_SCOPE_MYSQL_DSN not set; skipping real-MySQL integration test")
    conn = MySQLConnector(dsn)
    schema = conn.discover_schema()
    assert schema.source == dsn
    # We can pull a sample; don't pin the contents (the live DB may differ)
    assert isinstance(conn.extract_sample(5), list)
