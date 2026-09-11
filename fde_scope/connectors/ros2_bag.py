"""ROS 2 rosbag connector.

STATUS: skeleton. Real implementation will read a ``rosbag2`` SQLite/mcap
file, iterate messages on selected topics (joint states, TF, images, grasp
candidates, task transitions), and expose them as rows.

Industry note: rosbag2 is the standard record/replay unit for offline eval
and policy training. /tf carries the time-varying coordinate-frame tree
that any spatial-reasoning agent must consume.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

# Large binary message types — skipped by default, metadata-only stubs
# when include_binary=True. Exclusion fires before expansion logic.
_BINARY_TYPES: frozenset[str] = frozenset({
    "sensor_msgs/msg/Image",
    "sensor_msgs/msg/CompressedImage",
    "sensor_msgs/msg/PointCloud2",
})

# msg_type → expander callable. Populated in Task 5; empty dict means
# all non-binary types fall through to the payload JSON fallback.
_EXPANDERS: dict[str, Any] = {}


@register
class Ros2BagConnector(DataConnector):
    """Read messages from a rosbag2 file."""

    type = "ros2_bag"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.bag_path = Path(source)
        self.topics: list[str] = options.get("topics", [])  # empty = all
        self.expand: bool = options.get("expand", True)
        self.include_binary: bool = options.get("include_binary", False)
        self.skipped: int = 0
        self._path_form = self._detect_path_form()

    def _detect_path_form(self) -> str:
        """Return 'dir' for a bag directory (has metadata.yaml), 'mcap' for a
        .mcap file, or 'unknown' for anything else."""
        p = self.bag_path
        if p.is_dir() and (p / "metadata.yaml").exists():
            return "dir"
        if p.suffix == ".mcap":
            return "mcap"
        return "unknown"

    def _validate_path(self) -> None:
        """Raise ValueError with guidance if the path form is unsupported."""
        form = self._path_form
        if form in ("dir", "mcap"):
            return
        p = self.bag_path
        if p.is_dir():
            raise ValueError(
                f"Directory {p} has no metadata.yaml — not a standard rosbag2 bag. "
                "Bare .db3 files are not supported; re-record as mcap "
                "(rosbag2 record --storage mcap) or add a metadata.yaml."
            )
        raise ValueError(
            f"Unsupported bag path: {p}. Expected a bag directory (with metadata.yaml) or a .mcap file."
        )

    def _ensure_driver(self) -> None:
        try:
            from rosbags.highlevel import AnyReader  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "Ros2BagConnector needs the optional 'ros2' extra (rosbags): pip install 'fde-scope[ros2]'"
            ) from exc

    def _is_binary(self, msg_type: str) -> bool:
        return msg_type in _BINARY_TYPES

    def _normalize(
        self,
        *,
        topic: str,
        msg_type: str,
        timestamp_ns: int,
        msg: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Produce rows from one bag message.

        Binary exclusion fires first (before expansion). With
        ``include_binary=False`` (default) binary types are skipped entirely
        (the caller increments ``self.skipped``). With ``include_binary=True``
        a metadata-only stub row is emitted — scalar fields like
        width/height/encoding/format plus ``byte_size``, never the ``data``
        array.

        Non-binary types: if ``expand=True`` and an expander is registered
        for ``msg_type``, use it; otherwise fall back to payload JSON.
        """
        base = {
            "topic": topic,
            "msg_type": msg_type,
            "timestamp_ns": timestamp_ns,
        }

        if self._is_binary(msg_type):
            if not self.include_binary:
                return []  # caller increments self.skipped
            return [self._binary_stub(base, msg)]

        if self.expand:
            expander = _EXPANDERS.get(msg_type)
            if expander is not None:
                return [{**base, **row} for row in expander(msg)]

        return [{**base, "payload": msg}]

    def _binary_stub(self, base: dict[str, Any], msg: dict[str, Any]) -> dict[str, Any]:
        """Extract scalar metadata from a binary message — never the data array."""
        stub: dict[str, Any] = {}
        for key in ("width", "height", "encoding", "format", "is_bigendian", "step"):
            if key in msg:
                stub[key] = msg[key]
        if "fields" in msg and isinstance(msg["fields"], list):
            stub["fields"] = [
                {"name": f.get("name", ""), "datatype": f.get("datatype", 0)}
                for f in msg["fields"]
                if isinstance(f, dict)
            ]
        data = msg.get("data")
        stub["byte_size"] = len(data) if isinstance(data, (bytes, list)) else 0
        return {**base, **stub}

    def discover_schema(self) -> Schema:
        return Schema(
            source=str(self.bag_path),
            row_count=None,
            fields=[
                SchemaField(name="topic", inferred_type="string"),
                SchemaField(name="msg_type", inferred_type="string"),
                SchemaField(name="timestamp_ns", inferred_type="int"),
                SchemaField(name="payload", inferred_type="json"),
            ],
            detected_categories=self.topics,
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        # TODO: open AnyReader, iterate first n messages
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        # TODO: iterate all messages, batch-yield
        return
        yield  # pragma: no cover
