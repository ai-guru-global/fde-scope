"""Tests for the MQTT/Sparkplug connector.

Covers the JSONL-replay path (zero-dep, fully working) and the Sparkplug B
topic/payload parsing. Live-broker paths are ``pragma: no cover`` (they need a
real broker) and are exercised only in optional integration environments.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from fde_scope.connectors.mqtt_sparkplug import MqttSparkplugConnector


@pytest.fixture
def mqtt_capture(tmp_path: Path) -> Path:
    """A small JSONL capture of Sparkplug B-style messages."""
    msgs = [
        {
            "topic": "spBv1.0/plant1/DBIRTH/edge01/cobot-01",
            "payload": {"metric": "joint_temp", "value": 72.5},
            "qos": 0,
            "retain": False,
            "timestamp": "2026-08-05T10:00:00Z",
        },
        {
            "topic": "spBv1.0/plant1/DDATA/edge01/cobot-01",
            "payload": {"metrics": [{"name": "grip_force", "value": 35}]},
            "qos": 1,
            "retain": False,
            "timestamp": "2026-08-05T10:00:01Z",
        },
        {
            "topic": "factory/sensors/temp",
            "payload": '{"metric": "ambient", "value": 24}',
            "qos": 0,
            "retain": False,
            "timestamp": "2026-08-05T10:00:02Z",
        },
        {"topic": "spBv1.0/plant1/NDEATH/edge01", "payload": "raw-bytes-here", "qos": 0, "retain": True},
    ]
    p = tmp_path / "capture.jsonl"
    p.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in msgs), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fake paho.mqtt.client — the surface the connector actually uses
# ---------------------------------------------------------------------------
class _FakeMqttMessage:
    """Mirror paho's MQTTMessage — only the attributes _normalize reads."""

    def __init__(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False):
        self.topic = topic
        self.payload = payload
        self.qos = qos
        self.retain = retain


class _FakeMqttClient:
    """Mirror paho.mqtt.client.Client — records calls for assertions.

    ``loop_start`` replays the configured outbox through ``on_message`` on
    a real thread, so both the collect (list.append) and stream (queue.put)
    callbacks are exercised against real concurrency.
    """

    def __init__(
        self,
        callback_api_version: int,  # noqa: ARG002 — mirror paho signature
        outbox: list[_FakeMqttMessage] | None = None,
        *,
        fail_connect: bool = False,
        fail_subscribe: bool = False,
    ) -> None:
        self._outbox = outbox or []
        self._fail_connect = fail_connect
        self._fail_subscribe = fail_subscribe
        self.on_message: Any = None
        self.calls: list[str] = []
        self.subscribed: list[str] = []
        self.username_pw_args: tuple[str, str | None] | None = None
        self.tls_enabled = False
        self.connected = False
        self.loop_stopped = False
        self.disconnected = False
        self._thread: threading.Thread | None = None

    def username_pw_set(self, username: str, password: str | None = None) -> None:
        self.calls.append("username_pw_set")
        self.username_pw_args = (username, password)

    def tls_set(self) -> None:
        self.calls.append("tls_set")
        self.tls_enabled = True

    def connect(self, host: str, port: int, keepalive: int) -> None:  # noqa: ARG002
        self.calls.append("connect")
        if self._fail_connect:
            raise ConnectionRefusedError(f"[Errno 61] connect to {host}:{port} refused")
        self.connected = True

    def subscribe(self, topic: str) -> None:
        self.calls.append("subscribe")
        if self._fail_subscribe:
            raise RuntimeError(f"subscribe refused: {topic}")
        self.subscribed.append(topic)

    def loop_start(self) -> None:
        self.calls.append("loop_start")

        def _replay() -> None:
            for msg in self._outbox:
                if self.on_message is not None:
                    self.on_message(self, None, msg)

        self._thread = threading.Thread(target=_replay, daemon=True)
        self._thread.start()

    def loop_stop(self) -> None:
        self.calls.append("loop_stop")
        self.loop_stopped = True
        if self._thread is not None:
            self._thread.join(timeout=5)

    def disconnect(self) -> None:
        self.calls.append("disconnect")
        self.disconnected = True


