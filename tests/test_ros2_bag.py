"""Tests for the ROS 2 bag connector.

Contract layer: no rosbags dependency needed — fake dicts feed the
normalize/expand/exclude pipeline. Real-file layer: rosbags Writer
self-produces bags (dual format). Integration: env-gated real bag.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fde_scope.connectors.ros2_bag import Ros2BagConnector


# ---------------------------------------------------------------------------
# Path form detection
# ---------------------------------------------------------------------------
def test_bag_directory_detected(tmp_path: Path) -> None:
    """A directory containing metadata.yaml is a standard bag directory."""
    (tmp_path / "metadata.yaml").write_text("rosbag2_bagfile_information:\n", encoding="utf-8")
    c = Ros2BagConnector(str(tmp_path))
    assert c.bag_path == tmp_path
    assert c._path_form == "dir"


def test_mcap_file_detected(tmp_path: Path) -> None:
    c = Ros2BagConnector(str(tmp_path / "recording.mcap"))
    assert c._path_form == "mcap"


def test_db3_directory_rejected(tmp_path: Path) -> None:
    """A directory without metadata.yaml (e.g. bare .db3) must error with guidance."""
    (tmp_path / "data.db3").write_bytes(b"\x00")
    c = Ros2BagConnector(str(tmp_path))
    with pytest.raises(ValueError, match="metadata.yaml"):
        c._validate_path()


def test_unknown_extension_rejected(tmp_path: Path) -> None:
    c = Ros2BagConnector(str(tmp_path / "data.txt"))
    with pytest.raises(ValueError, match="mcap"):
        c._validate_path()


def test_ensure_driver_message_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the user forgot the [ros2] extra, the error names the fix."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "rosbags" or name.startswith("rosbags."):
            raise ImportError("simulated missing driver")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Need a valid path form to reach _ensure_driver
    c = Ros2BagConnector("dummy.mcap")
    with pytest.raises(ImportError, match=r"fde-scope\[ros2\]"):
        c._ensure_driver()


# ---------------------------------------------------------------------------
# normalize pipeline
# ---------------------------------------------------------------------------
def test_normalize_base_fields() -> None:
    """Every normalized row carries topic/msg_type/timestamp_ns/payload."""
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/chatter",
        msg_type="std_msgs/msg/String",
        timestamp_ns=1_000_000_000,
        msg={"data": "hello"},
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["topic"] == "/chatter"
    assert row["msg_type"] == "std_msgs/msg/String"
    assert row["timestamp_ns"] == 1_000_000_000
    assert row["payload"] == {"data": "hello"}


def test_binary_type_skipped_by_default() -> None:
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/camera/image",
        msg_type="sensor_msgs/msg/Image",
        timestamp_ns=100,
        msg={"width": 640, "height": 480, "encoding": "bgr8", "data": b"\x00" * 100},
    )
    assert rows == []


def test_binary_type_stub_with_include_binary() -> None:
    c = Ros2BagConnector("dummy.mcap", include_binary=True)
    rows = c._normalize(
        topic="/camera/image",
        msg_type="sensor_msgs/msg/Image",
        timestamp_ns=100,
        msg={"width": 640, "height": 480, "encoding": "bgr8", "data": b"\x00" * 100},
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["width"] == 640
    assert row["height"] == 480
    assert row["encoding"] == "bgr8"
    assert row["byte_size"] == 100
    assert "data" not in row  # never the raw array


def test_binary_exclusion_fires_before_expand() -> None:
    """expand=False must not re-enable binary types."""
    c = Ros2BagConnector("dummy.mcap", expand=False)
    rows = c._normalize(
        topic="/camera/image",
        msg_type="sensor_msgs/msg/Image",
        timestamp_ns=100,
        msg={"width": 640, "height": 480, "data": b"\x00" * 50},
    )
    assert rows == []


def test_pointcloud2_skipped_by_default() -> None:
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/lidar/points",
        msg_type="sensor_msgs/msg/PointCloud2",
        timestamp_ns=200,
        msg={"width": 100, "height": 1, "fields": [{"name": "x", "datatype": 7}], "data": b"\x00" * 200},
    )
    assert rows == []


def test_compressed_image_skipped_by_default() -> None:
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/camera/compressed",
        msg_type="sensor_msgs/msg/CompressedImage",
        timestamp_ns=300,
        msg={"format": "jpeg", "data": b"\xff\xd8\xff"},
    )
    assert rows == []


# ---------------------------------------------------------------------------
# expanders
# ---------------------------------------------------------------------------
def test_tf_message_expands_per_transform() -> None:
    """One TFMessage with 2 transforms → 2 rows, each with frame fields."""
    c = Ros2BagConnector("dummy.mcap")
    msg = {
        "transforms": [
            {
                "header": {"stamp": {"sec": 1, "nanosec": 0}},
                "child_frame_id": "base_link",
                "transform": {
                    "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
            },
            {
                "header": {"stamp": {"sec": 1, "nanosec": 500}},
                "child_frame_id": "camera_link",
                "transform": {
                    "translation": {"x": 0.1, "y": 0.0, "z": 0.5},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.707, "w": 0.707},
                },
            },
        ]
    }
    rows = c._normalize(
        topic="/tf",
        msg_type="tf2_msgs/msg/TFMessage",
        timestamp_ns=1_000_000_000,
        msg=msg,
    )
    assert len(rows) == 2
    assert rows[0]["child_frame_id"] == "base_link"
    assert rows[0]["tx"] == 1.0
    assert rows[0]["ty"] == 2.0
    assert rows[0]["tz"] == 3.0
    assert rows[0]["qx"] == 0.0
    assert rows[0]["qy"] == 0.0
    assert rows[0]["qz"] == 0.0
    assert rows[0]["qw"] == 1.0
    assert rows[0]["header_stamp_ns"] == 1_000_000_000  # sec=1, nanosec=0
    assert rows[1]["child_frame_id"] == "camera_link"
    assert rows[1]["tx"] == 0.1


def test_tf_message_empty_transforms() -> None:
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/tf",
        msg_type="tf2_msgs/msg/TFMessage",
        timestamp_ns=100,
        msg={"transforms": []},
    )
    assert rows == []


def test_joint_state_expands_per_joint() -> None:
    """One JointState with 3 joints → 3 rows."""
    c = Ros2BagConnector("dummy.mcap")
    msg = {
        "header": {"stamp": {"sec": 2, "nanosec": 500_000_000}},
        "name": ["joint_1", "joint_2", "joint_3"],
        "position": [1.0, 2.0, 3.0],
        "velocity": [0.1, 0.2, 0.3],
        "effort": [10.0, 20.0, 30.0],
    }
    rows = c._normalize(
        topic="/joint_states",
        msg_type="sensor_msgs/msg/JointState",
        timestamp_ns=2_500_000_000,
        msg=msg,
    )
    assert len(rows) == 3
    assert rows[0]["joint_name"] == "joint_1"
    assert rows[0]["position"] == 1.0
    assert rows[0]["velocity"] == 0.1
    assert rows[0]["effort"] == 10.0
    assert rows[0]["header_stamp_ns"] == 2_500_000_000
    assert rows[2]["joint_name"] == "joint_3"
    assert rows[2]["position"] == 3.0


def test_joint_state_mismatched_lengths_truncated() -> None:
    """If name/position/velocity/effort have different lengths, zip truncates."""
    c = Ros2BagConnector("dummy.mcap")
    msg = {
        "header": {"stamp": {"sec": 0, "nanosec": 0}},
        "name": ["j1", "j2"],
        "position": [1.0],  # shorter than name
        "velocity": [0.1],
        "effort": [10.0],
    }
    rows = c._normalize(
        topic="/joint_states",
        msg_type="sensor_msgs/msg/JointState",
        timestamp_ns=100,
        msg=msg,
    )
    # zip truncates to shortest → 1 row
    assert len(rows) == 1
    assert rows[0]["joint_name"] == "j1"
    assert rows[0]["position"] == 1.0


def test_expand_false_falls_back_to_payload() -> None:
    """expand=True is default; expand=False must skip all expanders."""
    c = Ros2BagConnector("dummy.mcap", expand=False)
    msg = {
        "transforms": [
            {
                "header": {"stamp": {"sec": 1, "nanosec": 0}},
                "child_frame_id": "base_link",
                "transform": {
                    "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
            },
        ]
    }
    rows = c._normalize(
        topic="/tf",
        msg_type="tf2_msgs/msg/TFMessage",
        timestamp_ns=100,
        msg=msg,
    )
    assert len(rows) == 1
    # No per-transform fields — just the raw payload
    assert "child_frame_id" not in rows[0]
    assert rows[0]["payload"] == msg


# ---------------------------------------------------------------------------
# three-step contract (contract layer, no rosbags)
# ---------------------------------------------------------------------------
def test_topics_filter_excludes_non_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    """When topics is set, only matching messages pass through."""
    c = Ros2BagConnector("dummy.mcap", topics=["/joint_states"])
    fake_msgs = [
        ("/tf", "tf2_msgs/msg/TFMessage", 100, {"transforms": []}),
        (
            "/joint_states",
            "sensor_msgs/msg/JointState",
            200,
            {
                "name": ["j1"],
                "position": [1.0],
                "velocity": [0.1],
                "effort": [10.0],
                "header": {"stamp": {"sec": 1, "nanosec": 0}},
            },
        ),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    rows = c.extract_sample(10)
    assert len(rows) == 1
    assert rows[0]["topic"] == "/joint_states"
    assert rows[0]["joint_name"] == "j1"


def test_topics_empty_means_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """topics=[] (default) -> no filtering, all messages pass."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [
        ("/tf", "tf2_msgs/msg/TFMessage", 100, {"transforms": []}),
        ("/chatter", "std_msgs/msg/String", 200, {"data": "hello"}),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    rows = c.extract_sample(10)
    # TFMessage with empty transforms -> 0 rows; String -> 1 row
    assert len(rows) == 1
    assert rows[0]["topic"] == "/chatter"


