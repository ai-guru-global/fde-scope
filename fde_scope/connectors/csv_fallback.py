"""CSV connector — the universal fallback.

When a customer can only hand over a CSV export (extremely common on a first
engagement), this connector is what stands between "we have a file" and "we
have a corpus". It is a fully working, stdlib-only implementation and is the
default cold-start path in the quickstart.

Field-name conventions: the forge looks for ``content`` (ticket text),
``category`` (intent label), and ``id``. Anything else is carried through
verbatim.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

# Heuristic: field names that suggest personally identifiable information.
_PII_NAME_HINTS = {"name", "customer_name", "email", "phone", "mobile", "address", "id_card"}


def _infer_type(values: list[Any]) -> str:
    """Best-effort type inference for a column from its sample values."""
    non_empty = [v for v in values if v not in (None, "")]
    if not non_empty:
        return "string"
    if all(_is_int(v) for v in non_empty):
        return "int"
    if all(_is_float(v) for v in non_empty):
        return "float"
    if all(str(v).lower() in {"true", "false"} for v in non_empty):
        return "bool"
    return "string"


def _is_int(v: Any) -> bool:
    try:
        int(str(v))
        return True
    except (TypeError, ValueError):
        return False


def _is_float(v: Any) -> bool:
    try:
        float(str(v))
        return "." in str(v) or "e" in str(v).lower()
    except (TypeError, ValueError):
        return False


@register
class CSVConnector(DataConnector):
    """Read ticket-like rows from a CSV file or directory of CSV files."""

    type = "csv"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self._path = Path(source)
        self._delimiter = options.get("delimiter", ",")

    # -- path helpers -----------------------------------------------------------
    def _iter_files(self) -> Iterator[Path]:
        if self._path.is_dir():
            yield from sorted(self._path.glob("*.csv"))
        elif self._path.is_file():
            yield self._path
        else:
            raise FileNotFoundError(f"CSV source not found: {self.source}")

    def _iter_rows(self) -> Iterator[dict[str, Any]]:
        for file in self._iter_files():
            with open(file, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh, delimiter=self._delimiter)
                for row in reader:
                    yield {k: (v if v != "" else None) for k, v in row.items()}

    # -- the three-step contract -----------------------------------------------
    def discover_schema(self) -> Schema:
        """Peek at the header + first rows to build a schema without loading all."""
        sample: list[dict[str, Any]] = []
        header: list[str] | None = None
        for row in self._iter_rows():
            if header is None:
                header = list(row.keys())
            sample.append(row)
            if len(sample) >= 50:
                break

        if header is None:
            return Schema(source=str(self.source), fields=[], row_count=0)

        fields: list[SchemaField] = []
        for name in header:
            col_values = [r.get(name) for r in sample]
            fields.append(
                SchemaField(
                    name=name,
                    inferred_type=_infer_type(col_values),
                    nullable=any(v is None for v in col_values),
                    sample_values=[v for v in col_values if v is not None][:3],
                    pii_candidate=any(h in name.lower() for h in _PII_NAME_HINTS),
                )
            )

        categories = _distinct(sample, "category")
        channels = _distinct(sample, "channel")
        row_count = self._count_rows()

        return Schema(
            source=str(self.source),
            fields=fields,
            row_count=row_count,
            detected_categories=categories,
            detected_channels=channels,
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in self._iter_rows():
            out.append(row)
            if len(out) >= n:
                break
        return out

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        batch: list[dict[str, Any]] = []
        for row in self._iter_rows():
            batch.append(row)
            if len(batch) >= batch_size:
                yield Batch(batch, source=str(self.source))
                batch = []
        if batch:
            yield Batch(batch, source=str(self.source))

    # -- helpers ----------------------------------------------------------------
    def _count_rows(self) -> int:
        """Count data rows across all files (excludes header)."""
        total = 0
        for file in self._iter_files():
            with open(file, encoding="utf-8") as fh:
                # sum(1 ...) skips the header via islice-style consumption
                total += max(sum(1 for _ in fh) - 1, 0)
        return total


def _distinct(rows: list[dict[str, Any]], key: str) -> list[str]:
    seen: list[str] = []
    for r in rows:
        v = r.get(key)
        if v and v not in seen:
            seen.append(str(v))
    return seen