class _FakeMqttModule(types.ModuleType):
    """Module stand-in for ``paho.mqtt.client``."""

    def __init__(self) -> None:
        super().__init__("paho.mqtt.client")
        self.outbox: list[_FakeMqttMessage] = []
        self.fail_connect = False
        self.fail_subscribe = False
        self.created: list[_FakeMqttClient] = []
        self.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)

    def Client(self, callback_api_version: int) -> _FakeMqttClient:  # noqa: N802
        c = _FakeMqttClient(
            callback_api_version,
            outbox=self.outbox,
            fail_connect=self.fail_connect,
            fail_subscribe=self.fail_subscribe,
        )
        self.created.append(c)
        return c


@pytest.fixture
def fake_paho_module() -> Iterator[_FakeMqttModule]:
    """Install a fake ``paho.mqtt.client`` (+ parent packages) in sys.modules.

    Tests configure behavior by mutating the yielded module (outbox,
    fail_connect, ...) before calling the connector.
    """
    paho = types.ModuleType("paho")
    mqtt_pkg = types.ModuleType("paho.mqtt")
    client_mod = _FakeMqttModule()
    paho.mqtt = mqtt_pkg  # type: ignore[attr-defined]
    mqtt_pkg.client = client_mod  # type: ignore[attr-defined]
    sys.modules["paho"] = paho
    sys.modules["paho.mqtt"] = mqtt_pkg
    sys.modules["paho.mqtt.client"] = client_mod
    try:
        yield client_mod
    finally:
        for name in ("paho", "paho.mqtt", "paho.mqtt.client"):
            sys.modules.pop(name, None)


def _live_msg(topic: str, payload: dict[str, Any]) -> _FakeMqttMessage:
    """Build one fake wire message (payload JSON-encoded like a real broker)."""
    return _FakeMqttMessage(topic=topic, payload=json.dumps(payload).encode("utf-8"))


def test_jsonl_discover_schema(mqtt_capture: Path) -> None:
    c = MqttSparkplugConnector(str(mqtt_capture))
    schema = c.discover_schema()
    assert schema.row_count == 4
    assert "topic" in schema.field_names()
    assert "device_id" in schema.field_names()


def test_jsonl_extract_sample_parses_sparkplug(mqtt_capture: Path) -> None:
    c = MqttSparkplugConnector(str(mqtt_capture))
    sample = c.extract_sample(10)
    assert len(sample) == 4
    # DBIRTH message → device extracted from topic, metric from payload
    first = sample[0]
    assert first["device_id"] == "cobot-01"
    assert first["metric_name"] == "joint_temp"
    assert first["value"] == 72.5
    # DDATA with metrics list → metric name/value
    second = sample[1]
    assert second["metric_name"] == "grip_force"
    assert second["value"] == 35
    # plain JSON-string payload parsed
    third = sample[2]
    assert third["metric_name"] == "ambient"
    # NDEATH (edge node death, 4-part topic) → device_id is the edge node,
    # retain flag honored
    death = sample[3]
    assert death["device_id"] == "edge01"
    assert death["retain"] is True


def test_multi_metric_payload_yields_one_row_per_metric(tmp_path: Path) -> None:
    """Every metric in a Sparkplug metrics list must produce a row."""
    msg = {
        "topic": "spBv1.0/plant1/DDATA/edge01/cobot-01",
        "payload": {
            "metrics": [
                {"name": "grip_force", "value": 35},
                {"name": "joint_temp", "value": 72.5},
                {"name": "cycle_count", "value": 1042},
            ]
        },
        "qos": 0,
        "retain": False,
    }
    p = tmp_path / "multi.jsonl"
    p.write_text(json.dumps(msg), encoding="utf-8")
    c = MqttSparkplugConnector(str(p))
    sample = c.extract_sample(10)
    assert len(sample) == 3
    assert [r["metric_name"] for r in sample] == ["grip_force", "joint_temp", "cycle_count"]
    assert [r["value"] for r in sample] == [35, 72.5, 1042]
    assert all(r["device_id"] == "cobot-01" for r in sample)
    assert c.discover_schema().row_count == 3


