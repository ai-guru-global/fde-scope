"""MQTT / Sparkplug B connector.

Two modes:

1. **JSONL capture replay** (fully working, zero deps): a wireshark/mosquitto
   capture exported as JSON lines — the FDE's offline-analysis path. Each line
   is one captured message ``{"topic":..., "payload":{...}, "qos":..., "retain":...}``.
   This is what the contract tests and the corpus forge exercise.

2. **Live broker subscription** (needs ``paho-mqtt``): connect to a real broker,
   subscribe, and collect messages. Plain-MQTT JSON payloads are parsed; native
   Sparkplug B protobuf decoding is roadmap (the payload schema is honored
   regardless, so downstream code is stable).

Industry note: Sparkplug B adds session/state management + named-metric
payloads on top of MQTT, so consumers know whether a device went silent vs.
is still alive — plain MQTT can't tell you that.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

# Fields a captured/replayed MQTT message exposes to downstream forge/eval.
_SCHEMA_FIELDS = [
    SchemaField(name="topic", inferred_type="string"),
    SchemaField(name="metric_name", inferred_type="string"),
    SchemaField(name="value", inferred_type="json"),
    SchemaField(name="timestamp", inferred_type="datetime"),
    SchemaField(name="device_id", inferred_type="string"),
    SchemaField(name="qos", inferred_type="int"),
    SchemaField(name="retain", inferred_type="bool"),
]

# Sparkplug B topic layout: spBv1.0/{group}/[NBIRTH|NDATA|NDEATH|DBIRTH|DDATA|DDEATH]/{edge}/{device}
_SPB_MSG_TYPES = {"NBIRTH", "NDATA", "NDEATH", "DBIRTH", "DDATA", "DDEATH", "STATE"}


@register
class MqttSparkplugConnector(DataConnector):
    """Subscribe to an MQTT broker, or replay a JSONL capture.

    ``source`` is either:
      - a broker URL ``mqtt://broker.local:1883`` (live mode, needs paho-mqtt), or
      - a path to a ``.jsonl`` capture file (replay mode, zero deps).
    """

    type = "mqtt_sparkplug"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.topic_filter = options.get("topic", "spBv1.0/#")
        self.sparkplug = options.get("sparkplug", True)
        self.timeout_seconds = options.get("timeout_seconds", 5)
        self._jsonl_path: Path | None = (
            Path(source) if not self._is_broker_url(source) and Path(source).suffix == ".jsonl" else None
        )
        self.broker = source if self._is_broker_url(source) else None

    @staticmethod
    def _is_broker_url(source: str) -> bool:
        return bool(re.match(r"^(mqtt|mqtts|tcp|ssl)://", source))

    # -- driver lazy import -----------------------------------------------------
    def _ensure_driver(self) -> None:
        try:
            import paho.mqtt.client  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "MqttSparkplugConnector live mode needs paho-mqtt: pip install paho-mqtt"
            ) from exc

    # -- auth -------------------------------------------------------------------
    def _apply_auth(self, client: Any) -> None:
        """Apply broker credentials from the environment, if configured.

        Invariant (AGENTS.md #3): credentials live in env vars only — they
        are read at connect time and never persisted. paho's
        ``username_pw_set`` requires a username, so a password without a
        username cannot be expressed and is ignored.
        """
        username = os.environ.get("FDE_SCOPE_MQTT_USERNAME")
        password = os.environ.get("FDE_SCOPE_MQTT_PASSWORD")
        if username is not None:
            client.username_pw_set(username, password)

    # -- payload parsing --------------------------------------------------------
    def _parse_payload(self, raw: Any) -> list[tuple[str, Any]]:
        """Return one (metric_name, value) pair per metric in the payload.

        Sparkplug B payloads carry a *list* of metrics — every metric gets
        its own pair so none are silently dropped. Handles: dict with
        ``metric``/``metrics``, JSON string, raw scalar. Sparkplug B
        protobuf is roadmap; we honor JSON payloads (the common
        broker-side test format) and degrade gracefully otherwise.
        """
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return [("raw", raw)]
        if isinstance(raw, dict):
            if "metric" in raw:
                return [(str(raw["metric"]), raw.get("value"))]
            if "metrics" in raw and isinstance(raw["metrics"], list) and raw["metrics"]:
                pairs = [
                    (str(m.get("name", "metric")), m.get("value"))
                    for m in raw["metrics"]
                    if isinstance(m, dict)
                ]
                if pairs:
                    return pairs
            return [("payload", raw)]
        return [("raw", raw)]

    def _decode_topic(self, topic: str) -> tuple[str, str]:
        """Extract (device_id, message_type) from a Sparkplug B topic.

        Layouts handled:
          - device-level (5 parts): spBv1.0/{group}/{DBIRTH|DDATA|DDEATH}/{edge}/{device}
          - node-level (4 parts):   spBv1.0/{group}/{NBIRTH|NDATA|NDEATH}/{edge_node}
          - host state:             spBv1.0/{group}/STATE[/{host_id}]
        """
        parts = topic.split("/")
        if len(parts) >= 3 and parts[0] == "spBv1.0":
            msg_type = parts[2]
            if msg_type == "STATE":
                return (parts[3] if len(parts) >= 4 else parts[1]), msg_type
            if len(parts) == 4 and msg_type.startswith("N"):
                return parts[3], msg_type
            if len(parts) >= 5:
                device = parts[-1] if msg_type.startswith("D") else parts[-2]
                return device, msg_type
        return topic, "unknown"

    def _normalize(self, msg: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten one captured/live message into rows — one per metric.

        ``timestamp``: replay passes the capture's timestamp string through
        untouched; the live path stamps the receive time itself.
        """
        topic = str(msg.get("topic", ""))
        device_id, _ = self._decode_topic(topic) if self.sparkplug else (topic, "")
        rows = []
        for metric_name, value in self._parse_payload(msg.get("payload")):
            rows.append(
                {
                    "topic": topic,
                    "metric_name": metric_name,
                    "value": value,
                    "timestamp": msg.get("timestamp"),
                    "device_id": device_id,
                    "qos": msg.get("qos", 0),
                    "retain": bool(msg.get("retain", False)),
                }
            )
        return rows

    # -- JSONL replay path ------------------------------------------------------
    def _iter_jsonl(self) -> Iterator[dict[str, Any]]:
        assert self._jsonl_path is not None  # callers gate on _jsonl_path is not None
        with open(self._jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield from self._normalize(json.loads(line))

    # -- the three-step contract -----------------------------------------------
    def discover_schema(self) -> Schema:
        row_count = None
        if self._jsonl_path is not None and self._jsonl_path.exists():
            row_count = sum(1 for _ in self._iter_jsonl())
        return Schema(
            source=str(self.broker or self._jsonl_path),
            row_count=row_count,
            fields=list(_SCHEMA_FIELDS),
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        if self._jsonl_path is not None and self._jsonl_path.exists():
            out: list[dict[str, Any]] = []
            for rec in self._iter_jsonl():
                out.append(rec)
                if len(out) >= n:
                    break
            return out
        if self.broker:
            return self._collect_live(n)
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        if self._jsonl_path is not None and self._jsonl_path.exists():
            batch: list[dict[str, Any]] = []
            for rec in self._iter_jsonl():
                batch.append(rec)
                if len(batch) >= batch_size:
                    yield Batch(batch, source=str(self._jsonl_path))
                    batch = []
            if batch:
                yield Batch(batch, source=str(self._jsonl_path))
            return
        if self.broker:
            yield from self._stream_live(batch_size)

    # -- live broker path (paho-mqtt) ------------------------------------------
    def _connection_params(self) -> tuple[str, int, bool]:
        """Resolve (host, port, use_tls) from the broker URL.

        ``mqtts://`` / ``ssl://`` default to port 8883 and require TLS;
        plain ``mqtt://`` / ``tcp://`` default to 1883.
        """
        parsed = urlparse(self.broker or "")
        use_tls = parsed.scheme in ("mqtts", "ssl")
        host = parsed.hostname or "localhost"
        port = parsed.port or (8883 if use_tls else 1883)
        return host, port, use_tls

    def _collect_live(self, n: int) -> list[dict[str, Any]]:  # pragma: no cover — needs broker
        """Connect, subscribe, collect up to ``n`` rows, disconnect.

        Cleanup is stage-aware: an unconnected client is not disconnected
        and a never-started loop is not stopped (paho's behavior on those
        calls against an unestablished session is not something we rely
        on). Errors propagate honestly — no silent empty-data fallback.
        """
        self._ensure_driver()
        import paho.mqtt.client as mqtt

        out: list[dict[str, Any]] = []
        host, port, use_tls = self._connection_params()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if use_tls:
            client.tls_set()
        self._apply_auth(client)

        def on_message(_c, _d, msg):  # noqa: ANN001
            out.extend(
                self._normalize(
                    {
                        "topic": msg.topic,
                        "payload": msg.payload.decode("utf-8", errors="replace"),
                        # No wire timestamp in plain MQTT — stamp receive time.
                        "timestamp": datetime.now(UTC).isoformat(),
                        "qos": msg.qos,
                        "retain": msg.retain,
                    }
                )
            )

        client.on_message = on_message
        connected = False
        loop_running = False
        try:
            client.connect(host, port, 60)
            connected = True
            client.subscribe(self.topic_filter)
            client.loop_start()
            loop_running = True
            import time

            deadline = time.time() + self.timeout_seconds
            while len(out) < n and time.time() < deadline:
                time.sleep(0.05)
        finally:
            if loop_running:
                client.loop_stop()
            if connected:
                client.disconnect()
        # The callback thread can out-run the poll loop's final check.
        return out[:n]

    def _stream_live(self, batch_size: int) -> Iterator[Batch]:  # pragma: no cover — needs broker
        """Long-lived subscription; yields batches as they fill."""
        self._ensure_driver()
        import queue

        import paho.mqtt.client as mqtt

        q: queue.Queue = queue.Queue()
        host, port, use_tls = self._connection_params()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if use_tls:
            client.tls_set()

        def on_message(_c, _d, msg):  # noqa: ANN001
            for row in self._normalize(
                {
                    "topic": msg.topic,
                    "payload": msg.payload.decode("utf-8", errors="replace"),
                    # No wire timestamp in plain MQTT — stamp receive time.
                    "timestamp": datetime.now(UTC).isoformat(),
                    "qos": msg.qos,
                    "retain": msg.retain,
                }
            ):
                q.put(row)

        client.on_message = on_message
        client.connect(host, port, 60)
        client.subscribe(self.topic_filter)
        client.loop_start()
        batch: list[dict[str, Any]] = []
        try:
            while True:
                try:
                    rec = q.get(timeout=1.0)
                    batch.append(rec)
                    if len(batch) >= batch_size:
                        yield Batch(batch, source=str(self.broker))
                        batch = []
                except queue.Empty:
                    continue
        finally:
            client.loop_stop()
            client.disconnect()