def test_stream_rejects_invalid_batch_size() -> None:
    c = Ros2BagConnector("dummy.mcap")
    for bad in (0, -1):
        with pytest.raises(ValueError, match="batch_size"):
            list(c.stream(batch_size=bad))


def test_extract_sample_with_fake_iter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract test: extract_sample reads from _iter_bag, normalizes, returns n rows."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [
        ("/chatter", "std_msgs/msg/String", 100, {"data": "hello"}),
        ("/chatter", "std_msgs/msg/String", 200, {"data": "world"}),
        ("/chatter", "std_msgs/msg/String", 300, {"data": "foo"}),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    sample = c.extract_sample(2)
    assert len(sample) == 2
    assert sample[0]["payload"] == {"data": "hello"}
    assert sample[1]["payload"] == {"data": "world"}


def test_stream_with_fake_iter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract test: stream yields Batch objects with correct source."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [("/chatter", "std_msgs/msg/String", i * 100, {"data": f"msg{i}"}) for i in range(5)]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    batches = list(c.stream(batch_size=2))
    assert len(batches) == 3  # 2+2+1
    assert sum(len(b) for b in batches) == 5
    assert batches[0].source == "dummy.mcap"


def test_stream_with_expanded_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stream with TF expansion: 1 message -> 2 rows."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [
        (
            "/tf",
            "tf2_msgs/msg/TFMessage",
            100,
            {
                "transforms": [
                    {
                        "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "odom"},
                        "child_frame_id": "base_link",
                        "transform": {
                            "translation": {"x": 1.0, "y": 0.0, "z": 0.0},
                            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                        },
                    },
                    {
                        "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "base_link"},
                        "child_frame_id": "camera_link",
                        "transform": {
                            "translation": {"x": 0.1, "y": 0.0, "z": 0.5},
                            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                        },
                    },
                ]
            },
        ),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    batches = list(c.stream(batch_size=10))
    assert len(batches) == 1
    assert len(batches[0]) == 2
    assert batches[0][0]["child_frame_id"] == "base_link"
    assert batches[0][1]["child_frame_id"] == "camera_link"
