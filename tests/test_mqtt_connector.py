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
        {"topic": "spBv1.0/plant1/DBIRTH/edge01/cobot-01",
         "payload": {"metric": "joint_temp", "value": 72.5},
         "qos": 0, "retain": False, "timestamp": "2026-08-05T10:00:00Z"},
        {"topic": "spBv1.0/plant1/DDATA/edge01/cobot-01",
         "payload": {"metrics": [{"name": "grip_force", "value": 35}]},
         "qos": 1, "retain": False, "timestamp": "2026-08-05T10:00:01Z"},
        {"topic": "factory/sensors/temp",
         "payload": '{"metric": "ambient", "value": 24}',
         "qos": 0, "retain": False, "timestamp": "2026-08-05T10:00:02Z"},
        {"topic": "spBv1.0/plant1/NDEATH/edge01",
         "payload": "raw-bytes-here", "qos": 0, "retain": True},
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
    # DDATA with metrics list → first metric name/value
    second = sample[1]
    assert second["metric_name"] == "grip_force"
    assert second["value"] == 35
    # plain JSON-string payload parsed
    third = sample[2]
    assert third["metric_name"] == "ambient"
    # NDEATH (edge node death) → retain flag honored
    death = sample[3]
    assert death["retain"] is True


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


def test_parse_payload_raw_bytes() -> None:
    c = MqttSparkplugConnector("x.jsonl")
    name, val = c._parse_payload(b"\x00\x01")  # non-decodable
    assert name == "raw"


def test_missing_file_extract_returns_empty(tmp_path: Path) -> None:
    c = MqttSparkplugConnector(str(tmp_path / "nope.jsonl"))
    assert c.extract_sample(10) == []
    assert c.discover_schema().row_count is None
