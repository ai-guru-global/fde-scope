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


# ---------------------------------------------------------------------------
# register() validation
# ---------------------------------------------------------------------------
def test_register_rejects_subclass_without_own_type() -> None:
    """A subclass that forgets to override ``type`` would inherit the base
    default ("base") and silently overwrite other connectors in the registry;
    register() must refuse it."""
    import pytest

    from fde_scope.connectors.base import register

    class ForgotType(DataConnector):
        def discover_schema(self):  # pragma: no cover - never instantiated
            ...

        def extract_sample(self, n: int = 100):  # pragma: no cover
            return []

        def stream(self, batch_size: int = 500):  # pragma: no cover
            yield

    with pytest.raises(AttributeError, match="type"):
        register(ForgotType)


def test_register_rejects_reserved_base_slug() -> None:
    import pytest

    from fde_scope.connectors.base import register

    class ExplicitBase(DataConnector):
        type = "base"

        def discover_schema(self):  # pragma: no cover - never instantiated
            ...

        def extract_sample(self, n: int = 100):  # pragma: no cover
            return []

        def stream(self, batch_size: int = 500):  # pragma: no cover
            yield

    with pytest.raises(ValueError, match="base"):
        register(ExplicitBase)


# ---------------------------------------------------------------------------
# CSV connector edge cases
# ---------------------------------------------------------------------------
def test_csv_utf8_bom_does_not_pollute_first_column(tmp_path: Path) -> None:
    path = tmp_path / "bom.csv"
    path.write_bytes(b'\xef\xbb\xbfid,content\n1,"hello"\n')
    connector = get("csv")(str(path))

    schema = connector.discover_schema()
    assert schema.field_names() == ["id", "content"]
    assert connector.extract_sample(1)[0] == {"id": "1", "content": "hello"}


def test_csv_row_count_matches_stream_with_quoted_newlines(tmp_path: Path) -> None:
    """A newline inside a quoted field is one logical record, not two lines."""
    path = tmp_path / "multiline.csv"
    path.write_text('id,content\n1,"line one\nline two"\n2,plain\n', encoding="utf-8")
    connector = get("csv")(str(path))

    schema = connector.discover_schema()
    streamed = sum(len(b) for b in connector.stream(batch_size=1))
    assert schema.row_count == 2
    assert schema.row_count == streamed


def test_csv_extra_fields_beyond_header_are_dropped(tmp_path: Path) -> None:
    """DictReader parks surplus fields under a None key; rows must not carry it."""
    path = tmp_path / "ragged.csv"
    path.write_text("id,content\n1,hello,extra1,extra2\n", encoding="utf-8")
    connector = get("csv")(str(path))

    row = connector.extract_sample(1)[0]
    assert None not in row
    assert row == {"id": "1", "content": "hello"}


def test_csv_directory_schema_merges_columns_across_files(tmp_path: Path) -> None:
    """A column that only exists in a later file must still land in the schema."""
    (tmp_path / "a.csv").write_text("id,content\n1,a\n", encoding="utf-8")
    (tmp_path / "b.csv").write_text("id,channel\n2,chat\n", encoding="utf-8")
    connector = get("csv")(str(tmp_path))

    schema = connector.discover_schema()
    assert schema.field_names() == ["id", "content", "channel"]


def test_csv_extract_sample_rejects_nonpositive_n(sample_csv: Path) -> None:
    import pytest

    connector = get("csv")(str(sample_csv))
    with pytest.raises(ValueError, match="n >= 1"):
        connector.extract_sample(0)


def test_csv_stream_rejects_nonpositive_batch_size(sample_csv: Path) -> None:
    import pytest

    connector = get("csv")(str(sample_csv))
    with pytest.raises(ValueError, match="batch_size >= 1"):
        list(connector.stream(batch_size=0))


# ---------------------------------------------------------------------------
# Salesforce connector options
# ---------------------------------------------------------------------------
def test_salesforce_falls_back_to_api_key_option() -> None:
    """The CLI passes credentials uniformly as ``api_key``; the connector
    must accept it instead of silently dropping the token."""
    cls = get("salesforce")
    connector = cls("https://example.my.salesforce.com", api_key="tok123")
    assert connector.access_token == "tok123"
    # An explicit access_token still wins over api_key.
    connector = cls("https://example.my.salesforce.com", access_token="tok456", api_key="tok123")
    assert connector.access_token == "tok456"
