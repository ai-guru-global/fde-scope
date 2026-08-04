"""Historian connector — time-series database (AVEVA PI / GE Proficy / Influx).

STATUS: skeleton. Real implementation will query a historian (PI Web API,
GE Proficy, or InfluxDB/Flux) for tag time-series over a window.

Industry note: AVEVA PI System (formerly OSIsoft PI) is the dominant
process-industry historian; this is where an FDE pulls long windows of tag
data for anomaly detection and predictive-maintenance eval.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField


@register
class HistorianConnector(DataConnector):
    """Query a process historian for tag time-series."""

    type = "historian"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.base_url = source.rstrip("/")    # PI Web API / Influx endpoint
        self.tags: list[str] = options.get("tags", [])
        self.start = options.get("start")     # ISO8601
        self.end = options.get("end")

    def _ensure_driver(self) -> None:
        # PI Web API is HTTP (requests); Influx uses influxdb-client.
        try:
            import requests  # type: ignore  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError("HistorianConnector needs 'requests': pip install requests") from exc

    def discover_schema(self) -> Schema:
        return Schema(
            source=self.base_url,
            row_count=None,
            fields=[
                SchemaField(name="tag", inferred_type="string"),
                SchemaField(name="timestamp", inferred_type="datetime"),
                SchemaField(name="value", inferred_type="float"),
                SchemaField(name="quality", inferred_type="string"),
            ],
            detected_categories=self.tags,
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        # TODO: recordedvalues / query for first n points per tag
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        # TODO: stream interpolated values over the window
        return
        yield  # pragma: no cover
