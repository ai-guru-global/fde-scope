"""MES (ISA-95) connector tests — HTTP mode (urllib mocked, offline) + JSONL fallback.

No real MES instance or token is ever contacted: the transport is mocked at
``urllib.request.urlopen`` level, mirroring ``tests/test_zammad_connector.py``.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from fde_scope.connectors._registry import get
from fde_scope.connectors.mes_isa95 import (
    ENV_API_TOKEN,
    ENV_BASE_URL,
    MesConnector,
    MesError,
)

_URL = "https://mes.plant.example.com"
_TOKEN = "mes-secret-token"


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _orders(*, count: int, start: int = 1) -> list[dict]:
    return [
        {
            "order_id": f"WO-{start + i:04d}",
            "product": "gearbox",
            "status": "released",
            "quantity": 100 + i,
            "defect_count": i,
            "description": f"build order {start + i}",
        }
        for i in range(count)
    ]


@pytest.fixture()
def clean_mes_env(monkeypatch):
    monkeypatch.delenv(ENV_BASE_URL, raising=False)
    monkeypatch.delenv(ENV_API_TOKEN, raising=False)
    return monkeypatch


def _connector(**options) -> MesConnector:
    cls = get("mes")
    return cls(_URL, api_key=_TOKEN, **options)


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
def test_http_mode_via_options(clean_mes_env) -> None:
    c = _connector()
    assert c._http_mode
    assert c.base_url == _URL
    assert c.api_token == _TOKEN


def test_http_mode_via_env(clean_mes_env) -> None:
    clean_mes_env.setenv(ENV_BASE_URL, _URL)
    clean_mes_env.setenv(ENV_API_TOKEN, _TOKEN)
    c = get("mes")(_URL)
    assert c._http_mode
    assert c.api_token == _TOKEN


def test_unconfigured_without_env_or_jsonl(clean_mes_env) -> None:
    c = get("mes")(_URL)
    assert not c._http_mode
    assert c._jsonl_path is None
    # Skeleton-compatible: selectable, schema intact, empty sample/stream.
    schema = c.discover_schema()
    assert "work_order_id" in schema.field_names()
    assert schema.detected_categories == ["work_orders"]
    assert c.extract_sample(5) == []
    assert list(c.stream()) == []


def test_partial_env_warns_and_falls_back(clean_mes_env, caplog) -> None:
    clean_mes_env.setenv(ENV_BASE_URL, _URL)  # no token
    with caplog.at_level("WARNING", logger="fde_scope.connectors.mes"):
        c = get("mes")(_URL)
    assert not c._http_mode
    assert c.extract_sample(3) == []
    assert any("incomplete MES configuration" in r.message for r in caplog.records)
    assert _TOKEN not in caplog.text


def test_partial_env_token_only_warns(clean_mes_env, caplog) -> None:
    clean_mes_env.setenv(ENV_API_TOKEN, _TOKEN)  # no base URL, non-URL source
    with caplog.at_level("WARNING", logger="fde_scope.connectors.mes"):
        c = get("mes")("not-a-url")
    assert not c._http_mode
    assert any("incomplete MES configuration" in r.message for r in caplog.records)
    assert _TOKEN not in caplog.text


# ---------------------------------------------------------------------------
# HTTP mode — request shape, mapping, pagination
# ---------------------------------------------------------------------------
def test_extract_sample_sends_bearer_header_and_maps_rows(clean_mes_env, monkeypatch) -> None:
    captured: dict = {}
    body = json.dumps(_orders(count=2)).encode()

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        return _FakeResp(body)

    monkeypatch.setattr("fde_scope.connectors.mes_isa95.urllib.request.urlopen", fake_urlopen)
    rows = _connector().extract_sample(10)

    assert captured["url"].startswith(f"{_URL}/api/v1/work-orders?")
    assert "limit=" in captured["url"] and "offset=0" in captured["url"]
    assert captured["headers"]["authorization"] == f"Bearer {_TOKEN}"
    assert len(rows) == 2
    row = rows[0]
    assert row["id"] == "WO-0001"  # order_id -> id
    assert row["category"] == "gearbox"  # product -> category
    assert row["state"] == "released"  # status -> state
    assert row["quantity"] == 100
    assert row["defect_count"] == 0
    assert row["content"] == "build order 1"  # description -> content


def test_endpoint_option_overrides_path(clean_mes_env, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "fde_scope.connectors.mes_isa95.urllib.request.urlopen",
        lambda request, timeout: (captured.update(url=request.full_url), _FakeResp(b"[]"))[1],  # noqa: ARG005
    )
    _connector(endpoint="/api/production/orders").extract_sample(5)
    assert captured["url"].startswith(f"{_URL}/api/production/orders?")


def test_endpoint_option_adds_leading_slash(clean_mes_env) -> None:
    c = _connector(endpoint="api/v2/orders")
    assert c.endpoint == "/api/v2/orders"


def test_extract_sample_truncates_at_n(clean_mes_env, monkeypatch) -> None:
    body = json.dumps(_orders(count=5)).encode()
    monkeypatch.setattr(
        "fde_scope.connectors.mes_isa95.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(body),  # noqa: ARG005
    )
    rows = _connector().extract_sample(3)
    assert len(rows) == 3


def test_extract_sample_paginates_by_offset_until_n(clean_mes_env, monkeypatch) -> None:
    calls: list[str] = []
    pages = {
        0: json.dumps(_orders(count=100, start=1)).encode(),
        100: json.dumps(_orders(count=100, start=101)).encode(),
        200: b"[]",
    }

    def fake_urlopen(request, timeout):  # noqa: ARG001
        calls.append(request.full_url)
        offset = int(request.full_url.rsplit("offset=", 1)[1])
        return _FakeResp(pages[offset])

    monkeypatch.setattr("fde_scope.connectors.mes_isa95.urllib.request.urlopen", fake_urlopen)
    rows = _connector().extract_sample(150)
    assert len(rows) == 150
    assert len(calls) == 2  # stopped mid-page-2 once n was reached
    assert "offset=0" in calls[0] and "offset=100" in calls[1]


def test_stream_paginates_to_short_page_and_batches(clean_mes_env, monkeypatch) -> None:
    pages = {
        0: json.dumps(_orders(count=100, start=1)).encode(),
        100: json.dumps(_orders(count=3, start=101)).encode(),
    }

    def fake_urlopen(request, timeout):  # noqa: ARG001
        offset = int(request.full_url.rsplit("offset=", 1)[1])
        return _FakeResp(pages[offset])

    monkeypatch.setattr("fde_scope.connectors.mes_isa95.urllib.request.urlopen", fake_urlopen)
    batches = list(_connector().stream(batch_size=100))
    assert [len(b) for b in batches] == [100, 3]
    assert all(b.source == _URL for b in batches)


def test_envelope_response_shape_accepted(clean_mes_env, monkeypatch) -> None:
    body = json.dumps({"items": _orders(count=2), "total": 2}).encode()
    monkeypatch.setattr(
        "fde_scope.connectors.mes_isa95.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(body),  # noqa: ARG005
    )
    rows = _connector().extract_sample(10)
    assert len(rows) == 2
    assert rows[0]["id"] == "WO-0001"


def test_discover_schema_http_probes_one_order(clean_mes_env, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        "fde_scope.connectors.mes_isa95.urllib.request.urlopen",
        lambda request, timeout: (captured.update(url=request.full_url), _FakeResp(b"[]"))[1],  # noqa: ARG005
    )
    schema = _connector().discover_schema()
    assert "limit=1" in captured["url"]
    assert "work_order_id" in schema.field_names()
    assert schema.row_count is None


# ---------------------------------------------------------------------------
# HTTP mode — error paths (token must never leak into exceptions)
# ---------------------------------------------------------------------------
def test_http_401_raises_mes_error_without_token(clean_mes_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad"))

    monkeypatch.setattr("fde_scope.connectors.mes_isa95.urllib.request.urlopen", fail)
    with pytest.raises(MesError, match="401") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


def test_http_500_raises_mes_error_without_token(clean_mes_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, io.BytesIO(b"boom"))

    monkeypatch.setattr("fde_scope.connectors.mes_isa95.urllib.request.urlopen", fail)
    with pytest.raises(MesError, match="500") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


def test_timeout_raises_mes_error_without_token(clean_mes_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise TimeoutError("read timed out")

    monkeypatch.setattr("fde_scope.connectors.mes_isa95.urllib.request.urlopen", fail)
    with pytest.raises(MesError, match="TimeoutError") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


def test_url_error_raises_mes_error(clean_mes_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("fde_scope.connectors.mes_isa95.urllib.request.urlopen", fail)
    with pytest.raises(MesError, match="URLError"):
        _connector().discover_schema()


def test_unexpected_response_shape_raises_without_token(clean_mes_env, monkeypatch) -> None:
    monkeypatch.setattr(
        "fde_scope.connectors.mes_isa95.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(b'{"error": "oops"}'),  # noqa: ARG005
    )
    with pytest.raises(MesError, match="unexpected MES response") as excinfo:
        _connector().extract_sample(1)
    assert _TOKEN not in str(excinfo.value)


# ---------------------------------------------------------------------------
# JSONL replay mode
# ---------------------------------------------------------------------------
def test_jsonl_fallback_extract_and_stream(clean_mes_env, tmp_path: Path) -> None:
    path = tmp_path / "mes.jsonl"
    lines = [
        {"work_order_id": "WO-1", "product": "gearbox", "status": "released"},
        {"work_order_id": "WO-2", "product": "housing", "status": "done"},
        {"work_order_id": "WO-3", "product": "gearbox", "status": "hold"},
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n", "utf-8")
    c = get("mes")(str(path))
    assert not c._http_mode
    assert c._is_jsonl

    schema = c.discover_schema()
    assert schema.row_count == 3

    assert c.extract_sample(2) == lines[:2]
    batches = list(c.stream(batch_size=2))
    assert [len(b) for b in batches] == [2, 1]
    assert batches[0].source == str(path)


def test_extract_sample_rejects_nonpositive_n(clean_mes_env) -> None:
    with pytest.raises(ValueError, match="n >= 1"):
        _connector().extract_sample(0)


def test_stream_rejects_nonpositive_batch_size(clean_mes_env) -> None:
    with pytest.raises(ValueError, match="batch_size >= 1"):
        list(_connector().stream(batch_size=0))
