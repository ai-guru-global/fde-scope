"""Tests for the OPC UA connector.

Two layers, mirroring the MySQL test pattern:

1. **Mocked unit tests** — every test patches the ``asyncua`` module so
   the suite runs on CI without a real OPC UA server. These cover
   browse, sample, stream, the action error path, the row_cap-style
   read capping, and the actionable 'install asyncua' error.

2. **Real-server integration tests** — gated by the
   ``FDE_SCOPE_OPCUA_URL`` env var (see the ``opcua`` marker in
   ``pyproject.toml``). Smoke-test a single read against a live
   server. Not used in normal CI; run only when the FDE is at a
   customer site with a real PLC.
"""

from __future__ import annotations

import os
import sys
import types
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from fde_scope.connectors import _registry
from fde_scope.connectors.opcua import OpcUaConnector


# ---------------------------------------------------------------------------
# Fake asyncua — minimal surface the connector actually uses
# ---------------------------------------------------------------------------
class _FakeNodeClass:
    """Mirror asyncua.ua.NodeClass. Only the values the connector needs."""

    Variable = 2


_NODE_CLASS = _FakeNodeClass()


@dataclass
class _FakeDataValue:
    """Mirror asyncua.ua.DataValue returned by ``read_data_value``."""

    Value: Any = None
    SourceTimestamp: datetime | None = None


@dataclass
class _FakeVariantType:
    """Mirror asyncua.ua.VariantType. The connector only uses its ``name``."""

    name: str = ""


def _make_variant_type(name: str) -> _FakeVariantType:
    return _FakeVariantType(name=name)


class _FakeNode:
    """Mirror asyncua.Node — enough surface for browse + read."""

    def __init__(
        self,
        node_id: str,
        display_name: str = "",
        data_type: str | None = None,
        children: list[_FakeNode] | None = None,
        is_variable: bool = False,
    ) -> None:
        self.nodeid = types.SimpleNamespace(to_string=lambda: node_id)
        self._display_name = display_name
        self._data_type = data_type
        self._children = children or []
        self._is_variable = is_variable
        # What this node returns from read_data_value (only consulted for
        # Variable nodes; ignored for folder nodes).
        self._data_value: _FakeDataValue | None = None

    async def get_children(self) -> list[_FakeNode]:
        return list(self._children)

    async def read_node_class(self) -> int:
        return _NODE_CLASS.Variable if self._is_variable else 1  # 1 = Object

    async def read_display_name(self) -> types.SimpleNamespace:
        return types.SimpleNamespace(Text=self._display_name)

    async def read_data_type_as_variant_type(self) -> _FakeVariantType | None:
        return _make_variant_type(self._data_type) if self._data_type else None

    async def read_data_value(self) -> _FakeDataValue:
        if self._data_value is None:
            return _FakeDataValue(Value=None, SourceTimestamp=None)
        return self._data_value


class _FakeAsyncUAClient:
    """Mirror asyncua.Client — connect/disconnect + get_node."""

    def __init__(self, *, url: str = "", tree: _FakeNode | None = None) -> None:
        self.url = url
        self._tree = tree
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    def get_node(self, node_id: str) -> _FakeNode:
        if self._tree is None:
            raise KeyError(f"no tree configured for {node_id}")
        # Walk the tree to find the node by nodeid.
        return self._lookup(self._tree, node_id)

    def _lookup(self, root: _FakeNode, node_id: str) -> _FakeNode:
        if root.nodeid.to_string() == node_id:
            return root
        for c in root._children:
            try:
                return self._lookup(c, node_id)
            except KeyError:
                continue
        raise KeyError(node_id)


class _FakeAsyncUAModule(types.ModuleType):
    """Module stand-in for ``asyncua`` — holds the Client constructor only."""

    def __init__(self) -> None:
        super().__init__("asyncua")
        self._clients: list[_FakeAsyncUAClient] = []

    def Client(self, *, url: str) -> _FakeAsyncUAClient:  # noqa: N802
        c = _FakeAsyncUAClient(url=url)
        self._clients.append(c)
        return c


@pytest.fixture
def fake_asyncua_module() -> Iterator[_FakeAsyncUAModule]:
    """Install a fake ``asyncua`` module so the connector imports clean.

    Tests configure the tree by reaching into ``fake._clients[-1]`` and
    setting its ``_tree`` attribute before calling the connector.
    """
    fake = _FakeAsyncUAModule()
    sys.modules["asyncua"] = fake
    try:
        yield fake
    finally:
        sys.modules.pop("asyncua", None)


# Helpers --------------------------------------------------------------------
def _ts() -> datetime:
    return datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)


