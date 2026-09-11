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
_BINARY_TYPES: frozenset[str] = frozenset(
    {
        "sensor_msgs/msg/Image",
        "sensor_msgs/msg/CompressedImage",
        "sensor_msgs/msg/PointCloud2",
    }
)

# msg_type → expander callable. Populated below with TF and JointState expanders.
_EXPANDERS: dict[str, Any] = {}


def _stamp_to_ns(stamp: Any) -> int:
    """Convert a ROS2 Time-like dict {sec, nanosec} to nanoseconds."""
    if isinstance(stamp, dict):
        return int(stamp.get("sec", 0)) * 10**9 + int(stamp.get("nanosec", 0))
    return 0


def _expand_tf(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """TFMessage → one row per transform."""
    transforms = msg.get("transforms", [])
    rows = []
    for tf in transforms:
        if not isinstance(tf, dict):
            continue
        header = tf.get("header", {})
        transform = tf.get("transform", {})
        trans = transform.get("translation", {})
        rot = transform.get("rotation", {})
        rows.append(
            {
                "frame_id": header.get("frame_id", ""),
                "child_frame_id": tf.get("child_frame_id", ""),
                "tx": trans.get("x", 0.0),
                "ty": trans.get("y", 0.0),
                "tz": trans.get("z", 0.0),
                "qx": rot.get("x", 0.0),
                "qy": rot.get("y", 0.0),
                "qz": rot.get("z", 0.0),
                "qw": rot.get("w", 1.0),
                "header_stamp_ns": _stamp_to_ns(header.get("stamp")),
            }
        )
    return rows


def _expand_joint_state(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """JointState → one row per joint (zip truncates to shortest)."""
    header = msg.get("header", {})
    names = msg.get("name", [])
    positions = msg.get("position", [])
    velocities = msg.get("velocity", [])
    efforts = msg.get("effort", [])
    rows = []
    for name, pos, vel, eff in zip(names, positions, velocities, efforts):
        rows.append(
            {
                "joint_name": name,
                "position": pos,
                "velocity": vel,
                "effort": eff,
                "header_stamp_ns": _stamp_to_ns(header.get("stamp")),
            }
        )
    return rows


# Populate the _EXPANDERS dict with semantic expanders.
_EXPANDERS.update(
    {
        "tf2_msgs/msg/TFMessage": _expand_tf,
        "sensor_msgs/msg/JointState": _expand_joint_state,
    }
)


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

    def _count_skips(self, msg_type: str, rows: list[dict[str, Any]]) -> None:
        """Increment self.skipped when a binary message was excluded."""
        if self._is_binary(msg_type) and not self.include_binary and not rows:
            self.skipped += 1

    def _iter_bag(self) -> Iterator[tuple[str, str, int, dict[str, Any]]]:
        """Open the bag and yield (topic, msg_type, timestamp_ns, msg_dict).

        This is the ONLY method that touches rosbags. All normalize/expand/
        exclude logic operates on plain dicts, so contract tests need no
        rosbags installed.
        """
        self._ensure_driver()
        self._validate_path()
        from rosbags.highlevel import AnyReader

        with AnyReader([self.bag_path]) as reader:
            for conn, timestamp, raw in reader.messages():
                try:
                    msg = reader.deserialize(raw, conn.msgtype)
                except Exception:  # noqa: BLE001 — half-corrupt messages happen in field bags
                    self.skipped += 1
                    continue
                yield conn.topic, conn.msgtype, timestamp, self._msg_to_dict(msg)

    @staticmethod
    def _msg_to_dict(msg: Any) -> dict[str, Any]:
        """Convert a rosbags-deserialized message object to a plain dict.

        rosbags 0.11.x message objects are dataclass-like — they expose
        ``__dataclass_fields__`` for field enumeration and ``__msgtype__``
        for the message type string. We recurse into nested messages and
        lists. bytes pass through as-is (the binary stub reads len(data)
        for byte_size). ``__msgtype__`` is excluded from the output.
        """
        if hasattr(msg, "__dataclass_fields__"):
            return {
                key: Ros2BagConnector._msg_to_dict(val)
                for key, val in vars(msg).items()
                if key != "__msgtype__"
            }
        if isinstance(msg, (list, tuple)):
            return [Ros2BagConnector._msg_to_dict(item) for item in msg]  # type: ignore[return-value]
        if isinstance(msg, bytes):
            return msg
        return msg  # primitives pass through

    def discover_schema(self) -> Schema:
        self._validate_path()
        self._ensure_driver()
        from rosbags.highlevel import AnyReader

        topic_info: dict[str, tuple[str, int]] = {}  # topic -> (msg_type, msg_count)
        with AnyReader([self.bag_path]) as reader:
            for conn, _timestamp, _raw in reader.messages():
                if conn.topic not in topic_info:
                    topic_info[conn.topic] = (conn.msgtype, 0)
                mt, count = topic_info[conn.topic]
                topic_info[conn.topic] = (mt, count + 1)

        total_msgs = sum(c for _, c in topic_info.values())
        fields = [
            SchemaField(name="topic", inferred_type="string"),
            SchemaField(name="msg_type", inferred_type="string"),
            SchemaField(name="timestamp_ns", inferred_type="int"),
            SchemaField(name="payload", inferred_type="json"),
        ]
        # Add expander-specific fields if TF/JointState topics are present
        for _topic, (msg_type, _count) in topic_info.items():
            if msg_type == "tf2_msgs/msg/TFMessage":
                for name in (
                    "frame_id",
                    "child_frame_id",
                    "tx",
                    "ty",
                    "tz",
                    "qx",
                    "qy",
                    "qz",
                    "qw",
                    "header_stamp_ns",
                ):
                    fields.append(
                        SchemaField(name=name, inferred_type="string" if "frame" in name else "float")
                    )
                break
        for _topic, (msg_type, _count) in topic_info.items():
            if msg_type == "sensor_msgs/msg/JointState":
                for name in ("joint_name", "position", "velocity", "effort", "header_stamp_ns"):
                    fields.append(
                        SchemaField(name=name, inferred_type="string" if name == "joint_name" else "float")
                    )
                break

        return Schema(
            source=str(self.bag_path),
            row_count=total_msgs,
            fields=fields,
            detected_categories=list(topic_info.keys()),
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        topic_set = set(self.topics) if self.topics else None
        out: list[dict[str, Any]] = []
        for topic, msg_type, timestamp_ns, msg in self._iter_bag():
            if topic_set is not None and topic not in topic_set:
                continue
            rows = self._normalize(
                topic=topic,
                msg_type=msg_type,
                timestamp_ns=timestamp_ns,
                msg=msg,
            )
            self._count_skips(msg_type, rows)
            for row in rows:
                out.append(row)
                if len(out) >= n:
                    return out
        return out

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        topic_set = set(self.topics) if self.topics else None
        batch: list[dict[str, Any]] = []
        for topic, msg_type, timestamp_ns, msg in self._iter_bag():
            if topic_set is not None and topic not in topic_set:
                continue
            rows = self._normalize(
                topic=topic,
                msg_type=msg_type,
                timestamp_ns=timestamp_ns,
                msg=msg,
            )
            self._count_skips(msg_type, rows)
            for row in rows:
                batch.append(row)
                if len(batch) >= batch_size:
                    yield Batch(batch, source=str(self.bag_path))
                    batch = []
        if batch:
            yield Batch(batch, source=str(self.bag_path))
