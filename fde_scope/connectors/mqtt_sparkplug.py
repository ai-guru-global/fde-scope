"""MQTT / Sparkplug B connector.

STATUS: skeleton. Real implementation will use ``paho-mqtt`` and parse
Sparkplug B protobuf payloads (BIRTH/DATA/DEATH certificates) so a historian
can auto-create tags. Plain MQTT is also supported (topic filters).

Industry note: Sparkplug B adds session/state management + named-metric
payloads on top of MQTT, so consumers know whether a device went silent vs.
is still alive — plain MQTT can't tell you that.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField


@register
class MqttSparkplugConnector(DataConnector):
    """Subscribe to an MQTT broker, optionally decoding Sparkplug B."""

    type = "mqtt_sparkplug"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.broker = source             # e.g. tcp://broker.local:1883
        self.topic_filter = options.get("topic", "spBv1.0/#")
        self.sparkplug = options.get("sparkplug", True)

    def _ensure_driver(self) -> None:
        try:
            import paho.mqtt.client  # type: ignore  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "MqttSparkplugConnector needs paho-mqtt: pip install paho-mqtt"
            ) from exc

    def discover_schema(self) -> Schema:
        return Schema(
            source=self.broker,
            row_count=None,
            fields=[
                SchemaField(name="topic", inferred_type="string"),
                SchemaField(name="metric_name", inferred_type="string"),
                SchemaField(name="value", inferred_type="json"),
                SchemaField(name="timestamp", inferred_type="datetime"),
                SchemaField(name="device_id", inferred_type="string"),
            ],
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        # TODO: connect, subscribe, collect n messages, disconnect
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        # TODO: long-lived subscription yielding batches
        return
        yield  # pragma: no cover