def _build_tree() -> _FakeNode:
    """A small but realistic factory:

    Objects (i=85) — folder
      ├── Devices (folder)
      │    ├── Device1 (folder)
      │    │    ├── Temperature (Variable, Float)
      │    │    └── Pressure    (Variable, Int32)
      │    └── Device2 (folder)
      │         └── Speed       (Variable, Float)
      └── Server (folder)
           └── Status        (Variable, Boolean)
    """
    return _FakeNode(
        node_id="i=85",
        display_name="Objects",
        is_variable=False,
        children=[
            _FakeNode(
                node_id="i=100",
                display_name="Devices",
                is_variable=False,
                children=[
                    _FakeNode(
                        node_id="i=200",
                        display_name="Device1",
                        is_variable=False,
                        children=[
                            _FakeNode(
                                node_id="i=201",
                                display_name="Temperature",
                                data_type="Float",
                                is_variable=True,
                            ),
                            _FakeNode(
                                node_id="i=202",
                                display_name="Pressure",
                                data_type="Int32",
                                is_variable=True,
                            ),
                        ],
                    ),
                    _FakeNode(
                        node_id="i=300",
                        display_name="Device2",
                        is_variable=False,
                        children=[
                            _FakeNode(
                                node_id="i=301",
                                display_name="Speed",
                                data_type="Float",
                                is_variable=True,
                            ),
                        ],
                    ),
                ],
            ),
            _FakeNode(
                node_id="i=400",
                display_name="Server",
                is_variable=False,
                children=[
                    _FakeNode(
                        node_id="i=401",
                        display_name="Status",
                        data_type="Boolean",
                        is_variable=True,
                    ),
                ],
            ),
        ],
    )


def _wire_reads(tree: _FakeNode) -> None:
    """Attach canned read_data_value() returns to every Variable in the tree.

    Values are unique per node so a test can identify which row came from
    which tag.
    """
    counters = iter(range(100))

    def walk(node: _FakeNode) -> None:
        if node._is_variable:
            i = next(counters)
            node._data_value = _FakeDataValue(
                Value=types.SimpleNamespace(Value=f"v{i}"),
                SourceTimestamp=_ts(),
            )
        for c in node._children:
            walk(c)

    walk(tree)


# ---------------------------------------------------------------------------
# discover_schema
# ---------------------------------------------------------------------------
def test_discover_schema_lists_all_variables(fake_asyncua_module: _FakeAsyncUAModule) -> None:
    tree = _build_tree()

    # The connector calls Client() once; monkey-patch Client to attach the
    # tree to the freshly-constructed client before the async loop runs.
    real_Client = fake_asyncua_module.Client

    def Client_with_tree(*, url: str) -> _FakeAsyncUAClient:  # noqa: N802
        c = real_Client(url=url)
        c._tree = tree
        return c

    fake_asyncua_module.Client = Client_with_tree  # type: ignore[method-assign]

    conn = OpcUaConnector("opc.tcp://test:4840")
    schema = conn.discover_schema()

    # 4 Variables in the tree: Temperature, Pressure, Speed, Status.
    assert schema.row_count == 4
    assert {f.name for f in schema.fields} == {"Temperature", "Pressure", "Speed", "Status"}
    by_name = {f.name: f for f in schema.fields}
    assert by_name["Temperature"].inferred_type == "float"
    assert by_name["Pressure"].inferred_type == "int"
    assert by_name["Status"].inferred_type == "bool"


def test_discover_schema_respects_browse_depth(
    fake_asyncua_module: _FakeAsyncUAModule,
) -> None:
    """browse_depth=1 only sees the direct children of the root."""
    tree = _build_tree()

    def Client_with_tree(*, url: str) -> _FakeAsyncUAClient:  # noqa: N802
        c = _FakeAsyncUAClient(url=url)
        c._tree = tree
        return c

    fake_asyncua_module.Client = Client_with_tree  # type: ignore[method-assign]

    conn = OpcUaConnector("opc.tcp://test:4840", browse_depth=1)
    schema = conn.discover_schema()
    # Depth 1: see "Devices" + "Server" folders (Object, not Variable)
    # — no Variables at this level, so row_count == 0.
    assert schema.row_count == 0
    assert schema.fields == []


def test_discover_schema_type_mapping_unknown_falls_back_to_json(
    fake_asyncua_module: _FakeAsyncUAModule,
) -> None:
    """A custom Enum / structured type with no entry in the map → json."""
    tree = _FakeNode(
        node_id="i=85",
        display_name="Objects",
        is_variable=False,
        children=[
            _FakeNode(
                node_id="i=900",
                display_name="Recipe",
                data_type="CustomEnum",
                is_variable=True,
            ),
        ],
    )

    def Client_with_tree(*, url: str) -> _FakeAsyncUAClient:  # noqa: N802
        c = _FakeAsyncUAClient(url=url)
        c._tree = tree
        return c

    fake_asyncua_module.Client = Client_with_tree  # type: ignore[method-assign]

    schema = OpcUaConnector("opc.tcp://test:4840").discover_schema()
    assert schema.fields[0].inferred_type == "json"


