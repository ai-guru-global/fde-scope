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
