"""MES connector — ISA-95 Level 3 manufacturing execution data.

Supports two modes:
    1. **JSONL export** (fully working, zero deps): a MES dump as JSON lines —
       the cold-start path an FDE uses when the live API isn't reachable yet.
       Each line is one record (work-order / quality / downtime).
    2. **Live REST/ODATA** (skeleton): SAP DMC / Apriso / Camstar / Rockwell
       FactoryTalk — roadmap, behind the same contract.

Industry note: ISA-95 Level 3 (MES) is the bridge between the plant floor
(L0-2) and ERP (L4). This is where downtime reason codes, FPY, and
genealogy live.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

# Per-entity field shapes (used by discover_schema for both modes).
_FIELDS_BY_ENTITY: dict[str, list[SchemaField]] = {
    "work_orders": [
        SchemaField(name="work_order_id", inferred_type="string"),
        SchemaField(name="product", inferred_type="string"),
        SchemaField(name="planned_qty", inferred_type="int"),
        SchemaField(name="good_qty", inferred_type="int"),
        SchemaField(name="started_units", inferred_type="int"),
        SchemaField(name="status", inferred_type="string"),
    ],
    "downtime": [
        SchemaField(name="asset", inferred_type="string"),
        SchemaField(name="reason_code", inferred_type="string"),
        SchemaField(name="duration_minutes", inferred_type="float"),
        SchemaField(name="shift", inferred_type="string"),
    ],
    "quality": [
        SchemaField(name="serial", inferred_type="string"),
        SchemaField(name="defect_class", inferred_type="string"),
        SchemaField(name="station", inferred_type="string"),
    ],
    # KPI-per-station records (the quickstart_manufacturing shape).
    "station_kpi": [
        SchemaField(name="station", inferred_type="string"),
        SchemaField(name="availability", inferred_type="float"),
        SchemaField(name="performance", inferred_type="float"),
        SchemaField(name="quality", inferred_type="float"),
        SchemaField(name="uptime_hours", inferred_type="float"),
        SchemaField(name="failures", inferred_type="int"),
        SchemaField(name="grasp_successes", inferred_type="int"),
        SchemaField(name="grasp_attempts", inferred_type="int"),
        SchemaField(name="interventions", inferred_type="int"),
        SchemaField(name="cycles", inferred_type="int"),
    ],
}


@register
class MesConnector(DataConnector):
    """Connect to a Manufacturing Execution System (ISA-95 Level 3).

    ``source`` is either a URL (live API, skeleton) or a path to a JSONL
    export (fully working). The connector auto-detects which.
    """

    connector_type = "mes"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.base_url = source.rstrip("/") if "://" in source else source
        self.api_token = options.get("api_token", "")
        self.entity = options.get("entity", "work_orders")
        self._jsonl_path = Path(source) if "://" not in source else None

    @property
    def _is_jsonl(self) -> bool:
        return self._jsonl_path is not None and self._jsonl_path.exists()

    def _iter_jsonl(self) -> Iterator[dict[str, Any]]:
        if self._jsonl_path is None:
            return
        with open(self._jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    # -- the three-step contract ------------------------------------------------
    def discover_schema(self) -> Schema:
        fields = _FIELDS_BY_ENTITY.get(self.entity, _FIELDS_BY_ENTITY["work_orders"])
        row_count = None
        if self._is_jsonl:
            row_count = sum(1 for _ in self._iter_jsonl())
        return Schema(
            source=str(self.base_url),
            row_count=row_count,
            fields=fields,
            detected_categories=[self.entity],
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        if self._is_jsonl:
            out: list[dict[str, Any]] = []
            for rec in self._iter_jsonl():
                out.append(rec)
                if len(out) >= n:
                    break
            return out
        # TODO: live API GET /api/{entity}?top={n}
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        if self._is_jsonl:
            batch: list[dict[str, Any]] = []
            for rec in self._iter_jsonl():
                batch.append(rec)
                if len(batch) >= batch_size:
                    yield Batch(batch, source=str(self.base_url))
                    batch = []
            if batch:
                yield Batch(batch, source=str(self.base_url))
            return
        # TODO: live API pagination
        return
        yield  # pragma: no cover