def test_jsonl_stream_batches(mqtt_capture: Path) -> None:
    c = MqttSparkplugConnector(str(mqtt_capture))
    batches = list(c.stream(batch_size=2))
    assert len(batches) == 2  # 4 msgs / batch_size 2
    assert sum(len(b) for b in batches) == 4


def test_broker_url_detection() -> None:
    c = MqttSparkplugConnector("mqtt://broker.local:1883")
    assert c.broker == "mqtt://broker.local:1883"
    assert c._jsonl_path is None


def test_jsonl_path_detection(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text("{}", encoding="utf-8")
    c = MqttSparkplugConnector(str(p))
    assert c._jsonl_path is not None
    assert c.broker is None


def test_decode_topic_non_sparkplug() -> None:
    c = MqttSparkplugConnector("x.jsonl", sparkplug=True)
    device, msg_type = c._decode_topic("factory/sensors/temp")
    assert msg_type == "unknown"


def test_decode_topic_node_level_4part() -> None:
    """Node-level topics have no device segment: spBv1.0/{group}/{N*}/{edge}."""
    c = MqttSparkplugConnector("x.jsonl", sparkplug=True)
    for msg_type in ("NBIRTH", "NDATA", "NDEATH"):
        device, mt = c._decode_topic(f"spBv1.0/plant1/{msg_type}/edge01")
        assert device == "edge01"
        assert mt == msg_type


def test_decode_topic_state() -> None:
    """Host-app STATE topics: spBv1.0/{group}/STATE/{host_id}."""
    c = MqttSparkplugConnector("x.jsonl", sparkplug=True)
    device, mt = c._decode_topic("spBv1.0/plant1/STATE/scada-host")
    assert device == "scada-host"
    assert mt == "STATE"
    # Bare STATE topic (no host segment) falls back to the group id.
    device, mt = c._decode_topic("spBv1.0/plant1/STATE")
    assert device == "plant1"
    assert mt == "STATE"


def test_connection_params_tls_schemes() -> None:
    """mqtts/ssl brokers default to 8883 + TLS; mqtt/tcp to 1883."""
    assert MqttSparkplugConnector("mqtts://broker.local")._connection_params() == (
        "broker.local",
        8883,
        True,
    )
    assert MqttSparkplugConnector("ssl://broker.local")._connection_params() == (
        "broker.local",
        8883,
        True,
    )
    assert MqttSparkplugConnector("mqtt://broker.local")._connection_params() == (
        "broker.local",
        1883,
        False,
    )
    # Explicit port always wins.
    assert MqttSparkplugConnector("mqtts://broker.local:9883")._connection_params() == (
        "broker.local",
        9883,
        True,
    )


def test_stream_rejects_invalid_batch_size(mqtt_capture: Path) -> None:
    """batch_size < 1 must fail loudly instead of one-row batches."""
    c = MqttSparkplugConnector(str(mqtt_capture))
    for bad in (0, -1):
        with pytest.raises(ValueError, match="batch_size"):
            list(c.stream(batch_size=bad))


def test_parse_payload_raw_bytes() -> None:
    c = MqttSparkplugConnector("x.jsonl")
    pairs = c._parse_payload(b"\x00\x01")  # non-decodable
    assert pairs == [("raw", b"\x00\x01")]


def test_missing_file_extract_returns_empty(tmp_path: Path) -> None:
    c = MqttSparkplugConnector(str(tmp_path / "nope.jsonl"))
    assert c.extract_sample(10) == []
    assert c.discover_schema().row_count is None


# ---------------------------------------------------------------------------
# Live broker path — mocked paho (fake module via sys.modules)
# ---------------------------------------------------------------------------
def test_live_collect_applies_env_auth(
    fake_paho_module: _FakeMqttModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both env vars set → username_pw_set('u','p') called BEFORE connect."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "joint_temp", "value": 72.5}),
    ]
    monkeypatch.setenv("FDE_SCOPE_MQTT_USERNAME", "svc-fde")
    monkeypatch.setenv("FDE_SCOPE_MQTT_PASSWORD", "s3cret")

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    rows = conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.username_pw_args == ("svc-fde", "s3cret")
    assert client.calls.index("username_pw_set") < client.calls.index("connect")
    assert rows, "expected the replayed message to come back as a row"


def test_live_collect_username_only(
    fake_paho_module: _FakeMqttModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FDE_SCOPE_MQTT_USERNAME", "svc-fde")
    monkeypatch.delenv("FDE_SCOPE_MQTT_PASSWORD", raising=False)

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.username_pw_args == ("svc-fde", None)


def test_live_collect_password_only_ignored(
    fake_paho_module: _FakeMqttModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """paho has no password-only API → a lone password must not be applied."""
    monkeypatch.delenv("FDE_SCOPE_MQTT_USERNAME", raising=False)
    monkeypatch.setenv("FDE_SCOPE_MQTT_PASSWORD", "s3cret")

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.username_pw_args is None
    assert "username_pw_set" not in client.calls


def test_live_collect_no_env_no_auth(
    fake_paho_module: _FakeMqttModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FDE_SCOPE_MQTT_USERNAME", raising=False)
    monkeypatch.delenv("FDE_SCOPE_MQTT_PASSWORD", raising=False)

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.username_pw_args is None
    assert "username_pw_set" not in client.calls


def test_live_collect_normalizes_and_cleans_up(fake_paho_module: _FakeMqttModule) -> None:
    """Rows come out normalized; loop and socket are always torn down."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "joint_temp", "value": 72.5}),
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metrics": [{"name": "grip_force", "value": 35}]}),
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    rows = conn.extract_sample(10)

    assert [r["metric_name"] for r in rows] == ["joint_temp", "grip_force"]
    assert rows[0]["device_id"] == "cobot-01"
    assert rows[0]["value"] == 72.5
    assert rows[0]["timestamp"]  # live path stamps receive time
    client = fake_paho_module.created[0]
    assert client.subscribed == ["spBv1.0/#"]
    assert client.tls_enabled is False  # plain mqtt:// → no TLS
    assert client.loop_stopped is True
    assert client.disconnected is True


def test_live_collect_truncates_at_n(fake_paho_module: _FakeMqttModule) -> None:
    """Callback thread may out-run the poll loop → truncate to n."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": f"m{i}", "value": i}) for i in range(5)
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    rows = conn.extract_sample(2)

    assert len(rows) == 2


def test_live_collect_timeout_returns_empty(fake_paho_module: _FakeMqttModule) -> None:
    """Silent broker → [] after timeout_seconds, no hang."""
    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    assert conn.extract_sample(5) == []
    client = fake_paho_module.created[0]
    assert client.disconnected is True


def test_live_collect_connect_failure_propagates_without_cleanup(
    fake_paho_module: _FakeMqttModule,
) -> None:
    """Refused connect → error propagates; nothing to clean up is touched."""
    fake_paho_module.fail_connect = True

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    with pytest.raises(ConnectionRefusedError):
        conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.connected is False
    assert client.loop_stopped is False
    assert client.disconnected is False


def test_live_collect_subscribe_failure_still_disconnects(
    fake_paho_module: _FakeMqttModule,
) -> None:
    """Connected but subscribe failed → socket must still be disconnected."""
    fake_paho_module.fail_subscribe = True

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    with pytest.raises(RuntimeError, match="subscribe"):
        conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.connected is True
    assert client.loop_stopped is False  # loop never started
    assert client.disconnected is True


def test_live_collect_mqtts_enables_tls(fake_paho_module: _FakeMqttModule) -> None:
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "t", "value": 1}),
    ]

    conn = MqttSparkplugConnector("mqtts://broker.local:8883", timeout_seconds=1)
    conn.extract_sample(1)

    client = fake_paho_module.created[0]
    assert client.tls_enabled is True


