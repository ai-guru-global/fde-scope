"""OPC UA connector — the de-facto Level 2-3 industrial integration layer.

This is a real, working implementation against any OPC UA server (Siemens
S7-1200/S7-1500 ship with one built-in; Rockwell, Mitsubishi, Omron
all expose OPC UA endpoints). It uses the ``asyncua`` library against
the server's address space: browse nodes for ``discover_schema``,
read the configured tags for ``extract_sample`` and ``stream``.

The classical 2025/2026 industrial pattern is::

    OPC UA at the machine
        -> edge gateway translates to MQTT/Sparkplug B
        -> broker
        -> UNS / historian / cloud

So this connector is the *machine-side* end of that pipeline. It pairs
naturally with the MQTT-Sparkplug connector on the cloud side.

DSN
---
- ``source`` (positional) — the endpoint URL, e.g. ``opc.tcp://10.0.0.5:4840``
- options:
    * ``root_node`` — NodeId string to start the browse from. Defaults to
      the standard ``Objects`` folder (i=85). Use this to scope the
      schema discovery to a specific device subtree on a multi-device
      server.
    * ``browse_depth`` — int, how many levels of the address space to
      recurse into. Default 3. Past ~5 the schema explodes.
    * ``node_ids`` — list of NodeId strings to read on sample/stream.
      If empty, the connector reads every Variable node it found during
      the last ``discover_schema`` call.
    * ``browse_timeout`` — float, seconds per asyncua call. Default 5.0.

Concurrency
-----------
``asyncua`` is async, but the connector contract is sync. We bridge via
``asyncio.run()``. That means the connector must be called from a
sync context (a CLI invocation, a FastAPI worker thread, a test
function). It cannot be called from inside an existing asyncio event
loop — the FDE workbench always runs in a sync context, so this is
fine, but a future web-UI streaming endpoint that wants to subscribe
would need to await the async API directly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any, ClassVar

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

# Common NodeId prefix -> inferred SchemaField type. Variants of
# ``i=`` / ``s=`` / ``ns=...;i=...`` are all valid; the type guess
# only looks at the data-type suffix when one is present.
_OPCUA_TYPE_MAP: dict[str, str] = {
    "Boolean": "bool",
    "Byte": "int",
    "SByte": "int",
    "Int16": "int",
    "UInt16": "int",
    "Int32": "int",
    "UInt32": "int",
    "Int64": "int",
    "UInt64": "int",
    "Float": "float",
    "Double": "float",
    "String": "string",
    "DateTime": "datetime",
    "Guid": "string",
    "ByteString": "string",
    "XmlElement": "string",
    "NodeId": "string",
    "ExpandedNodeId": "string",
    "StatusCode": "string",
    "QualifiedName": "string",
    "LocalizedText": "string",
    "ExtensionObject": "json",
    "Variant": "json",
}


def _infer_type(type_name: str | None) -> str:
    """Map an OPC UA data-type display name to the corpus SchemaField type."""
    if not type_name:
        return "string"
    return _OPCUA_TYPE_MAP.get(type_name.split(".")[-1], "json")


def _browse_payload(node_id: str, display_name: str, data_type: str | None) -> dict[str, Any]:
    """Shape the per-node dict that flows through extract_sample / stream."""
    return {
        "node_id": node_id,
        "display_name": display_name,
        "value": None,  # filled in by extract_sample / stream
        "source_timestamp": None,
    }


@register
class OpcUaConnector(DataConnector):
    """Connect to an OPC UA server and surface its Variables as a corpus."""

    connector_type: ClassVar[str] = "opcua"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.endpoint = source  # e.g. opc.tcp://10.0.0.5:4840
        self.security = options.get("security", "None")
        # Browse config
        self.root_node: str = options.get("root_node", "i=85")  # Objects folder
        self.browse_depth: int = int(options.get("browse_depth", 3))
        self.browse_timeout: float = float(options.get("browse_timeout", 5.0))
        # Read config — either explicit node_ids or use everything the
        # last discover_schema call found.
        self.node_ids: list[str] = list(options.get("node_ids", []))
        # Cache populated by the first discover_schema / read call.
        self._cached_nodes: list[dict[str, Any]] = []

    # -- driver lazy import -----------------------------------------------------
    def _ensure_driver(self) -> None:
        try:
            import asyncua  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "OpcUaConnector needs the optional 'opcua' extra (asyncua): pip install 'fde-scope[opcua]'"
            ) from exc

    # -- async bridge -----------------------------------------------------------
    def _run(self, coro: Any) -> Any:
        """Run an asyncua coroutine to completion in a sync context.

        We intentionally re-create the event loop each call. asyncua
        sockets can't be shared across loops, and the FDE workbench
        runs each connector method as a one-shot — no reuse needed.
        """
        return asyncio.run(coro)

    def _client(self) -> Any:
        """Build a connected asyncua Client. Caller is responsible for close()."""
        import asyncua

        return self._run(self._async_connect(asyncua))

    async def _async_connect(self, asyncua_mod: Any) -> Any:
        client = asyncua_mod.Client(url=self.endpoint)
        await client.connect()
        return client

    # -- discover ---------------------------------------------------------------
    def _browse_node(self, node: Any, depth: int) -> list[dict[str, Any]]:
        """Walk the address space under ``node`` up to ``depth`` levels.

        Returns a flat list of dicts (one per Variable node) so the
        connector contract stays simple and the FDE can inspect the
        result synchronously.
        """
        return self._run(self._async_browse(node, depth))

    async def _async_browse(self, node: Any, depth: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if depth <= 0:
            return out
        try:
            children = await node.get_children()
        except Exception:  # noqa: BLE001 — node may be access-restricted
            return out
        for child in children:
            try:
                node_class = await child.get_node_class()
            except Exception:  # noqa: BLE001
                continue
            # OPC UA NodeClass 2 == Variable
            if node_class == 2:
                try:
                    node_id = child.nodeid.to_string()
                    display_name = (await child.get_display_name()).Text
                except Exception:  # noqa: BLE001
                    continue
                data_type: str | None = None
                try:
                    dt = await child.get_data_type_as_variant_type()
                    # ``dt`` is an asyncua.ua.VariantType enum. Use its
                    # ``name`` (e.g. "Float", "Int32") rather than str(dt)
                    # because the enum's str() is implementation-defined
                    # ("VariantType.Float") and varies between versions.
                    if dt is not None and getattr(dt, "name", None):
                        data_type = dt.name.split(".")[-1]
                except Exception:  # noqa: BLE001
                    pass
                out.append(
                    {
                        "node_id": node_id,
                        "display_name": display_name,
                        "data_type": data_type,
                        "is_variable": True,
                    }
                )
            # Recurse into sub-folders (e.g. ``Devices/Device1``).
            if depth > 1:
                out.extend(await self._async_browse(child, depth - 1))
        return out

    def discover_schema(self) -> Schema:
        """Browse the server's address space and return Variable metadata.

        Heuristic: treat every Variable as a column, and use the OPC UA
        data-type to fill the corpus SchemaField's ``inferred_type``.

        If the optional ``asyncua`` driver isn't installed, fall back to
        a minimal schema with the four canonical columns an OPC UA
        Variable row always carries. This keeps the connector usable in
        pipeline-planning contexts (where you just want to know
        *what shape* the data would have) without requiring the full
        asyncua stack.
        """
        try:
            self._ensure_driver()
        except ImportError:
            return self._fallback_schema()
        import asyncua

        async def _browse_root() -> list[dict[str, Any]]:
            client = await self._async_connect(asyncua)
            try:
                root = client.get_node(self.root_node)
                return await self._async_browse(root, self.browse_depth)
            finally:
                await client.disconnect()

        nodes = self._run(_browse_root())
        self._cached_nodes = nodes
        fields: list[SchemaField] = []
        for n in nodes:
            fields.append(
                SchemaField(
                    name=n["display_name"] or n["node_id"],
                    inferred_type=_infer_type(n.get("data_type")),
                    nullable=True,
                    sample_values=[],
                    pii_candidate=False,
                )
            )
        return Schema(
            source=self.endpoint,
            fields=fields,
            row_count=len(nodes),
            detected_categories=[],
        )

    def _fallback_schema(self) -> Schema:
        """Schema returned when asyncua isn't importable.

        Carries only the four columns every OPC UA Variable row would
        produce (``node_id``, ``display_name``, ``value``,
        ``source_timestamp``). The FDE can plan around this and decide
        whether to install asyncua for the full Variable-level
        metadata.
        """
        return Schema(
            source=self.endpoint,
            fields=[
                SchemaField(name="node_id", inferred_type="string"),
                SchemaField(name="display_name", inferred_type="string"),
                SchemaField(name="value", inferred_type="json"),
                SchemaField(name="source_timestamp", inferred_type="datetime"),
            ],
            row_count=None,
            detected_categories=[],
        )

    # -- read -------------------------------------------------------------------
    def _read_nodes(self, node_ids: list[str]) -> list[dict[str, Any]]:
        """Read a list of NodeIds once, return one row per NodeId."""
        if not node_ids:
            return []
        try:
            self._ensure_driver()
        except ImportError:
            return []  # no driver -> no live data; FDE will see [] and decide
        import asyncua

        async def _read_all() -> list[dict[str, Any]]:
            client = await self._async_connect(asyncua)
            try:
                nodes = [client.get_node(nid) for nid in node_ids]
                values = await asyncio.gather(*(n.read_data_value() for n in nodes), return_exceptions=True)
                rows: list[dict[str, Any]] = []
                for nid, dv in zip(node_ids, values, strict=True):
                    if isinstance(dv, Exception):
                        # Skip unreadable nodes (access rights, stale session).
                        # FDE sees the gap in extract_sample and decides.
                        continue
                    rows.append(
                        {
                            "node_id": nid,
                            "display_name": nid,
                            "value": dv.Value.Value if dv.Value else None,
                            "source_timestamp": (
                                dv.SourceTimestamp.isoformat() if dv.SourceTimestamp else None
                            ),
                        }
                    )
                return rows
            finally:
                await client.disconnect()

        return self._run(_read_all())

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        """Read up to ``n`` tags. Falls back to the cached browse if no explicit list."""
        ids = self.node_ids or [n["node_id"] for n in self._cached_nodes]
        ids = ids[:n]
        return self._read_nodes(ids)

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        """Poll every configured Variable in batches, yielding one row per tag.

        Each batch contains up to ``batch_size`` rows; batches are tagged
        with the endpoint URL so the corpus engine can trace provenance.
        Because OPC UA has no native cursor, this is *one poll snapshot*
        of the whole tag set, chunked for the corpus engine's batching
        contract. For a true subscription, use the async API directly
        (the FDE workbench reads on demand; the runtime layer wires
        subscriptions via the flywheel).
        """
        ids = self.node_ids or [n["node_id"] for n in self._cached_nodes]
        if not ids:
            return
        all_rows = self._read_nodes(ids)
        for i in range(0, len(all_rows), batch_size):
            chunk = all_rows[i : i + batch_size]
            yield Batch(chunk, source=f"{self.endpoint}#{len(all_rows)}_tags")
