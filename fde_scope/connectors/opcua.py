"""OPC UA connector — the de-facto Level 2-3 industrial integration layer.

STATUS: skeleton. Real implementation will use the ``opcua`` (asyncua)
library against a server's address space (browse nodes, subscribe to tags).
The contract surface is in place so the FDE workflow is selectable today.

Industry note: Siemens S7-1200/S7-1500 ship with a built-in OPC UA server;
Rockwell/Mitsubishi/Omron all expose OPC UA endpoints. The classic 2025/2026
pattern is OPC UA at the machine → edge gateway translates to MQTT/Sparkplug B
→ broker → UNS/historian.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField


@register
class OpcUaConnector(DataConnector):
    """Connect to an OPC UA server endpoint."""

    type = "opcua"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.endpoint = source  # e.g. opc.tcp://10.0.0.5:4840
        self.security = options.get("security", "None")
        self.node_ids: list[str] = options.get("node_ids", [])  # tags to read

    def _ensure_driver(self) -> None:
        try:
            import asyncua  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "OpcUaConnector needs the optional 'opcua' extra (asyncua): pip install asyncua"
            ) from exc

    def discover_schema(self) -> Schema:
        # TODO: connect client, browse address space under options['root_node']
        return Schema(
            source=self.endpoint,
            row_count=None,
            fields=[
                SchemaField(name="node_id", inferred_type="string"),
                SchemaField(name="display_name", inferred_type="string"),
                SchemaField(name="value", inferred_type="json"),
                SchemaField(name="source_timestamp", inferred_type="datetime"),
            ],
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        # TODO: read_node_value over self.node_ids
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        # TODO: subscribe to node changes, yield in batches
        return
        yield  # pragma: no cover