# ---------------------------------------------------------------------------
# Live stream — bounded termination (the hang fix)
# ---------------------------------------------------------------------------
def test_stream_live_bounded_terminates(fake_paho_module: _FakeMqttModule) -> None:
    """max_messages=3 + batch_size=2 → [2, 1] batches, generator ends."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "joint_temp", "value": 72.5}),
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": "grip_force", "value": 35}),
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": "cycle_count", "value": 1042}),
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=2, max_messages=3)
    batches = list(conn.stream(batch_size=2))

    assert [len(b) for b in batches] == [2, 1]
    assert batches[0].source == "mqtt://localhost:1883"
    client = fake_paho_module.created[0]
    assert client.loop_stopped is True
    assert client.disconnected is True


def test_stream_live_silence_terminates(fake_paho_module: _FakeMqttModule) -> None:
    """Silent broker → generator exits after timeout_seconds (no hang)."""
    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    assert list(conn.stream(batch_size=5)) == []
    client = fake_paho_module.created[0]
    assert client.loop_stopped is True
    assert client.disconnected is True


def test_stream_live_counts_messages_not_rows(fake_paho_module: _FakeMqttModule) -> None:
    """One multi-metric message is ONE message for max_messages purposes."""
    fake_paho_module.outbox = [
        _live_msg(
            "spBv1.0/plant1/DDATA/edge01/cobot-01",
            {
                "metrics": [
                    {"name": "grip_force", "value": 35},
                    {"name": "joint_temp", "value": 72.5},
                    {"name": "cycle_count", "value": 1042},
                ]
            },
        ),
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=2, max_messages=1)
    batches = list(conn.stream(batch_size=10))

    # 1 message → 3 rows, all in the single tail batch.
    assert [len(b) for b in batches] == [3]


def test_stream_live_default_max_messages_is_bounded(
    fake_paho_module: _FakeMqttModule,
) -> None:
    """Default max_messages=1000: a small outbox still terminates on silence."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": "m", "value": 1}),
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    batches = list(conn.stream(batch_size=10))

    assert [len(b) for b in batches] == [1]


