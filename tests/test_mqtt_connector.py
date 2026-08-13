"""Tests for the MQTT/Sparkplug connector.

Covers the JSONL-replay path (zero-dep, fully working) and the Sparkplug B
topic/payload parsing. Live-broker paths are ``pragma: no cover`` (they need a
real broker) and are exercised only in optional integration environments.
"""

from __future__ import annotations

import json
from pathlib import Path

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
