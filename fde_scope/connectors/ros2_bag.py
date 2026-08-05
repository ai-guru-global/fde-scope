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

    connector_type = "ros2_bag"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.bag_path = Path(source)
        self.topics: list[str] = options.get("topics", [])  # empty = all

    def _ensure_driver(self) -> None:
        try:
            from rosbags.highlevel import AnyReader  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Ros2BagConnector needs the 'rosbags' package: pip install rosbags") from exc

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