def test_stream_live_unbounded_terminates_on_silence(
    fake_paho_module: _FakeMqttModule,
) -> None:
    """max_messages=0 → unbounded: the cap guard must be skipped entirely.

    Batch shape alone can't distinguish this from a dropped guard (the
    cap-path drain collects the same rows), so we also assert the coarse
    timing: guard present → the generator lives until the silence deadline
    (~1s); guard dropped → `len(messages) >= 0` fires immediately (<10ms).
    """
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": "m", "value": 1}),
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1, max_messages=0)
    started = time.monotonic()
    batches = list(conn.stream(batch_size=10))
    elapsed = time.monotonic() - started

    assert [len(b) for b in batches] == [1]
    assert elapsed >= 0.5, "0-mode terminated instantly — cap guard not skipped"
    client = fake_paho_module.created[0]
    assert client.loop_stopped is True
    assert client.disconnected is True


def test_stream_live_yields_full_batches_before_cap(
    fake_paho_module: _FakeMqttModule,
) -> None:
    """Cap not hit + batch_size < rows → mid-stream yields at exactly batch_size.

    Locks the normal batch-size yield path, distinct from the cap-drain path
    the bounded-terminates test exercises (1 row/message lets the cap fire
    before the batch-size check there). timeout_seconds=2 also walks the
    pre-deadline Empty→continue branch: the first ~1s poll precedes the
    deadline, the second terminates.
    """
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": f"m{i}", "value": i}) for i in range(5)
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=2, max_messages=100)
    batches = list(conn.stream(batch_size=2))

    assert [len(b) for b in batches] == [2, 2, 1]


def test_stream_live_mqtts_enables_tls(fake_paho_module: _FakeMqttModule) -> None:
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "t", "value": 1}),
    ]

    conn = MqttSparkplugConnector("mqtts://broker.local:8883", timeout_seconds=1)
    batches = list(conn.stream(batch_size=1))

    assert [len(b) for b in batches] == [1]
    client = fake_paho_module.created[0]
    assert client.tls_enabled is True
