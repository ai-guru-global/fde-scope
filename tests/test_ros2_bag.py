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
