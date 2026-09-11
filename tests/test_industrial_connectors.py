"""Contract tests for the industrial connector stubs.

These connectors (OPC UA / MQTT-Sparkplug / ROS2-bag / Historian) are stubs
for live protocol I/O, but their *contract surface* — discover_schema returns
a valid Schema, extract_sample returns a list, stream is a generator, the
registry resolves them — must still hold. These tests pin that contract so a
future real-IO implementation can't silently break the shape the FDE workflow
depends on.
"""

from __future__ import annotations

import pytest

from fde_scope.connectors._registry import get
from fde_scope.connectors.base import DataConnector

# All industrial connector slugs the manufacturing profile advertises.
INDUSTRIAL_SLUGS = ["opcua", "mqtt_sparkplug", "ros2_bag", "mes", "historian"]


@pytest.mark.parametrize("slug", INDUSTRIAL_SLUGS)
def test_registry_resolves_industrial_connector(slug: str) -> None:
    cls = get(slug)
    assert issubclass(cls, DataConnector)
    assert cls.type == slug


@pytest.mark.parametrize("slug", INDUSTRIAL_SLUGS)
def test_discover_schema_returns_valid_schema(slug: str, tmp_path, monkeypatch) -> None:
    """discover_schema must work without optional deps and return a Schema."""
    from fde_scope.connectors.schema import Schema

    cls = get(slug)
    # Use a placeholder source; stubs shouldn't try to connect on schema discovery.
    src = {
        "opcua": "opc.tcp://localhost:4840",
        "mqtt_sparkplug": "tcp://localhost:1883",
        "ros2_bag": str(tmp_path / "recording.mcap"),  # valid .mcap path form
        "mes": "https://mes.example.com",
        "historian": "https://pi.example.com",
    }[slug]
    connector = cls(src)
    if slug == "ros2_bag":
        # ros2_bag is no longer a stub: monkeypatch the driver + bag iterator
        monkeypatch.setattr(connector, "_ensure_driver", lambda: None)
        monkeypatch.setattr(connector, "_iter_bag", lambda: iter([]))
        # discover_schema opens AnyReader directly — mock it to yield no messages
        import contextlib
        import unittest.mock

        monkeypatch.setattr(
            "rosbags.highlevel.AnyReader",
            lambda paths: contextlib.nullcontext(unittest.mock.MagicMock(messages=lambda: iter([]))),
        )
    schema = connector.discover_schema()
    assert isinstance(schema, Schema)
    # Schema must carry its source and at least declare its fields list.
    assert schema.source
    assert isinstance(schema.fields, list)


@pytest.mark.parametrize("slug", INDUSTRIAL_SLUGS)
def test_extract_sample_returns_list(slug: str, tmp_path, monkeypatch) -> None:
    cls = get(slug)
    src = str(tmp_path / "recording.mcap") if slug == "ros2_bag" else "placeholder://source"
    connector = cls(src)
    if slug == "ros2_bag":
        monkeypatch.setattr(connector, "_ensure_driver", lambda: None)
        monkeypatch.setattr(connector, "_iter_bag", lambda: iter([]))
    sample = connector.extract_sample(10)
    assert isinstance(sample, list)


@pytest.mark.parametrize("slug", INDUSTRIAL_SLUGS)
def test_stream_is_iterable(slug: str, tmp_path, monkeypatch) -> None:
    """stream() must return an iterable of Batch (even if empty for stubs)."""
    cls = get(slug)
    src = str(tmp_path / "recording.mcap") if slug == "ros2_bag" else "placeholder://source"
    connector = cls(src)
    if slug == "ros2_bag":
        monkeypatch.setattr(connector, "_ensure_driver", lambda: None)
        monkeypatch.setattr(connector, "_iter_bag", lambda: iter([]))
    batches = list(connector.stream())
    assert isinstance(batches, list)


def test_opcua_connector_carries_node_ids_option() -> None:
    """OPC UA connector should accept node_ids for targeted reads."""
    OpcUa = get("opcua")
    c = OpcUa("opc.tcp://host:4840", node_ids=["ns=2;s=Temperature"])
    assert c.node_ids == ["ns=2;s=Temperature"]


def test_mqtt_connector_carries_topic_and_sparkplug_flag() -> None:
    Mqtt = get("mqtt_sparkplug")
    c = Mqtt("tcp://broker:1883", topic="spBv1.0/plant/#", sparkplug=True)
    assert c.topic_filter == "spBv1.0/plant/#"
    assert c.sparkplug is True


def test_ros2_connector_carries_topics_option() -> None:
    Ros2 = get("ros2_bag")
    c = Ros2("/data/bag", topics=["/joint_states", "/tf"])
    assert c.topics == ["/joint_states", "/tf"]


def test_historian_connector_carries_tags_and_window() -> None:
    Hist = get("historian")
    c = Hist("https://pi/webapi", tags=["TEMP_01", "PRESS_02"], start="2026-01-01", end="2026-02-01")
    assert c.tags == ["TEMP_01", "PRESS_02"]
    assert c.start == "2026-01-01"


def test_manufacturing_profile_advertises_all_industrial_connectors() -> None:
    """The profile's primary_connectors must all resolve in the registry."""
    from fde_scope.profiles import get_profile

    prof = get_profile("manufacturing")
    for slug in prof.primary_connectors:
        assert get(slug) is not None


def test_mes_stream_rejects_invalid_batch_size(tmp_path) -> None:  # noqa: ANN001
    """batch_size < 1 must fail loudly instead of degrading to one-row batches."""
    import json

    p = tmp_path / "mes.jsonl"
    p.write_text(json.dumps({"work_order_id": "WO-1"}), encoding="utf-8")
    Mes = get("mes")
    c = Mes(str(p))
    for bad in (0, -1):
        with pytest.raises(ValueError, match="batch_size"):
            list(c.stream(batch_size=bad))
