"""Tests for Layer 1 — connectors (CSV is fully exercised)."""

from __future__ import annotations

from pathlib import Path

from fde_scope.connectors import DataConnector
from fde_scope.connectors._registry import get, get_registry


def test_csv_connector_discovers_schema(sample_csv: Path) -> None:
    cls = get("csv")
    connector = cls(str(sample_csv))
    schema = connector.discover_schema()

    assert schema.source == str(sample_csv)
    names = schema.field_names()
    assert "content" in names
    assert "category" in names
    assert schema.row_count == 8
    assert "退款" in schema.detected_categories


def test_csv_connector_extract_sample(sample_csv: Path) -> None:
    connector = get("csv")(str(sample_csv))
    sample = connector.extract_sample(3)
    assert len(sample) == 3
    assert all("content" in row for row in sample)


def test_csv_connector_stream_batches(sample_csv: Path) -> None:
    connector = get("csv")(str(sample_csv))
    batches = list(connector.stream(batch_size=3))
    # 8 rows / batch_size 3 → ceil(8/3) = 3 batches
    assert len(batches) == 3
    assert sum(len(b) for b in batches) == 8


def test_registry_loads_all_builtin() -> None:
    reg = get_registry()
    # csv + zammad + salesforce always importable; mysql may be absent
    assert "csv" in reg
    assert "zammad" in reg
    assert "salesforce" in reg


def test_registry_unknown_type_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get("not-a-real-type")


def test_missing_file_raises(tmp_path: Path) -> None:
    import pytest

    connector = get("csv")(str(tmp_path / "nope.csv"))
    with pytest.raises(FileNotFoundError):
        connector.discover_schema()


def test_connector_is_subclass_of_base() -> None:
    csv_cls = get("csv")
    assert issubclass(csv_cls, DataConnector)
