"""Tests for the documents connector (AgentScope rag parsers behind a DataConnector).

The connector module imports *without* the agentscope extra (lazy parse), so
the registration test always runs. The parse tests exercise the real
``agentscope.rag`` text path and skip cleanly when the extra is absent.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from fde_scope.connectors import DataConnector
from fde_scope.connectors._registry import get, get_registry

HAS_AGENTSCOPE = importlib.util.find_spec("agentscope") is not None
needs_as = pytest.mark.skipif(not HAS_AGENTSCOPE, reason="agentscope extra not installed")


def test_documents_connector_is_registered() -> None:
    # Registry import must not require agentscope (lazy parse), so this always works.
    assert "documents" in get_registry()
    cls = get("documents")
    assert issubclass(cls, DataConnector)
    assert cls.type == "documents"


def test_documents_missing_source_raises(tmp_path: Path) -> None:
    cls = get("documents")
    connector = cls(str(tmp_path / "does-not-exist"))
    # Either the extra is missing (RuntimeError) or the source is (FileNotFoundError);
    # both are actionable failures, never a silent empty corpus.
    with pytest.raises((FileNotFoundError, RuntimeError)):
        connector.discover_schema()


def test_documents_extract_sample_requires_positive_n(tmp_path: Path) -> None:
    connector = get("documents")(str(tmp_path))
    with pytest.raises(ValueError):
        connector.extract_sample(0)


@needs_as
def test_documents_parses_text_and_markdown(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("first line\nsecond line\n", encoding="utf-8")
    (tmp_path / "runbook.md").write_text("# Title\n\nsome body text\n", encoding="utf-8")
    connector = get("documents")(str(tmp_path))

    rows = connector.extract_sample(10)
    assert rows, "expected at least one parsed row"
    assert all(r["content"] for r in rows)
    assert all({"id", "content", "source", "category"} <= set(r) for r in rows)
    categories = {r["category"] for r in rows}
    assert categories <= {"txt", "md"}


@needs_as
def test_documents_discover_schema_reports_row_count(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta\ngamma\n", encoding="utf-8")
    connector = get("documents")(str(tmp_path))
    schema = connector.discover_schema()

    assert schema.row_count == len(connector.extract_sample(999))
    assert "id" in schema.field_names()
    assert "content" in schema.field_names()


@needs_as
def test_documents_skips_unsupported_extension(tmp_path: Path) -> None:
    (tmp_path / "data.bin").write_bytes(b"\x00\x01\x02binary")
    (tmp_path / "note.txt").write_text("real text\n", encoding="utf-8")
    rows = get("documents")(str(tmp_path)).extract_sample(50)

    assert all(r["category"] != "bin" for r in rows)
    assert any(r["category"] == "txt" for r in rows)


@needs_as
def test_documents_streams_in_batches(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"doc{i}.txt").write_text(f"content {i}\n", encoding="utf-8")
    connector = get("documents")(str(tmp_path))
    batches = list(connector.stream(batch_size=2))
    total = sum(len(b) for b in batches)

    assert total == 5
    assert len(batches) == 3  # ceil(5/2)
    assert all(b.source == str(tmp_path) for b in batches)