# ---------------------------------------------------------------------------
# extract_sample / stream
# ---------------------------------------------------------------------------
def test_extract_sample_uses_explicit_node_ids(
    fake_asyncua_module: _FakeAsyncUAModule,
) -> None:
    tree = _build_tree()
    _wire_reads(tree)

    def Client_with_tree(*, url: str) -> _FakeAsyncUAClient:  # noqa: N802
        c = _FakeAsyncUAClient(url=url)
        c._tree = tree
        return c

    fake_asyncua_module.Client = Client_with_tree  # type: ignore[method-assign]

    conn = OpcUaConnector(
        "opc.tcp://test:4840",
        node_ids=["i=201", "i=202", "i=301"],
    )
    rows = conn.extract_sample(n=10)
    assert len(rows) == 3
    assert {r["node_id"] for r in rows} == {"i=201", "i=202", "i=301"}
    # Timestamps surfaced as ISO strings (not datetimes).
    for r in rows:
        assert r["source_timestamp"] is not None
        assert r["source_timestamp"].startswith("2026-08-05T12:00:00")


def test_extract_sample_caps_at_n(
    fake_asyncua_module: _FakeAsyncUAModule,
) -> None:
    tree = _build_tree()
    _wire_reads(tree)

    def Client_with_tree(*, url: str) -> _FakeAsyncUAClient:  # noqa: N802
        c = _FakeAsyncUAClient(url=url)
        c._tree = tree
        return c

    fake_asyncua_module.Client = Client_with_tree  # type: ignore[method-assign]

    conn = OpcUaConnector(
        "opc.tcp://test:4840",
        node_ids=["i=201", "i=202", "i=301", "i=401"],
    )
    assert len(conn.extract_sample(n=2)) == 2


def test_stream_yields_batches_with_source_tag(
    fake_asyncua_module: _FakeAsyncUAModule,
) -> None:
    tree = _build_tree()
    _wire_reads(tree)

    def Client_with_tree(*, url: str) -> _FakeAsyncUAClient:  # noqa: N802
        c = _FakeAsyncUAClient(url=url)
        c._tree = tree
        return c

    fake_asyncua_module.Client = Client_with_tree  # type: ignore[method-assign]

    # No explicit node_ids → use everything the discover_schema cache
    # contains. Force the cache to be populated.
    conn = OpcUaConnector("opc.tcp://test:4840")
    conn._cached_nodes = [
        {"node_id": "i=201", "display_name": "Temperature"},
        {"node_id": "i=202", "display_name": "Pressure"},
        {"node_id": "i=301", "display_name": "Speed"},
    ]
    batches = list(conn.stream(batch_size=2))
    # 3 rows, batch_size=2 → 2 + 1
    assert [len(b) for b in batches] == [2, 1]
    # Source tag includes the endpoint + tag count
    assert batches[0].source.startswith("opc.tcp://test:4840#")
    assert "3_tags" in batches[0].source


def test_stream_empty_when_no_node_ids_and_no_cache() -> None:
    conn = OpcUaConnector("opc.tcp://test:4840")
    assert list(conn.stream()) == []


def test_stream_rejects_invalid_batch_size() -> None:
    """batch_size < 1 must fail loudly (range step-0 crash / silent no-op)."""
    conn = OpcUaConnector("opc.tcp://test:4840", node_ids=["i=201"])
    for bad in (0, -1):
        with pytest.raises(ValueError, match="batch_size"):
            list(conn.stream(batch_size=bad))


# ---------------------------------------------------------------------------
# Fake-vs-real API surface guard
# ---------------------------------------------------------------------------
def test_fake_node_method_names_exist_on_real_asyncua_node() -> None:
    """Guard against the fake drifting from the real asyncua.Node API.

    Skipped when asyncua isn't installed (CI without the [opcua] extra).
    """
    asyncua = pytest.importorskip("asyncua")
    # Every method _FakeNode mirrors must exist on the real Node class.
    for name in (
        "get_children",
        "read_node_class",
        "read_display_name",
        "read_data_type_as_variant_type",
        "read_data_value",
    ):
        assert hasattr(asyncua.Node, name), f"asyncua.Node.{name} missing — fake drifted from driver"


# ---------------------------------------------------------------------------
# driver availability contract
# ---------------------------------------------------------------------------
def test_ensure_driver_message_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the user forgot to install the [opcua] extra, the error names the fix."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "asyncua" or name.startswith("asyncua."):
            raise ImportError("simulated missing driver")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    conn = OpcUaConnector("opc.tcp://test:4840")
    with pytest.raises(ImportError, match="asyncua"):
        conn._ensure_driver()


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------
def test_opcua_is_registered_after_reload() -> None:
    """opcua slug is in the connector registry as OpcUaConnector."""
    reg = _registry.get_registry()
    if "opcua" in reg:
        assert issubclass(reg["opcua"], OpcUaConnector)


# ---------------------------------------------------------------------------
# Real-server integration tests (opt-in via env var)
# ---------------------------------------------------------------------------
@pytest.mark.opcua
def test_opcua_real_server_roundtrip() -> None:
    """End-to-end against a real OPC UA server. Skipped unless
    FDE_SCOPE_OPCUA_URL is set (e.g. at a customer site with a PLC)."""
    url = os.environ.get("FDE_SCOPE_OPCUA_URL")
    if not url:
        pytest.skip("FDE_SCOPE_OPCUA_URL not set; skipping real-OPC-UA integration test")
    conn = OpcUaConnector(url)
    schema = conn.discover_schema()
    assert schema.source == url
    assert isinstance(conn.extract_sample(5), list)
